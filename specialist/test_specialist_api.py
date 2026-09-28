from unittest.mock import patch

from fastapi.testclient import TestClient

from specialist.models import SpecialistResult
from specialist.server import app


client = TestClient(app)


def test_successful_task():
    fake_result = SpecialistResult(
        category="Network",
        resolution="Reconnect the device.",
        sources=["network.md"],
    )

    with patch(
        "specialist.agent.answer_support_question",
        return_value=fake_result,
    ):
        response = client.post(
            "/tasks",
            json={
                "question": "My Wi-Fi is broken."
            },
        )

        assert response.status_code == 200

        acknowledgment = response.json()
        assert acknowledgment["status"] == "submitted"

        task_id = acknowledgment["task_id"]

        result = client.get(f"/tasks/{task_id}").json()

        assert result["status"] == "completed"
        assert result["result"]["category"] == "Network"


def test_failed_task():
    with patch(
        "specialist.agent.answer_support_question",
        side_effect=ValueError("No relevant information."),
    ):
        response = client.post(
            "/tasks",
            json={
                "question": "An unsupported question"
            },
        )

        task_id = response.json()["task_id"]
        result = client.get(f"/tasks/{task_id}").json()

        assert result["status"] == "failed"
        assert result["error"] == "No relevant information."


def test_empty_question():
    response = client.post(
        "/tasks",
        json={"question": "   "},
    )

    assert response.status_code == 422