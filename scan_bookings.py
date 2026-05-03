#!/usr/bin/env python3
"""
Scan upcoming pickleball bookings from ActiveNet account.
Saves results as a JSON GitHub variable (UPCOMING_BOOKINGS).
"""

import os
import sys
import json
import subprocess
from datetime import datetime
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

        # Go to upcoming reservations
        page.goto(f"{BASE_URL}/reservation/reservations", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # Try to find reservation entries
        bookings = page.evaluate("""
            () => {
                const results = [];
                // Look for reservation cards/rows
                const items = document.querySelectorAll(
                    '[class*="reservation-item"], [class*="booking"], tr[class*="reservation"], ' +
                    '[class*="card"], [class*="event-item"], [class*="list-item"]'
                );

                for (const item of items) {
                    const text = item.textContent || '';
                    // Only include pickleball-related entries
                    if (text.toLowerCase().includes('pickleball') || text.toLowerCase().includes('ftc')) {
                        results.push(text.replace(/\\s+/g, ' ').trim().substring(0, 200));
                    }
                }

                // If no structured items found, try to get all text that mentions pickleball
                if (results.length === 0) {
                    const allText = document.body.innerText;
                    const lines = allText.split('\\n').filter(l =>
                        l.toLowerCase().includes('pickleball') || l.toLowerCase().includes('ftc')
                    );
                    for (const line of lines.slice(0, 20)) {
                        const trimmed = line.trim();
                        if (trimmed.length > 10) results.push(trimmed.substring(0, 200));
                    }
                }

                return results;
            }
        """)

        # Also try the account page for reservations
        if not bookings:
            page.goto(f"{BASE_URL}/myaccount", wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Look for upcoming reservations section
            reservations_link = page.locator("a:has-text('Reservations'), a:has-text('Upcoming'), a:has-text('My Reservations')")
            if reservations_link.count() > 0:
                reservations_link.first.click()
                page.wait_for_timeout(3000)

                bookings = page.evaluate("""
                    () => {
                        const text = document.body.innerText;
                        const lines = text.split('\\n').filter(l =>
                            l.toLowerCase().includes('pickleball') || l.toLowerCase().includes('ftc') || l.toLowerCase().includes('court')
                        );
                        return lines.filter(l => l.trim().length > 10).map(l => l.trim().substring(0, 200)).slice(0, 20);
                    }
                """)

        browser.close()

        # Format as structured data
        formatted = []
        for b in bookings:
            formatted.append({"description": b})

        return formatted


if __name__ == "__main__":
    bookings = scan()
    result = json.dumps(bookings)
    print(f"Found {len(bookings)} upcoming bookings")
    for b in bookings:
        print(f"  - {b['description']}")

    # Save to GitHub variable if running in CI
    if os.getenv("GITHUB_ACTIONS"):
        subprocess.run(
            ["gh", "variable", "set", "UPCOMING_BOOKINGS", "--body", result,
             "--repo", "nosevitan/fremont-pickleball-res"],
            check=True
        )
        print("Saved to UPCOMING_BOOKINGS variable")
    else:
        print(json.dumps(bookings, indent=2))
