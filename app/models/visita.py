"""Visita model — records a completed home visit.

See docs/architecture/decisoes_design.md G1 — visit creation triggers atomic
resolution of lista_sugestoes and fila_reposicao in the same transaction.
"""

import uuid
from datetime import date

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Visita(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "visitas"

    profissional_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profissionais.id"))
    crianca_ref: Mapped[uuid.UUID] = mapped_column(ForeignKey("criancas.id"))
    data_visita: Mapped[date]

    # Visit outcomes
    responsavel_presente: Mapped[bool]
    vacinacao_em_dia: Mapped[bool | None]
    consulta_em_dia: Mapped[bool | None]
    aleitamento: Mapped[bool | None]
    desenvolvimento_ok: Mapped[bool | None]
    observacoes: Mapped[str | None]

    # FSM state snapshot at time of visit
    estado_ficha: Mapped[str | None]  # JSON with FSM answers

    def __repr__(self) -> str:
        return (
            f"<Visita id={self.id} profissional={self.profissional_id}"
            f" crianca={self.crianca_ref} data={self.data_visita}>"
        )
