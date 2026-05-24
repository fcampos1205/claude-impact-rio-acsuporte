"""Gestor model — health team manager who receives aggregated notifications.

See docs/architecture/decisoes_design.md G11 — this table was not in the PRD
but is required for manager notification feature.

LGPD: telegram_chat_id stored as hash (SHA-256 + salt), never raw.
"""

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Gestor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "gestores"

    nome: Mapped[str]
    telegram_chat_id_hash: Mapped[str] = mapped_column(unique=True)
    equipes_ids: Mapped[list] = mapped_column(JSONB, default=list)
    ativo: Mapped[bool] = mapped_column(default=True)

    def __repr__(self) -> str:
        return f"<Gestor id={self.id} nome={self.nome!r} ativo={self.ativo}>"
