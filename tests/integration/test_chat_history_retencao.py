"""Testes da retenção de 90 dias do chat_history — Fase 6. G5. 3 testes."""
import pytest


async def test_limpeza_apos_90_dias(db_session, seed_minimal):
    """G5 — mensagens com criado_em < hoje - 90d são deletadas."""
    from app.models import ChatHistory
    from app.crypto import encrypt
    from app.schedulers.limpeza_historico import executar_limpeza_historico
    from datetime import datetime, timedelta
    from sqlalchemy import select

    acs = seed_minimal["acs_list"][0]

    # Insert old message (95 days ago)
    old_msg = ChatHistory(
        profissional_id=acs.id,
        role="user",
        content_enc=encrypt("old message"),
        criado_em=datetime.utcnow() - timedelta(days=95),
    )
    db_session.add(old_msg)
    await db_session.flush()

    result = await executar_limpeza_historico(db_session)
    assert result["linhas_removidas"] >= 1

    check = await db_session.execute(select(ChatHistory).where(ChatHistory.id == old_msg.id))
    assert check.scalar_one_or_none() is None


async def test_limpeza_nao_remove_mensagens_recentes(db_session, seed_minimal):
    """Mensagens dos últimos 90 dias permanecem intactas."""
    from app.models import ChatHistory
    from app.crypto import encrypt
    from app.schedulers.limpeza_historico import executar_limpeza_historico
    from datetime import datetime
    from sqlalchemy import select

    acs = seed_minimal["acs_list"][0]

    recent_msg = ChatHistory(
        profissional_id=acs.id,
        role="user",
        content_enc=encrypt("recent message"),
    )
    db_session.add(recent_msg)
    await db_session.flush()

    await executar_limpeza_historico(db_session)

    check = await db_session.execute(select(ChatHistory).where(ChatHistory.id == recent_msg.id))
    assert check.scalar_one_or_none() is not None


async def test_limpeza_audita_quantidade_removida(db_session, seed_minimal):
    """auditoria registra LIMPEZA_AUTOMATICA_CHAT com contagem."""
    from app.schedulers.limpeza_historico import executar_limpeza_historico
    from app.models.auditoria import Auditoria
    from sqlalchemy import select

    await executar_limpeza_historico(db_session)

    result = await db_session.execute(
        select(Auditoria).where(Auditoria.acao == "LIMPEZA_AUTOMATICA_CHAT")
    )
    audit = result.scalar_one_or_none()
    assert audit is not None
    assert "linhas_removidas" in audit.metadata_json
