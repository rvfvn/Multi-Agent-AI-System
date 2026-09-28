import socket
from unittest.mock import Mock

import pytest

from requester import agent
from tests.fake_specialist import create_app


def test_real_http_success_passes_result_to_browser(server_factory, monkeypatch):
    browser = Mock(
        return_value={
            "success": True,
            "ticket_id": "12345",
            "category": "Network",
            "resolution": "Simulated resolution: reconnect the device.",
        }
    )
    monkeypatch.setattr(agent, "submit_ticket", browser)
    outcome = agent.handle_request(
        "Network question", base_url=server_factory(create_app("success")), timeout=4
    )
    assert outcome["success"]
    browser.assert_called_once_with(
        issue="Network question",
        category="Network",
        resolution="Simulated resolution: reconnect the device.",
        headless=True,
    )


@pytest.mark.parametrize(
    ("scenario", "stage"),
    [
        ("failed", "specialist"),
        ("timeout", "timeout"),
        ("bad-json", "protocol"),
        ("malformed", "protocol"),
        ("http-error", "communication"),
        ("unsupported", "no_result"),
    ],
)
def test_real_http_failure_never_opens_browser(
    scenario, stage, server_factory, monkeypatch
):
    browser = Mock()
    monkeypatch.setattr(agent, "submit_ticket", browser)
    timeout = 0.15 if scenario == "timeout" else 4
    result = agent.handle_request(
        "question", base_url=server_factory(create_app(scenario)), timeout=timeout
    )
    assert result["success"] is False and result["stage"] == stage
    browser.assert_not_called()


def test_unavailable_server(monkeypatch):
    # Reserve, but do not listen on, an ephemeral port so it cannot be taken by another server.
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        browser = Mock()
        monkeypatch.setattr(agent, "submit_ticket", browser)
        result = agent.handle_request("question", base_url=f"http://127.0.0.1:{port}")
    assert result["stage"] == "communication"
    browser.assert_not_called()
