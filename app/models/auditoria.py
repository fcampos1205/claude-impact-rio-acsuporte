"""Auditoria model — immutable audit log for LGPD compliance.

CRITICAL LGPD: Every action that reads, writes, or exports personal data
MUST create an audit record. Content (message text, CPF, full name) must
NEVER appear in metadata — only IDs, action names, and aggregate counts.

See CLAUDE.md Regra 3 and docs/architecture/decisoes_design.md G10.
"""

import uuid
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin


class Auditoria(UUIDMixin, Base):
    """Audit record — no updated_at (records are immutable by design)."""

    __tablename__ = "auditoria"

    acao: Mapped[str]
    profissional_id: Mapped[uuid.UUID | None]
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, name="metadata_json")
    criado_em: Mapped[datetime] = mapped_column(server_default=func.now())

    def __repr__(self) -> str:
        return f"<Auditoria id={self.id} acao={self.acao!r} profissional={self.profissional_id}>"
