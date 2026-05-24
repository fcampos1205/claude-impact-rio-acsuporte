"""Deduplicação de candidatos — evita reapresentar crianças já visitadas no ciclo.

Ver docs/architecture/decisoes_design.md seção 4.3 — ciclo de deduplicação de 30 dias.
"""
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lista_sugestoes import ListaSugestoes


async def obter_visitadas_no_ciclo(
    session: AsyncSession,
    profissional_id: UUID,
    ciclo_dias: int = 30,
) -> set[UUID]:
    """Retorna UUIDs de crianças com status=VISITADA nos últimos ciclo_dias."""
    corte = date.today() - timedelta(days=ciclo_dias)
    result = await session.execute(
        select(ListaSugestoes.crianca_ref)
        .where(
            ListaSugestoes.profissional_id == profissional_id,
            ListaSugestoes.status == "VISITADA",
            ListaSugestoes.data_sugestao >= corte,
        )
    )
    return {row[0] for row in result.fetchall()}


def filtrar_candidatos(candidatos: list, visitadas: set[UUID]) -> list:
    """Remove de candidatos qualquer item cujo .crianca_ref esteja em visitadas."""
    return [c for c in candidatos if c.crianca_ref not in visitadas]
