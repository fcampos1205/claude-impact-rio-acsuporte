"""FilaReposicao model — queue of unvisited children carried over from previous day.

See docs/architecture/decisoes_design.md:
- G1: resolved via resolvida_em timestamp when visit is recorded
- G3: scoring hierarchy (risco > override > score)
- G6: UNIQUE constraint enables idempotent ON CONFLICT DO UPDATE in night batch
"""

import uuid
from datetime import date, datetime

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class FilaReposicao(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "fila_reposicao"

    profissional_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("profissionais.id"))
    crianca_ref: Mapped[uuid.UUID] = mapped_column(ForeignKey("criancas.id"))
    data_origem: Mapped[date]

    # Escalation tracking
    dias_pendente: Mapped[int] = mapped_column(default=1)
    score_ajustado: Mapped[int] = mapped_column(default=0)
    score_original: Mapped[int] = mapped_column(default=0)
    grupo_risco: Mapped[bool] = mapped_column(default=False)
    override_topo: Mapped[bool] = mapped_column(default=False)

    # Resolution (G1): set when visit is recorded
    resolvida_em: Mapped[datetime | None]

    __table_args__ = (
        # G6: idempotency — ON CONFLICT (profissional_id, crianca_ref, data_origem) DO UPDATE
        UniqueConstraint(
            "profissional_id",
            "crianca_ref",
            "data_origem",
            name="uq_fila_reposicao_profissional_crianca_origem",
        ),
        # Partial index for active queue (WHERE resolvida_em IS NULL)
        # Note: SQLAlchemy creates this, but partial index syntax requires postgresql_where
        Index(
            "ix_fila_reposicao_profissional_pendente",
            "profissional_id",
            postgresql_where="resolvida_em IS NULL",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<FilaReposicao id={self.id} profissional={self.profissional_id}"
            f" crianca={self.crianca_ref} dias={self.dias_pendente}"
            f" resolvida={self.resolvida_em is not None}>"
        )
