import subprocess
import sys
from unittest.mock import Mock

import pytest
from playwright.sync_api import Error as PlaywrightError

from requester import agent
from requester.a2a_client import (
    CommunicationError,
    ProtocolError,
    TaskFailedError,
    TaskTimeoutError,
)


@pytest.fixture
def workflow(monkeypatch, envelope, support_result):
    client = Mock()
    client.submit_task.return_value = envelope()
    client.wait_for_result.return_value = envelope("completed")
    factory = Mock(return_value=client)
    browser = Mock(
        return_value={"success": True, "ticket_id": "12345", **support_result}
    )
    monkeypatch.setattr(agent, "SpecialistClient", factory)
    monkeypatch.setattr(agent, "submit_ticket", browser)
    return factory, client, browser


@pytest.mark.parametrize("question", [None, 2, "", "   ", "x" * 2001])
def test_invalid_question_never_submits(question, workflow):
    factory, _, browser = workflow
    result = agent.handle_request(question)
    assert result["stage"] == "input" and result["success"] is False
    factory.assert_not_called()
    browser.assert_not_called()


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True, "20"])
def test_invalid_timeout_never_submits(timeout, workflow):
    factory, _, browser = workflow
    assert agent.handle_request("question", timeout=timeout)["stage"] == "input"
    factory.assert_not_called()
    browser.assert_not_called()


def test_success_passes_exact_values(workflow):
    _, client, browser = workflow
    result = agent.handle_request("  Wi-Fi question  ", timeout=40, headless=False)
    assert result["success"] and result["stage"] == "done"
    client.submit_task.assert_called_once_with("Wi-Fi question")
    client.wait_for_result.assert_called_once_with("task-1", timeout=40)
    browser.assert_called_once_with(
        issue="Wi-Fi question",
        category="Network",
        resolution="Reconnect the device.",
        headless=False,
        slow_mo=0,
        keep_open=False,
    )


def test_question_length_boundary(workflow):
    assert agent.handle_request("x" * 2000)["success"]


@pytest.mark.parametrize("method", ["submit_task", "wait_for_result"])
@pytest.mark.parametrize(
    ("error", "stage"),
    [
        (CommunicationError("HTTP 422"), "communication"),
        (ProtocolError("bad response"), "protocol"),
        (TaskFailedError("failed"), "specialist"),
        (TaskTimeoutError("expired"), "timeout"),
    ],
)
def test_client_failures_never_launch_browser(method, error, stage, workflow):
    _, client, browser = workflow
    getattr(client, method).side_effect = error
    result = agent.handle_request("question")
    assert result["success"] is False and result["stage"] == stage
    assert str(error) in result["error"]
    browser.assert_not_called()


@pytest.mark.parametrize("value", [None, [], {}, "answer"])
def test_invalid_result_object(value, workflow):
    _, client, browser = workflow
    client.wait_for_result.return_value = {"result": value}
    assert agent.handle_request("question")["stage"] == "no_result"
    browser.assert_not_called()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("category", 7),
        ("category", " "),
        ("resolution", None),
        ("resolution", " "),
        ("sources", []),
        ("sources", "network.md"),
        ("sources", [None]),
        ("sources", [" "]),
        ("category", "Email"),
        ("category", "Security"),
        ("category", "Unknown"),
    ],
)
def test_invalid_or_unsupported_result(field, value, workflow):
    _, client, browser = workflow
    client.wait_for_result.return_value["result"][field] = value
    result = agent.handle_request("question")
    assert result["stage"] == "no_result" and result["success"] is False
    browser.assert_not_called()


@pytest.mark.parametrize("raises", [False, True])
def test_browser_failure(raises, workflow):
    _, _, browser = workflow
    if raises:
        browser.side_effect = PlaywrightError("launch failed")
    else:
        browser.return_value = {"success": False, "error": "confirmation mismatch"}
    result = agent.handle_request("question")
    assert result["stage"] == "browser" and result["success"] is False


@pytest.mark.parametrize("success", [True, False])
def test_main_exit_code(success, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["requester", "question"])
    monkeypatch.setattr(
        agent, "handle_request", Mock(return_value={"success": success})
    )
    assert agent.main() == (0 if success else 1)


def test_cli_invalid_input_returns_nonzero():
    process = subprocess.run(
        [sys.executable, "-m", "requester.agent", "   "],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert process.returncode == 1
    assert "nonblank" in process.stdout
    assert "Traceback" not in process.stderr


@pytest.mark.parametrize(
    "options",
    [
        {"slow_mo": -1},
        {"slow_mo": float("nan")},
        {"slow_mo": float("inf")},
        {"slow_mo": True},
        {"slow_mo": 500},
        {"keep_open": True},
    ],
)
def test_invalid_display_options_never_submit(options, workflow):
    factory, _, browser = workflow
    result = agent.handle_request("question", **options)
    assert result["stage"] == "input"
    factory.assert_not_called()
    browser.assert_not_called()


def test_visible_options_reach_browser(workflow):
    _, _, browser = workflow
    assert agent.handle_request(
        "question", headless=False, slow_mo=500, keep_open=True
    )["success"]
    assert browser.call_args.kwargs["slow_mo"] == 500
    assert browser.call_args.kwargs["keep_open"] is True
    assert browser.call_args.kwargs["headless"] is False


def test_cli_passes_visible_options(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        ["requester", "question", "--show-browser", "--slow-mo", "500", "--keep-open"],
    )
    handle = Mock(return_value={"success": True})
    monkeypatch.setattr(agent, "handle_request", handle)
    assert agent.main() == 0
    assert handle.call_args.kwargs["headless"] is False
    assert handle.call_args.kwargs["slow_mo"] == 500
    assert handle.call_args.kwargs["keep_open"] is True
