"""ChatHistory model — encrypted conversation history with ACS.

LGPD CRITICAL:
- content_enc: ALWAYS stored encrypted with Fernet. Never store raw text.
- Retention: 90 days absolute (G5). Automated cleanup job at 03h.
- Access logs: every read of content must be audited.

See CLAUDE.md Regra 3 and docs/architecture/decisoes_design.md G5.
"""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Identity, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class ChatHistory(UUIDMixin, Base):
    """Conversation message — no TimestampMixin (uses criado_em only, immutable)."""

    __tablename__ = "chat_history"

    profissional_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profissionais.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str]  # "user" or "assistant"
    content_enc: Mapped[bytes]  # Fernet-encrypted message content
    estado_fsm: Mapped[str | None]  # FSM state at time of message
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())
    # Monotonic sequence for stable ordering within the same criado_em timestamp.
    # Uses PostgreSQL IDENTITY so inserts within a transaction remain ordered.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(always=False), nullable=False)

    __table_args__ = (
        # Efficient history lookup ordered by time
        Index("ix_chat_history_profissional_criado_em", "profissional_id", "criado_em"),
        # Index for retention cleanup job
        Index("ix_chat_history_criado_em", "criado_em"),
    )

    def __repr__(self) -> str:
        return (
            f"<ChatHistory id={self.id} profissional={self.profissional_id}"
            f" role={self.role!r} criado_em={self.criado_em}>"
        )
