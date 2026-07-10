from app.llm.config import LLMSettings


def test_llm_settings_default_to_disabled(monkeypatch):
    for key in [
        "LLM_ENABLED",
        "LLM_BASE_URL",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
        "LLM_TEMPERATURE",
    ]:
        monkeypatch.delenv(key, raising=False)

    settings = LLMSettings.from_env()

    assert settings.enabled is False
    assert settings.is_ready is False
    assert settings.timeout_seconds == 30
    assert settings.temperature == 0.2


def test_llm_settings_can_enable_openai_compatible_provider(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "deepseek-chat")
    monkeypatch.setenv("LLM_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("LLM_TEMPERATURE", "0.1")

    settings = LLMSettings.from_env()

    assert settings.enabled is True
    assert settings.is_ready is True
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.api_key == "test-key"
    assert settings.model == "deepseek-chat"
    assert settings.timeout_seconds == 12
    assert settings.temperature == 0.1


def test_llm_settings_enabled_but_missing_required_values_is_not_ready(monkeypatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setenv("LLM_MODEL", "qwen-plus")

    settings = LLMSettings.from_env()

    assert settings.enabled is True
    assert settings.is_ready is False
