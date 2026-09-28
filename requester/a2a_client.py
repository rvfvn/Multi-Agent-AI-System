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


class ProtocolError(Exception):
    """The Specialist returned an invalid response."""


class CommunicationError(Exception):
    """An HTTP request to the Specialist failed."""


class SpecialistClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _request(method: str, url: str, **kwargs) -> requests.Response:
        try:
            response = requests.request(method, url, **kwargs)
        except requests.exceptions.Timeout as exc:
            raise CommunicationError(
                "HTTP request to the Specialist timed out"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise CommunicationError(
                "Could not connect to the Specialist"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise CommunicationError(
                "Could not send the request to the Specialist"
            ) from exc

        if method.upper() == "GET" and response.status_code == 404:
            raise TaskFailedError("Requested task was not found")

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            raise CommunicationError(
                f"Specialist returned HTTP {response.status_code}"
            ) from exc

        return response

    def _parse_response(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise ProtocolError(
                "Specialist returned invalid JSON"
            ) from exc

        return self.validate_response_envelope(data)

    def submit_task(self, question: str) -> dict:
        """POST /tasks -> immediate acknowledgment containing task_id + status."""
        response = self._request(
            "POST",
            f"{self.base_url}/tasks",
            json={"question": question},
            timeout=10,
        )
        data = self._parse_response(response)
        if data["status"] != "submitted":
            raise ProtocolError("Task acknowledgement must have a submitted status")
        return data

    def get_task(self, task_id: str, timeout: float = 10.0) -> dict:
        """GET /tasks/{task_id} -> current status, and result once completed."""
        response = self._request(
            "GET",
            f"{self.base_url}/tasks/{task_id}",
            timeout=timeout,
        )
        data = self._parse_response(response)
        if data["task_id"] != task_id:
            raise ProtocolError("Specialist returned a different task_id")
        return data

    def wait_for_result(
        self,
        task_id: str,
        timeout: float = 20.0,
        poll_interval: float = 1.0,
    ) -> dict:
        """Poll GET /tasks/{task_id} until status is 'completed' or 'failed',
        or raise TaskTimeoutError once `timeout` seconds have elapsed."""
        if timeout <= 0:
            raise ValueError("Timeout needs to be a value greater than 0")
        if poll_interval <= 0:
            raise ValueError("The poll interval needs to be a value greater than 0")
        deadline = time.monotonic() + timeout
        status = None

        while True:
            remainingBudget = deadline - time.monotonic()
            if remainingBudget <= 0:
                raise TaskTimeoutError(
                    f"Task {task_id} did not complete within {timeout}s "
                    f"(last known status: {status!r})"
                )
            task = self.get_task(task_id, timeout=min(10.0, remainingBudget))
            remainingBudget = deadline - time.monotonic()
            if remainingBudget <= 0:
                raise TaskTimeoutError(f"Task {task_id} did not complete within {timeout}s")
            status = task.get("status")
            if status == "completed":
                return task
            if status == "failed":
                raise TaskFailedError(task.get("error") or "Specialist task failed")
            remainingBudget = deadline - time.monotonic()
            if remainingBudget > 0:
                time.sleep(min(poll_interval, remainingBudget))

    @staticmethod
    def validate_response_envelope(data: object) -> dict:
        if not isinstance(data, dict):
            raise ProtocolError("Specialist response must be a JSON object")
        required = {"task_id", "status", "result", "error"}
        if not required.issubset(data):
            raise ProtocolError("Specialist response is missing required fields")
        task_id = data["task_id"]
        if not isinstance(task_id, str) or not task_id.strip():
            raise ProtocolError("Specialist response has an invalid task_id")
        status = data["status"]
        allowed = {"submitted", "working", "completed", "failed"}
        if not isinstance(status, str) or status not in allowed:
            raise ProtocolError("Specialist response has an invalid status")
        if status == "completed":
            if not isinstance(data["result"], dict):
                raise ProtocolError("Completed task must contain a result object")
        elif data["result"] is not None:
            raise ProtocolError("Unfinished or failed task must have a null result")
        if status == "failed":
            error = data["error"]
            if not isinstance(error, str) or not error.strip():
                raise ProtocolError("Failed task must contain an error message")
        elif data["error"] is not None:
            raise ProtocolError("Nonfailed task must have a null error")

        return data
