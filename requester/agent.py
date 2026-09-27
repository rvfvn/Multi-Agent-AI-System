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

import requests

from requester.a2a_client import SpecialistClient, TaskFailedError, TaskTimeoutError
from requester.browser_flow import submit_ticket


def handle_request(
    question: str,
    base_url: str = "http://127.0.0.1:8000",
    timeout: float = 20.0,
    headless: bool = True,
) -> dict:
    """Runs the full Requester Agent workflow for one user question.

    Returns a small dict summarizing the outcome, and never raises for
    the "expected" failure paths (connection failure, Specialist failure,
    timeout, missing result, or a Playwright/form failure) -- those are
    all reported back instead, per the project's failure-handling
    requirement.
    """
    client = SpecialistClient(base_url=base_url)

    print(f"[Requester] Submitting question to Specialist Agent: {question!r}")

    try:
        ack = client.submit_task(question)
    except requests.exceptions.ConnectionError:
        message = (
            "Could not reach the Specialist Agent. "
            f"Is it running at {base_url}?"
        )
        print(f"[Requester] {message}")
        return {"success": False, "stage": "connection", "error": message}

    task_id = ack["task_id"]
    print(f"[Requester] Task submitted. task_id={task_id} status={ack['status']}")

    try:
        task = client.wait_for_result(task_id, timeout=timeout)
    except TaskFailedError as exc:
        message = f"Specialist Agent reported failure: {exc}"
        print(f"[Requester] {message}")
        return {"success": False, "stage": "specialist", "error": message}
    except TaskTimeoutError as exc:
        message = f"Timed out waiting for Specialist Agent: {exc}"
        print(f"[Requester] {message}")
        return {"success": False, "stage": "timeout", "error": message}

    result = task.get("result") or {}
    category = result.get("category")
    resolution = result.get("resolution")
    sources = result.get("sources", [])

    if not category or not resolution:
        message = "Specialist Agent returned no usable category/resolution."
        print(f"[Requester] {message}")
        return {"success": False, "stage": "no_result", "error": message}

    print(f"[Requester] Specialist result -> category={category!r}, sources={sources}")
    print("[Requester] Filling out support ticket form via Playwright...")

    outcome = submit_ticket(
        issue=question,
        category=category,
        resolution=resolution,
        headless=headless,
    )

    if outcome["success"]:
        print(
            "[Requester] Support ticket submitted successfully. "
            f"Ticket ID: {outcome['ticket_id']}, Category: {outcome['category']}"
        )
        return {"success": True, "stage": "done", **outcome}

    message = f"Playwright could not submit the ticket: {outcome['error']}"
    print(f"[Requester] {message}")
    return {"success": False, "stage": "browser", "error": message}


def main() -> None:
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
        help="Seconds to wait for the Specialist Agent before giving up",
    )
    parser.add_argument(
        "--show-browser",
        action="store_true",
        help="Run the browser headed (visible) instead of headless",
    )
    args = parser.parse_args()

    handle_request(
        args.question,
        base_url=args.base_url,
        timeout=args.timeout,
        headless=not args.show_browser,
    )


if __name__ == "__main__":
    main()