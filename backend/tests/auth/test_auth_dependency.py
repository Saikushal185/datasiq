from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
import httpx
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql.dml import Insert
from starlette.requests import Request

from backend.app.core import auth
from backend.app.core.config import Settings, get_settings
from backend.app.models.db import Base, User


def _b64url_uint(value: int) -> str:
    byte_length = max(1, (value.bit_length() + 7) // 8)
    encoded = base64.urlsafe_b64encode(value.to_bytes(byte_length, "big"))
    return encoded.rstrip(b"=").decode("ascii")


def _build_request(*, authorization: str | None = None, session_cookie: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode("utf-8")))
    if session_cookie is not None:
        headers.append((b"cookie", f"__session={session_cookie}".encode("utf-8")))

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "https",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


def _build_settings() -> Settings:
    return Settings(clerk_secret_key="sk_test_123")


async def _build_session_factory() -> tuple[async_sessionmaker[AsyncSession], object, Path]:
    temp_directory = Path("backend/.tmp-test-db")
    temp_directory.mkdir(exist_ok=True)
    database_path = temp_directory / f"auth-dependency-{uuid4().hex}.sqlite3"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False), engine, database_path


def _build_signing_material() -> tuple[bytes, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_numbers = private_key.public_key().public_numbers()
    jwks = {
        "keys": [
            {
                "kid": "test-key",
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "n": _b64url_uint(public_numbers.n),
                "e": _b64url_uint(public_numbers.e),
            }
        ]
    }
    return private_key_pem, jwks


def _build_session_token(private_key_pem: bytes, *, claims: dict[str, object] | None = None, kid: str = "test-key") -> str:
    payload = {
        "iss": "https://example.clerk.accounts.dev",
        "sid": "sess_123",
        "sub": "user_verified_123",
        "v": 2,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "nbf": datetime.now(timezone.utc) - timedelta(seconds=5),
        "iat": datetime.now(timezone.utc),
    }
    if claims is not None:
        payload.update(claims)

    return jwt.encode(
        payload,
        private_key_pem,
        algorithm="RS256",
        headers={"kid": kid},
    )


@pytest.mark.asyncio
async def test_verify_clerk_session_token_extracts_verified_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings()
    private_key_pem, jwks = _build_signing_material()
    token = _build_session_token(private_key_pem)

    async def fake_fetch_jwks(_: Settings) -> dict[str, object]:
        return jwks

    monkeypatch.setattr(auth, "fetch_clerk_jwks", fake_fetch_jwks)

    claims = await auth.verify_clerk_session_token(token, settings, origin=None)

    assert claims["sub"] == "user_verified_123"


@pytest.mark.asyncio
async def test_verify_clerk_session_token_refreshes_jwks_once_on_key_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings()
    private_key_pem, refreshed_jwks = _build_signing_material()
    initial_jwks = {
        "keys": [
            {
                "kid": "stale-key",
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "n": refreshed_jwks["keys"][0]["n"],
                "e": refreshed_jwks["keys"][0]["e"],
            }
        ]
    }
    token = _build_session_token(private_key_pem)
    calls = 0

    async def fake_fetch_jwks(_: Settings, *, force_refresh: bool = False) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return refreshed_jwks if force_refresh else initial_jwks

    monkeypatch.setattr(auth, "fetch_clerk_jwks", fake_fetch_jwks)

    claims = await auth.verify_clerk_session_token(token, settings, origin=None)

    assert claims["sub"] == "user_verified_123"
    assert calls == 2


@pytest.mark.asyncio
async def test_fetch_clerk_jwks_returns_controlled_error_on_transport_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings()
    auth._clear_jwks_cache()

    class FailingClient:
        async def __aenter__(self) -> "FailingClient":
            return self

        async def __aexit__(self, exc_type, exc, tb) -> None:
            return None

        async def get(self, *_args, **_kwargs):
            raise httpx.ConnectError("boom")

    monkeypatch.setattr(auth.httpx, "AsyncClient", lambda **_kwargs: FailingClient())

    with pytest.raises(HTTPException) as exc_info:
        await auth.fetch_clerk_jwks(settings)

    assert exc_info.value.status_code == 503


@pytest.mark.asyncio
async def test_verify_clerk_session_token_rejects_incomplete_session_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings()
    private_key_pem, jwks = _build_signing_material()
    token = _build_session_token(
        private_key_pem,
        claims={"sid": None, "iss": None, "v": None},
    )

    async def fake_fetch_jwks(_: Settings, *, force_refresh: bool = False) -> dict[str, object]:
        return jwks

    monkeypatch.setattr(auth, "fetch_clerk_jwks", fake_fetch_jwks)

    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_clerk_session_token(token, settings, origin=None)

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_verify_clerk_session_token_rejects_mismatched_authorized_party(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _build_settings()
    private_key_pem, jwks = _build_signing_material()
    token = _build_session_token(private_key_pem, claims={"azp": "https://other.example.com"})

    async def fake_fetch_jwks(_: Settings, *, force_refresh: bool = False) -> dict[str, object]:
        return jwks

    monkeypatch.setattr(auth, "fetch_clerk_jwks", fake_fetch_jwks)

    with pytest.raises(HTTPException) as exc_info:
        await auth.verify_clerk_session_token(token, settings, origin="https://app.example.com")

    assert exc_info.value.status_code == 401


def test_get_settings_requires_only_clerk_secret_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_from_env")
    monkeypatch.delenv("CLERK_JWKS_URL", raising=False)
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    monkeypatch.delenv("CLERK_AUDIENCE", raising=False)
    monkeypatch.delenv("CLERK_AUTHORIZED_PARTIES", raising=False)
    get_settings.cache_clear()

    settings = get_settings()

    get_settings.cache_clear()
    assert settings == Settings(clerk_secret_key="sk_test_from_env")


@pytest.mark.asyncio
async def test_get_current_user_uses_race_safe_upsert_pattern(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _build_settings()
    session_factory, engine, database_path = await _build_session_factory()

    async def fake_verify(_: str, __: Settings, *, origin: str | None) -> dict[str, object]:
        return {"sub": "user_race_123", "email": "winner@example.com"}

    monkeypatch.setattr(auth, "verify_clerk_session_token", fake_verify)

    class BootstrapSessionFactory:
        def __init__(self, inner_factory: async_sessionmaker[AsyncSession]) -> None:
            self._inner_factory = inner_factory
            self.raced = False

        def __call__(self) -> AsyncSession:
            session = self._inner_factory()
            original_execute = session.execute

            async def execute_with_race(statement, *args, **kwargs):
                if isinstance(statement, Insert) and not self.raced:
                    self.raced = True
                    async with self._inner_factory() as competing_session:
                        competing_session.add(User(clerk_id="user_race_123", email="winner@example.com"))
                        await competing_session.commit()
                return await original_execute(statement, *args, **kwargs)

            session.execute = execute_with_race  # type: ignore[method-assign]
            return session

    bootstrap_factory = BootstrapSessionFactory(session_factory)
    monkeypatch.setattr(auth, "AsyncSessionLocal", bootstrap_factory)

    async with session_factory() as session:
        async def request_commit_should_not_be_called() -> None:
            raise AssertionError("request session commit should not be used in auth dependency")

        monkeypatch.setattr(session, "commit", request_commit_should_not_be_called)

        user = await auth.get_current_user(
            _build_request(session_cookie="session-cookie-token"),
            session,
            settings,
        )

        persisted_users = (await session.scalars(select(User).where(User.clerk_id == "user_race_123"))).all()

    await engine.dispose()
    database_path.unlink(missing_ok=True)

    assert bootstrap_factory.raced is True
    assert user.clerk_id == "user_race_123"
    assert user.email == "winner@example.com"
    assert len(persisted_users) == 1
