import os
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Iterator

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_CONFIGURATION_LOCK = Lock()
_CONFIGURED = False
_FASTAPI_INSTRUMENTED = False


@dataclass(frozen=True)
class TracingSettings:
    enabled: bool
    service_name: str
    endpoint: str
    insecure: bool

    @classmethod
    def from_env(cls) -> "TracingSettings":
        return cls(
            enabled=_bool_env("OTEL_ENABLED", False),
            service_name=os.getenv(
                "OTEL_SERVICE_NAME",
                "embedded-bug-agent-api",
            ).strip()
            or "embedded-bug-agent-api",
            endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT",
                "http://127.0.0.1:4317",
            ).strip(),
            insecure=_bool_env("OTEL_EXPORTER_OTLP_INSECURE", True),
        )


def configure_tracing(app: FastAPI) -> bool:
    global _FASTAPI_INSTRUMENTED
    settings = TracingSettings.from_env()
    if not settings.enabled:
        return False
    provider = _configure_provider(settings)
    with _CONFIGURATION_LOCK:
        if _FASTAPI_INSTRUMENTED:
            return True
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls="/health,/metrics",
        )
        _FASTAPI_INSTRUMENTED = True
    return True


def configure_worker_tracing() -> bool:
    settings = TracingSettings.from_env()
    if not settings.enabled:
        return False
    _configure_provider(settings)
    return True


def flush_tracing(timeout_millis: int = 5000) -> bool:
    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        return False
    return provider.force_flush(timeout_millis=timeout_millis)


def _configure_provider(settings: TracingSettings) -> TracerProvider:
    global _CONFIGURED
    with _CONFIGURATION_LOCK:
        if _CONFIGURED:
            provider = trace.get_tracer_provider()
            if isinstance(provider, TracerProvider):
                return provider
            raise RuntimeError("OpenTelemetry provider was configured by another library")
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": settings.service_name,
                    "service.namespace": "embedded-bug-agent",
                }
            )
        )
        exporter = OTLPSpanExporter(
            endpoint=settings.endpoint,
            insecure=settings.insecure,
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        HTTPXClientInstrumentor().instrument(tracer_provider=provider)
        _CONFIGURED = True
        return provider


@contextmanager
def start_span(
    name: str,
    attributes: dict[str, str | int | float | bool] | None = None,
) -> Iterator[trace.Span]:
    tracer = trace.get_tracer("embedded-bug-agent")
    with tracer.start_as_current_span(name, attributes=attributes or {}) as span:
        yield span


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
