"""Profissional model — represents an ACS (Community Health Agent).

LGPD: telegram_chat_id is stored as a hash (SHA-256 + salt), never raw.
See CLAUDE.md Regra 3 and docs/architecture/decisoes_design.md.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.equipe import Equipe


class Profissional(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "profissionais"

    nome: Mapped[str]
    telegram_chat_id_hash: Mapped[str] = mapped_column(unique=True)
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipes.id"))
    ativo: Mapped[bool] = mapped_column(default=True)
    estado_fsm: Mapped[str | None]  # serialized FSM state

    # Relationships
    equipe: Mapped["Equipe"] = relationship(back_populates="profissionais", lazy="select")

    def __repr__(self) -> str:
        return f"<Profissional id={self.id} nome={self.nome!r} ativo={self.ativo}>"
