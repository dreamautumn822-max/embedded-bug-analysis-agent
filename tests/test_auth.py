import pytest
from fastapi import HTTPException

from app.security.auth import clear_auth_settings_cache, get_principal, hash_api_key


def test_api_key_auth_maps_hash_to_tenant(monkeypatch):
    api_key = "tenant-a-secret-key-123"
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv(
        "BUG_AGENT_API_KEY_HASHES_JSON",
        f'{{"tenant-a":"{hash_api_key(api_key)}"}}',
    )
    clear_auth_settings_cache()

    principal = get_principal(api_key)

    assert principal.tenant_id == "tenant-a"


def test_api_key_auth_rejects_missing_or_invalid_key(monkeypatch):
    monkeypatch.setenv("API_AUTH_ENABLED", "true")
    monkeypatch.setenv(
        "BUG_AGENT_API_KEY_HASHES_JSON",
        f'{{"tenant-a":"{hash_api_key("tenant-a-secret-key-123")}"}}',
    )
    clear_auth_settings_cache()

    with pytest.raises(HTTPException) as missing:
        get_principal(None)
    with pytest.raises(HTTPException) as invalid:
        get_principal("wrong-key")

    assert missing.value.status_code == 401
    assert invalid.value.status_code == 401


def test_auth_disabled_uses_local_tenant(monkeypatch):
    monkeypatch.setenv("API_AUTH_ENABLED", "false")
    monkeypatch.delenv("BUG_AGENT_API_KEY_HASHES_JSON", raising=False)
    clear_auth_settings_cache()

    assert get_principal(None).tenant_id == "local"
