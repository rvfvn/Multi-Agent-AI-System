"""Submit Specialist-provided values to the unchanged support form and verify them."""
from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

CATEGORY_VALUE_MAP = {
    "account access": "account_access",
    "hardware": "hardware",
    "software": "software",
    "network": "network",
}
LAUNCH_TIMEOUT_MS = 15000
NAVIGATION_TIMEOUT_MS = 10000
INTERACTION_TIMEOUT_MS = 5000


def normalize_category(category: str) -> str:
    """Map only supported category labels to the form's select values."""
    if not isinstance(category, str) or not category.strip():
        raise ValueError("Category must be a nonblank string.")
    key = category.strip().lower()
    if key not in CATEGORY_VALUE_MAP:
        raise ValueError(f"Support form does not support category: {category!r}.")
    return CATEGORY_VALUE_MAP[key]


def submit_ticket(
    issue: str,
    category: str,
    resolution: str,
    app_path: str | None = None,
    headless: bool = True,
) -> dict:
    """Return a verified ticket or a controlled failure; timeouts are per operation."""
    for name, value in (("Issue", issue), ("Category", category), ("Resolution", resolution)):
        if not isinstance(value, str) or not value.strip():
            return {"success": False, "error": f"{name} must be a nonblank string."}

    issue = issue.strip()
    category = category.strip()
    resolution = resolution.strip()
    operation = "input validation"
    outcome = {"success": False, "error": "Browser workflow did not complete."}

    try:
        category_value = normalize_category(category)
        expected_category = category.lower().title()
        path = (
            Path(app_path) if app_path is not None
            else Path(__file__).resolve().parent.parent / "mock_support_app" / "index.html"
        ).resolve()
        if not path.is_file():
            raise ValueError(f"Support application file does not exist: {path}")

        operation = "Playwright startup"
        with sync_playwright() as p:
            browser = None
            try:
                operation = "browser launch"
                browser = p.chromium.launch(headless=headless, timeout=LAUNCH_TIMEOUT_MS)
                page = browser.new_page()
                page.set_default_timeout(INTERACTION_TIMEOUT_MS)
                page.set_default_navigation_timeout(NAVIGATION_TIMEOUT_MS)

                operation = "navigation"
                page.goto(path.as_uri())

                operation = "form interaction"
                page.fill("#issue", issue)
                page.select_option("#category", category_value)
                page.fill("#resolution", resolution)
                page.click("#submit-ticket")

                operation = "confirmation verification"
                page.wait_for_selector("#confirmation:not(.hidden)", state="visible")
                ticket_id = page.locator("#ticket-id").inner_text()
                shown_category = page.locator("#ticket-category").inner_text()
                shown_resolution = page.locator("#ticket-resolution").inner_text()

                if shown_category != expected_category:
                    raise ValueError("Confirmed category does not match the submitted category.")
                if shown_resolution != resolution:
                    raise ValueError("Confirmed resolution does not match the submitted resolution.")
                if re.fullmatch(r"[0-9]{5}", ticket_id) is None:
                    raise ValueError("Confirmed ticket ID must contain exactly five digits.")

                outcome = {
                    "success": True,
                    "ticket_id": ticket_id,
                    "category": shown_category,
                    "resolution": shown_resolution,
                }
            except (PlaywrightError, OSError, ValueError) as exc:
                outcome = {"success": False, "error": f"{operation} failed: {exc}"}
            finally:
                if browser is not None:
                    try:
                        browser.close()
                    except (PlaywrightError, OSError) as exc:
                        if outcome["success"]:
                            outcome = {"success": False, "error": f"Browser cleanup failed: {exc}"}
            operation = "Playwright cleanup"
    except (PlaywrightError, OSError, ValueError) as exc:
        # Preserve an earlier failure if stopping Playwright also fails.
        if outcome["success"] or outcome["error"] == "Browser workflow did not complete.":
            outcome = {"success": False, "error": f"{operation} failed: {exc}"}

    return outcome
