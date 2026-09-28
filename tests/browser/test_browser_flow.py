import re
from pathlib import Path

import pytest

from requester import browser_flow

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "mock_support_app"


@pytest.mark.parametrize(
    "category", ["Account Access", "Network", "Hardware", "Software"]
)
def test_submits_and_verifies_supported_category(category):
    result = browser_flow.submit_ticket(
        "  Test issue  ", category, "  Verify identity.\nThen follow guidance.  "
    )
    assert result["success"], result
    assert result["category"] == category
    assert result["resolution"] == "Verify identity.\nThen follow guidance."
    assert re.fullmatch(r"[0-9]{5}", result["ticket_id"])


def copied_app(tmp_path, javascript):
    for name in ["index.html", "style.css"]:
        (tmp_path / name).write_text((APP / name).read_text())
    (tmp_path / "script.js").write_text(javascript)
    return tmp_path / "index.html"


@pytest.mark.parametrize(
    ("selector", "value"),
    [
        ("#ticket-category", "Wrong"),
        ("#ticket-resolution", "Wrong"),
        ("#ticket-id", "1234"),
    ],
)
def test_detects_wrong_confirmation_in_temporary_copy(selector, value, tmp_path):
    script = (APP / "script.js").read_text()
    script += f'\ndocument.getElementById("ticket-form").addEventListener("submit", () => {{ document.querySelector("{selector}").textContent = "{value}"; }});'
    path = copied_app(tmp_path, script)
    result = browser_flow.submit_ticket("issue", "Network", "notes", app_path=path)
    assert result["success"] is False
    assert "verification" in result["error"]


def test_missing_confirmation_is_bounded(tmp_path, monkeypatch):
    script = 'document.getElementById("ticket-form").addEventListener("submit", e => e.preventDefault());'
    path = copied_app(tmp_path, script)
    monkeypatch.setattr(browser_flow, "INTERACTION_TIMEOUT_MS", 750)
    result = browser_flow.submit_ticket("issue", "Network", "notes", app_path=path)
    assert result["success"] is False and "verification" in result["error"]


@pytest.mark.parametrize("missing", ["issue", "category", "resolution"])
def test_unchanged_form_rejects_blank_fields(page, missing):
    page.goto((APP / "index.html").as_uri())
    if missing != "issue":
        page.fill("#issue", "issue")
    if missing != "category":
        page.select_option("#category", "network")
    if missing != "resolution":
        page.fill("#resolution", "notes")
    page.click("#submit-ticket")
    assert page.locator("#error").is_visible()
    assert (
        page.locator("#error").inner_text()
        == "Please fill out all fields before submitting."
    )
    assert not page.locator("#confirmation").is_visible()
