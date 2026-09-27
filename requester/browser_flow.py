"""Playwright automation for mock_support_app/index.html.

Takes the category/resolution produced by the Specialist Agent and uses
them to actually fill out and submit the support ticket form, then
verifies the confirmation panel appeared.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

# The <select> uses lowercase, underscored values; the Specialist Agent
# returns human-readable labels like "Network" or "Account Access".
CATEGORY_VALUE_MAP = {
    "account access": "account_access",
    "hardware": "hardware",
    "software": "software",
    "network": "network",
}


def normalize_category(category: str) -> str:
    """Map a free-text category from the Specialist to a valid <select> value."""
    key = category.strip().lower()
    return CATEGORY_VALUE_MAP.get(key, key.replace(" ", "_"))


def submit_ticket(
    issue: str,
    category: str,
    resolution: str,
    app_path: Optional[str] = None,
    headless: bool = True,
) -> dict:
    """Open the mock support app, fill the form with info from the
    Specialist Agent's result, submit it, and verify the confirmation.

    Returns e.g.:
        {"success": True, "ticket_id": "48213", "category": "Network",
         "resolution": "..."}
        {"success": False, "error": "..."}
    """
    if app_path is None:
        app_path = str(
            Path(__file__).resolve().parent.parent
            / "mock_support_app"
            / "index.html"
        )

    file_url = Path(app_path).resolve().as_uri()
    category_value = normalize_category(category)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(file_url)

        page.fill("#issue", issue)
        page.select_option("#category", category_value)
        page.fill("#resolution", resolution)
        page.click("#submit-ticket")

        try:
            page.wait_for_selector("#confirmation:not(.hidden)", timeout=5000)
        except Exception:
            error_locator = page.locator("#error")
            error_text = error_locator.inner_text() if error_locator.is_visible() else None
            browser.close()
            return {
                "success": False,
                "error": error_text or "Confirmation panel did not appear",
            }

        ticket_id = page.locator("#ticket-id").inner_text()
        shown_category = page.locator("#ticket-category").inner_text()
        shown_resolution = page.locator("#ticket-resolution").inner_text()

        browser.close()

        return {
            "success": True,
            "ticket_id": ticket_id,
            "category": shown_category,
            "resolution": shown_resolution,
        }
