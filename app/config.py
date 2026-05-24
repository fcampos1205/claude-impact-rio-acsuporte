from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Required fields
    database_url: str
    telegram_bot_token: str
    telegram_webhook_url: str
    anthropic_api_key: str
    encryption_key: str
    telegram_chat_id_salt: str

    # Optional with defaults
    anthropic_model: str = "claude-haiku-4-5"
    batch_manha_hora: int = 5
    batch_noite_hora: int = 22
    limite_lista_diaria: int = 15
    ciclo_deduplicacao_dias: int = 30
    retencao_chat_dias: int = 90
    score_threshold_risco: int = 40
    log_level: str = "INFO"
    env: str = "dev"

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must start with postgresql+asyncpg://")
        return v


settings = Settings()
