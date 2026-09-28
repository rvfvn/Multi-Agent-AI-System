import json
import re
from pathlib import Path
from unittest.mock import Mock

import pytest

from requester import agent
from requester.a2a_client import SpecialistClient

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "test_cases.json").read_text())
SUPPORTED_CASES = [
    case
    for case in CASES
    if case["expected_category"]
    in {"Account Access", "Network", "Hardware", "Software"}
]


@pytest.fixture
def observed_tasks(monkeypatch):
    tasks = []

    class ObservedClient(SpecialistClient):
        def wait_for_result(self, *args, **kwargs):
            task = super().wait_for_result(*args, **kwargs)
            tasks.append(task)
            return task

    monkeypatch.setattr(agent, "SpecialistClient", ObservedClient)
    return tasks


@pytest.mark.parametrize(
    "case", SUPPORTED_CASES, ids=lambda case: case["expected_category"]
)
def test_live_ticket(case, live_service, observed_tasks, request):
    outcome = agent.handle_request(
        case["request"],
        base_url=live_service,
        timeout=request.config.getoption("--live-timeout"),
    )
    assert outcome["success"], outcome
    result = observed_tasks[0]["result"]
    assert result["category"] == case["expected_category"]
    assert outcome["category"] == result["category"]
    assert outcome["resolution"] == result["resolution"].strip()
    assert re.fullmatch(r"[0-9]{5}", outcome["ticket_id"])
    assert result["sources"]
    assert all(
        (ROOT / "knowledge_base" / source).is_file() for source in result["sources"]
    )
    print(
        f"Verified {case['expected_category']}: sources={result['sources']}, ticket={outcome['ticket_id']}"
    )


@pytest.mark.parametrize(
    ("question", "category"),
    [
        (CASES[4]["request"], "Email"),
        ("I suspect my account was compromised and see suspicious logins.", "Security"),
    ],
)
def test_live_classification_without_browser(
    question, category, live_service, observed_tasks, monkeypatch, request
):
    browser = Mock()
    monkeypatch.setattr(agent, "submit_ticket", browser)
    outcome = agent.handle_request(
        question,
        base_url=live_service,
        timeout=request.config.getoption("--live-timeout"),
    )
    assert observed_tasks and observed_tasks[0]["result"]["category"] == category
    assert outcome["success"] is False and outcome["stage"] == "no_result"
    browser.assert_not_called()
