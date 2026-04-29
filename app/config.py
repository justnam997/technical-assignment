"""Application settings.

Why pydantic-settings: env vars are typed and validated at boot, so a
mistyped DATABASE_URL fails fast at startup instead of at first query.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- DB ---
    database_url: str = "postgresql+asyncpg://hr:hr@localhost:5432/hr"

    # --- Rate limit (per principal per org) ---
    rate_limit_per_second: int = 10
    rate_limit_burst: int = 20

    # --- API safety caps ---
    max_page_size: int = 100
    default_page_size: int = 50

    # --- Logging ---
    log_level: str = "INFO"


settings = Settings()
