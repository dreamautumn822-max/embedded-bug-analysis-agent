import hashlib
import hmac
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Header, HTTPException


_HASH_PATTERN = re.compile(r"^sha256:[a-f0-9]{64}$")


@dataclass(frozen=True)
class Principal:
    tenant_id: str


@dataclass(frozen=True)
class AuthSettings:
    enabled: bool
    tenant_key_hashes: tuple[tuple[str, str], ...]

    @classmethod
    def from_env(cls) -> "AuthSettings":
        enabled = _bool_env("API_AUTH_ENABLED", False)
        raw = os.getenv("BUG_AGENT_API_KEY_HASHES_JSON", "{}").strip() or "{}"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("BUG_AGENT_API_KEY_HASHES_JSON must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("BUG_AGENT_API_KEY_HASHES_JSON must be a JSON object")

        entries: list[tuple[str, str]] = []
        for tenant_id, key_hash in payload.items():
            tenant = str(tenant_id).strip()
            digest = str(key_hash).strip().lower()
            if not tenant or len(tenant) > 100:
                raise ValueError("Tenant identifiers must contain 1-100 characters")
            if not _HASH_PATTERN.fullmatch(digest):
                raise ValueError(
                    "API key hashes must use sha256:<64 lowercase hex> format"
                )
            entries.append((tenant, digest))
        if enabled and not entries:
            raise ValueError("API authentication is enabled but no API key hashes exist")
        return cls(enabled=enabled, tenant_key_hashes=tuple(sorted(entries)))


def get_principal(
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> Principal:
    settings = current_auth_settings()
    if not settings.enabled:
        return Principal(tenant_id="local")
    if not api_key:
        raise _unauthorized()

    candidate = hash_api_key(api_key)
    matched_tenant: str | None = None
    for tenant_id, configured_hash in settings.tenant_key_hashes:
        if hmac.compare_digest(candidate, configured_hash):
            matched_tenant = tenant_id
    if matched_tenant is None:
        raise _unauthorized()
    return Principal(tenant_id=matched_tenant)


def hash_api_key(api_key: str) -> str:
    return "sha256:" + hashlib.sha256(api_key.encode("utf-8")).hexdigest()


def clear_auth_settings_cache() -> None:
    _cached_auth_settings.cache_clear()


@lru_cache(maxsize=8)
def _cached_auth_settings(raw_enabled: str, raw_hashes: str) -> AuthSettings:
    return AuthSettings.from_env()


def current_auth_settings() -> AuthSettings:
    return _cached_auth_settings(
        os.getenv("API_AUTH_ENABLED", "false"),
        os.getenv("BUG_AGENT_API_KEY_HASHES_JSON", "{}"),
    )


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Missing or invalid API key",
        headers={"WWW-Authenticate": "ApiKey"},
    )


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")
