"""Testes do webhook Telegram — Fase 5. 4 testes."""
from unittest.mock import AsyncMock, patch


def _make_valid_payload(chat_id: int = 12345678) -> dict:
    return {
        "message": {
            "message_id": 1,
            "chat": {"id": chat_id, "type": "private"},
            "text": "hello",
            "date": 1716547200,
            "from": {"id": chat_id, "is_bot": False, "first_name": "Test"},
        }
    }


async def test_webhook_recebe_payload_telegram_valido(db_session, seed_minimal):
    """Webhook returns 200 for a structurally valid Telegram payload."""
    from fastapi.testclient import TestClient

    from app.main import app

    # Patch resolver_acs to return None (unknown ACS) — avoids real DB call from TestClient
    with patch("app.bot.webhook.resolver_acs", new_callable=AsyncMock) as mock_resolver:
        mock_resolver.return_value = None
        # Patch SessionLocal so the webhook doesn't try to open a real DB session
        with patch("app.bot.webhook.SessionLocal") as mock_sl:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_sl.return_value = mock_cm

            client = TestClient(app, raise_server_exceptions=True)
            response = client.post("/telegram/webhook", json=_make_valid_payload())

    assert response.status_code == 200


async def test_webhook_recusa_payload_invalido(db_session):
    """Webhook returns 400 for a payload missing message/callback_query keys."""
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app, raise_server_exceptions=True)
    response = client.post("/telegram/webhook", json={"garbage": "data"})
    assert response.status_code == 400


async def test_webhook_resolve_acs_por_chat_id(db_session, seed_minimal):
    """When chat_id matches a known ACS, webhook returns ok=True (no status field)."""
    from app.models.profissional import Profissional
    from fastapi.testclient import TestClient

    from app.main import app

    # Simulate a known ACS being returned from resolver_acs
    fake_acs = Profissional(
        nome="ACS Known",
        telegram_chat_id_hash="some_hash",
        equipe_id=seed_minimal["equipe"].id,
        ativo=True,
    )

    with patch("app.bot.webhook.resolver_acs", new_callable=AsyncMock) as mock_resolver:
        mock_resolver.return_value = fake_acs
        with patch("app.bot.webhook.SessionLocal") as mock_sl:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_sl.return_value = mock_cm

            client = TestClient(app, raise_server_exceptions=True)
            response = client.post("/telegram/webhook", json=_make_valid_payload(chat_id=99999999))

    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    # Known ACS → no "unknown_acs" status
    assert data.get("status") != "unknown_acs"


async def test_webhook_rejeita_chat_id_desconhecido(db_session):
    """Unknown chat_id returns ok=True but status=unknown_acs."""
    from fastapi.testclient import TestClient

    from app.main import app

    # resolver_acs returns None → unknown ACS path
    with patch("app.bot.webhook.resolver_acs", new_callable=AsyncMock) as mock_resolver:
        mock_resolver.return_value = None
        with patch("app.bot.webhook.SessionLocal") as mock_sl:
            mock_cm = AsyncMock()
            mock_cm.__aenter__ = AsyncMock(return_value=AsyncMock())
            mock_cm.__aexit__ = AsyncMock(return_value=False)
            mock_sl.return_value = mock_cm

            client = TestClient(app, raise_server_exceptions=True)
            response = client.post("/telegram/webhook", json=_make_valid_payload(chat_id=-1))

    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "unknown_acs"
