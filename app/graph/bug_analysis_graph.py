from functools import lru_cache

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    extract_bug_info_node,
    generate_hypotheses_node,
    generate_report_node,
    parse_logs_node,
    retrieve_related_docs_node,
    search_bug_history_node,
    search_codebase_node,
)
from app.graph.state import BugAnalysisState


@lru_cache(maxsize=1)
def build_bug_analysis_graph():
    graph = StateGraph(BugAnalysisState)

    graph.add_node("extract_bug_info", extract_bug_info_node)
    graph.add_node("parse_logs", parse_logs_node)
    graph.add_node("search_bug_history", search_bug_history_node)
    graph.add_node("search_codebase", search_codebase_node)
    graph.add_node("retrieve_related_docs", retrieve_related_docs_node)
    graph.add_node("generate_hypotheses", generate_hypotheses_node)
    graph.add_node("generate_report", generate_report_node)

    graph.set_entry_point("extract_bug_info")
    graph.add_edge("extract_bug_info", "parse_logs")
    graph.add_edge("parse_logs", "search_bug_history")
    graph.add_edge("search_bug_history", "search_codebase")
    graph.add_edge("search_codebase", "retrieve_related_docs")
    graph.add_edge("retrieve_related_docs", "generate_hypotheses")
    graph.add_edge("generate_hypotheses", "generate_report")
    graph.add_edge("generate_report", END)

    return graph.compile()


def analyze_bug(
    device_model: str,
    firmware_version: str,
    symptom: str,
    logs: str,
    stack_trace: str | None = None,
    module_hint: str | None = None,
) -> BugAnalysisState:
    initial_state: BugAnalysisState = {
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
        "fix_suggestions": [],
        "final_report": "",
    }
    app = build_bug_analysis_graph()
    return app.invoke(initial_state)
