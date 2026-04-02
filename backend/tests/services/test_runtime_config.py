from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app.core import config


def test_database_settings_do_not_require_clerk_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://runtime-only")
    config.get_database_settings.cache_clear()

    assert config.get_database_url() == "postgresql+asyncpg://runtime-only"
    assert config.get_alembic_database_url() == "postgresql+asyncpg://runtime-only"

    config.get_database_settings.cache_clear()


def test_runtime_settings_load_backend_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    temp_directory = Path("backend/.tmp-test-db")
    temp_directory.mkdir(exist_ok=True)
    env_file = temp_directory / f"runtime-config-{uuid4().hex}.env"
    env_file.write_text(
        "\n".join(
            [
                "CLERK_SECRET_KEY=sk_test_env_file",
                "DATABASE_URL=postgresql+asyncpg://env-file-database",
                "TIMEZONE=Asia/Kolkata",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv("CLERK_SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setitem(config.Settings.model_config, "env_file", env_file)
    monkeypatch.setitem(config.DatabaseSettings.model_config, "env_file", env_file)
    config.get_settings.cache_clear()
    config.get_database_settings.cache_clear()

    settings = config.get_settings()

    assert settings.clerk_secret_key == "sk_test_env_file"
    assert settings.database_url == "postgresql+asyncpg://env-file-database"
    assert config.get_database_url() == "postgresql+asyncpg://env-file-database"

    config.get_settings.cache_clear()
    config.get_database_settings.cache_clear()
    env_file.unlink(missing_ok=True)
