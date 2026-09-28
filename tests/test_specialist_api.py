import threading
from unittest.mock import Mock
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from groq import APIConnectionError

from requester.a2a_client import SpecialistClient
from specialist import agent
from specialist.models import SpecialistResult
from specialist.server import app


@pytest.fixture
def api_client():
    with TestClient(app) as client:
        yield client


def test_successful_task(api_client, monkeypatch, support_result):
    answer = Mock(return_value=SpecialistResult(**support_result))
    monkeypatch.setattr(agent, "answer_support_question", answer)
    response = api_client.post("/tasks", json={"question": "  My Wi-Fi is broken.  "})
    assert response.status_code == 200
    ack = response.json()
    assert (
        ack["status"] == "submitted" and ack["result"] is None and ack["error"] is None
    )
    UUID(ack["task_id"])
    task = api_client.get(f"/tasks/{ack['task_id']}").json()
    assert (
        task["status"] == "completed"
        and task["result"] == support_result
        and task["error"] is None
    )
    answer.assert_called_once_with("My Wi-Fi is broken.")


@pytest.mark.parametrize(
    "error",
    [
        ValueError("No relevant information."),
        RuntimeError("retrieval failed"),
        APIConnectionError(request=httpx.Request("POST", "https://example.invalid")),
    ],
)
def test_failed_task(api_client, monkeypatch, error):
    monkeypatch.setattr(agent, "answer_support_question", Mock(side_effect=error))
    ack = api_client.post("/tasks", json={"question": "question"}).json()
    task = api_client.get(f"/tasks/{ack['task_id']}").json()
    assert task["status"] == "failed" and task["result"] is None
    assert task["error"] == str(error)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"question": ""},
        {"question": "   "},
        {"question": None},
        {"question": 2},
        {"question": "x" * 2001},
    ],
)
def test_invalid_question(api_client, monkeypatch, payload):
    answer = Mock()
    monkeypatch.setattr(agent, "answer_support_question", answer)
    assert api_client.post("/tasks", json=payload).status_code == 422
    answer.assert_not_called()
    assert agent.tasks == {}


def test_unknown_task(api_client):
    assert api_client.get("/tasks/missing").status_code == 404


def test_tasks_are_unique_and_isolated(api_client, monkeypatch):
    def answer(question):
        return SpecialistResult(
            category="Network", resolution=question, sources=["network.md"]
        )

    monkeypatch.setattr(agent, "answer_support_question", answer)
    first = api_client.post("/tasks", json={"question": "first"}).json()
    second = api_client.post("/tasks", json={"question": "second"}).json()
    assert first["task_id"] != second["task_id"]
    for ack, expected in [(first, "first"), (second, "second")]:
        task = api_client.get(f"/tasks/{ack['task_id']}").json()
        assert task["result"]["resolution"] == expected


def test_real_http_ack_before_work_finishes(
    monkeypatch, server_factory, support_result
):
    entered, release = threading.Event(), threading.Event()

    def answer(question):
        entered.set()
        if not release.wait(timeout=5):
            raise RuntimeError("Test did not release worker")
        return SpecialistResult(**support_result)

    monkeypatch.setattr(agent, "answer_support_question", answer)
    client = SpecialistClient(server_factory(app))
    try:
        ack = client.submit_task("question")
        assert ack["status"] == "submitted"
        assert entered.wait(timeout=2)
        assert not release.is_set()
        assert client.get_task(ack["task_id"])["status"] == "working"
    finally:
        release.set()
    assert (
        client.wait_for_result(ack["task_id"], timeout=3, poll_interval=0.01)["result"]
        == support_result
    )
