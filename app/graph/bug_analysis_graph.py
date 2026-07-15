from functools import lru_cache
from pathlib import Path

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    assess_review_node,
    extract_bug_info_node,
    generate_hypotheses_node,
    generate_report_node,
    parse_logs_node,
    queue_human_review_node,
    retrieve_related_docs_node,
    route_after_review_assessment,
    search_bug_history_node,
    search_codebase_node,
)
from app.graph.observability import traced_node
from app.graph.checkpoint import checkpoint_path_from_env, get_sqlite_checkpointer
from app.graph.state import BugAnalysisState


def _build_state_graph() -> StateGraph:
    graph = StateGraph(BugAnalysisState)

    graph.add_node(
        "extract_bug_info",
        traced_node("extract_bug_info", extract_bug_info_node),
    )
    graph.add_node("parse_logs", traced_node("parse_logs", parse_logs_node))
    graph.add_node(
        "search_bug_history",
        traced_node("search_bug_history", search_bug_history_node),
    )
    graph.add_node(
        "search_codebase",
        traced_node("search_codebase", search_codebase_node),
    )
    graph.add_node(
        "retrieve_related_docs",
        traced_node("retrieve_related_docs", retrieve_related_docs_node),
    )
    graph.add_node(
        "generate_hypotheses",
        traced_node("generate_hypotheses", generate_hypotheses_node),
    )
    graph.add_node("assess_review", traced_node("assess_review", assess_review_node))
    graph.add_node(
        "queue_human_review",
        traced_node("queue_human_review", queue_human_review_node),
    )
    graph.add_node("generate_report", traced_node("generate_report", generate_report_node))

    graph.set_entry_point("extract_bug_info")
    graph.add_edge("extract_bug_info", "parse_logs")
    graph.add_edge("parse_logs", "search_bug_history")
    graph.add_edge("search_bug_history", "search_codebase")
    graph.add_edge("search_codebase", "retrieve_related_docs")
    graph.add_edge("retrieve_related_docs", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "assess_review")
    graph.add_conditional_edges(
        "assess_review",
        route_after_review_assessment,
        {
            "human_review": "queue_human_review",
            "auto_report": "generate_report",
        },
    )
    graph.add_edge("queue_human_review", "generate_report")
    graph.add_edge("generate_report", END)

    return graph


@lru_cache(maxsize=1)
def build_bug_analysis_graph():
    return _build_state_graph().compile()


def build_persistent_bug_analysis_graph(checkpoint_path: Path | str | None = None):
    resolved = (
        Path(checkpoint_path).resolve()
        if checkpoint_path is not None
        else checkpoint_path_from_env()
    )
    return _cached_persistent_graph(str(resolved))


@lru_cache(maxsize=8)
def _cached_persistent_graph(checkpoint_path: str):
    checkpointer = get_sqlite_checkpointer(checkpoint_path)
    return _build_state_graph().compile(checkpointer=checkpointer)


def initial_bug_analysis_state(
    *,
    device_model: str,
    firmware_version: str,
    symptom: str,
    logs: str,
    stack_trace: str | None = None,
    module_hint: str | None = None,
    interactive_review: bool = False,
    tenant_id: str = "local",
) -> BugAnalysisState:
    return {
        "tenant_id": tenant_id,
        "device_model": device_model,
        "firmware_version": firmware_version,
        "symptom": symptom,
        "logs": logs,
        "stack_trace": stack_trace,
        "module_hint": module_hint,
        "extracted_info": {},
        "bug_type": "",
        "related_docs": [],
        "related_bugs": [],
        "related_code": [],
        "parsed_logs": {},
        "hypotheses": [],
        "evidence": [],
        "evidence_details": [],
        "fix_suggestions": [],
        "final_report": "",
        "generation_mode": "",
        "fallback_reasons": [],
        "trace_events": [],
        "review_required": False,
        "review_status": "not_assessed",
        "review_reasons": [],
        "interactive_review": interactive_review,
        "review_decision": None,
    }


def analyze_bug(
    device_model: str,
    firmware_version: str,
    symptom: str,
    logs: str,
    stack_trace: str | None = None,
    module_hint: str | None = None,
    tenant_id: str = "local",
) -> BugAnalysisState:
    initial_state = initial_bug_analysis_state(
        device_model=device_model,
        firmware_version=firmware_version,
        symptom=symptom,
        logs=logs,
        stack_trace=stack_trace,
        module_hint=module_hint,
        tenant_id=tenant_id,
    )
    app = build_bug_analysis_graph()
    return app.invoke(initial_state)
