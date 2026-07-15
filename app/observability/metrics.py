import os

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)


NODE_RUNS_TOTAL = Counter(
    "bug_agent_node_runs_total",
    "LangGraph node execution attempts.",
    ("node", "status"),
)
NODE_DURATION_SECONDS = Histogram(
    "bug_agent_node_duration_seconds",
    "LangGraph node execution duration in seconds.",
    ("node", "status"),
)
FALLBACK_TOTAL = Counter(
    "bug_agent_fallback_total",
    "Structured fallback reasons emitted by agent nodes.",
    ("node", "code"),
)
RETRIEVAL_REQUESTS_TOTAL = Counter(
    "bug_agent_retrieval_requests_total",
    "Knowledge retrieval requests by source and outcome.",
    ("source_type", "status"),
)
RETRIEVAL_DURATION_SECONDS = Histogram(
    "bug_agent_retrieval_duration_seconds",
    "Knowledge retrieval duration in seconds.",
    ("source_type", "status"),
)
RETRIEVAL_RESULTS_TOTAL = Counter(
    "bug_agent_retrieval_results_total",
    "Returned retrieval results by source and retrieval method.",
    ("source_type", "retrieval_method"),
)
ANALYSIS_RUNS_TOTAL = Counter(
    "bug_agent_analysis_runs_total",
    "Bug analysis requests by workflow and outcome.",
    ("workflow", "status", "generation_mode", "review_status"),
)
ANALYSIS_DURATION_SECONDS = Histogram(
    "bug_agent_analysis_duration_seconds",
    "Bug analysis request duration in seconds.",
    ("workflow", "status"),
)
HUMAN_REVIEW_TOTAL = Counter(
    "bug_agent_human_review_total",
    "Human review decisions and resume outcomes.",
    ("decision", "status"),
)
HUMAN_REVIEW_DURATION_SECONDS = Histogram(
    "bug_agent_human_review_duration_seconds",
    "Human review resume duration in seconds.",
    ("decision", "status"),
)
HTTP_REQUESTS_TOTAL = Counter(
    "bug_agent_http_requests_total",
    "HTTP requests by method, route and status code.",
    ("method", "route", "status_code"),
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "bug_agent_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "route"),
)
LLM_REQUESTS_TOTAL = Counter(
    "bug_agent_llm_requests_total",
    "Root-cause LLM requests by model and outcome.",
    ("model", "status"),
)
LLM_REQUEST_DURATION_SECONDS = Histogram(
    "bug_agent_llm_request_duration_seconds",
    "Root-cause LLM request duration in seconds.",
    ("model", "status"),
)
LLM_TOKENS_TOTAL = Counter(
    "bug_agent_llm_tokens_total",
    "Reported LLM tokens by model and token type.",
    ("model", "token_type"),
)
QUEUE_JOBS_TOTAL = Counter(
    "bug_agent_queue_jobs_total",
    "Queued analysis operations by operation and outcome.",
    ("operation", "status"),
)
QUEUE_JOB_DURATION_SECONDS = Histogram(
    "bug_agent_queue_job_duration_seconds",
    "Worker job duration in seconds.",
    ("operation", "status"),
)
QUEUE_DEPTH = Gauge(
    "bug_agent_queue_depth",
    "Current RQ queue depth.",
    ("queue",),
    multiprocess_mode="livemostrecent",
)
QUEUE_JOBS_CURRENT = Gauge(
    "bug_agent_queue_jobs_current",
    "Current persisted jobs by status.",
    ("status",),
    multiprocess_mode="livemostrecent",
)


def observe_node(
    *,
    node: str,
    status: str,
    duration_seconds: float,
    fallback_reasons: list[dict] | None = None,
) -> None:
    NODE_RUNS_TOTAL.labels(node=node, status=status).inc()
    NODE_DURATION_SECONDS.labels(node=node, status=status).observe(duration_seconds)
    for reason in fallback_reasons or []:
        FALLBACK_TOTAL.labels(
            node=str(reason.get("node", node)),
            code=str(reason.get("code", "unknown")),
        ).inc()


def observe_retrieval(
    *,
    source_type: str,
    status: str,
    duration_seconds: float,
    results: list[dict] | None = None,
) -> None:
    RETRIEVAL_REQUESTS_TOTAL.labels(
        source_type=source_type,
        status=status,
    ).inc()
    RETRIEVAL_DURATION_SECONDS.labels(
        source_type=source_type,
        status=status,
    ).observe(duration_seconds)
    methods: dict[str, int] = {}
    for result in results or []:
        method = str(result.get("retrieval_method", "unknown"))
        methods[method] = methods.get(method, 0) + 1
    for method, count in methods.items():
        RETRIEVAL_RESULTS_TOTAL.labels(
            source_type=source_type,
            retrieval_method=method,
        ).inc(count)


def observe_analysis(
    *,
    workflow: str,
    status: str,
    generation_mode: str,
    review_status: str,
    duration_seconds: float,
) -> None:
    ANALYSIS_RUNS_TOTAL.labels(
        workflow=workflow,
        status=status,
        generation_mode=generation_mode or "unknown",
        review_status=review_status or "unknown",
    ).inc()
    ANALYSIS_DURATION_SECONDS.labels(
        workflow=workflow,
        status=status,
    ).observe(duration_seconds)


def observe_human_review(
    *,
    approved: bool,
    status: str,
    duration_seconds: float,
) -> None:
    decision = "approved" if approved else "rejected"
    HUMAN_REVIEW_TOTAL.labels(decision=decision, status=status).inc()
    HUMAN_REVIEW_DURATION_SECONDS.labels(
        decision=decision,
        status=status,
    ).observe(duration_seconds)


def observe_http(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    HTTP_REQUESTS_TOTAL.labels(
        method=method,
        route=route,
        status_code=str(status_code),
    ).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, route=route).observe(
        duration_seconds
    )


def observe_llm(
    *,
    model: str,
    status: str,
    duration_seconds: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    LLM_REQUESTS_TOTAL.labels(model=model, status=status).inc()
    LLM_REQUEST_DURATION_SECONDS.labels(model=model, status=status).observe(
        duration_seconds
    )
    if prompt_tokens:
        LLM_TOKENS_TOTAL.labels(model=model, token_type="prompt").inc(prompt_tokens)
    if completion_tokens:
        LLM_TOKENS_TOTAL.labels(model=model, token_type="completion").inc(
            completion_tokens
        )


def observe_queue_job(
    *,
    operation: str,
    status: str,
    duration_seconds: float | None = None,
) -> None:
    QUEUE_JOBS_TOTAL.labels(operation=operation, status=status).inc()
    if duration_seconds is not None:
        QUEUE_JOB_DURATION_SECONDS.labels(
            operation=operation,
            status=status,
        ).observe(duration_seconds)


def set_queue_depth(*, queue: str, depth: int) -> None:
    QUEUE_DEPTH.labels(queue=queue).set(max(0, depth))


def set_queue_status_counts(counts: dict[str, int]) -> None:
    statuses = (
        "queued",
        "running",
        "pending_review",
        "completed",
        "failed",
        "cancel_requested",
        "cancelled",
        "timed_out",
    )
    for status in statuses:
        QUEUE_JOBS_CURRENT.labels(status=status).set(counts.get(status, 0))


def generate_metrics_payload() -> bytes:
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry)
    return generate_latest()
