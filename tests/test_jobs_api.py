from fastapi.testclient import TestClient

from app.jobs.models import StoredJob
from app.main import app


def test_queued_job_endpoint_returns_accepted(monkeypatch):
    monkeypatch.setenv("API_AUTH_ENABLED", "false")
    record = StoredJob.create(
        job_id="api-job-1",
        tenant_id="local",
        timeout_seconds=120,
        request_fingerprint="fingerprint",
        request_payload={},
        trace_context={},
    )

    def fake_enqueue(request, *, tenant_id, idempotency_key):
        assert tenant_id == "local"
        assert idempotency_key == "request-001"
        return record

    monkeypatch.setattr("app.jobs.router.enqueue_analysis_job", fake_enqueue)
    response = TestClient(app).post(
        "/v1/jobs",
        headers={"Idempotency-Key": "request-001"},
        json={
            "device_model": "AX3000",
            "firmware_version": "v1",
            "symptom": "DHCP failed",
            "logs": "dhcpd: lease allocation failed",
        },
    )

    assert response.status_code == 202
    assert response.json()["job_id"] == "api-job-1"
    assert response.json()["poll_url"] == "/v1/jobs/api-job-1"
