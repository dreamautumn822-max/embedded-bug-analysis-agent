import os
from uuid import uuid4

from locust import HttpUser, between, task


ANALYSIS_PAYLOAD = {
    "device_model": "LOADTEST-AX3000",
    "firmware_version": "v-loadtest",
    "symptom": "Firmware reload causes intermittent DHCP lease allocation failure",
    "logs": (
        "netifd: bridge br-lan reload started\n"
        "dhcpd: lease allocation failed bridge br-lan not ready"
    ),
    "module_hint": "network_dhcp",
}


class BugAgentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self) -> None:
        api_key = os.getenv("BUG_AGENT_LOADTEST_API_KEY", "").strip()
        self.headers = {"X-API-Key": api_key} if api_key else {}
        self.job_ids: list[str] = []

    @task(4)
    def enqueue_analysis(self) -> None:
        headers = {**self.headers, "Idempotency-Key": uuid4().hex}
        with self.client.post(
            "/v1/jobs",
            json=ANALYSIS_PAYLOAD,
            headers=headers,
            name="POST /v1/jobs",
            catch_response=True,
        ) as response:
            if response.status_code != 202:
                response.failure(f"enqueue returned {response.status_code}")
                return
            self.job_ids.append(response.json()["job_id"])

    @task(6)
    def poll_analysis(self) -> None:
        if not self.job_ids:
            return
        job_id = self.job_ids[0]
        with self.client.get(
            f"/v1/jobs/{job_id}",
            headers=self.headers,
            name="GET /v1/jobs/:id",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"poll returned {response.status_code}")
                return
            payload = response.json()
            status = payload["status"]
            if status == "pending_review":
                self._approve(job_id)
            elif status in {"completed", "failed", "cancelled", "timed_out"}:
                self.job_ids.pop(0)

    @task(1)
    def cancel_analysis(self) -> None:
        if len(self.job_ids) < 2:
            return
        job_id = self.job_ids.pop()
        self.client.delete(
            f"/v1/jobs/{job_id}",
            headers=self.headers,
            name="DELETE /v1/jobs/:id",
        )

    def _approve(self, job_id: str) -> None:
        self.client.post(
            f"/v1/jobs/{job_id}/review",
            headers=self.headers,
            json={
                "approved": True,
                "reviewer": "locust",
                "comment": "load-test review path",
            },
            name="POST /v1/jobs/:id/review",
        )
