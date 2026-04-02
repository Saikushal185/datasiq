from __future__ import annotations

from dataclasses import dataclass
import json
from json import JSONDecodeError
from typing import Any, TypeVar, cast
from uuid import UUID

import httpx

from backend.app.core.config import Settings, get_settings

T = TypeVar("T")


class UpstashRedisError(RuntimeError):
    pass


class UpstashRedisConfigurationError(UpstashRedisError):
    pass


def _normalize_user_id(user_id: UUID | str) -> str:
    return str(user_id)


def build_namespaced_key(namespace: str, user_id: UUID | str, key: str = "state") -> str:
    return f"{namespace}:{_normalize_user_id(user_id)}:{key}"


def build_session_key(user_id: UUID | str, key: str) -> str:
    return build_namespaced_key("session", user_id, key)


def build_streak_key(user_id: UUID | str, key: str = "state") -> str:
    return build_namespaced_key("streak", user_id, key)


def _require_redis_settings(settings: Settings | None = None) -> tuple[str, str]:
    runtime_settings = settings or get_settings()
    if not runtime_settings.upstash_redis_rest_url or not runtime_settings.upstash_redis_rest_token:
        raise UpstashRedisConfigurationError("Upstash Redis REST URL and token are required.")
    return runtime_settings.upstash_redis_rest_url.rstrip("/"), runtime_settings.upstash_redis_rest_token


def _validate_ttl(ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be greater than zero.")


@dataclass(frozen=True, slots=True)
class UpstashRedisClient:
    rest_url: str
    token: str
    timeout_seconds: float = 5.0

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    async def execute(self, command: str, *args: object) -> Any:
        try:
            async with httpx.AsyncClient(
                base_url=self.rest_url,
                timeout=self.timeout_seconds,
                headers=self.headers,
            ) as client:
                response = await client.post("/", json=[command, *args])
        except httpx.HTTPError as exc:
            raise UpstashRedisError("Upstash request failed.") from exc

        if response.status_code >= 400:
            raise UpstashRedisError(f"Upstash request failed with HTTP {response.status_code}.")

        try:
            payload = response.json()
        except ValueError as exc:
            raise UpstashRedisError("Upstash returned a non-JSON response.") from exc

        if not isinstance(payload, dict):
            raise UpstashRedisError("Upstash returned an unexpected response shape.")

        error = payload.get("error")
        if isinstance(error, str) and error:
            raise UpstashRedisError(error)

        return payload.get("result")

    async def get(self, key: str) -> str | None:
        result = await self.execute("GET", key)
        if result is None:
            return None
        return str(result)

    async def set(self, key: str, value: str, *, ttl_seconds: int) -> None:
        _validate_ttl(ttl_seconds)
        await self.execute("SET", key, value, "EX", ttl_seconds)

    async def delete(self, *keys: str) -> int:
        if not keys:
            return 0
        result = await self.execute("DEL", *keys)
        return int(result or 0)

    async def set_json(self, key: str, value: object, *, ttl_seconds: int) -> None:
        serialized_value = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        await self.set(key, serialized_value, ttl_seconds=ttl_seconds)

    async def get_json(self, key: str) -> T | None:
        raw_value = await self.get(key)
        if raw_value is None:
            return None

        try:
            decoded_value = json.loads(raw_value)
        except JSONDecodeError as exc:
            raise UpstashRedisError("Stored value is not valid JSON.") from exc

        return cast(T, decoded_value)


def get_redis_client(settings: Settings | None = None, *, timeout_seconds: float = 5.0) -> UpstashRedisClient:
    rest_url, token = _require_redis_settings(settings)
    return UpstashRedisClient(rest_url=rest_url, token=token, timeout_seconds=timeout_seconds)


async def set_ephemeral_json(
    key: str,
    value: object,
    *,
    ttl_seconds: int,
    settings: Settings | None = None,
) -> None:
    client = get_redis_client(settings)
    await client.set_json(key, value, ttl_seconds=ttl_seconds)


async def get_ephemeral_json(key: str, *, settings: Settings | None = None) -> Any | None:
    client = get_redis_client(settings)
    return await client.get_json(key)
