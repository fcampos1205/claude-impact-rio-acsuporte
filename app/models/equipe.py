"""Equipe model — represents a health team (ESF/UBS)."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.crianca import Crianca
    from app.models.profissional import Profissional


class Equipe(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "equipes"

    nome: Mapped[str]
    endereco_latitude: Mapped[float | None]
    endereco_longitude: Mapped[float | None]

    # Relationships
    profissionais: Mapped[list["Profissional"]] = relationship(
        back_populates="equipe", lazy="select"
    )
    criancas: Mapped[list["Crianca"]] = relationship(
        back_populates="equipe", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<Equipe id={self.id} nome={self.nome!r}>"
