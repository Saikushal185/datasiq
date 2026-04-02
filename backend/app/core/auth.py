from __future__ import annotations

import asyncio
from json import JSONDecodeError
import secrets
import time
from typing import Any

import httpx
from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import Settings, get_settings
from backend.app.core.database import AsyncSessionLocal, get_db_session
from backend.app.models.db import User


CLERK_BACKEND_JWKS_URL = "https://api.clerk.com/v1/jwks"
CLERK_SESSION_COOKIE = "__session"
JWKS_CACHE_TTL_SECONDS = 300

_jwks_cache: dict[str, Any] = {"payload": None, "expires_at": 0.0}
_jwks_cache_lock = asyncio.Lock()


def _unauthorized(detail: str = "Authentication required.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def _service_unavailable(detail: str = "Authentication provider is temporarily unavailable.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)


def _bad_gateway(detail: str = "Authentication provider returned an invalid response.") -> HTTPException:
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)


def require_admin_secret(
    x_admin_secret: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    configured_secret = settings.admin_secret
    if not configured_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="ADMIN_SECRET is not configured.",
        )
    if x_admin_secret is None or not secrets.compare_digest(x_admin_secret, configured_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")


def _extract_session_token(request: Request) -> str:
    authorization_header = request.headers.get("authorization", "").strip()
    if authorization_header:
        scheme, _, token = authorization_header.partition(" ")
        if scheme.lower() == "bearer" and token:
            return token.strip()

    cookie_token = request.cookies.get(CLERK_SESSION_COOKIE, "").strip()
    if cookie_token:
        return cookie_token

    raise _unauthorized()


def _extract_dev_auth_token(request: Request) -> str | None:
    authorization_header = request.headers.get("authorization", "").strip()
    if not authorization_header:
        return None

    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None

    return token.strip()


def _clear_jwks_cache() -> None:
    _jwks_cache["payload"] = None
    _jwks_cache["expires_at"] = 0.0


def _read_cached_jwks(*, now: float) -> dict[str, Any] | None:
    payload = _jwks_cache["payload"]
    expires_at = _jwks_cache["expires_at"]
    if isinstance(payload, dict) and isinstance(expires_at, float) and expires_at > now:
        return payload
    return None


def _validate_jwks_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _bad_gateway("Clerk JWKS response must be a JSON object.")

    keys = payload.get("keys")
    if not isinstance(keys, list):
        raise _bad_gateway("Clerk JWKS response is missing the keys list.")

    for key in keys:
        if not isinstance(key, dict):
            raise _bad_gateway("Clerk JWKS response contains an invalid key entry.")
        if key.get("kty") != "RSA" or not isinstance(key.get("kid"), str):
            raise _bad_gateway("Clerk JWKS response contains an invalid signing key.")
        if not isinstance(key.get("n"), str) or not isinstance(key.get("e"), str):
            raise _bad_gateway("Clerk JWKS response contains an incomplete signing key.")

    return payload


async def _fetch_jwks_from_clerk(settings: Settings) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(
                CLERK_BACKEND_JWKS_URL,
                headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise _service_unavailable() from exc

    try:
        payload = response.json()
    except (JSONDecodeError, ValueError) as exc:
        raise _bad_gateway() from exc

    return _validate_jwks_payload(payload)


async def fetch_clerk_jwks(settings: Settings, *, force_refresh: bool = False) -> dict[str, Any]:
    now = time.monotonic()
    if not force_refresh:
        cached_payload = _read_cached_jwks(now=now)
        if cached_payload is not None:
            return cached_payload

    async with _jwks_cache_lock:
        now = time.monotonic()
        if not force_refresh:
            cached_payload = _read_cached_jwks(now=now)
            if cached_payload is not None:
                return cached_payload

        payload = await _fetch_jwks_from_clerk(settings)
        _jwks_cache["payload"] = payload
        _jwks_cache["expires_at"] = now + JWKS_CACHE_TTL_SECONDS
        return payload


def _find_signing_key(jwks: dict[str, Any], key_id: str) -> dict[str, Any] | None:
    signing_keys = jwks.get("keys", [])
    if not isinstance(signing_keys, list):
        raise _bad_gateway("Clerk JWKS response is missing the keys list.")

    return next(
        (
            candidate
            for candidate in signing_keys
            if isinstance(candidate, dict) and candidate.get("kid") == key_id
        ),
        None,
    )


def _normalize_origin(origin: str) -> str:
    return origin.rstrip("/")


def _validate_session_claims(claims: dict[str, Any], *, origin: str | None) -> None:
    issuer = claims.get("iss")
    session_id = claims.get("sid")
    subject = claims.get("sub")
    version = claims.get("v")
    expiration = claims.get("exp")
    not_before = claims.get("nbf")
    issued_at = claims.get("iat")

    if not isinstance(issuer, str) or not issuer.startswith("https://"):
        raise _unauthorized("Session token is missing a valid issuer.")
    if not isinstance(session_id, str) or not session_id.startswith("sess_"):
        raise _unauthorized("Session token is missing a valid session id.")
    if not isinstance(subject, str) or not subject.startswith("user_"):
        raise _unauthorized("Session token is missing the Clerk subject.")
    if version not in {2, "2"}:
        raise _unauthorized("Unsupported Clerk session token version.")
    if not isinstance(expiration, (int, float)):
        raise _unauthorized("Session token is missing its expiration.")
    if not isinstance(not_before, (int, float)):
        raise _unauthorized("Session token is missing its not-before claim.")
    if not isinstance(issued_at, (int, float)):
        raise _unauthorized("Session token is missing its issued-at claim.")

    authorized_party = claims.get("azp")
    if origin and authorized_party is not None:
        if not isinstance(authorized_party, str) or _normalize_origin(authorized_party) != _normalize_origin(origin):
            raise _unauthorized("Invalid authorized party.")


async def verify_clerk_session_token(token: str, settings: Settings, *, origin: str | None) -> dict[str, Any]:
    try:
        token_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _unauthorized("Invalid session token.") from exc

    key_id = token_header.get("kid")
    if not isinstance(key_id, str) or not key_id:
        raise _unauthorized("Session token is missing a signing key identifier.")
    if token_header.get("alg") != "RS256":
        raise _unauthorized("Unsupported session token algorithm.")

    jwks = await fetch_clerk_jwks(settings)
    signing_key = _find_signing_key(jwks, key_id)
    if signing_key is None:
        jwks = await fetch_clerk_jwks(settings, force_refresh=True)
        signing_key = _find_signing_key(jwks, key_id)
    if signing_key is None:
        raise _unauthorized("Unable to find a Clerk signing key for this session.")

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False, "verify_iat": True, "verify_nbf": True, "verify_exp": True},
        )
    except JWTError as exc:
        raise _unauthorized("Invalid session token.") from exc

    _validate_session_claims(claims, origin=origin)
    return claims


