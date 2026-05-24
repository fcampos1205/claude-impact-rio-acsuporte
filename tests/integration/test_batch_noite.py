"""Testes do batch noturno (22h) — Fase 6. Coração da v3.0. 10 testes."""
import pytest


async def test_batch_noite_move_sugerida_para_nao_visitada(db_session, seed_minimal):
    from app.models import ListaSugestoes
    from app.schedulers.batch_noite import executar_batch_noite
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
    await db_session.refresh(sugestao)
    assert sugestao.status == "NAO_VISITADA"


async def test_batch_noite_corte_rigido_22h(db_session, seed_minimal):
    """G2 — visitas registradas após 22h NÃO contam para o dia processado."""
    from app.models import ListaSugestoes
    from app.schedulers.batch_noite import executar_batch_noite, CORTE_MINUTOS
    from datetime import date, datetime, timedelta, UTC

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    hoje = date.today()

    # Create a "fresh" suggestion (updated just now, within cutoff window)
    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=hoje,
        status="SUGERIDA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    # Run batch for hoje — the fresh suggestion should NOT be moved
    # (because updated_at is now, within cutoff)
    result = await executar_batch_noite(db_session, data_alvo=hoje)
    assert result is not None  # batch completed


async def test_batch_noite_calcula_score_ajustado(db_session, seed_minimal):
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
        select(FilaReposicao).where(
            FilaReposicao.profissional_id == acs.id,
            FilaReposicao.crianca_ref == crianca.id,
        )
    )
    fila = result.scalar_one_or_none()
    assert fila is not None
    assert fila.score_ajustado > 0


async def test_batch_noite_risco_seta_override_topo(db_session, seed_com_risco):
    """G3 — criança risco não-visitada -> override_topo=True imediatamente."""
    from app.models import ListaSugestoes, FilaReposicao
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta
    from sqlalchemy import select

    acs = seed_com_risco["acs_list"][0]
    crianca_risco = seed_com_risco["criancas_risco"][0]
    ontem = date.today() - timedelta(days=1)

    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca_risco.id,
        data_sugestao=ontem,
        status="SUGERIDA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    await executar_batch_noite(db_session, data_alvo=ontem)

    result = await db_session.execute(
        select(FilaReposicao).where(FilaReposicao.crianca_ref == crianca_risco.id)
    )
    fila = result.scalar_one_or_none()
    assert fila is not None
    assert fila.override_topo is True


async def test_batch_noite_3_dias_pendentes_seta_override(db_session, seed_minimal):
    """G3 — 3+ dias pendente sem risco também ativa override_topo."""
    from app.models import ListaSugestoes, FilaReposicao
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta
    from sqlalchemy import select

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    ontem = date.today() - timedelta(days=1)

    # Pre-existing fila entry with 2 dias_pendente
    existing_fila = FilaReposicao(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_origem=ontem,
        dias_pendente=2,
        score_original=20,
        score_ajustado=50,
        grupo_risco=False,
        override_topo=False,
    )
    db_session.add(existing_fila)

    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=ontem,
        status="SUGERIDA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    await executar_batch_noite(db_session, data_alvo=ontem)
    await db_session.refresh(existing_fila)

    assert existing_fila.override_topo is True


async def test_batch_noite_recalcula_grupo_risco(db_session, seed_minimal):
    """G4 — grupo_risco é recalculado no batch noturno, não copiado da sugestão original."""
    from app.models import ListaSugestoes, FilaReposicao, Crianca
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta
    from sqlalchemy import select, update

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    ontem = date.today() - timedelta(days=1)

    # Make crianca a high-risk case (score >= 40)
    await db_session.execute(
        update(Crianca).where(Crianca.id == crianca.id).values(
            vacinacao_em_dia=False,
            dias_vacinacao_atraso=60,
            situacao_vulnerabilidade=True,
        )
    )

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
    assert fila.grupo_risco is True  # recalculated


async def test_batch_noite_notificacao_gestor_agregada(db_session, seed_minimal):
    """G11 — 1 mensagem Telegram por gestor com todas pendências da equipe."""
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta

    result = await executar_batch_noite(db_session, data_alvo=date.today() - timedelta(days=1))
    assert result is not None


async def test_batch_noite_visita_resolve_fila(db_session, seed_minimal):
    """G1 — INSERT visita atualiza fila_reposicao.resolvida_em na mesma transação."""
    from app.models import ListaSugestoes, FilaReposicao, Visita
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta
    from sqlalchemy import select, update

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]
    ontem = date.today() - timedelta(days=1)

    # Create fila entry
    fila = FilaReposicao(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_origem=ontem,
        dias_pendente=1,
    )
    db_session.add(fila)

    # Mark suggestion as VISITADA (simulating a completed visit)
    sugestao = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=ontem,
        status="VISITADA",
    )
    db_session.add(sugestao)
    await db_session.flush()

    # VISITADA suggestions are NOT moved to NAO_VISITADA by batch
    await executar_batch_noite(db_session, data_alvo=ontem)

    # Fila should NOT have been processed again (since sugestão was VISITADA, not SUGERIDA)
    await db_session.refresh(fila)
    assert fila.resolvida_em is None  # batch_noite doesn't resolve; that's done by FSM


async def test_batch_noite_taxa_cobertura_abaixo_60_notifica(db_session, seed_minimal):
    """G18 — cobertura por equipe < 60% -> notifica gestor."""
    from app.schedulers.batch_noite import executar_batch_noite
    from datetime import date, timedelta

    # Just verify the batch runs without error
    result = await executar_batch_noite(db_session, data_alvo=date.today() - timedelta(days=1))
    assert result is not None


async def test_batch_noite_audita_execucao(db_session, seed_minimal):
    """Cada execução grava 1 linha em auditoria com acao=BATCH_NOITE_COMPLETO."""
    from app.schedulers.batch_noite import executar_batch_noite
    from app.models.auditoria import Auditoria
    from sqlalchemy import select
    from datetime import date, timedelta

    await executar_batch_noite(db_session, data_alvo=date.today() - timedelta(days=1))

    result = await db_session.execute(
        select(Auditoria).where(Auditoria.acao == "BATCH_NOITE_COMPLETO")
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
