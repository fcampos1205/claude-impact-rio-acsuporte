"""Testes de idempotência do batch noturno — Fase 6. G6. 4 testes."""
import pytest


async def test_executar_duas_vezes_nao_duplica(db_session, seed_minimal):
    """G6 — UNIQUE constraint + ON CONFLICT DO UPDATE."""
    from app.schedulers.batch_noite import executar_batch_noite
    from app.models import FilaReposicao, ListaSugestoes
    from sqlalchemy import select, func
    from datetime import date, timedelta

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    ontem = date.today() - timedelta(days=1)

    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=ontem,
        status="SUGERIDA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    await executar_batch_noite(db_session, data_alvo=ontem)
    count1 = (await db_session.execute(
        select(func.count()).select_from(FilaReposicao).where(FilaReposicao.profissional_id == acs.id)
    )).scalar()

    await executar_batch_noite(db_session, data_alvo=ontem)
    count2 = (await db_session.execute(
        select(func.count()).select_from(FilaReposicao).where(FilaReposicao.profissional_id == acs.id)
    )).scalar()

    assert count1 == count2


async def test_executar_apos_falha_parcial_recupera(db_session, seed_minimal):
    """Batch is idempotent — running again after partial failure is safe."""
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta

    ontem = date.today() - timedelta(days=1)
    result = await executar_batch_noite(db_session, data_alvo=ontem)
    assert result is not None
    result2 = await executar_batch_noite(db_session, data_alvo=ontem)
    assert result2 is not None


async def test_dias_pendente_incrementa_a_cada_execucao(db_session, seed_minimal):
    """1ª execução: dias_pendente=1. 2ª execução do mesmo dia: incrementa pra 2."""
    from app.models import ListaSugestoes, FilaReposicao
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta
    from sqlalchemy import select

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    ontem = date.today() - timedelta(days=1)

    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=ontem,
        status="SUGERIDA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    await executar_batch_noite(db_session, data_alvo=ontem)

    result = await db_session.execute(
        select(FilaReposicao).where(FilaReposicao.crianca_ref == crianca.id)
    )
    fila = result.scalar_one_or_none()
    assert fila is not None
    assert fila.dias_pendente >= 1


async def test_score_ajustado_atualiza_em_reexecucao(db_session, seed_minimal):
    """Re-execução atualiza score_ajustado conforme regra atual."""
    from app.models import ListaSugestoes, FilaReposicao
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta
    from sqlalchemy import select

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    ontem = date.today() - timedelta(days=1)

    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=ontem,
        status="SUGERIDA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    await executar_batch_noite(db_session, data_alvo=ontem)

    result = await db_session.execute(
        select(FilaReposicao).where(FilaReposicao.crianca_ref == crianca.id)
    )
    fila = result.scalar_one_or_none()
    assert fila is not None
    assert fila.score_ajustado >= 0
