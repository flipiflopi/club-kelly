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

    # Twitter / X via GetXAPI (getxapi.com)
    getxapi_key: str = ""        # GetXAPI account key (Bearer token)
    twitter_auth_token: str = "" # X session cookie: auth_token
    twitter_ct0: str = ""        # X session cookie: ct0 (CSRF token)
    twitter_twid: str = ""       # X session cookie: twid (optional)


@lru_cache
def get_settings() -> Settings:
    return Settings()
