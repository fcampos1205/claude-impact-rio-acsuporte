"""Limpeza automatica de chat_history > 90 dias (G5 LGPD).

Runs at 03:00 daily, separate from the critical batches.
"""
import structlog
from datetime import datetime, timedelta, UTC

from sqlalchemy import delete, func, select

from app.models.chat_history import ChatHistory
from app.auditoria import registrar

logger = structlog.get_logger()


async def executar_limpeza_historico(session) -> dict:
    """Delete chat messages older than 90 days. Idempotent (no-op if nothing to delete)."""
    from app.config import settings

    corte = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=settings.retencao_chat_dias)

    # Count before deletion
    count_result = await session.execute(
        select(func.count()).select_from(ChatHistory).where(ChatHistory.criado_em < corte)
    )
    count = count_result.scalar() or 0

    if count > 0:
        await session.execute(
            delete(ChatHistory).where(ChatHistory.criado_em < corte)
        )

    await registrar(
        session,
        acao="LIMPEZA_AUTOMATICA_CHAT",
        metadata={"linhas_removidas": count, "corte_data": corte.isoformat()},
    )

    logger.info("limpeza_historico_ok", removidas=count)
    return {"linhas_removidas": count}
