import os
from dataclasses import dataclass


@dataclass(frozen=True)
class JobQueueSettings:
    redis_url: str
    queue_name: str
    timeout_seconds: int
    max_timeout_seconds: int
    result_ttl_seconds: int
    failure_ttl_seconds: int
    idempotency_ttl_seconds: int
    max_retries: int

    @classmethod
    def from_env(cls) -> "JobQueueSettings":
        timeout = _positive_int_env("JOB_TIMEOUT_SECONDS", 120)
        maximum = _positive_int_env("JOB_MAX_TIMEOUT_SECONDS", 900)
        if timeout > maximum:
            raise ValueError("JOB_TIMEOUT_SECONDS must not exceed JOB_MAX_TIMEOUT_SECONDS")
        return cls(
            redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip(),
            queue_name=os.getenv("JOB_QUEUE_NAME", "bug-analysis").strip()
            or "bug-analysis",
            timeout_seconds=timeout,
            max_timeout_seconds=maximum,
            result_ttl_seconds=_positive_int_env("JOB_RESULT_TTL_SECONDS", 86400),
            failure_ttl_seconds=_positive_int_env("JOB_FAILURE_TTL_SECONDS", 86400),
            idempotency_ttl_seconds=_positive_int_env(
                "JOB_IDEMPOTENCY_TTL_SECONDS",
                86400,
            ),
            max_retries=_non_negative_int_env("JOB_MAX_RETRIES", 1),
        )


def _positive_int_env(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be >= 1")
    return value


def _non_negative_int_env(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value
