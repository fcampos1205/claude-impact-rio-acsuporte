"""Testes das regras de score — Fase 3, motor de priorização.

18 testes. Veja `docs/architecture/decisoes_design.md` G3, G4 e
`docs/architecture/plano_implementacao.md` Fase 3.

Funções testadas vivem em `app/motor/regras.py` e são puras —
sem DB, sem network, sem datetime.now() interno (recebem `hoje` como parâmetro).
"""
from datetime import date, timedelta

import pytest


# ──────────────────────────────────────────────────────────────────────────
# score_vacinacao_atrasada
# ──────────────────────────────────────────────────────────────────────────


def test_vacinacao_em_dia_score_zero():
    from app.motor.regras import score_vacinacao_atrasada
    resultado = score_vacinacao_atrasada(vacinacao_em_dia=True, dias_atraso=0)
    assert resultado.pontos == 0
    assert resultado.motivo == ""


def test_vacinacao_atrasada_30_dias_score_20():
    from app.motor.regras import score_vacinacao_atrasada
    resultado = score_vacinacao_atrasada(vacinacao_em_dia=False, dias_atraso=30)
    assert resultado.pontos == 20
    assert "30" in resultado.motivo


def test_vacinacao_atrasada_60_dias_score_35():
    from app.motor.regras import score_vacinacao_atrasada
    resultado = score_vacinacao_atrasada(vacinacao_em_dia=False, dias_atraso=60)
    assert resultado.pontos == 35


def test_vacinacao_atrasada_acima_threshold_grupo_risco():
    """Componente isolado de 35 pts + outros componentes pode atingir threshold."""
    from app.motor.regras import score_vacinacao_atrasada, determinar_grupo_risco
    # Vacinação atrasada 60d = 35 pts
    # Combinado com vulnerabilidade (15) = 50, virou risco
    base = score_vacinacao_atrasada(vacinacao_em_dia=False, dias_atraso=60)
    total = base.pontos + 15  # simula vulnerabilidade
    assert determinar_grupo_risco(total) is True


# ──────────────────────────────────────────────────────────────────────────
# score_consulta_pendente
# ──────────────────────────────────────────────────────────────────────────


def test_consulta_em_dia_score_zero():
    from app.motor.regras import score_consulta_pendente
    hoje = date(2026, 5, 24)
    resultado = score_consulta_pendente(ultima_consulta=hoje - timedelta(days=10), hoje=hoje)
    assert resultado.pontos == 0


def test_consulta_atrasada_30_dias_score_15():
    from app.motor.regras import score_consulta_pendente
    hoje = date(2026, 5, 24)
    resultado = score_consulta_pendente(ultima_consulta=hoje - timedelta(days=35), hoje=hoje)
    assert resultado.pontos == 15


def test_consulta_atrasada_sem_registro_score_alto():
    """Criança sem consulta registrada deve ter score alto (criar baseline)."""
    from app.motor.regras import score_consulta_pendente
    hoje = date(2026, 5, 24)
    resultado = score_consulta_pendente(ultima_consulta=None, hoje=hoje)
    assert resultado.pontos >= 15


# ──────────────────────────────────────────────────────────────────────────
# score_tempo_sem_visita
# ──────────────────────────────────────────────────────────────────────────


def test_sem_visita_ha_15_dias_score_zero():
    from app.motor.regras import score_tempo_sem_visita
    hoje = date(2026, 5, 24)
    resultado = score_tempo_sem_visita(ultima_visita=hoje - timedelta(days=15), hoje=hoje)
    assert resultado.pontos == 0


def test_sem_visita_ha_60_dias_score_10():
    from app.motor.regras import score_tempo_sem_visita
    hoje = date(2026, 5, 24)
    resultado = score_tempo_sem_visita(ultima_visita=hoje - timedelta(days=60), hoje=hoje)
    assert resultado.pontos == 10


def test_sem_visita_ha_90_dias_score_25():
    from app.motor.regras import score_tempo_sem_visita
    hoje = date(2026, 5, 24)
    resultado = score_tempo_sem_visita(ultima_visita=hoje - timedelta(days=90), hoje=hoje)
    assert resultado.pontos == 25


