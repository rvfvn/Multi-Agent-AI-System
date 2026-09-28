"""Simple A2A-style client for the Requester Agent to talk to the
Specialist Agent's FastAPI task service (specialist/server.py).

Contract (see specialist/models.py):
    POST /tasks            body: {"question": str}
                           returns: {"task_id", "status", "result": null, "error": null}
    GET  /tasks/{task_id}  returns the same shape, with "status" one of
                           "submitted" | "working" | "completed" | "failed"
"""
from __future__ import annotations

import time

import requests


class TaskFailedError(Exception):
    """Raised when the Specialist Agent reports status == 'failed'."""


class TaskTimeoutError(Exception):
    """Raised when polling exceeds the allowed timeout without completing."""


class SpecialistClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    def submit_task(self, question: str) -> dict:
        """POST /tasks -> immediate acknowledgment containing task_id + status."""
        response = requests.post(
            f"{self.base_url}/tasks",
            json={"question": question},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_task(self, task_id: str) -> dict:
        """GET /tasks/{task_id} -> current status, and result once completed."""
        response = requests.get(f"{self.base_url}/tasks/{task_id}", timeout=10)
        if response.status_code == 404:
            raise TaskFailedError(f"Task {task_id} not found on Specialist Agent")
        response.raise_for_status()
        return response.json()

    def wait_for_result(
        self,
        task_id: str,
        timeout: float = 20.0,
        poll_interval: float = 1.0,
    ) -> dict:
        """Poll GET /tasks/{task_id} until status is 'completed' or 'failed',
        or raise TaskTimeoutError once `timeout` seconds have elapsed."""
        deadline = time.monotonic() + timeout

        while True:
            task = self.get_task(task_id)
            status = task.get("status")

            if status == "completed":
                return task
            if status == "failed":
                raise TaskFailedError(task.get("error") or "Specialist task failed")

            if time.monotonic() >= deadline:
                raise TaskTimeoutError(
                    f"Task {task_id} did not complete within {timeout}s "
                    f"(last known status: {status!r})"
                )

            time.sleep(poll_interval)
