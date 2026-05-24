"""Testes do fallback Jinja2 — Fase 4. G15 — quando Claude API falha. 5 testes."""
import uuid
from datetime import date
from unittest.mock import MagicMock


def _make_item(
    motivos: list[str] | None = None,
    grupo_risco: bool = False,
    eh_pendencia: bool = False,
    dias_pendente: int = 0,
) -> MagicMock:
    item = MagicMock()
    item.crianca_ref = uuid.uuid4()
    item.grupo_risco = grupo_risco
    item.eh_pendencia = eh_pendencia
    item.motivos = motivos or []
    item.score = 30
    item.dias_pendente = dias_pendente
    return item


def _make_lista(itens: list[MagicMock]) -> MagicMock:
    lista = MagicMock()
    lista.itens = itens
    lista.data = date(2026, 5, 24)
    return lista


def test_fallback_gera_mensagem_valida():
    """formatar_lista_fallback retorna string não-vazia."""
    from app.llm.fallback import formatar_lista_fallback

    lista = _make_lista([_make_item(motivos=["Vacinação atrasada"])])
    resultado = formatar_lista_fallback(lista)
    assert isinstance(resultado, str)
    assert len(resultado) > 0


def test_fallback_formato_telegram_markdown():
    """Saída tem marcadores Markdown válidos do Telegram (*, _, etc)."""
    from app.llm.fallback import formatar_lista_fallback

    lista = _make_lista([_make_item(motivos=["Vacinação atrasada"])])
    resultado = formatar_lista_fallback(lista)
    # Template uses * for bold and _ for italic
    assert "*" in resultado or "_" in resultado


def test_fallback_inclui_motivo_de_cada_crianca():
    """Cada item da lista tem seu motivo no texto final."""
    from app.llm.fallback import formatar_lista_fallback

    motivo_esperado = "Vacinação atrasada"
    lista = _make_lista([_make_item(motivos=[motivo_esperado])])
    resultado = formatar_lista_fallback(lista)
    assert motivo_esperado in resultado


def test_fallback_quando_lista_vazia():
    """Lista vazia retorna mensagem informativa, não erro."""
    from app.llm.fallback import formatar_lista_fallback

    # Test with None
    resultado = formatar_lista_fallback(None)
    assert isinstance(resultado, str)
    assert len(resultado) > 0

    # Test with object having empty itens
    lista = _make_lista([])
    resultado = formatar_lista_fallback(lista)
    assert isinstance(resultado, str)
    assert len(resultado) > 0


async def test_fallback_quando_claude_api_offline(db_session, mock_claude_api_falha):
    """gerar_mensagem_telegram cai pro fallback quando ClaudeClient falha."""
    from app.llm.gerador_lista import gerar_mensagem_telegram

    lista = _make_lista([])

    resultado = await gerar_mensagem_telegram(lista)
    assert isinstance(resultado, str)
    assert len(resultado) > 0
