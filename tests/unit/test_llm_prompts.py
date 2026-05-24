"""Testes de prompts e formatação — Fase 4. 6 testes.

G7 — texto dinâmico de pendência. LGPD — nunca nome completo no prompt.
"""
import uuid
from unittest.mock import MagicMock


def test_motivo_pendencia_1_dia():
    from app.llm.prompts import motivo_pendencia

    assert motivo_pendencia(1) == "PENDENTE DO DIA ANTERIOR"


def test_motivo_pendencia_2_dias():
    from app.llm.prompts import motivo_pendencia

    assert "2 DIAS" in motivo_pendencia(2)


def test_motivo_pendencia_5_dias_com_override():
    from app.llm.prompts import motivo_pendencia

    texto = motivo_pendencia(5)
    assert "5" in texto
    assert "OVERRIDE" in texto


def test_montar_prompt_inclui_todos_candidatos():
    """Quantidade de itens na lista == quantidade de linhas no prompt."""
    from app.llm.prompts import montar_prompt_usuario

    item1 = MagicMock()
    item1.crianca_ref = uuid.uuid4()
    item1.grupo_risco = False
    item1.eh_pendencia = False
    item1.motivos = ["Vacinação atrasada"]
    item1.score = 30
    item1.dias_pendente = 0

    item2 = MagicMock()
    item2.crianca_ref = uuid.uuid4()
    item2.grupo_risco = False
    item2.eh_pendencia = False
    item2.motivos = []
    item2.score = 20
    item2.dias_pendente = 0

    item3 = MagicMock()
    item3.crianca_ref = uuid.uuid4()
    item3.grupo_risco = True
    item3.eh_pendencia = True
    item3.motivos = []
    item3.score = 50
    item3.dias_pendente = 2

    lista = MagicMock()
    lista.itens = [item1, item2, item3]

    prompt = montar_prompt_usuario(lista)
    # 3 items should produce 3 numbered lines
    lines_with_numbers = [ln for ln in prompt.split("\n") if ln.strip() and ln.strip()[0].isdigit()]
    assert len(lines_with_numbers) == 3


def test_system_prompt_contem_instrucoes_lgpd():
    """SYSTEM_PROMPT_LISTA deve mencionar nunca inventar dados e usar iniciais."""
    from app.llm.prompts import SYSTEM_PROMPT_LISTA

    assert "iniciais" in SYSTEM_PROMPT_LISTA.lower() or "inventar" in SYSTEM_PROMPT_LISTA.lower()


def test_prompt_nao_vaza_dados_pessoais_completos():
    """LGPD — prompt enviado ao Claude não tem UUID completo da criança."""
    from app.llm.prompts import montar_prompt_usuario

    item = MagicMock()
    item.crianca_ref = uuid.uuid4()
    item.grupo_risco = False
    item.eh_pendencia = False
    item.motivos = ["Vacinação atrasada"]
    item.score = 30
    item.dias_pendente = 0

    lista = MagicMock()
    lista.itens = [item]

    prompt = montar_prompt_usuario(lista)
    # Full UUID (36 chars) must NOT appear in the prompt
    assert str(item.crianca_ref) not in prompt
