"""Motor de priorização — pipeline completo para gerar lista diária de visitas.

Decisões de design: G8 (ordenação), G9 (limite + mínimo 3 novos), G17 (ACS inativo).
"""
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crianca import Crianca
from app.models.fila_reposicao import FilaReposicao
from app.models.profissional import Profissional
from app.models.visita import Visita
from app.motor.constants import LIMITE_LISTA_DIARIA, MINIMO_NOVOS_NA_LISTA
from app.motor.deduplicacao import obter_visitadas_no_ciclo
from app.motor.regras import calcular_score_total, determinar_grupo_risco


@dataclass
class CandidatoSugestao:
    crianca_ref: UUID
    score: int
    grupo_risco: bool
    eh_pendencia: bool
    dias_pendente: int
    override_topo: bool
    score_ajustado: int
    motivos: list[str] = field(default_factory=list)
    created_at: object = None  # usado para desempate por criação (ASC)


@dataclass
class ListaPriorizada:
    profissional_id: UUID
    data: date
    itens: list[CandidatoSugestao] = field(default_factory=list)


async def gerar_lista(
    session: AsyncSession,
    profissional_id: UUID,
    data: date | None = None,
) -> ListaPriorizada:
    """Gera lista priorizada de visitas para um ACS.

    G9: máximo 15 itens, mínimo 3 candidatos novos.
    G8: overrides ordenados por dias_pendente DESC, grupo_risco DESC,
        score_ajustado DESC, created_at ASC.
    G17: ACS inativo retorna lista vazia.
    """
    hoje = data or date.today()

    # G17: verificar se ACS existe e está ativo
    result = await session.execute(
        select(Profissional).where(Profissional.id == profissional_id)
    )
    profissional = result.scalar_one_or_none()
    if profissional is None or not profissional.ativo:
        return ListaPriorizada(profissional_id=profissional_id, data=hoje)

    # Obter conjunto de deduplicação (visitadas no ciclo atual)
    visitadas = await obter_visitadas_no_ciclo(session, profissional_id)

    # Obter overrides pendentes da fila_reposicao (não resolvidos)
    overrides_result = await session.execute(
        select(FilaReposicao)
        .where(
            FilaReposicao.profissional_id == profissional_id,
            FilaReposicao.resolvida_em.is_(None),
        )
        .order_by(
            FilaReposicao.dias_pendente.desc(),
            FilaReposicao.grupo_risco.desc(),
            FilaReposicao.score_ajustado.desc(),
            FilaReposicao.created_at.asc(),
        )
    )
    overrides = overrides_result.scalars().all()

    # Construir candidatos de override (excluindo já visitadas no ciclo)
    override_candidatos: list[CandidatoSugestao] = []
    for o in overrides:
        if o.crianca_ref in visitadas:
            continue
        override_candidatos.append(CandidatoSugestao(
            crianca_ref=o.crianca_ref,
            score=o.score_original,
            grupo_risco=o.grupo_risco,
            eh_pendencia=True,
            dias_pendente=o.dias_pendente,
            override_topo=o.override_topo,
            score_ajustado=o.score_ajustado,
            created_at=o.created_at,
        ))

    # G9: limitar overrides para garantir espaço mínimo para novos candidatos
    max_overrides = LIMITE_LISTA_DIARIA - MINIMO_NOVOS_NA_LISTA
    if len(override_candidatos) > max_overrides:
        override_candidatos = override_candidatos[:max_overrides]

    slots_novos = LIMITE_LISTA_DIARIA - len(override_candidatos)

    # IDs a excluir dos novos candidatos (já em override ou visitadas)
    override_refs = {c.crianca_ref for c in override_candidatos}
    excluir = visitadas | override_refs

    # Buscar novas crianças do ACS (ativas, não em overrides ou visitadas)
    if excluir:
        criancas_result = await session.execute(
            select(Crianca).where(
                Crianca.profissional_id == profissional_id,
                Crianca.ativo == True,  # noqa: E712
                Crianca.id.not_in(list(excluir)),
            )
        )
    else:
        criancas_result = await session.execute(
            select(Crianca).where(
                Crianca.profissional_id == profissional_id,
                Crianca.ativo == True,  # noqa: E712
            )
        )
    criancas = criancas_result.scalars().all()

    # Calcular score para cada nova criança
    novos_candidatos: list[CandidatoSugestao] = []
    for c in criancas:
        visita_result = await session.execute(
            select(Visita.data_visita)
            .where(Visita.crianca_ref == c.id)
            .order_by(Visita.data_visita.desc())
            .limit(1)
        )
        ultima_visita = visita_result.scalar_one_or_none()

        score_total = calcular_score_total(
            vacinacao_em_dia=c.vacinacao_em_dia,
            dias_vacinacao_atraso=c.dias_vacinacao_atraso,
            ultima_consulta=c.ultima_consulta,
            ultima_visita=ultima_visita,
            situacao_vulnerabilidade=c.situacao_vulnerabilidade,
            hoje=hoje,
        )
        grupo_risco = determinar_grupo_risco(score_total.total)

        novos_candidatos.append(CandidatoSugestao(
            crianca_ref=c.id,
            score=score_total.total,
            grupo_risco=grupo_risco,
            eh_pendencia=False,
            dias_pendente=0,
            override_topo=grupo_risco,
            score_ajustado=score_total.total,
            motivos=score_total.motivos,
            created_at=c.created_at,
        ))

    # Ordenar novos por score DESC, created_at ASC (desempate estável)
    novos_candidatos.sort(key=lambda x: (-x.score, str(x.created_at)))
    novos_candidatos = novos_candidatos[:slots_novos]

    itens = override_candidatos + novos_candidatos
    return ListaPriorizada(profissional_id=profissional_id, data=hoje, itens=itens)
