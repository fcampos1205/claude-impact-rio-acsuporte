"""Encrypted conversation history for ACS bot.

LGPD: content_enc is always encrypted. Decryption only in-memory.
Retention: 90 days (enforced by limpeza_historico batch job at 03h).

See docs/architecture/decisoes_design.md G5, G10.
"""
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt, encrypt
from app.models.chat_history import ChatHistory


async def salvar_mensagem(
    session: AsyncSession,
    profissional_id: UUID,
    role: str,
    content: str,
    estado_fsm: str | None = None,
) -> ChatHistory:
    """Encrypt and persist a chat message. Does NOT commit — caller owns transaction."""
    entry = ChatHistory(
        profissional_id=profissional_id,
        role=role,
        content_enc=encrypt(content),
        estado_fsm=estado_fsm,
    )
    session.add(entry)
    await session.flush()
    return entry


async def carregar_contexto(
    session: AsyncSession,
    profissional_id: UUID,
    n_ultimas: int = 20,
) -> list[dict]:
    """Load and decrypt the last n_ultimas messages for a profissional.

    Returns messages in chronological order (oldest first).
    """
    result = await session.execute(
        select(ChatHistory)
        .where(ChatHistory.profissional_id == profissional_id)
        .order_by(ChatHistory.criado_em.desc(), ChatHistory.seq.desc())
        .limit(n_ultimas)
    )
    rows = result.scalars().all()
    # Reverse to get oldest-first (chronological) order
    rows = list(reversed(rows))
    return [
        {
            "role": r.role,
            "content": decrypt(r.content_enc),
            "estado_fsm": r.estado_fsm,
            "criado_em": r.criado_em,
        }
        for r in rows
    ]


async def limpar_historico(
    session: AsyncSession,
    profissional_id: UUID,
) -> int:
    """G10: Delete all messages for an ACS. Returns count of deleted messages.

    Audit record is written by the caller (comandos.py) so the caller can
    include period metadata before deletion.
    """
    # Count before deletion
    count_result = await session.execute(
        select(ChatHistory).where(ChatHistory.profissional_id == profissional_id)
    )
    mensagens = count_result.scalars().all()
    count = len(mensagens)

    # Delete all messages for this profissional
    await session.execute(
        delete(ChatHistory).where(ChatHistory.profissional_id == profissional_id)
    )
    return count
