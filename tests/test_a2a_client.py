from unittest.mock import Mock

import pytest
import requests

from requester.a2a_client import (
    CommunicationError,
    ProtocolError,
    SpecialistClient,
    TaskFailedError,
    TaskTimeoutError,
)


@pytest.mark.parametrize("method", ["submit", "get"])
def test_http_request_contract(method, monkeypatch, envelope, http_response):
    request = Mock(return_value=http_response(envelope()))
    monkeypatch.setattr(requests, "request", request)
    client = SpecialistClient("http://localhost:8000/")
    if method == "submit":
        assert client.submit_task("Wi-Fi?") == envelope()
        request.assert_called_once_with(
            "POST",
            "http://localhost:8000/tasks",
            json={"question": "Wi-Fi?"},
            timeout=10,
        )
    else:
        assert client.get_task("task-1", timeout=0.3) == envelope()
        request.assert_called_once_with(
            "GET", "http://localhost:8000/tasks/task-1", timeout=0.3
        )


@pytest.mark.parametrize("field", ["timeout", "poll_interval"])
@pytest.mark.parametrize("value", [0, -1])
def test_nonpositive_settings_do_not_poll(field, value, monkeypatch):
    client = SpecialistClient()
    get = Mock()
    monkeypatch.setattr(client, "get_task", get)
    with pytest.raises(ValueError):
        client.wait_for_result("task-1", **{field: value})
    get.assert_not_called()


def test_poll_transitions_to_completed(monkeypatch, clock, envelope):
    client = SpecialistClient()
    get = Mock(side_effect=[envelope(), envelope("working"), envelope("completed")])
    monkeypatch.setattr(client, "get_task", get)
    assert client.wait_for_result("task-1", timeout=20) == envelope("completed")
    assert get.call_count == 3
    assert clock.sleeps == [1, 1]
    assert all(call.kwargs["timeout"] <= 10 for call in get.call_args_list)


def test_remaining_budget_limits_get_sleep_and_next_poll(monkeypatch, clock, envelope):
    client = SpecialistClient()

    def get(task_id, timeout):
        assert timeout == pytest.approx(0.8)
        clock.advance(0.6)
        return envelope("working")

    mocked = Mock(side_effect=get)
    monkeypatch.setattr(client, "get_task", mocked)
    with pytest.raises(TaskTimeoutError):
        client.wait_for_result("task-1", timeout=0.8)
    mocked.assert_called_once()
    assert clock.sleeps == pytest.approx([0.2])


def test_expired_before_first_get(monkeypatch):
    from requester import a2a_client

    client = SpecialistClient()
    get = Mock()
    monkeypatch.setattr(client, "get_task", get)
    monkeypatch.setattr(a2a_client, "time", Mock(monotonic=Mock(side_effect=[0, 2])))
    with pytest.raises(TaskTimeoutError):
        client.wait_for_result("task-1", timeout=1)
    get.assert_not_called()


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_late_response_is_timeout(status, monkeypatch, clock, envelope):
    client = SpecialistClient()

    def get(*args, **kwargs):
        clock.advance(2)
        return envelope(status)

    monkeypatch.setattr(client, "get_task", get)
    with pytest.raises(TaskTimeoutError):
        client.wait_for_result("task-1", timeout=1)
    assert clock.sleeps == []


def test_failed_task_stops_immediately(monkeypatch, clock, envelope):
    client = SpecialistClient()
    monkeypatch.setattr(client, "get_task", Mock(return_value=envelope("failed")))
    with pytest.raises(TaskFailedError, match="No relevant"):
        client.wait_for_result("task-1")
    assert clock.sleeps == []


@pytest.mark.parametrize(
    "data",
    [
        None,
        [],
        {},
        {"task_id": "t"},
        {"task_id": "t", "status": "working", "error": None},
    ],
)
def test_invalid_envelope_structure(data):
    with pytest.raises(ProtocolError):
        SpecialistClient.validate_response_envelope(data)


@pytest.mark.parametrize(
    "changes",
    [
        {"task_id": ""},
        {"task_id": 3},
        {"status": "done"},
        {"status": []},
        {"result": {}},
        {"error": "unexpected"},
        {"status": "completed", "result": None},
        {"status": "failed", "error": " "},
        {"status": "failed", "error": 2},
    ],
)
def test_invalid_envelope_fields(changes, envelope):
    with pytest.raises(ProtocolError):
        SpecialistClient.validate_response_envelope(envelope(**changes))


@pytest.mark.parametrize("status", ["submitted", "working", "completed", "failed"])
def test_valid_status_envelopes(status, envelope):
    assert SpecialistClient.validate_response_envelope(envelope(status)) == envelope(
        status
    )


def test_mismatched_task_id(monkeypatch, http_response, envelope):
    monkeypatch.setattr(
        requests, "request", Mock(return_value=http_response(envelope(task_id="other")))
    )
    with pytest.raises(ProtocolError, match="different task_id"):
        SpecialistClient().get_task("task-1")


def test_ack_must_be_submitted(monkeypatch, http_response, envelope):
    monkeypatch.setattr(
        requests, "request", Mock(return_value=http_response(envelope("working")))
    )
    with pytest.raises(ProtocolError, match="submitted"):
        SpecialistClient().submit_task("question")


@pytest.mark.parametrize("method", ["submit_task", "get_task"])
@pytest.mark.parametrize(
    "error",
    [requests.Timeout(), requests.ConnectionError(), requests.RequestException()],
)
def test_transport_errors_are_wrapped(method, error, monkeypatch):
    monkeypatch.setattr(requests, "request", Mock(side_effect=error))
    with pytest.raises(CommunicationError):
        getattr(SpecialistClient(), method)("question-or-id")


@pytest.mark.parametrize("method", ["submit_task", "get_task"])
@pytest.mark.parametrize("status", [422, 500])
def test_http_errors_are_wrapped(method, status, monkeypatch, http_response):
    monkeypatch.setattr(
        requests, "request", Mock(return_value=http_response(status=status))
    )
    with pytest.raises(CommunicationError, match=str(status)):
        getattr(SpecialistClient(), method)("question-or-id")


def test_unknown_task_is_failed(monkeypatch, http_response):
    monkeypatch.setattr(
        requests, "request", Mock(return_value=http_response(status=404))
    )
    with pytest.raises(TaskFailedError):
        SpecialistClient().get_task("missing")


@pytest.mark.parametrize("method", ["submit_task", "get_task"])
def test_invalid_json_is_protocol_error(method, monkeypatch, http_response):
    monkeypatch.setattr(
        requests, "request", Mock(return_value=http_response(raw=b"not json"))
    )
    with pytest.raises(ProtocolError, match="JSON"):
        getattr(SpecialistClient(), method)("question-or-id")
