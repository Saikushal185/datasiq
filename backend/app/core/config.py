from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/datisiq"
DEFAULT_LOCAL_DATABASE_PATH = Path(__file__).resolve().parents[2] / ".local" / "datisiq-dev.sqlite3"
DEFAULT_LOCAL_DATABASE_URL = f"sqlite+aiosqlite:///{DEFAULT_LOCAL_DATABASE_PATH.as_posix()}"
DEFAULT_TIMEZONE = "Asia/Kolkata"
DEFAULT_DEV_AUTH_TOKEN = "dev-demo-token"
DEFAULT_DEV_AUTH_CLERK_ID = "user_demo_local"
DEFAULT_DEV_AUTH_EMAIL = "test.user@datasiq.local"
BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    dev_auth_enabled: bool = False
    dev_seed_data: bool = False
    database_url: str = DEFAULT_DATABASE_URL
    alembic_database_url: str | None = None

    @model_validator(mode="after")
    def populate_alembic_database_url(self) -> Self:
        if (self.dev_auth_enabled or self.dev_seed_data) and self.database_url == DEFAULT_DATABASE_URL:
            self.database_url = DEFAULT_LOCAL_DATABASE_URL
        if self.alembic_database_url is None:
            self.alembic_database_url = self.database_url
        return self


def get_database_url() -> str:
    return get_database_settings().database_url


def get_alembic_database_url() -> str:
    return get_database_settings().alembic_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    clerk_secret_key: str | None = None
    dev_auth_enabled: bool = False
    dev_seed_data: bool = False
    dev_auth_token: str = DEFAULT_DEV_AUTH_TOKEN
    dev_auth_clerk_id: str = DEFAULT_DEV_AUTH_CLERK_ID
    dev_auth_email: str = DEFAULT_DEV_AUTH_EMAIL
    database_url: str = DEFAULT_DATABASE_URL
    alembic_database_url: str | None = None
    upstash_redis_rest_url: str | None = None
    upstash_redis_rest_token: str | None = None
    anthropic_api_key: str | None = None
    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = 0.1
    admin_secret: str | None = None
    timezone: str = DEFAULT_TIMEZONE

    @model_validator(mode="after")
    def populate_alembic_database_url(self) -> Self:
        if (self.dev_auth_enabled or self.dev_seed_data) and self.database_url == DEFAULT_DATABASE_URL:
            self.database_url = DEFAULT_LOCAL_DATABASE_URL
        if self.alembic_database_url is None:
            self.alembic_database_url = self.database_url
        if not self.dev_auth_enabled and not self.clerk_secret_key:
            raise ValueError("CLERK_SECRET_KEY is required unless DEV_AUTH_ENABLED=true.")
        return self


@lru_cache
def get_database_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
