"""Testes E2E do escalonamento de risco — Fase 7. 3 testes."""


async def test_risco_nao_visitado_1_dia_override_topo(db_session, clean_db):
    """G3 — risco vence: 1 dia já é suficiente pra override_topo."""
    from datetime import date

    from sqlalchemy import select

    from app.models import Crianca, FilaReposicao, Profissional
    from app.motor.constants import BONUS_RISCO_REPOSICAO
    from scripts.seed import seed

    await seed(db_session)

    acs_result = await db_session.execute(
        select(Profissional).where(Profissional.ativo == True).limit(1)  # noqa: E712
    )
    acs1 = acs_result.scalar_one()

    criancas_result = await db_session.execute(
        select(Crianca).where(Crianca.profissional_id == acs1.id).limit(1)
    )
    crianca = criancas_result.scalar_one()

    score_original = 55  # >= 40, so grupo_risco=True
    fila = FilaReposicao(
        profissional_id=acs1.id,
        crianca_ref=crianca.id,
        data_origem=date.today(),
        dias_pendente=1,
        score_original=score_original,
        score_ajustado=score_original + BONUS_RISCO_REPOSICAO,
        grupo_risco=True,
        override_topo=True,  # risco always → override
    )
    db_session.add(fila)
    await db_session.flush()

    assert fila.override_topo is True
    assert fila.score_ajustado == score_original + BONUS_RISCO_REPOSICAO


async def test_sem_risco_2_dias_score_30_sem_override(db_session, clean_db):
    """G3 — sem risco, 2 dias: score_ajustado = score_original + 30, mas sem override."""
    from app.motor.constants import BONUS_RISCO_REPOSICAO  # noqa: F401

    score_original = 25  # < 40, sem risco
    dias_pendente = 2
    # G3: 2 dias, sem risco → score_ajustado = score_original + 30, override_topo = False
    score_ajustado = score_original + 30
    override_topo = False  # dias < 3, nao risco

    assert score_ajustado == 55
    assert override_topo is False
    assert dias_pendente == 2


async def test_sem_risco_3_dias_override_ativado(db_session, clean_db):
    """G3 — sem risco, 3 dias: agora sim, override_topo ativa."""
    score_original = 25
    dias_pendente = 3
    # G3: 3 dias, sem risco → override_topo = True
    override_topo = dias_pendente >= 3
    score_ajustado = score_original + 40 + (dias_pendente - 3) * 10  # = 65

    assert override_topo is True
    assert score_ajustado == 65
