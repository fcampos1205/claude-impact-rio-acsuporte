"""Testes do script de seed — Fase 2. 6 testes."""

from sqlalchemy import func, select


async def test_seed_popula_equipe_3_acs_1_gestor(db_session, clean_db):
    from scripts.seed import seed
    from app.models import Equipe, Gestor, Profissional

    await seed(db_session)

    equipes = (await db_session.execute(select(func.count()).select_from(Equipe))).scalar()
    profissionais = (
        await db_session.execute(
            select(func.count()).select_from(Profissional).where(Profissional.ativo == True)  # noqa: E712
        )
    ).scalar()
    gestores = (await db_session.execute(select(func.count()).select_from(Gestor))).scalar()

    assert equipes >= 1
    assert profissionais == 3
    assert gestores >= 1


async def test_seed_distribui_criancas_entre_acs(db_session, clean_db):
    from scripts.seed import seed
    from app.models import Crianca, Profissional

    await seed(db_session)

    acs_list = (
        await db_session.execute(select(Profissional).where(Profissional.ativo == True))  # noqa: E712
    ).scalars().all()

    for acs in acs_list:
        count = (
            await db_session.execute(
                select(func.count()).select_from(Crianca).where(Crianca.profissional_id == acs.id)
            )
        ).scalar()
        assert count > 0


async def test_seed_gera_historico_visitas_30_dias(db_session, clean_db):
    from datetime import date, timedelta

    from scripts.seed import seed
    from app.models import Visita

    await seed(db_session)

    cutoff = date.today() - timedelta(days=31)
    count = (
        await db_session.execute(
            select(func.count()).select_from(Visita).where(Visita.data_visita >= cutoff)
        )
    ).scalar()
    assert count > 0


async def test_seed_marca_5_criancas_alto_risco(db_session, clean_db):
    from scripts.seed import seed
    from app.models import Crianca

    await seed(db_session)

    count = (
        await db_session.execute(
            select(func.count()).select_from(Crianca).where(Crianca.grupo_risco == True)  # noqa: E712
        )
    ).scalar()
    assert count >= 5


async def test_seed_idempotente_segunda_execucao_nao_duplica(db_session, clean_db):
    from scripts.seed import seed
    from app.models import Profissional

    await seed(db_session)
    acs_count_1 = (
        await db_session.execute(
            select(func.count()).select_from(Profissional).where(Profissional.ativo == True)  # noqa: E712
        )
    ).scalar()

    await seed(db_session)
    acs_count_2 = (
        await db_session.execute(
            select(func.count()).select_from(Profissional).where(Profissional.ativo == True)  # noqa: E712
        )
    ).scalar()

    assert acs_count_1 == acs_count_2


async def test_seed_respeita_faixa_etaria_0_6(db_session, clean_db):
    from scripts.seed import seed
    from app.models import Crianca

    await seed(db_session)

    total = (await db_session.execute(select(func.count()).select_from(Crianca))).scalar()
    valid = (
        await db_session.execute(
            select(func.count()).select_from(Crianca).where(Crianca.faixa_etaria == "0-6")
        )
    ).scalar()
    assert valid == total
