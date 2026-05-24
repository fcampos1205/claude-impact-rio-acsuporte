"""Testes do ClaudeClient — Fase 4. 3 testes."""
from unittest.mock import MagicMock

import pytest


async def test_cliente_retry_3_vezes_em_500(monkeypatch):
    """Mock httpx retornar 500 três vezes → ClaudeClient tenta 3x antes de desistir."""
    from app.llm.cliente import ClaudeClient, LLMUnavailableError

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        raise Exception("500 Server Error")

    client = ClaudeClient()
    monkeypatch.setattr(client._client.messages, "create", fake_create)

    with pytest.raises(LLMUnavailableError):
        await client.chamar(system="sys", user="user", max_retries=3, backoff_base=0.01)

    assert call_count == 3


async def test_cliente_levanta_unavailable_apos_max_retries(monkeypatch):
    from app.llm.cliente import ClaudeClient, LLMUnavailableError

    async def fake_create(**kwargs):
        raise Exception("API Error")

    client = ClaudeClient()
    monkeypatch.setattr(client._client.messages, "create", fake_create)

    with pytest.raises(LLMUnavailableError):
        await client.chamar(system="sys", user="user", max_retries=2, backoff_base=0.01)


async def test_cliente_sucesso_em_segunda_tentativa(monkeypatch):
    """Primeira falha, segunda OK → retorna texto da segunda."""
    from app.llm.cliente import ClaudeClient

    call_count = 0

    async def fake_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("First attempt fails")
        response = MagicMock()
        response.content = [MagicMock(text="Success on 2nd try")]
        return response

    client = ClaudeClient()
    monkeypatch.setattr(client._client.messages, "create", fake_create)

    result = await client.chamar(system="sys", user="user", max_retries=3, backoff_base=0.01)
    assert result == "Success on 2nd try"
    assert call_count == 2
