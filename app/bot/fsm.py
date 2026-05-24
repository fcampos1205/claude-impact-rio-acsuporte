"""FSM for the Ficha Primeira Infância interview.

Uses transitions.extensions.asyncio.AsyncMachine so all triggers
are awaitable. ignore_invalid_triggers=False ensures MachineError is
raised on illegal transitions (tested in test_bot_fsm.py).
"""
from enum import Enum

from transitions.extensions.asyncio import AsyncMachine


class EstadoFicha(str, Enum):
    S0_INICIO = "S0_INICIO"
    S1_SELECAO_CRIANCA = "S1_SELECAO_CRIANCA"
    S2_RESPONSAVEL_PRESENTE = "S2_RESPONSAVEL_PRESENTE"
    S3_VACINACAO_EM_DIA = "S3_VACINACAO_EM_DIA"
    S4_CONSULTAS_EM_DIA = "S4_CONSULTAS_EM_DIA"
    S5_ALEITAMENTO = "S5_ALEITAMENTO"
    S6_DESENVOLVIMENTO = "S6_DESENVOLVIMENTO"
    S7_OBSERVACOES_LIVRES = "S7_OBSERVACOES_LIVRES"
    S8_ENCERRAMENTO = "S8_ENCERRAMENTO"


class FichaFSM:
    states = [e.value for e in EstadoFicha]

    def __init__(self, estado_inicial: str = EstadoFicha.S0_INICIO.value):
        self.machine = AsyncMachine(
            model=self,
            states=self.states,
            initial=estado_inicial,
            ignore_invalid_triggers=False,  # raise MachineError on invalid trigger
        )
        self._add_transitions()

    def _add_transitions(self) -> None:
        m = self.machine
        # Main happy-path flow
        m.add_transition(
            "selecionar_crianca",
            EstadoFicha.S0_INICIO.value,
            EstadoFicha.S1_SELECAO_CRIANCA.value,
        )
        m.add_transition(
            "confirmar_responsavel",
            EstadoFicha.S1_SELECAO_CRIANCA.value,
            EstadoFicha.S2_RESPONSAVEL_PRESENTE.value,
        )
        # Alternate branch: responsible absent → skip directly to closure
        m.add_transition(
            "responsavel_ausente",
            EstadoFicha.S1_SELECAO_CRIANCA.value,
            EstadoFicha.S8_ENCERRAMENTO.value,
        )
        m.add_transition(
            "confirmar_vacinacao",
            EstadoFicha.S2_RESPONSAVEL_PRESENTE.value,
            EstadoFicha.S3_VACINACAO_EM_DIA.value,
        )
        m.add_transition(
            "confirmar_consulta",
            EstadoFicha.S3_VACINACAO_EM_DIA.value,
            EstadoFicha.S4_CONSULTAS_EM_DIA.value,
        )
        m.add_transition(
            "confirmar_aleitamento",
            EstadoFicha.S4_CONSULTAS_EM_DIA.value,
            EstadoFicha.S5_ALEITAMENTO.value,
        )
        m.add_transition(
            "confirmar_desenvolvimento",
            EstadoFicha.S5_ALEITAMENTO.value,
            EstadoFicha.S6_DESENVOLVIMENTO.value,
        )
        m.add_transition(
            "registrar_observacoes",
            EstadoFicha.S6_DESENVOLVIMENTO.value,
            EstadoFicha.S7_OBSERVACOES_LIVRES.value,
        )
        m.add_transition(
            "encerrar",
            EstadoFicha.S7_OBSERVACOES_LIVRES.value,
            EstadoFicha.S8_ENCERRAMENTO.value,
        )
        # Cancel from any state resets to S0 (including S8)
        m.add_transition("cancelar", "*", EstadoFicha.S0_INICIO.value)

    def serializar(self) -> str:
        """Return current state name as string for persistence."""
        return self.state  # type: ignore[attr-defined]

    @classmethod
    def restaurar(cls, estado_str: str) -> "FichaFSM":
        """Restore FSM from a previously serialized state string."""
        return cls(estado_inicial=estado_str)
