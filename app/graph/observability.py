import logging
from collections.abc import Callable
from functools import wraps
from time import perf_counter

from langgraph.errors import GraphInterrupt

from app.graph.state import BugAnalysisState
from app.observability.metrics import observe_node
from app.observability.tracing import start_span


logger = logging.getLogger(__name__)


def traced_node(
    node_name: str,
    function: Callable[[BugAnalysisState], dict],
) -> Callable[[BugAnalysisState], dict]:
    @wraps(function)
    def wrapped(state: BugAnalysisState) -> dict:
        with start_span(
            f"langgraph.node.{node_name}",
            {"agent.node.name": node_name},
        ) as span:
            started_at = perf_counter()
            previous_fallbacks = len(state.get("fallback_reasons", []))
            try:
                updates = function(state)
            except GraphInterrupt:
                span.set_attribute("agent.node.status", "interrupted")
                observe_node(
                    node=node_name,
                    status="interrupted",
                    duration_seconds=perf_counter() - started_at,
                )
                raise
            except Exception:
                span.set_attribute("agent.node.status", "error")
                observe_node(
                    node=node_name,
                    status="error",
                    duration_seconds=perf_counter() - started_at,
                )
                logger.exception("Agent node failed: %s", node_name)
                raise

            fallback_reasons = updates.get(
                "fallback_reasons",
                state.get("fallback_reasons", []),
            )
            fallback_added = max(0, len(fallback_reasons) - previous_fallbacks)
            status = "fallback" if fallback_added else "success"
            duration_seconds = perf_counter() - started_at
            output_count = _output_count(updates)
            span.set_attribute("agent.node.status", status)
            span.set_attribute("agent.node.output_count", output_count)
            span.set_attribute("agent.node.fallback_count", fallback_added)
            observe_node(
                node=node_name,
                status=status,
                duration_seconds=duration_seconds,
                fallback_reasons=fallback_reasons[previous_fallbacks:],
            )
            event = {
                "node": node_name,
                "status": status,
                "duration_ms": round(duration_seconds * 1000, 2),
                "output_count": output_count,
                "fallback_count": fallback_added,
            }
            return {
                **updates,
                "trace_events": [*state.get("trace_events", []), event],
            }

    return wrapped


def _output_count(updates: dict) -> int:
    for key in (
        "related_docs",
        "related_bugs",
        "related_code",
        "hypotheses",
        "evidence_details",
    ):
        value = updates.get(key)
        if isinstance(value, list):
            return len(value)
    return len(updates)
