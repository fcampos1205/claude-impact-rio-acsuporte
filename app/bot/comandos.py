"""Bot commands: /start, /lista, /limpar_historico.

LGPD: audit records never include message content — only counts and periods.
See docs/architecture/decisoes_design.md G10.
"""
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auditoria import registrar
from app.bot.historico import limpar_historico
from app.models.chat_history import ChatHistory


async def cmd_limpar_historico(session: AsyncSession, profissional_id: UUID) -> str:
    """G10: Clear chat history and write an audit record without content.

    Returns a confirmation message for the ACS.
    """
    # Capture period metadata BEFORE deletion (audit must not expose content)
    result = await session.execute(
        select(
            func.min(ChatHistory.criado_em),
            func.max(ChatHistory.criado_em),
        ).where(ChatHistory.profissional_id == profissional_id)
    )
    row = result.one()
    periodo_inicio = row[0].date().isoformat() if row[0] else None
    periodo_fim = row[1].date().isoformat() if row[1] else None

    count = await limpar_historico(session, profissional_id)

    await registrar(
        session,
        acao="LIMPAR_HISTORICO",
        profissional_id=profissional_id,
        metadata={
            "mensagens_apagadas": count,
            "periodo_inicio": periodo_inicio,
            "periodo_fim": periodo_fim,
        },
    )

    return f"Historico limpo. {count} mensagens apagadas."
