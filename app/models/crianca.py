"""Crianca model — child registered for ACS home visits.

LGPD: This model contains health data of minors — highest protection class.
All access must be logged in auditoria. Content fields must never appear in logs.
"""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.equipe import Equipe
    from app.models.profissional import Profissional


class Crianca(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "criancas"

    profissional_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profissionais.id"))
    equipe_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("equipes.id"))

    # Demographics
    faixa_etaria: Mapped[str]  # e.g. "0-6"
    sexo: Mapped[str]
    raca_cor: Mapped[str]

    # Risk factors
    situacao_vulnerabilidade: Mapped[bool] = mapped_column(default=False)
    vacinacao_em_dia: Mapped[bool] = mapped_column(default=True)
    dias_vacinacao_atraso: Mapped[int] = mapped_column(default=0)
    ultima_consulta: Mapped[date | None]
    grupo_risco: Mapped[bool] = mapped_column(default=False)

    # Location
    endereco_latitude: Mapped[float | None]
    endereco_longitude: Mapped[float | None]

    # Status
    ativo: Mapped[bool] = mapped_column(default=True)

    # Relationships
    profissional: Mapped["Profissional"] = relationship(lazy="select")
    equipe: Mapped["Equipe"] = relationship(back_populates="criancas", lazy="select")

    def __repr__(self) -> str:
        return f"<Crianca id={self.id} faixa={self.faixa_etaria!r} risco={self.grupo_risco}>"
