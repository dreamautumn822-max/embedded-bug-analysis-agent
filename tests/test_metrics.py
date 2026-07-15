from fastapi.testclient import TestClient

from app.graph.observability import traced_node
from app.main import app


def test_traced_node_exports_node_and_fallback_metrics():
    wrapped = traced_node(
        "metric_test_node",
        lambda state: {
            "fallback_reasons": [
                *state.get("fallback_reasons", []),
                {
                    "node": "metric_test_node",
                    "code": "metric_test_fallback",
                    "message": "test",
                },
            ]
        },
    )

    wrapped({"fallback_reasons": [], "trace_events": []})
    metrics = TestClient(app).get("/metrics")

    assert metrics.status_code == 200
    assert "bug_agent_node_runs_total" in metrics.text
    assert 'node="metric_test_node",status="fallback"' in metrics.text
    assert "bug_agent_fallback_total" in metrics.text
    assert 'code="metric_test_fallback",node="metric_test_node"' in metrics.text


def test_metrics_endpoint_exposes_retrieval_and_analysis_families():
    metrics = TestClient(app).get("/metrics")

    assert metrics.status_code == 200
    assert metrics.headers["content-type"].startswith("text/plain")
    assert "bug_agent_retrieval_requests_total" in metrics.text
    assert "bug_agent_analysis_runs_total" in metrics.text
    assert "bug_agent_human_review_total" in metrics.text
    assert "bug_agent_http_requests_total" in metrics.text
    assert "bug_agent_llm_requests_total" in metrics.text
    assert "bug_agent_queue_depth" in metrics.text
    assert "bug_agent_queue_jobs_current" in metrics.text
