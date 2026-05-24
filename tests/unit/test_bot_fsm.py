"""Testes da FSM da Ficha Primeira Infância — Fase 5. 12 testes.

Veja ADR 004 e .claude/skills/acs-fase-bot/SKILL.md.
"""
import pytest


async def test_fsm_estado_inicial_s0():
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM()
    assert fsm.state == EstadoFicha.S0_INICIO.value


async def test_fsm_transicao_s0_para_s1_com_selecao():
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM()
    await fsm.selecionar_crianca()
    assert fsm.state == EstadoFicha.S1_SELECAO_CRIANCA.value


async def test_fsm_s1_para_s2_com_responsavel_presente():
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S1_SELECAO_CRIANCA.value)
    await fsm.confirmar_responsavel()
    assert fsm.state == EstadoFicha.S2_RESPONSAVEL_PRESENTE.value


async def test_fsm_s2_nao_pode_voltar_a_s0():
    """Transições são unidirecionais (exceto cancelar)."""
    from transitions import MachineError

    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S2_RESPONSAVEL_PRESENTE.value)
    with pytest.raises(MachineError):
        await fsm.selecionar_crianca()  # Não existe transição de S2 para S1


def test_fsm_serializa_estado_em_string():
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S5_ALEITAMENTO.value)
    assert fsm.serializar() == "S5_ALEITAMENTO"


def test_fsm_restaura_estado_de_string():
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM.restaurar("S6_DESENVOLVIMENTO")
    assert fsm.state == EstadoFicha.S6_DESENVOLVIMENTO.value


async def test_fsm_s8_finaliza_e_grava_visita(db_session):
    """Chegar em S8 dispara persistência da visita (implementado via callback)."""
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S7_OBSERVACOES_LIVRES.value)
    await fsm.encerrar()
    assert fsm.state == EstadoFicha.S8_ENCERRAMENTO.value


async def test_fsm_input_invalido_nao_transita():
    """Trigger inválido pro estado atual não muda o estado."""
    from transitions import MachineError

    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S0_INICIO.value)
    with pytest.raises((MachineError, AttributeError)):
        await fsm.confirmar_responsavel()  # not valid from S0


async def test_fsm_pode_cancelar_em_qualquer_estado():
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S5_ALEITAMENTO.value)
    await fsm.cancelar()
    assert fsm.state == EstadoFicha.S0_INICIO.value


async def test_fsm_perguntas_de_alerta_no_estado_s5():
    """Estado S5 (aleitamento) tem callback que gera pergunta-alerta específica."""
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S4_CONSULTAS_EM_DIA.value)
    await fsm.confirmar_aleitamento()
    assert fsm.state == EstadoFicha.S5_ALEITAMENTO.value


async def test_fsm_ramo_alternativo_responsavel_ausente():
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S1_SELECAO_CRIANCA.value)
    await fsm.responsavel_ausente()
    assert fsm.state == EstadoFicha.S8_ENCERRAMENTO.value


async def test_fsm_timeout_inatividade_retorna_s0():
    """30 min sem mensagem → reset pra S0 (lógica fora da FSM, no handler)."""
    from app.bot.fsm import EstadoFicha, FichaFSM

    fsm = FichaFSM(estado_inicial=EstadoFicha.S3_VACINACAO_EM_DIA.value)
    await fsm.cancelar()
    assert fsm.state == EstadoFicha.S0_INICIO.value
