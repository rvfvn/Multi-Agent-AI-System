"""Offline browser boundary tests: no Chromium is launched."""

from unittest.mock import MagicMock, Mock

import pytest
from playwright.sync_api import Error as PlaywrightError

from requester import browser_flow


@pytest.mark.parametrize(
    "fields",
    [
        ("", "Network", "notes"),
        ("issue", None, "notes"),
        ("issue", "Network", " "),
        ("issue", "Email", "notes"),
        ("issue", "Security", "notes"),
        ("issue", "Unknown", "notes"),
        (123, "Network", "notes"),
    ],
)
def test_invalid_input_never_starts_playwright(fields, monkeypatch):
    start = Mock()
    monkeypatch.setattr(browser_flow, "sync_playwright", start)
    assert browser_flow.submit_ticket(*fields)["success"] is False
    start.assert_not_called()


def test_missing_app_never_starts_playwright(tmp_path, monkeypatch):
    start = Mock()
    monkeypatch.setattr(browser_flow, "sync_playwright", start)
    result = browser_flow.submit_ticket(
        "issue", "Network", "notes", app_path=tmp_path / "missing.html"
    )
    assert result["success"] is False and "does not exist" in result["error"]
    start.assert_not_called()


@pytest.fixture
def simulated_browser(monkeypatch):
    start = MagicMock()
    monkeypatch.setattr(browser_flow, "sync_playwright", start)
    p = start.return_value.__enter__.return_value
    browser = p.chromium.launch.return_value
    page = browser.new_page.return_value
    values = {
        "#ticket-id": "12345",
        "#ticket-category": "Network",
        "#ticket-resolution": "notes",
    }
    page.locator.side_effect = lambda selector: Mock(
        inner_text=Mock(return_value=values[selector]),
        text_content=Mock(return_value=values[selector]),
    )
    return start, p, browser, page, values


@pytest.mark.parametrize(
    "stage", ["launch", "navigation", "interaction", "verification", "cleanup"]
)
def test_browser_errors_are_reported_and_closed(stage, simulated_browser):
    _, p, browser, page, _ = simulated_browser
    operations = {
        "launch": p.chromium.launch,
        "navigation": page.goto,
        "interaction": page.fill,
        "verification": page.wait_for_selector,
        "cleanup": browser.close,
    }
    operations[stage].side_effect = PlaywrightError(f"{stage} failure")
    result = browser_flow.submit_ticket("issue", "Network", "notes")
    assert result["success"] is False and stage in result["error"].lower()
    if stage != "launch":
        browser.close.assert_called_once()


def test_original_error_survives_cleanup_failure(simulated_browser):
    _, _, browser, page, _ = simulated_browser
    page.goto.side_effect = PlaywrightError("original navigation failure")
    browser.close.side_effect = PlaywrightError("secondary cleanup failure")
    result = browser_flow.submit_ticket("issue", "Network", "notes")
    assert "original navigation failure" in result["error"]
    assert "secondary" not in result["error"]


def test_startup_failure(simulated_browser):
    start, _, _, _, _ = simulated_browser
    start.return_value.__enter__.side_effect = PlaywrightError("startup failed")
    assert not browser_flow.submit_ticket("issue", "Network", "notes")["success"]


@pytest.mark.parametrize(
    ("selector", "value"),
    [
        ("#ticket-category", "Hardware"),
        ("#ticket-resolution", "wrong notes"),
        ("#ticket-id", "123456"),
        ("#ticket-id", "abcde"),
    ],
)
def test_mismatched_confirmation_is_not_success(selector, value, simulated_browser):
    _, _, browser, _, values = simulated_browser
    values[selector] = value
    assert browser_flow.submit_ticket("issue", "Network", "notes")["success"] is False
    browser.close.assert_called_once()


def test_default_execution_never_prompts(simulated_browser, monkeypatch):
    prompt = Mock()
    monkeypatch.setattr("builtins.input", prompt)
    assert browser_flow.submit_ticket("issue", "Network", "notes")["success"]
    prompt.assert_not_called()


@pytest.mark.parametrize(
    "interruption", [None, EOFError(), KeyboardInterrupt(), OSError("no input")]
)
def test_pause_after_verification_still_closes_browser(
    interruption, simulated_browser, monkeypatch
):
    _, p, browser, _, _ = simulated_browser

    def pause(message):
        assert "Press Enter" in message
        browser.close.assert_not_called()
        if interruption is not None:
            raise interruption
        return ""

    prompt = Mock(side_effect=pause)
    monkeypatch.setattr("builtins.input", prompt)
    result = browser_flow.submit_ticket(
        "issue", "Network", "notes", headless=False, slow_mo=500, keep_open=True
    )
    assert result["success"]
    prompt.assert_called_once()
    p.chromium.launch.assert_called_once_with(
        headless=False, timeout=browser_flow.LAUNCH_TIMEOUT_MS, slow_mo=500
    )
    browser.close.assert_called_once()


def test_verification_failure_does_not_pause(simulated_browser, monkeypatch):
    _, _, browser, _, values = simulated_browser
    values["#ticket-id"] = "bad"
    prompt = Mock()
    monkeypatch.setattr("builtins.input", prompt)
    assert not browser_flow.submit_ticket(
        "issue", "Network", "notes", headless=False, keep_open=True
    )["success"]
    prompt.assert_not_called()
    browser.close.assert_called_once()


@pytest.mark.parametrize(
    "options", [{"slow_mo": -1}, {"slow_mo": 500}, {"keep_open": True}]
)
def test_direct_invalid_display_options_do_not_launch(options, monkeypatch):
    start = Mock()
    monkeypatch.setattr(browser_flow, "sync_playwright", start)
    assert not browser_flow.submit_ticket("issue", "Network", "notes", **options)[
        "success"
    ]
    start.assert_not_called()
