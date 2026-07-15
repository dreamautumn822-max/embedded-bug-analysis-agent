import fakeredis
import pytest

from app.jobs.models import StoredJob
from app.jobs.store import JobStore, StoredJobNotFoundError


def _store() -> JobStore:
    return JobStore(
        fakeredis.FakeRedis(),
        ttl_seconds=3600,
        idempotency_ttl_seconds=3600,
    )


def _record() -> StoredJob:
    return StoredJob.create(
        job_id="job-1",
        tenant_id="tenant-a",
        timeout_seconds=120,
        request_fingerprint="fingerprint",
        request_payload={"logs": "test"},
        trace_context={},
    )


def test_job_store_isolates_tenants_and_updates_atomically():
    store = _store()
    store.create(_record())

    updated = store.update("job-1", status="running", attempts=1)

    assert updated.status == "running"
    assert updated.attempts == 1
    assert store.get_for_tenant("job-1", "tenant-a").status == "running"
    with pytest.raises(StoredJobNotFoundError):
        store.get_for_tenant("job-1", "tenant-b")


def test_job_store_claims_idempotency_key_once():
    store = _store()

    assert store.claim_idempotency_key(
        tenant_id="tenant-a",
        idempotency_key="request-1",
        job_id="job-1",
        request_fingerprint="fingerprint",
    )
    assert not store.claim_idempotency_key(
        tenant_id="tenant-a",
        idempotency_key="request-1",
        job_id="job-2",
        request_fingerprint="other",
    )
    assert store.get_idempotent_job(
        tenant_id="tenant-a",
        idempotency_key="request-1",
    ) == ("job-1", "fingerprint")
