from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

from langgraph.types import Command

from app.graph.bug_analysis_graph import (
    build_persistent_bug_analysis_graph,
    initial_bug_analysis_state,
)
from app.graph.state import BugAnalysisState


AnalysisRunStatus = Literal["pending_review", "completed", "failed"]


class AnalysisNotFoundError(LookupError):
    pass


class AnalysisNotPendingReviewError(RuntimeError):
    pass


@dataclass(frozen=True)
class AnalysisRun:
    analysis_id: str
    status: AnalysisRunStatus
    state: BugAnalysisState
    review_payload: dict | None = None
    error: str | None = None


def start_reviewable_analysis(
    *,
    device_model: str,
    firmware_version: str,
    symptom: str,
    logs: str,
    stack_trace: str | None = None,
    module_hint: str | None = None,
    analysis_id: str | None = None,
    checkpoint_path: Path | str | None = None,
    tenant_id: str = "local",
) -> AnalysisRun:
    run_id = analysis_id or uuid4().hex
    graph = build_persistent_bug_analysis_graph(checkpoint_path)
    config = _thread_config(run_id)
    graph.invoke(
        initial_bug_analysis_state(
            device_model=device_model,
            firmware_version=firmware_version,
            symptom=symptom,
            logs=logs,
            stack_trace=stack_trace,
            module_hint=module_hint,
            interactive_review=True,
            tenant_id=tenant_id,
        ),
        config=config,
    )
    return _snapshot_to_run(run_id, graph.get_state(config))


def get_reviewable_analysis(
    analysis_id: str,
    *,
    checkpoint_path: Path | str | None = None,
    tenant_id: str = "local",
) -> AnalysisRun:
    graph = build_persistent_bug_analysis_graph(checkpoint_path)
    snapshot = graph.get_state(_thread_config(analysis_id))
    if snapshot.created_at is None:
        raise AnalysisNotFoundError(analysis_id)
    _ensure_tenant(snapshot, analysis_id, tenant_id)
    return _snapshot_to_run(analysis_id, snapshot)


def resume_reviewable_analysis(
    analysis_id: str,
    *,
    approved: bool,
    reviewer: str,
    comment: str | None = None,
    checkpoint_path: Path | str | None = None,
    tenant_id: str = "local",
) -> AnalysisRun:
    graph = build_persistent_bug_analysis_graph(checkpoint_path)
    config = _thread_config(analysis_id)
    snapshot = graph.get_state(config)
    if snapshot.created_at is None:
        raise AnalysisNotFoundError(analysis_id)
    _ensure_tenant(snapshot, analysis_id, tenant_id)
    if not _interrupt_payload(snapshot):
        raise AnalysisNotPendingReviewError(analysis_id)

    graph.invoke(
        Command(
            resume={
                "approved": approved,
                "reviewer": reviewer,
                "comment": comment,
            }
        ),
        config=config,
    )
    return _snapshot_to_run(analysis_id, graph.get_state(config))


def _thread_config(analysis_id: str) -> dict:
    return {"configurable": {"thread_id": analysis_id}}


def _snapshot_to_run(analysis_id: str, snapshot) -> AnalysisRun:
    review_payload = _interrupt_payload(snapshot)
    errors = [str(task.error) for task in snapshot.tasks if task.error]
    if review_payload is not None:
        status: AnalysisRunStatus = "pending_review"
    elif errors:
        status = "failed"
    else:
        status = "completed"
    return AnalysisRun(
        analysis_id=analysis_id,
        status=status,
        state=dict(snapshot.values),
        review_payload=review_payload,
        error="; ".join(errors) if errors else None,
    )


def _interrupt_payload(snapshot) -> dict | None:
    for task in snapshot.tasks:
        for graph_interrupt in task.interrupts:
            if isinstance(graph_interrupt.value, dict):
                return graph_interrupt.value
    return None


def _ensure_tenant(snapshot, analysis_id: str, tenant_id: str) -> None:
    owner = str(snapshot.values.get("tenant_id", "local"))
    if owner != tenant_id:
        raise AnalysisNotFoundError(analysis_id)
