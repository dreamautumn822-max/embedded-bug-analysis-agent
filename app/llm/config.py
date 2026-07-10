import os
from dataclasses import dataclass


TRUE_VALUES = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LLMSettings:
    enabled: bool
    base_url: str | None
    api_key: str | None
    model: str | None
    timeout_seconds: int = 30
    temperature: float = 0.2

    @classmethod
    def from_env(cls) -> "LLMSettings":
        enabled = os.getenv("LLM_ENABLED", "false").strip().lower() in TRUE_VALUES
        return cls(
            enabled=enabled,
            base_url=_optional_env("LLM_BASE_URL"),
            api_key=_optional_env("LLM_API_KEY"),
            model=_optional_env("LLM_MODEL"),
            timeout_seconds=_int_env("LLM_TIMEOUT_SECONDS", 30),
            temperature=_float_env("LLM_TEMPERATURE", 0.2),
        )

    @property
    def is_ready(self) -> bool:
        return bool(self.enabled and self.base_url and self.api_key and self.model)


def _optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _int_env(name: str, default: int) -> int:
    value = _optional_env(name)
    if value is None:
        return default
    return int(value)


def _float_env(name: str, default: float) -> float:
    value = _optional_env(name)
    if value is None:
        return default
    return float(value)
