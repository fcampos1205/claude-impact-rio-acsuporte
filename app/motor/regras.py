"""Regras de score do motor de priorização — Fase 3.

Funções puras: sem acesso a DB, sem datetime.now() interno.
Recebem `hoje` como parâmetro para facilitar testes determinísticos.
"""
from dataclasses import dataclass, field
from datetime import date

from app.motor.constants import SCORE_THRESHOLD_RISCO


@dataclass
class ScoreComponente:
    pontos: int
    motivo: str


@dataclass
class ScoreTotal:
    total: int
    motivos: list[str] = field(default_factory=list)


def score_vacinacao_atrasada(vacinacao_em_dia: bool, dias_atraso: int) -> ScoreComponente:
    """Retorna pontuação pelo atraso de vacinação.

    vacinacao_em_dia=True → 0 pontos.
    1–30 dias de atraso → 20 pontos.
    >30 dias → 35 pontos.
    """
    if vacinacao_em_dia:
        return ScoreComponente(pontos=0, motivo="")

    if dias_atraso <= 30:
        return ScoreComponente(pontos=20, motivo=f"Vacinação atrasada {dias_atraso} dias")

    return ScoreComponente(pontos=35, motivo=f"Vacinação atrasada {dias_atraso} dias")


def score_consulta_pendente(ultima_consulta: date | None, hoje: date) -> ScoreComponente:
    """Retorna pontuação por consulta pendente.

    Sem registro ou > 30 dias desde a última consulta → 15 pontos.
    Caso contrário → 0 pontos.
    """
    if ultima_consulta is None:
        return ScoreComponente(pontos=15, motivo="Consulta sem registro")

    dias = (hoje - ultima_consulta).days
    if dias > 30:
        return ScoreComponente(pontos=15, motivo=f"Consulta pendente há {dias} dias")

    return ScoreComponente(pontos=0, motivo="")


def score_tempo_sem_visita(ultima_visita: date | None, hoje: date) -> ScoreComponente:
    """Retorna pontuação pelo tempo sem visita domiciliar.

    Sem visita ou > 60 dias → 25 pontos.
    31–60 dias → 10 pontos.
    <= 30 dias → 0 pontos.
    """
    if ultima_visita is None:
        return ScoreComponente(pontos=25, motivo="Sem visita registrada")

    dias = (hoje - ultima_visita).days

    if dias > 60:
        return ScoreComponente(pontos=25, motivo=f"Sem visita há {dias} dias")

    if dias >= 31:
        return ScoreComponente(pontos=10, motivo=f"Sem visita há {dias} dias")

    return ScoreComponente(pontos=0, motivo="")


def score_vulnerabilidade(situacao_vulnerabilidade: bool) -> ScoreComponente:
    """Retorna pontuação por situação de vulnerabilidade social.

    True → 15 pontos.
    False → 0 pontos.
    """
    if situacao_vulnerabilidade:
        return ScoreComponente(pontos=15, motivo="Situação de vulnerabilidade")

    return ScoreComponente(pontos=0, motivo="")


def calcular_score_total(
    vacinacao_em_dia: bool,
    dias_vacinacao_atraso: int,
    ultima_consulta: date | None,
    ultima_visita: date | None,
    situacao_vulnerabilidade: bool,
    hoje: date,
) -> ScoreTotal:
    """Calcula score total somando todos os componentes.

    Retorna ScoreTotal com o total de pontos e lista de motivos não-vazios.
    """
    componentes = [
        score_vacinacao_atrasada(vacinacao_em_dia, dias_vacinacao_atraso),
        score_consulta_pendente(ultima_consulta, hoje),
        score_tempo_sem_visita(ultima_visita, hoje),
        score_vulnerabilidade(situacao_vulnerabilidade),
    ]

    total = sum(c.pontos for c in componentes)
    motivos = [c.motivo for c in componentes if c.motivo]

    return ScoreTotal(total=total, motivos=motivos)


def determinar_grupo_risco(score: int) -> bool:
    """Classifica como grupo de risco se score >= SCORE_THRESHOLD_RISCO (40)."""
    return score >= SCORE_THRESHOLD_RISCO
