from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "postgresql://football:changeme@localhost:5432/football_prediction"

    # App
    debug: bool = False
    log_level: str = "INFO"
    secret_key: str = "change-me"

    # Paper trading
    initial_bankroll: float = 1000.0

    # External APIs
    the_odds_api_key: str = ""
    anthropic_api_key: str = ""
    github_token: str = ""

    # n8n webhooks
    webhook_api_key: str = ""   # empty = no auth required

    # Telegram notifications
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""  # channel @name or numeric group/chat ID


@lru_cache
def get_settings() -> Settings:
    return Settings()