async def _get_user_by_clerk_id(session: AsyncSession, clerk_id: str) -> User | None:
    return await session.scalar(select(User).where(User.clerk_id == clerk_id))


def _build_user_upsert_statement(*, clerk_id: str, email: str | None, dialect_name: str):
    values: dict[str, str | None] = {"clerk_id": clerk_id, "email": email}

    if dialect_name == "postgresql":
        return postgresql_insert(User).values(**values).on_conflict_do_nothing(index_elements=[User.clerk_id])
    if dialect_name == "sqlite":
        return sqlite_insert(User).values(**values).on_conflict_do_nothing(index_elements=[User.clerk_id])

    raise RuntimeError(f"Unsupported database dialect for auth upsert: {dialect_name}")


async def resolve_user_for_clerk_subject(
    session: AsyncSession,
    clerk_id: str,
    *,
    email: str | None,
) -> User:
    async with AsyncSessionLocal() as bootstrap_session:
        bind = bootstrap_session.get_bind()
        statement = _build_user_upsert_statement(
            clerk_id=clerk_id,
            email=email,
            dialect_name=bind.dialect.name,
        )
        await bootstrap_session.execute(statement)
        await bootstrap_session.commit()

        bootstrap_user = await _get_user_by_clerk_id(bootstrap_session, clerk_id)
        if bootstrap_user is None:
            raise _service_unavailable("Failed to bootstrap the local user record.")

        if email and bootstrap_user.email != email:
            bootstrap_user.email = email
            await bootstrap_session.commit()

    user = await _get_user_by_clerk_id(session, clerk_id)
    if user is None:
        raise _service_unavailable("Failed to load the local user record.")

    return user


async def get_current_user(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> User:
    if settings.dev_auth_enabled:
        dev_token = _extract_dev_auth_token(request)
        if dev_token is not None and secrets.compare_digest(dev_token, settings.dev_auth_token):
            return await resolve_user_for_clerk_subject(
                session,
                settings.dev_auth_clerk_id,
                email=settings.dev_auth_email,
            )

    token = _extract_session_token(request)
    origin_header = request.headers.get("origin")
    origin = origin_header.strip() if origin_header else None
    claims = await verify_clerk_session_token(token, settings, origin=origin)

    email_claim = claims.get("email")
    email = email_claim if isinstance(email_claim, str) and email_claim else None

    return await resolve_user_for_clerk_subject(
        session,
        str(claims["sub"]),
        email=email,
    )
