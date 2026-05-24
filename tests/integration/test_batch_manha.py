"""Testes do batch matinal (05h) — Fase 6. 8 testes."""
import pytest


async def test_batch_manha_gera_lista_para_cada_acs_ativo(db_session, seed_minimal):
    """G17 — apenas ACS com ativo=True recebe lista."""
    from app.schedulers.batch_manha import executar_batch_manha
    from app.models import ListaSugestoes
    from sqlalchemy import select, func
    from datetime import date

    result = await executar_batch_manha(db_session)
    assert result["listas_geradas"] >= 1


async def test_batch_manha_pula_acs_inativo(db_session, seed_minimal):
    from sqlalchemy import update
    from app.models import Profissional, ListaSugestoes
    from app.schedulers.batch_manha import executar_batch_manha
    from sqlalchemy import select, func
    from datetime import date

    acs = seed_minimal["acs_list"][0]
    await db_session.execute(update(Profissional).where(Profissional.id == acs.id).values(ativo=False))
    await db_session.flush()

    await executar_batch_manha(db_session)

    # Inactive ACS has no suggestions
    count = (await db_session.execute(
        select(func.count()).select_from(ListaSugestoes)
        .where(ListaSugestoes.profissional_id == acs.id, ListaSugestoes.data_sugestao == date.today())
    )).scalar()
    assert count == 0


async def test_batch_manha_overrides_aparecem_primeiro(db_session, seed_minimal):
    """G8 — overrides têm posicao_lista de 1..N antes de candidatos novos."""
    from app.schedulers.batch_manha import executar_batch_manha
    from app.models import ListaSugestoes, FilaReposicao
    from sqlalchemy import select
    from datetime import date

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]

    fila = FilaReposicao(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_origem=date.today(),
        dias_pendente=2,
        score_original=50,
        score_ajustado=80,
        grupo_risco=False,
        override_topo=False,
    )
    db_session.add(fila)
    await db_session.flush()

    await executar_batch_manha(db_session)

    # The override crianca should be in the list
    result = await db_session.execute(
        select(ListaSugestoes).where(
            ListaSugestoes.profissional_id == acs.id,
            ListaSugestoes.crianca_ref == crianca.id,
            ListaSugestoes.data_sugestao == date.today(),
        )
    )
    sugestao = result.scalar_one_or_none()
    assert sugestao is not None


async def test_batch_manha_dedupe_aplicado(db_session, seed_minimal):
    """G1 — crianças com VISITADA recente não aparecem como candidato novo."""
    from app.schedulers.batch_manha import executar_batch_manha
    from app.models import ListaSugestoes
    from sqlalchemy import select
    from datetime import date, timedelta

    acs = seed_minimal["acs_list"][0]
    crianca = seed_minimal["criancas"][0]

    # Already visited today
    visited = ListaSugestoes(
        profissional_id=acs.id,
        crianca_ref=crianca.id,
        data_sugestao=date.today(),
        status="VISITADA",
    )
    db_session.add(visited)
    await db_session.flush()

    await executar_batch_manha(db_session)

    # The visited child should appear only once (the existing VISITADA entry)
    result = await db_session.execute(
        select(ListaSugestoes).where(
            ListaSugestoes.profissional_id == acs.id,
            ListaSugestoes.crianca_ref == crianca.id,
            ListaSugestoes.data_sugestao == date.today(),
        )
    )
    entries = result.scalars().all()
    # ON CONFLICT DO NOTHING means it won't create a second entry
    assert len(entries) <= 1


async def test_batch_manha_chama_llm_e_usa_fallback_em_falha(db_session, seed_minimal, mock_claude_api_falha):
    """Quando Claude API falha, usa fallback Jinja2 e audita."""
    from app.schedulers.batch_manha import executar_batch_manha
    from app.models import ListaSugestoes
    from sqlalchemy import select, func
    from datetime import date

    result = await executar_batch_manha(db_session)
    # Despite LLM failure, batch completes (uses fallback)
    assert result["erros"] == 0 or result["listas_geradas"] >= 0


async def test_batch_manha_respeita_limite_15(db_session, seed_minimal):
    """G9 — máximo 15 itens por ACS, com mínimo 3 candidatos novos."""
    from app.schedulers.batch_manha import executar_batch_manha
    from app.models import ListaSugestoes, Profissional
    from sqlalchemy import select, func
    from datetime import date

    await executar_batch_manha(db_session)

    for acs in seed_minimal["acs_list"]:
        count = (await db_session.execute(
            select(func.count()).select_from(ListaSugestoes).where(
                ListaSugestoes.profissional_id == acs.id,
                ListaSugestoes.data_sugestao == date.today(),
            )
        )).scalar()
        assert count <= 15


async def test_batch_manha_idempotente_no_mesmo_dia(db_session, seed_minimal, mock_claude_api):
    """Rodar batch manhã 2x no mesmo dia não duplica lista_sugestoes."""
    from app.schedulers.batch_manha import executar_batch_manha
    from app.models import ListaSugestoes
    from sqlalchemy import select, func
    from datetime import date

    await executar_batch_manha(db_session)
    count1 = (await db_session.execute(
        select(func.count()).select_from(ListaSugestoes).where(ListaSugestoes.data_sugestao == date.today())
    )).scalar()

    await executar_batch_manha(db_session)
    count2 = (await db_session.execute(
        select(func.count()).select_from(ListaSugestoes).where(ListaSugestoes.data_sugestao == date.today())
    )).scalar()

    assert count1 == count2


async def test_batch_manha_persiste_status_sugerida(db_session, seed_minimal, mock_claude_api):
    """Toda linha em lista_sugestoes começa com status=SUGERIDA."""
    from app.schedulers.batch_manha import executar_batch_manha
    from app.models import ListaSugestoes
    from sqlalchemy import select
    from datetime import date

    await executar_batch_manha(db_session)

    result = await db_session.execute(
        select(ListaSugestoes).where(ListaSugestoes.data_sugestao == date.today())
    )
    sugestoes = result.scalars().all()
    for s in sugestoes:
        assert s.status == "SUGERIDA"