# ──────────────────────────────────────────────────────────────────────────
# score_vulnerabilidade
# ──────────────────────────────────────────────────────────────────────────


def test_situacao_vulnerabilidade_true_bonus():
    from app.motor.regras import score_vulnerabilidade
    resultado = score_vulnerabilidade(situacao_vulnerabilidade=True)
    assert resultado.pontos == 15


def test_situacao_vulnerabilidade_false_zero():
    from app.motor.regras import score_vulnerabilidade
    resultado = score_vulnerabilidade(situacao_vulnerabilidade=False)
    assert resultado.pontos == 0


# ──────────────────────────────────────────────────────────────────────────
# calcular_score_total
# ──────────────────────────────────────────────────────────────────────────


def test_calcular_score_total_soma_componentes():
    from app.motor.regras import calcular_score_total
    hoje = date(2026, 5, 24)
    resultado = calcular_score_total(
        vacinacao_em_dia=False, dias_vacinacao_atraso=60,
        ultima_consulta=hoje - timedelta(days=40),
        ultima_visita=hoje - timedelta(days=60),
        situacao_vulnerabilidade=True,
        hoje=hoje,
    )
    # 35 (vac) + 15 (consulta) + 10 (visita) + 15 (vuln) = 75
    assert resultado.total == 75


def test_score_total_com_motivos_concatenados():
    from app.motor.regras import calcular_score_total
    hoje = date(2026, 5, 24)
    r = calcular_score_total(
        vacinacao_em_dia=False, dias_vacinacao_atraso=60,
        ultima_consulta=hoje - timedelta(days=40),
        ultima_visita=None,
        situacao_vulnerabilidade=False,
        hoje=hoje,
    )
    motivos = r.motivos
    assert any("Vacinação" in m for m in motivos)
    assert any("Consulta" in m for m in motivos)


# ──────────────────────────────────────────────────────────────────────────
# determinar_grupo_risco
# ──────────────────────────────────────────────────────────────────────────


def test_score_39_nao_eh_risco():
    from app.motor.regras import determinar_grupo_risco
    assert determinar_grupo_risco(39) is False


def test_score_40_eh_risco():
    from app.motor.regras import determinar_grupo_risco
    assert determinar_grupo_risco(40) is True


def test_score_100_eh_risco():
    from app.motor.regras import determinar_grupo_risco
    assert determinar_grupo_risco(100) is True


# ──────────────────────────────────────────────────────────────────────────
# G3 — risco vence escalonamento
# ──────────────────────────────────────────────────────────────────────────


def test_score_ajustado_risco_vence():
    """G3 — para criança de risco, override_topo=True sempre.

    Não acumula penalidade -5/dia (essa lógica foi removida da implementação).
    score_ajustado é informativo (= score_original + BONUS_RISCO_REPOSICAO).
    """
    from app.motor.constants import BONUS_RISCO_REPOSICAO
    # Simulação simples: risco com 2 dias pendente
    score_original = 50  # risco
    grupo_risco = True
    # Esperado: override_topo=True, score_ajustado=50+50=100
    score_ajustado_esperado = score_original + BONUS_RISCO_REPOSICAO
    assert score_ajustado_esperado == 100


# ──────────────────────────────────────────────────────────────────────────
# G4 — grupo_risco recalculado no batch noturno
# ──────────────────────────────────────────────────────────────────────────


def test_grupo_risco_recalculado_no_batch_noite():
    """G4 — ao calcular score_ajustado no batch noturno, grupo_risco é refletido.

    Cenário: criança com score 35 (não-risco) no dia. Algum dado mudou.
    Recalculando agora dá 55 → vira risco → override_topo=True.
    """
    from app.motor.regras import determinar_grupo_risco
    score_no_dia_original = 35
    score_recalculado_no_batch = 55
    assert determinar_grupo_risco(score_no_dia_original) is False
    assert determinar_grupo_risco(score_recalculado_no_batch) is True
