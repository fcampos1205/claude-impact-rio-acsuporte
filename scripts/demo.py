"""End-to-end pitch demo scenario.

Demonstrates the complete ACS Primeira Infância workflow:
1. Reset DB + seed
2. Run batch 05h → show lists for 3 ACS
3. Simulate ACS-1 visiting 8 of 15 children (via direct DB manipulation)
4. Run batch 22h → show 7 in fila_reposicao, 2 critical with override
5. Run batch 05h day+1 → show new list with pending on top
6. Print final summary table

Run: make demo
Or:  python -m scripts.demo
"""
import asyncio
import unittest.mock
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models import Base, Crianca, FilaReposicao, ListaSugestoes, Profissional, Visita

SEPARATOR = "=" * 60


async def main() -> None:
    from app.config import settings

    engine = create_async_engine(settings.database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    print(f"\n{SEPARATOR}")
    print("ACS Primeira Infância — Demo Hackathon")
    print(SEPARATOR)

    # Step 1: Seed
    print("\nEtapa 1: Populando banco de dados...")
    async with SessionLocal() as session:
        from scripts.seed import seed

        await seed(session)
        await session.commit()
    print("  1 equipe, 3 ACS, ~150 criancas, 30 dias de historico")

    # Step 2: Batch manhã dia 1
    print(f"\n{SEPARATOR}")
    print("Etapa 2: Batch 05h — Gerando listas do dia")
    print(SEPARATOR)

    hoje = date.today()
    async with SessionLocal() as session:
        from app.schedulers.batch_manha import executar_batch_manha

        await executar_batch_manha(session)
        await session.commit()

        acs_list_result = await session.execute(
            select(Profissional).where(Profissional.ativo == True)  # noqa: E712
        )
        acs_list = acs_list_result.scalars().all()

        for acs in acs_list:
            sugestoes_result = await session.execute(
                select(ListaSugestoes)
                .where(
                    ListaSugestoes.profissional_id == acs.id,
                    ListaSugestoes.data_sugestao == hoje,
                )
                .order_by(ListaSugestoes.posicao_lista)
            )
            sugestoes = sugestoes_result.scalars().all()
            print(f"\n  ACS: {acs.nome} — {len(sugestoes)} criancas na lista")
            for s in sugestoes[:5]:
                flag = "[RISCO]" if s.grupo_risco else ("[OVERRIDE]" if s.override_topo else "  ")
                print(f"    {flag} Pos {s.posicao_lista}: score={s.score} status={s.status}")
            if len(sugestoes) > 5:
                print(f"    ... e mais {len(sugestoes) - 5}")

    # Step 3: Simulate visits for ACS-1 (8 of 15)
    print(f"\n{SEPARATOR}")
    print("Etapa 3: ACS-1 realiza 8 visitas")
    print(SEPARATOR)

    async with SessionLocal() as session:
        acs_result = await session.execute(
            select(Profissional).where(Profissional.ativo == True).limit(1)  # noqa: E712
        )
        acs1 = acs_result.scalar_one()

        sugestoes_result = await session.execute(
            select(ListaSugestoes)
            .where(
                ListaSugestoes.profissional_id == acs1.id,
                ListaSugestoes.data_sugestao == hoje,
            )
            .limit(8)
        )
        sugestoes_para_visitar = sugestoes_result.scalars().all()

        for s in sugestoes_para_visitar:
            s.status = "VISITADA"
            visita = Visita(
                profissional_id=acs1.id,
                crianca_ref=s.crianca_ref,
                data_visita=hoje,
                responsavel_presente=True,
                vacinacao_em_dia=True,
            )
            session.add(visita)

        await session.commit()

    print(f"  {len(sugestoes_para_visitar)} visitas registradas para {acs1.nome}")

    # Step 4: Batch noite
    print(f"\n{SEPARATOR}")
    print("Etapa 4: Batch 22h — Processando nao-visitadas")
    print(SEPARATOR)

    async with SessionLocal() as session:
        from app.schedulers.batch_noite import executar_batch_noite

        stats_noite = await executar_batch_noite(session, data_alvo=hoje)
        await session.commit()

        fila_result = await session.execute(
            select(FilaReposicao).where(FilaReposicao.resolvida_em.is_(None))
        )
        fila = fila_result.scalars().all()
        criticas = [f for f in fila if f.override_topo]

        print(f"  Sugestoes marcadas NAO_VISITADA: {stats_noite['sugeridas_marcadas']}")
        print(f"  Entradas na fila de reposicao: {len(fila)}")
        print(f"  Com override_topo (criticas): {len(criticas)}")

    # Step 5: Batch manhã dia+1
    print(f"\n{SEPARATOR}")
    print("Etapa 5: Batch 05h Dia+1 — Pendentes no topo")
    print(SEPARATOR)

    amanha = hoje + timedelta(days=1)
    async with SessionLocal() as session:
        from app.schedulers.batch_manha import executar_batch_manha

        with unittest.mock.patch("app.schedulers.batch_manha.date") as mock_date:
            mock_date.today.return_value = amanha
            await executar_batch_manha(session)
        await session.commit()

        acs_result = await session.execute(
            select(Profissional).where(Profissional.ativo == True).limit(1)  # noqa: E712
        )
        acs1 = acs_result.scalar_one()

        lista_amanha_result = await session.execute(
            select(ListaSugestoes)
            .where(
                ListaSugestoes.profissional_id == acs1.id,
            )
            .order_by(ListaSugestoes.data_sugestao.desc(), ListaSugestoes.posicao_lista)
            .limit(5)
        )
        lista_amanha = lista_amanha_result.scalars().all()

        print(f"\n  {acs1.nome} — Primeiras posicoes amanha:")
        for s in lista_amanha[:5]:
            flag = "[RISCO]" if s.grupo_risco else ("[OVERRIDE]" if s.override_topo else "  ")
            print(f"    {flag} score={s.score} override={s.override_topo} status={s.status}")

    # Step 6: Final summary
    print(f"\n{SEPARATOR}")
    print("Etapa 6: Resumo Final")
    print(SEPARATOR)

    async with SessionLocal() as session:
        total_criancas = (
            await session.execute(select(func.count()).select_from(Crianca))
        ).scalar()
        total_sugestoes = (
            await session.execute(select(func.count()).select_from(ListaSugestoes))
        ).scalar()
        total_visitadas = (
            await session.execute(
                select(func.count())
                .select_from(ListaSugestoes)
                .where(ListaSugestoes.status == "VISITADA")
            )
        ).scalar()
        fila_ativa = (
            await session.execute(
                select(func.count())
                .select_from(FilaReposicao)
                .where(FilaReposicao.resolvida_em.is_(None))
            )
        ).scalar()

        cobertura = (total_visitadas / total_sugestoes * 100) if total_sugestoes > 0 else 0

        print(f"\n  {'Criancas cadastradas':<30} {total_criancas}")
        print(f"  {'Sugestoes geradas':<30} {total_sugestoes}")
        print(f"  {'Visitas realizadas':<30} {total_visitadas}")
        print(f"  {'Taxa de cobertura':<30} {cobertura:.1f}%")
        print(f"  {'Fila de reposicao ativa':<30} {fila_ativa}")

    print(f"\n{SEPARATOR}")
    print("Demo concluido com sucesso!")
    print(SEPARATOR)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
