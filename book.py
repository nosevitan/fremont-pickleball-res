#!/usr/bin/env python3
"""
Fremont Pickleball Court Auto-Booker

Automatically books pickleball courts at Fremont Tennis Center
via the ActiveNet reservation system at 7:30am PT daily.

Usage:
    python book.py              # Run once (for cron)
    python book.py --dry-run    # Preview what would be booked
    python book.py --date 2026-05-05  # Book for specific date
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()

# --- Config ---
BASE_URL = "https://anc.apm.activecommunities.com/fremont"
QUICK_RES_URL = f"{BASE_URL}/reservation/landing/quick?groupId=6"
LOGIN_URL = BASE_URL

USERNAME = os.getenv("ACTIVENET_USERNAME", "")
PASSWORD = os.getenv("ACTIVENET_PASSWORD", "")

PREFERRED_COURTS = [
    c.strip() for c in os.getenv(
        "PREFERRED_COURTS",
        "FTC Pickleball Court A,FTC Pickleball Court B,FTC Pickleball Court C,FTC Pickleball Court D"
    ).split(",")
]

BOOK_START_HOUR = int(os.getenv("BOOK_START_HOUR", "16"))
BOOK_END_HOUR = int(os.getenv("BOOK_END_HOUR", "18"))
DAYS_AHEAD = int(os.getenv("DAYS_AHEAD", "2"))

# Desired time slots (30-min increments from 4:00 PM to 5:30 PM = 4 slots covering 4-6pm)
TARGET_SLOTS = []
for h in range(BOOK_START_HOUR, BOOK_END_HOUR):
    for m in [0, 30]:
        period = "AM" if h < 12 else "PM"
        display_h = h if h <= 12 else h - 12
        TARGET_SLOTS.append(f"{display_h}:{m:02d} {period}")

# Setup logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"book_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# Screenshots for debugging
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def take_screenshot(page, name):
    path = SCREENSHOT_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{name}.png"
    page.screenshot(path=str(path))
    log.info(f"Screenshot saved: {path}")


def login(page):
    """Sign in to ActiveNet."""
    log.info("Navigating to site...")
    page.goto(BASE_URL, wait_until="networkidle", timeout=30000)

    # Click Sign In link
    log.info("Clicking Sign In...")
    page.click("text=Sign In")
    page.wait_for_timeout(2000)

    # Fill login form
    log.info(f"Logging in as {USERNAME}...")
    username_input = page.locator("input[type='text'][name='weblogin_username'], input[id*='username'], input[placeholder*='User'], input[placeholder*='Login']").first
    username_input.fill(USERNAME)

    password_input = page.locator("input[type='password']").first
    password_input.fill(PASSWORD)

    take_screenshot(page, "login_filled")

    # Submit
    page.locator("button:has-text('Sign In'), button:has-text('Log In'), input[type='submit']").first.click()
    page.wait_for_timeout(3000)

    # Verify login success
    take_screenshot(page, "after_login")

    # Check if still on login page or got an error
    if page.locator("text=Invalid").count() > 0:
        log.error("Login failed - invalid credentials")
        return False

    log.info("Login successful!")
    return True


def navigate_to_date(page, target_date):
    """Navigate the quick reservation calendar to the target date."""
    log.info(f"Navigating to quick reservation page...")
    page.goto(QUICK_RES_URL, wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(3000)

    take_screenshot(page, "quick_res_loaded")

    # Click the date picker to change date
    date_text = page.locator(".quick-reservation-date, [class*='date-picker'], [class*='datepicker']").first
    current_date_text = date_text.text_content() if date_text.count() > 0 else ""
    log.info(f"Current date shown: {current_date_text}")

    # Format target date for comparison
    target_formatted = target_date.strftime("%a, %b %-d, %Y")
    log.info(f"Target date: {target_formatted}")

    if target_formatted.lower() not in current_date_text.lower().replace("  ", " "):
        # Need to change the date - click the date and navigate
        log.info("Changing date...")
        date_text.click()
        page.wait_for_timeout(1000)

        take_screenshot(page, "date_picker_open")

        # Navigate forward to the target date
        # The calendar shows month view, we need to click forward arrows and then the day
        target_day = target_date.day
        target_month = target_date.strftime("%B %Y")

        # Keep clicking next month until we find the right month
        for _ in range(6):
            calendar_header = page.locator("[class*='calendar'] [class*='header'], [class*='month-year'], .datepicker-switch, [class*='title']")
            if calendar_header.count() > 0:
                header_text = calendar_header.first.text_content()
                if target_month.lower() in header_text.lower():
                    break
            # Click next month arrow
            next_btn = page.locator("[class*='calendar'] [class*='next'], [class*='right-arrow'], .next, [aria-label='Next Month']")
            if next_btn.count() > 0:
                next_btn.first.click()
                page.wait_for_timeout(500)

        # Click the target day
        day_button = page.locator(f"[class*='calendar'] button:has-text('{target_day}'), [class*='calendar'] td:has-text('{target_day}'), [class*='day']:has-text('{target_day}')")
        if day_button.count() > 0:
            day_button.first.click()
            page.wait_for_timeout(2000)
            log.info(f"Selected date: {target_formatted}")
        else:
            log.warning(f"Could not find day {target_day} in calendar, trying direct URL approach")
            # Try URL-based date navigation
            date_str = target_date.strftime("%Y-%m-%d")
            page.goto(f"{QUICK_RES_URL}&date={date_str}", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

    take_screenshot(page, "correct_date")
    return True


def find_and_book_slots(page, dry_run=False):
    """Find available slots in the 4-6pm range and book them."""
    log.info(f"Looking for available slots between {BOOK_START_HOUR}:00 and {BOOK_END_HOUR}:00...")

    take_screenshot(page, "before_booking")

    # Read the grid to find available slots
    # The grid has rows (courts) and columns (time slots)
    # Available slots are clickable cells that aren't marked as reserved/unavailable

    booked = []

    for court_name in PREFERRED_COURTS:
        log.info(f"Checking court: {court_name}")

        # Find the row for this court
        court_link = page.locator(f"a:has-text('{court_name}')")
        if court_link.count() == 0:
            # Try partial match
            short_name = court_name.split("Court ")[-1] if "Court" in court_name else court_name
            court_link = page.locator(f"a:has-text('{short_name}')")

        if court_link.count() == 0:
            log.warning(f"Court '{court_name}' not found on page")
            continue

        # Get the parent row
        court_row = court_link.first.locator("xpath=ancestor::tr | ancestor::div[contains(@class, 'row')]").first

        # Find available time slots in this row
        # Available slots are typically td/div elements that are clickable and in our time range
        available_cells = court_row.locator("td[class*='available'], td:not([class*='unavailable']):not([class*='reserved']):not([class*='header']), div[class*='slot'][class*='available']")

        if available_cells.count() == 0:
            # Try clicking cells in the time columns directly
            # The grid columns correspond to time slots
            log.info(f"Trying direct cell selection for {court_name}...")

            # Scroll to make 4pm visible
            page.evaluate("document.querySelector('[class*=\"grid\"], [class*=\"schedule\"], table').scrollLeft = 500")
            page.wait_for_timeout(500)

        # Try to find and click cells at our target times
        for target_time in TARGET_SLOTS:
            log.info(f"  Looking for {target_time} slot...")

            # Find the column header matching this time
            time_header = page.locator(f"th:has-text('{target_time}'), td:has-text('{target_time}'), div[class*='header']:has-text('{target_time}')")
            if time_header.count() == 0:
                log.info(f"  Time column '{target_time}' not visible, scrolling...")
                # Scroll the grid to find this time
                page.evaluate("""
                    const headers = document.querySelectorAll('th, [class*="header"]');
                    for (const h of headers) {
                        if (h.textContent.includes('%s')) {
                            h.scrollIntoView({inline: 'center'});
                            break;
                        }
                    }
                """ % target_time)
                page.wait_for_timeout(500)
                time_header = page.locator(f"th:has-text('{target_time}'), td:has-text('{target_time}')")

            if time_header.count() > 0:
                # Get the column index
                col_index = page.evaluate("""
                    (headerText) => {
                        const headers = document.querySelectorAll('th, [role="columnheader"]');
                        for (let i = 0; i < headers.length; i++) {
                            if (headers[i].textContent.trim().includes(headerText)) return i;
                        }
                        return -1;
                    }
                """, target_time)

                if col_index >= 0:
                    # Find the cell at this column in the court's row
                    # Use the court name to identify the row
                    cell = page.evaluate("""
                        ([courtName, colIdx]) => {
                            const rows = document.querySelectorAll('tr, [role="row"]');
                            for (const row of rows) {
                                if (row.textContent.includes(courtName)) {
                                    const cells = row.querySelectorAll('td, [role="gridcell"]');
                                    if (cells[colIdx]) {
                                        const cls = cells[colIdx].className || '';
                                        return {
                                            available: !cls.includes('unavailable') && !cls.includes('reserved') && !cls.includes('closed'),
                                            className: cls
                                        };
                                    }
                                }
                            }
                            return null;
                        }
                    """, [court_name, col_index])

                    if cell and cell.get("available"):
                        log.info(f"  AVAILABLE: {court_name} at {target_time}")
                        if not dry_run:
                            # Click the cell to start booking
                            page.evaluate("""
                                ([courtName, colIdx]) => {
                                    const rows = document.querySelectorAll('tr, [role="row"]');
                                    for (const row of rows) {
                                        if (row.textContent.includes(courtName)) {
                                            const cells = row.querySelectorAll('td, [role="gridcell"]');
                                            if (cells[colIdx]) cells[colIdx].click();
                                            break;
                                        }
                                    }
                                }
                            """, [court_name, col_index])
                            page.wait_for_timeout(2000)
                            take_screenshot(page, f"clicked_{court_name}_{target_time}".replace(" ", "_").replace(":", ""))

                            booked.append(f"{court_name} @ {target_time}")
                            # After clicking, we may need to handle a booking dialog
                            # Break to handle one court at a time
                            break
                    else:
                        log.info(f"  NOT available: {court_name} at {target_time} (class: {cell.get('className', 'unknown') if cell else 'not found'})")

        if booked:
            break  # We found a slot, handle the booking flow

    return booked


def complete_booking(page):
    """Handle the post-click booking flow (add to cart, checkout)."""
    log.info("Completing booking flow...")

    take_screenshot(page, "booking_dialog")

    # Look for "Add to Cart" or "Reserve" button
    add_to_cart = page.locator("button:has-text('Add to Cart'), button:has-text('Reserve'), button:has-text('Add To Cart'), button:has-text('Book')")
    if add_to_cart.count() > 0:
        log.info("Clicking 'Add to Cart'...")
        add_to_cart.first.click()
        page.wait_for_timeout(3000)
        take_screenshot(page, "added_to_cart")

    # Navigate to cart / checkout
    checkout_btn = page.locator("button:has-text('Checkout'), a:has-text('Checkout'), button:has-text('Proceed'), a:has-text('My Cart')")
    if checkout_btn.count() > 0:
        log.info("Proceeding to checkout...")
        checkout_btn.first.click()
        page.wait_for_timeout(3000)
        take_screenshot(page, "checkout")

    # Look for final confirmation / accept terms
    agree_checkbox = page.locator("input[type='checkbox'][id*='agree'], input[type='checkbox'][id*='waiver'], input[type='checkbox'][id*='term']")
    if agree_checkbox.count() > 0:
        log.info("Accepting terms...")
        agree_checkbox.first.check()
        page.wait_for_timeout(500)

    # Final submit
    submit_btn = page.locator("button:has-text('Complete'), button:has-text('Submit'), button:has-text('Confirm'), button:has-text('Place Order')")
    if submit_btn.count() > 0:
        log.info("Submitting reservation...")
        submit_btn.first.click()
        page.wait_for_timeout(5000)
        take_screenshot(page, "confirmation")
        log.info("Booking submitted!")
        return True

    log.warning("Could not find checkout/submit buttons - may need manual completion")
    take_screenshot(page, "booking_incomplete")
    return False


def run(dry_run=False, target_date=None):
    """Main booking flow."""
    if not USERNAME or not PASSWORD:
        log.error("Missing credentials! Set ACTIVENET_USERNAME and ACTIVENET_PASSWORD in .env")
        sys.exit(1)

    if target_date is None:
        target_date = datetime.now() + timedelta(days=DAYS_AHEAD)

    log.info(f"=== Fremont Pickleball Auto-Booker ===")
    log.info(f"Target date: {target_date.strftime('%A, %B %d, %Y')}")
    log.info(f"Time range: {BOOK_START_HOUR}:00 - {BOOK_END_HOUR}:00")
    log.info(f"Preferred courts: {', '.join(PREFERRED_COURTS)}")
    log.info(f"Dry run: {dry_run}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        page.set_default_timeout(15000)

        try:
            # Step 1: Login
            if not login(page):
                log.error("Login failed, aborting")
                browser.close()
                return False

            # Step 2: Navigate to target date
            navigate_to_date(page, target_date)

            # Step 3: Find and book slots
            booked = find_and_book_slots(page, dry_run=dry_run)

            if not booked:
                log.warning("No available slots found in the target time range")
                take_screenshot(page, "no_slots")
                browser.close()
                return False

            log.info(f"Selected slots: {booked}")

            if dry_run:
                log.info("DRY RUN - skipping checkout")
                browser.close()
                return True

            # Step 4: Complete booking
            success = complete_booking(page)
            browser.close()
            return success

        except PlaywrightTimeout as e:
            log.error(f"Timeout error: {e}")
            take_screenshot(page, "timeout_error")
            browser.close()
            return False
        except Exception as e:
            log.error(f"Unexpected error: {e}", exc_info=True)
            take_screenshot(page, "error")
            browser.close()
            return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fremont Pickleball Court Auto-Booker")
    parser.add_argument("--dry-run", action="store_true", help="Preview without booking")
    parser.add_argument("--date", type=str, help="Target date (YYYY-MM-DD)")
    args = parser.parse_args()

    target = None
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d")

    success = run(dry_run=args.dry_run, target_date=target)
    sys.exit(0 if success else 1)
