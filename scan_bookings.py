#!/usr/bin/env python3
"""
Scan upcoming pickleball bookings from ActiveNet account.
Uses the family schedule API. Saves results as UPCOMING_BOOKINGS GitHub variable.
"""

import os
import sys
import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://anc.apm.activecommunities.com/fremont"
USERNAME = os.getenv("ACTIVENET_USERNAME", "")
PASSWORD = os.getenv("ACTIVENET_PASSWORD", "")
PT = ZoneInfo("America/Los_Angeles")


def scan():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        page.set_default_timeout(15000)

        # Login
        page.goto(f"{BASE_URL}/signin", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)
        page.locator("input[type='email'], input[placeholder*='Email']").first.fill(USERNAME)
        page.locator("input[type='password']").first.fill(PASSWORD)
        page.locator("button:has-text('Sign in')").first.click()
        page.wait_for_url(lambda url: "/signin" not in url, timeout=15000)
        page.wait_for_timeout(2000)

        # Navigate to family schedule to establish session
        page.goto(
            f"{BASE_URL}/myaccount/familymemberschedule?memberIds=86022&view=3",
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(3000)

        # Fetch schedule via API (handles CSRF/cookies automatically)
        today = datetime.now(PT)
        start_date = today.strftime("%Y-%m-%d")
        end_date = (today + timedelta(days=30)).strftime("%Y-%m-%d")

        data = page.evaluate("""
            async ([startDate, endDate]) => {
                try {
                    const resp = await fetch(
                        `/fremont/rest/myaccount/familyschedules?start_date=${startDate}&end_date=${endDate}&locale=en-US`,
                        { credentials: 'include' }
                    );
                    return await resp.json();
                } catch (e) {
                    return { error: e.message };
                }
            }
        """, [start_date, end_date])

        browser.close()

        # Parse response: body.schedules[]
        bookings = []
        schedules = []
        if isinstance(data, dict):
            body = data.get("body", {})
            if isinstance(body, dict):
                schedules = body.get("schedules", [])

        for item in schedules:
            facilities = item.get("facilities", [])
            facility_name = facilities[0]["facility_name"] if facilities else ""
            centers = item.get("centers", [])
            center_name = centers[0]["name"] if centers else ""

            bookings.append({
                "date": item.get("schedule_date", ""),
                "time": item.get("time_text", ""),
                "court": facility_name,
                "center": center_name,
                "event": item.get("activity_name", ""),
            })

        # Sort by date
        bookings.sort(key=lambda b: b.get("date", ""))

        # Only keep future bookings
        today_str = today.strftime("%Y-%m-%d")
        bookings = [b for b in bookings if b.get("date", "") >= today_str]

        return bookings


if __name__ == "__main__":
    bookings = scan()
    result = json.dumps(bookings)
    print(f"Found {len(bookings)} upcoming bookings")
    for b in bookings:
        print(f"  - {b['date']} {b['time']} @ {b['court']}")

    if os.getenv("GITHUB_ACTIONS"):
        subprocess.run(
            ["gh", "variable", "set", "UPCOMING_BOOKINGS", "--body", result,
             "--repo", "nosevitan/fremont-pickleball-res"],
            check=True
        )
        print("Saved to UPCOMING_BOOKINGS variable")
    else:
        print(json.dumps(bookings, indent=2))
