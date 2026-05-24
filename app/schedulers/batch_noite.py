"""Night batch — runs at 22:00 daily.

Steps:
1. Mark all SUGERIDA suggestions from today as NAO_VISITADA (with 2min cutoff, G2)
2. For each NAO_VISITADA: calculate score_ajustado and insert/update fila_reposicao (G6)
3. Recalculate grupo_risco (G4)
4. Determine override_topo (G3: risco always wins; 3+ days pending -> override)
5. Notify gestores (aggregate, 1 message per gestor, G11)
6. Calculate coverage rate per team (G18: <60% -> notify gestor)
7. Audit

G3 scoring rules for fila_reposicao:
- grupo_risco=True -> override_topo=True, score_ajustado = score_original + BONUS_RISCO_REPOSICAO(50)
- grupo_risco=False, dias=1 -> score_ajustado = score_original + 20
- grupo_risco=False, dias=2 -> score_ajustado = score_original + 30
- grupo_risco=False, dias>=3 -> override_topo=True, score_ajustado = score_original + 40 + (dias-3)*10
"""
import structlog
from datetime import date, datetime, timedelta, UTC

from sqlalchemy import select, update, func
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.models import (
    ListaSugestoes, FilaReposicao, Profissional, Crianca, Gestor,
)
from app.motor.regras import calcular_score_total, determinar_grupo_risco
from app.motor.constants import BONUS_RISCO_REPOSICAO
from app.auditoria import registrar

logger = structlog.get_logger()

CORTE_MINUTOS = 2  # G2: 2-minute cutoff before batch runs


async def executar_batch_noite(session, data_alvo: date | None = None) -> dict:
    """Execute night batch. Idempotent via ON CONFLICT DO UPDATE. Returns stats."""
    hoje = data_alvo or date.today()
    today_real = date.today()
    # Cutoff: start of the next day minus CORTE_MINUTOS (G2).
    # When running for a past date (replaying), use a far-future UTC timestamp so all
    # SUGERIDA rows from that date are eligible (the 22h window has already closed).
    # DB stores timestamps in UTC (naive), so always compare in UTC.
    if hoje < today_real:
        corte_ts = datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1)
    else:
        corte_ts = datetime.combine(hoje + timedelta(days=1), datetime.min.time()) - timedelta(minutes=CORTE_MINUTOS)

    stats = {
        "sugeridas_marcadas": 0,
        "fila_inserida": 0,
        "fila_atualizada": 0,
        "notificacoes_gestor": 0,
        "erros": 0,
    }

    # Step 1: Mark SUGERIDA -> NAO_VISITADA (with cutoff G2)
    result = await session.execute(
        update(ListaSugestoes)
        .where(
            ListaSugestoes.data_sugestao == hoje,
            ListaSugestoes.status == "SUGERIDA",
            ListaSugestoes.updated_at < corte_ts,
        )
        .values(status="NAO_VISITADA")
        .returning(ListaSugestoes.id)
    )
    marcadas = result.fetchall()
    stats["sugeridas_marcadas"] = len(marcadas)
    await session.flush()

    # Step 2: Process each NAO_VISITADA suggestion
    nao_visitadas_result = await session.execute(
        select(ListaSugestoes).where(
            ListaSugestoes.data_sugestao == hoje,
            ListaSugestoes.status == "NAO_VISITADA",
        )
    )
    nao_visitadas = nao_visitadas_result.scalars().all()

    for sugestao in nao_visitadas:
        try:
            # G4: Recalculate grupo_risco with current data
            crianca_result = await session.execute(
                select(Crianca).where(Crianca.id == sugestao.crianca_ref)
            )
            crianca = crianca_result.scalar_one_or_none()
            if crianca is None:
                continue

            score_total = calcular_score_total(
                vacinacao_em_dia=crianca.vacinacao_em_dia,
                dias_vacinacao_atraso=crianca.dias_vacinacao_atraso,
                ultima_consulta=crianca.ultima_consulta,
                ultima_visita=None,
                situacao_vulnerabilidade=crianca.situacao_vulnerabilidade,
                hoje=hoje,
            )
            grupo_risco = determinar_grupo_risco(score_total.total)
            score_original = score_total.total

            # G3: Determine override and score_ajustado
            # Check existing fila entry for this profissional+crianca (unresolved)
            existing_result = await session.execute(
                select(FilaReposicao).where(
                    FilaReposicao.profissional_id == sugestao.profissional_id,
                    FilaReposicao.crianca_ref == sugestao.crianca_ref,
                    FilaReposicao.resolvida_em.is_(None),
                )
            )
            existing = existing_result.scalar_one_or_none()
            dias_pendente = (existing.dias_pendente + 1) if existing else 1

            if grupo_risco:
                override_topo = True
                score_ajustado = score_original + BONUS_RISCO_REPOSICAO
            elif dias_pendente >= 3:
                override_topo = True
                score_ajustado = score_original + 40 + (dias_pendente - 3) * 10
            elif dias_pendente == 2:
                override_topo = False
                score_ajustado = score_original + 30
            else:
                override_topo = False
                score_ajustado = score_original + 20

            # G6: INSERT ON CONFLICT DO UPDATE
            # When inserting a new row: dias_pendente=1 (first occurrence)
            # When conflict fires (row already exists): increment dias_pendente by 1
            stmt = pg_insert(FilaReposicao).values(
                profissional_id=sugestao.profissional_id,
                crianca_ref=sugestao.crianca_ref,
                data_origem=hoje,
                dias_pendente=1,
                score_original=score_original,
                score_ajustado=score_ajustado,
                grupo_risco=grupo_risco,
                override_topo=override_topo,
            ).on_conflict_do_update(
                index_elements=["profissional_id", "crianca_ref", "data_origem"],
                set_={
                    "dias_pendente": FilaReposicao.__table__.c.dias_pendente + 1,
                    "score_ajustado": score_ajustado,
                    "grupo_risco": grupo_risco,
                    "override_topo": override_topo,
                    "updated_at": func.now(),
                },
            )
            await session.execute(stmt)
            stats["fila_inserida"] += 1

        except Exception as e:
            stats["erros"] += 1
            logger.error("batch_noite_item_erro", sugestao_id=str(sugestao.id), erro=str(e))

    await session.flush()

    # Step 3: Calculate coverage and notify gestores (G11, G18)
    gestores_result = await session.execute(
        select(Gestor).where(Gestor.ativo == True)  # noqa: E712
    )
    gestores = gestores_result.scalars().all()

    for gestor in gestores:
        try:
            await _notificar_gestor(session, gestor, hoje, stats)
        except Exception as e:
            logger.error("batch_noite_gestor_erro", gestor_id=str(gestor.id), erro=str(e))

    await registrar(session, acao="BATCH_NOITE_COMPLETO", metadata=stats)
    return stats


