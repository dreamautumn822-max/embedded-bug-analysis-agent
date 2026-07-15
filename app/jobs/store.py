import hashlib
import json
from collections import Counter
from datetime import datetime, timezone

from redis import Redis
from redis.exceptions import WatchError

from app.jobs.config import JobQueueSettings
from app.jobs.models import StoredJob


class StoredJobNotFoundError(LookupError):
    pass


class JobStore:
    def __init__(
        self,
        connection: Redis,
        *,
        ttl_seconds: int,
        idempotency_ttl_seconds: int,
    ):
        self.connection = connection
        self.ttl_seconds = ttl_seconds
        self.idempotency_ttl_seconds = idempotency_ttl_seconds

    def create(self, record: StoredJob) -> None:
        created = self.connection.set(
            self._job_key(record.job_id),
            record.model_dump_json(),
            ex=self.ttl_seconds,
            nx=True,
        )
        if not created:
            raise ValueError(f"Job already exists: {record.job_id}")

    def get(self, job_id: str) -> StoredJob:
        raw = self.connection.get(self._job_key(job_id))
        if raw is None:
            raise StoredJobNotFoundError(job_id)
        return StoredJob.model_validate_json(raw)

    def get_for_tenant(self, job_id: str, tenant_id: str) -> StoredJob:
        record = self.get(job_id)
        if record.tenant_id != tenant_id:
            raise StoredJobNotFoundError(job_id)
        return record

    def update(self, job_id: str, **updates: object) -> StoredJob:
        key = self._job_key(job_id)
        for _ in range(5):
            with self.connection.pipeline() as pipeline:
                try:
                    pipeline.watch(key)
                    raw = pipeline.get(key)
                    if raw is None:
                        raise StoredJobNotFoundError(job_id)
                    current = StoredJob.model_validate_json(raw)
                    updated = current.model_copy(
                        update={
                            **updates,
                            "updated_at": datetime.now(timezone.utc),
                        }
                    )
                    updated = StoredJob.model_validate(updated.model_dump())
                    pipeline.multi()
                    pipeline.set(
                        key,
                        updated.model_dump_json(),
                        ex=self.ttl_seconds,
                    )
                    pipeline.execute()
                    return updated
                except WatchError:
                    continue
        raise RuntimeError(f"Concurrent update limit exceeded for job {job_id}")

    def claim_idempotency_key(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
        job_id: str,
        request_fingerprint: str,
    ) -> bool:
        payload = json.dumps(
            {"job_id": job_id, "request_fingerprint": request_fingerprint},
            separators=(",", ":"),
        )
        return bool(
            self.connection.set(
                self._idempotency_key(tenant_id, idempotency_key),
                payload,
                ex=self.idempotency_ttl_seconds,
                nx=True,
            )
        )

    def get_idempotent_job(
        self,
        *,
        tenant_id: str,
        idempotency_key: str,
    ) -> tuple[str, str] | None:
        raw = self.connection.get(self._idempotency_key(tenant_id, idempotency_key))
        if raw is None:
            return None
        payload = json.loads(raw)
        return str(payload["job_id"]), str(payload["request_fingerprint"])

    def status_counts(self) -> dict[str, int]:
        counts: Counter[str] = Counter()
        for key in self.connection.scan_iter(match="bug-agent:job:*"):
            raw = self.connection.get(key)
            if raw is None:
                continue
            try:
                counts[StoredJob.model_validate_json(raw).status] += 1
            except ValueError:
                continue
        return dict(counts)

    @staticmethod
    def _job_key(job_id: str) -> str:
        return f"bug-agent:job:{job_id}"

    @staticmethod
    def _idempotency_key(tenant_id: str, idempotency_key: str) -> str:
        digest = hashlib.sha256(
            f"{tenant_id}\0{idempotency_key}".encode("utf-8")
        ).hexdigest()
        return f"bug-agent:idempotency:{digest}"


def create_redis_connection(settings: JobQueueSettings | None = None) -> Redis:
    settings = settings or JobQueueSettings.from_env()
    return Redis.from_url(
        settings.redis_url,
        decode_responses=False,
        socket_connect_timeout=0.5,
        socket_timeout=1,
        health_check_interval=30,
    )


def create_job_store(
    connection: Redis | None = None,
    settings: JobQueueSettings | None = None,
) -> JobStore:
    settings = settings or JobQueueSettings.from_env()
    return JobStore(
        connection or create_redis_connection(settings),
        ttl_seconds=max(settings.result_ttl_seconds, settings.failure_ttl_seconds),
        idempotency_ttl_seconds=settings.idempotency_ttl_seconds,
    )
