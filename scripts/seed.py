"""Seed script for hackathon demo.

Creates: 1 equipe, 3 ACS, 1 gestor, ~150 criancas, 30 days of visitas, 5 criancas alto risco.
Idempotent: safe to run multiple times.

Run: make seed
Or: python -m scripts.seed
"""

import asyncio
import hashlib
import random
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import all models so Base.metadata is populated
from app.models import Base, Crianca, Equipe, Gestor, Profissional, Visita


async def seed(session: AsyncSession) -> None:
    """Idempotent seed function.

    Does NOT commit — caller is responsible for committing (main() does it).
    This allows tests to call seed() inside a rollback-scoped transaction.
    """
    from app.config import settings

    salt = settings.telegram_chat_id_salt

    # --- 1. Equipe ---
    equipe_result = await session.execute(select(Equipe).where(Equipe.nome == "ESF Demo - Rio"))
    equipe = equipe_result.scalar_one_or_none()
    if equipe is None:
        equipe = Equipe(
            nome="ESF Demo - Rio",
            endereco_latitude=-22.9068,
            endereco_longitude=-43.1729,
        )
        session.add(equipe)
        await session.flush()

    # --- 2. 3 ACS ---
    acs_data = [
        {"nome": "João Roberto", "chat_id": 1001},
        {"nome": "Maria Vitória", "chat_id": 1002},
        {"nome": "Ana Clara", "chat_id": 1003},
    ]

    acs_list = []
    for d in acs_data:
        hashed = hashlib.sha256(f"{d['chat_id']}{salt}".encode()).hexdigest()
        result = await session.execute(
            select(Profissional).where(Profissional.telegram_chat_id_hash == hashed)
        )
        acs = result.scalar_one_or_none()
        if acs is None:
            acs = Profissional(
                nome=d["nome"],
                telegram_chat_id_hash=hashed,
                equipe_id=equipe.id,
                ativo=True,
            )
            session.add(acs)
        acs_list.append(acs)
    await session.flush()

    # --- 3. 1 Gestor ---
    gestor_hash = hashlib.sha256(f"9001{salt}".encode()).hexdigest()
    gestor_result = await session.execute(
        select(Gestor).where(Gestor.telegram_chat_id_hash == gestor_hash)
    )
    gestor = gestor_result.scalar_one_or_none()
    if gestor is None:
        gestor = Gestor(
            nome="Gestor Demo",
            telegram_chat_id_hash=gestor_hash,
            equipes_ids=[str(equipe.id)],
            ativo=True,
        )
        session.add(gestor)
        await session.flush()

    # --- 4. ~150 Criancas (50 per ACS) ---
    RACAS = ["parda", "branca", "preta", "amarela", "indigena"]

    criancas_per_acs: dict = {}
    for acs in acs_list:
        result = await session.execute(
            select(Crianca).where(Crianca.profissional_id == acs.id)
        )
        existing = list(result.scalars().all())
        criancas_per_acs[acs.id] = existing

    all_criancas: list[Crianca] = []
    for acs in acs_list:
        existing = criancas_per_acs[acs.id]
        count_needed = max(0, 50 - len(existing))
        for _ in range(count_needed):
            c = Crianca(
                profissional_id=acs.id,
                equipe_id=equipe.id,
                faixa_etaria="0-6",
                sexo=random.choice(["M", "F"]),
                raca_cor=random.choice(RACAS),
                situacao_vulnerabilidade=random.random() < 0.15,
                endereco_latitude=-22.9068 + random.uniform(-0.05, 0.05),
                endereco_longitude=-43.1729 + random.uniform(-0.05, 0.05),
                vacinacao_em_dia=random.random() < 0.85,
                dias_vacinacao_atraso=random.randint(0, 20) if random.random() < 0.15 else 0,
                ultima_consulta=date.today() - timedelta(days=random.randint(10, 90)),
                grupo_risco=False,
                ativo=True,
            )
            session.add(c)
            existing.append(c)
        all_criancas.extend(existing)

    await session.flush()

    # --- 5. Mark 5 children as alto risco ---
    # Only mark if none are grupo_risco yet (idempotency: avoid re-marking on second call)
    alto_risco_existing = [c for c in all_criancas if c.grupo_risco]
    if len(alto_risco_existing) < 5:
        candidates = [c for c in all_criancas if not c.grupo_risco]
        to_mark = random.sample(candidates, min(5, len(candidates)))
        for c in to_mark:
            c.vacinacao_em_dia = False
            c.dias_vacinacao_atraso = random.randint(45, 90)
            c.situacao_vulnerabilidade = True
            c.ultima_consulta = date.today() - timedelta(days=random.randint(60, 120))
            c.grupo_risco = True
        await session.flush()

    # --- 6. 30 days of visit history ---
    hoje = date.today()
    for acs in acs_list:
        acs_criancas = [c for c in all_criancas if c.profissional_id == acs.id]
        for day_offset in range(30, 0, -1):
            dia = hoje - timedelta(days=day_offset)
            # Visit 5-8 children per day
            n_visitas = random.randint(5, 8)
            sample_criancas = random.sample(acs_criancas, min(n_visitas, len(acs_criancas)))
            for c in sample_criancas:
                # Check if visit already exists
                v_result = await session.execute(
                    select(Visita).where(
                        Visita.profissional_id == acs.id,
                        Visita.crianca_ref == c.id,
                        Visita.data_visita == dia,
                    )
                )
                if v_result.scalar_one_or_none() is None:
                    visita = Visita(
                        profissional_id=acs.id,
                        crianca_ref=c.id,
                        data_visita=dia,
                        responsavel_presente=random.random() < 0.8,
                        vacinacao_em_dia=c.vacinacao_em_dia,
                        consulta_em_dia=random.random() < 0.7,
                        aleitamento=random.random() < 0.6,
                        desenvolvimento_ok=random.random() < 0.9,
                    )
                    session.add(visita)

    await session.flush()

    alto_risco_count = len([c for c in all_criancas if c.grupo_risco])
    print(
        f"Seed concluido: 1 equipe, {len(acs_list)} ACS, "
        f"{len(all_criancas)} criancas, {alto_risco_count} alto risco"
    )


async def main() -> None:
    from app.config import settings

    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        await seed(session)
        await session.commit()

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