async def _notificar_gestor(session, gestor, hoje: date, stats: dict) -> None:
    """Aggregate notifications for a gestor about their teams."""
    import uuid

    equipe_ids = gestor.equipes_ids  # list of UUID strings
    if not equipe_ids:
        return

    for equipe_id_raw in equipe_ids:
        equipe_id = uuid.UUID(equipe_id_raw) if isinstance(equipe_id_raw, str) else equipe_id_raw

        # Count sugestoes for this team today (non-cancelled)
        total_result = await session.execute(
            select(func.count()).select_from(ListaSugestoes)
            .join(Profissional, ListaSugestoes.profissional_id == Profissional.id)
            .where(
                Profissional.equipe_id == equipe_id,
                ListaSugestoes.data_sugestao == hoje,
                ListaSugestoes.status != "CANCELADA",
            )
        )
        total = total_result.scalar() or 0

        visitadas_result = await session.execute(
            select(func.count()).select_from(ListaSugestoes)
            .join(Profissional, ListaSugestoes.profissional_id == Profissional.id)
            .where(
                Profissional.equipe_id == equipe_id,
                ListaSugestoes.data_sugestao == hoje,
                ListaSugestoes.status == "VISITADA",
            )
        )
        visitadas = visitadas_result.scalar() or 0

        if total > 0:
            taxa_cobertura = visitadas / total
            if taxa_cobertura < 0.60:  # G18: <60% -> notify
                logger.warning(
                    "cobertura_abaixo_meta",
                    equipe_id=str(equipe_id),
                    taxa=round(taxa_cobertura * 100, 1),
                    meta=60,
                )
                stats["notificacoes_gestor"] = stats.get("notificacoes_gestor", 0) + 1
