"""Testes da Fase 0 — config (pydantic-settings).

Todos os testes começam com @pytest.mark.skip. Remova o skip quando for implementar
o comportamento correspondente, seguindo o workflow TDD (Red → Green → Refactor)
descrito em `.claude/skills/acs-tdd-helper/SKILL.md`.
"""
import pytest


def test_config_carrega_de_env(monkeypatch):
    """app.config.Settings deve carregar variáveis do .env corretamente."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h:5432/db")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-token")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_URL", "https://test.example.com/webhook")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    monkeypatch.setenv("ENCRYPTION_KEY", "fake-encryption-key")
    monkeypatch.setenv("TELEGRAM_CHAT_ID_SALT", "fake-salt")

    from app.config import Settings
    settings = Settings()
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.telegram_bot_token == "fake-token"


def test_config_falha_sem_database_url(monkeypatch):
    """Settings sem DATABASE_URL deve levantar ValidationError."""
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_config_usa_defaults_quando_aplicavel():
    """Settings deve aplicar defaults para campos opcionais."""
    from app.config import Settings
    # Garantir env mínima
    s = Settings()
    assert s.anthropic_model == "claude-haiku-4-5"
    assert s.batch_manha_hora == 5
    assert s.batch_noite_hora == 22
    assert s.limite_lista_diaria == 15
    assert s.ciclo_deduplicacao_dias == 30
    assert s.retencao_chat_dias == 90
    assert s.score_threshold_risco == 40


def test_config_valida_formato_database_url(monkeypatch):
    """URL com formato inválido deve falhar."""
    monkeypatch.setenv("DATABASE_URL", "isso_nao_e_uma_url")
    from pydantic import ValidationError
    from app.config import Settings

    with pytest.raises((ValidationError, ValueError)):
        Settings()
