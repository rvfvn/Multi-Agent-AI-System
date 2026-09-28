"""Requester Agent: coordinates the overall workflow.

    User question -> Specialist Agent (A2A) -> RAG result
                   -> Playwright fills + submits the support ticket form
                   -> Verifies confirmation

Run it directly, e.g.:

    python -m requester.agent "My account has been locked, what should I do?"

Make sure the Specialist Agent is running first:

    uvicorn specialist.server:app --reload
"""
from __future__ import annotations

import argparse
import math

from playwright.sync_api import Error as PlaywrightError

from requester.a2a_client import (
    CommunicationError,
    ProtocolError,
    SpecialistClient,
    TaskFailedError,
    TaskTimeoutError,
)
from requester.browser_flow import (
    CATEGORY_VALUE_MAP,
    submit_ticket,
    validate_browser_options,
)


def _failure(stage: str, message: str) -> dict:
    print(f"[Requester] {message}")
    return {"success": False, "stage": stage, "error": message}


def handle_request(
    question: str,
    base_url: str = "http://127.0.0.1:8000",
    timeout: float = 20.0,
    headless: bool = True,
    slow_mo: float = 0,
    keep_open: bool = False,
) -> dict:
    """Runs the full Requester Agent workflow for one user question.

    Returns a small dict summarizing the outcome, and never raises for
    the "expected" failure paths (connection failure, Specialist failure,
    timeout, missing result, or a Playwright/form failure) -- those are
    all reported back instead, per the project's failure-handling
    requirement.
    """
    if not isinstance(question, str) or not question.strip():
        return _failure("input", "Question must be a nonblank string.")
    if len(question) > 2000:
        return _failure("input", "Question must not exceed 2,000 characters.")
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout <= 0
    ):
        return _failure("input", "Polling timeout must be a finite number greater than 0.")

    try:
        validate_browser_options(headless, slow_mo, keep_open)
    except ValueError as exc:
        return _failure("input", str(exc))

    question = question.strip()
    client = SpecialistClient(base_url=base_url)
    print(f"[Requester] Submitting question to Specialist Agent: {question!r}")

    try:
        ack = client.submit_task(question)
        task_id = ack["task_id"]
        print(f"[Requester] Task submitted. task_id={task_id} status={ack['status']}")
        task = client.wait_for_result(task_id, timeout=timeout)
    except CommunicationError as exc:
        return _failure("communication", f"Could not communicate with Specialist Agent: {exc}")
    except ProtocolError as exc:
        return _failure("protocol", f"Invalid Specialist Agent response: {exc}")
    except TaskFailedError as exc:
        return _failure("specialist", f"Specialist Agent reported failure: {exc}")
    except TaskTimeoutError as exc:
        return _failure("timeout", f"Timed out waiting for Specialist Agent: {exc}")

    result = task.get("result")
    if not isinstance(result, dict):
        return _failure("no_result", "Specialist Agent returned no usable result object.")

    category = result.get("category")
    resolution = result.get("resolution")
    sources = result.get("sources")

    if (
        not isinstance(category, str)
        or not category.strip()
        or not isinstance(resolution, str)
        or not resolution.strip()
    ):
        return _failure("no_result", "Specialist Agent returned no usable category/resolution.")
    if (
        not isinstance(sources, list)
        or not sources
        or any(not isinstance(source, str) or not source.strip() for source in sources)
    ):
        return _failure("no_result", "Specialist Agent returned no usable source references.")

    category = category.strip()
    resolution = resolution.strip()
    if category.lower() not in CATEGORY_VALUE_MAP:
        return _failure("no_result", f"Support form does not support category: {category!r}.")

    print(f"[Requester] Specialist result -> category={category!r}, sources={sources}")
    print("[Requester] Filling out support ticket form via Playwright...")

    try:
        outcome = submit_ticket(
            issue=question, category=category, resolution=resolution,
            headless=headless, slow_mo=slow_mo, keep_open=keep_open,
        )
    except PlaywrightError as exc:
        return _failure("browser", f"Playwright could not submit the ticket: {exc}")

    if outcome["success"]:
        print(
            "[Requester] Support ticket submitted successfully. "
            f"Ticket ID: {outcome['ticket_id']}, Category: {outcome['category']}"
        )
        return {"success": True, "stage": "done", **outcome}

    message = f"Playwright could not submit the ticket: {outcome['error']}"
    print(f"[Requester] {message}")
    return {"success": False, "stage": "browser", "error": message}


def main() -> int:
    parser = argparse.ArgumentParser(description="Requester Agent")
    parser.add_argument("question", help="The user's support question")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="Base URL of the Specialist Agent's A2A service",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Polling timeout in seconds (excludes task submission and browser automation)",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Run the browser headed (visible) instead of headless",
    )
    parser.add_argument(
        "--slow-mo", type=float, default=0,
        help="Delay browser actions by this many milliseconds (requires --show-browser)",
    )
    parser.add_argument(
        "--keep-open", action="store_true",
        help="Wait for Enter after ticket verification (requires --show-browser)",
    )
    args = parser.parse_args()

    outcome = handle_request(
        args.question,
        base_url=args.base_url,
        timeout=args.timeout,
        headless=not args.show_browser,
        slow_mo=args.slow_mo,
        keep_open=args.keep_open,
    )

    return 0 if outcome["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
