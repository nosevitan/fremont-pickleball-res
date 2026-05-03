#!/usr/bin/env python3
"""
Fremont Pickleball Court Auto-Booker (v2 -- Playwright + JS injection)

Books pickleball courts on the ActiveNet platform 7 days in advance.
Pre-warms browser at 7:28am PT, fires booking request at 7:30:00.000 sharp.

Usage:
    python book.py                       # Wait until 7:30am PT, book 7 days out
    python book.py --now                 # Book immediately (no 7:30 wait)
    python book.py --dry-run             # Preview without booking
    python book.py --date 2026-05-09     # Book for a specific date
    python book.py --now --dry-run       # Preview immediately
"""

import os
import sys
import json
import time
import logging
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
load_dotenv(Path(__file__).parent / ".env")

BASE_URL = "https://anc.apm.activecommunities.com/fremont"
LOGIN_URL = f"{BASE_URL}/signin"
QUICK_RES_URL = f"{BASE_URL}/reservation/landing/quick?groupId=6"

USERNAME = os.getenv("ACTIVENET_USERNAME", "")
PASSWORD = os.getenv("ACTIVENET_PASSWORD", "")
CUSTOMER_ID = int(os.getenv("ACTIVENET_CUSTOMER_ID", "86022"))

TOGGLE_FILE = Path(__file__).parent / "toggle.json"
DAYS_AHEAD = 7
PT = ZoneInfo("America/Los_Angeles")

# Courts in priority order
PREFERRED_COURTS = [
    ("FTC Pickleball Court D", 368),
    ("FTC Pickleball Court C", 367),
    ("FTC Pickleball Court A", 365),
    ("FTC Pickleball Court B", 366),
    ("FTC Orange Ball/Pickleball Court 1", 361),
    ("FTC Orange Ball/Pickleball Court 2", 362),
    ("FTC Orange Ball/Pickleball Court 3", 363),
]

# Target 30-min slot start times (24h format) -- covers the 4:00-6:00pm window
TARGET_SLOTS_24H = ["16:00:00", "16:30:00", "17:00:00", "17:30:00"]

# Matching aria-label fragments (12h display)
TARGET_SLOTS_DISPLAY = [
    ("4:00 PM", "4:30 PM"),
    ("4:30 PM", "5:00 PM"),
    ("5:00 PM", "5:30 PM"),
    ("5:30 PM", "6:00 PM"),
]

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / f"book_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("booker")


def screenshot(page, name: str):
    """Save a timestamped screenshot."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = SCREENSHOT_DIR / f"{ts}_{name}.png"
    try:
        page.screenshot(path=str(path), full_page=False)
        log.info(f"Screenshot: {path}")
    except Exception as e:
        log.warning(f"Screenshot failed ({name}): {e}")


# ---------------------------------------------------------------------------
# Toggle check
# ---------------------------------------------------------------------------
def check_toggle() -> bool:
    """Return True if toggle.json says enabled, or if file is missing (default on)."""
    if not TOGGLE_FILE.exists():
        log.info("toggle.json not found -- defaulting to enabled")
        return True
    try:
        data = json.loads(TOGGLE_FILE.read_text())
        enabled = data.get("enabled", True)
        log.info(f"toggle.json => enabled={enabled}")
        return enabled
    except Exception as e:
        log.warning(f"Error reading toggle.json: {e} -- defaulting to enabled")
        return True


# ---------------------------------------------------------------------------
# Wait for 7:30am PT
# ---------------------------------------------------------------------------
def wait_for_launch_time():
    """Block until 7:30:00.000 PT. Returns immediately if already past."""
    now_pt = datetime.now(PT)
    launch = now_pt.replace(hour=7, minute=30, second=0, microsecond=0)
    if now_pt >= launch:
        log.info("Already past 7:30am PT -- proceeding immediately")
        return
    delta = (launch - now_pt).total_seconds()
    log.info(f"Waiting {delta:.1f}s until 7:30:00 PT ...")
    # Sleep in chunks so we can log progress
    while True:
        now_pt = datetime.now(PT)
        remaining = (launch - now_pt).total_seconds()
        if remaining <= 0:
            break
        if remaining > 5:
            log.info(f"  T-{remaining:.0f}s ...")
            time.sleep(min(remaining - 2, 30))
        elif remaining > 0.05:
            time.sleep(0.01)  # Tight spin for last 5 seconds
        else:
            break
    log.info("7:30:00 PT reached -- GO!")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def login(page, retries=3) -> bool:
    """Log in via the /signin page. Retries on failure."""
    for attempt in range(1, retries + 1):
        log.info(f"Login attempt {attempt}/{retries}")
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(2000)

            # Fill email
            email_input = page.locator("input[type='email'], input[placeholder*='Email'], input[name*='email'], input[id*='email']").first
            email_input.wait_for(state="visible", timeout=10_000)
            email_input.fill(USERNAME)

            # Fill password
            pw_input = page.locator("input[type='password']").first
            pw_input.fill(PASSWORD)

            screenshot(page, "login_filled")

            # Click Sign In
            page.locator("button:has-text('Sign in'), button:has-text('Sign In'), button:has-text('Log In')").first.click()
            log.info("Clicked Sign In, waiting for navigation...")

            # Wait for redirect away from signin page
            page.wait_for_url(lambda url: "/signin" not in url, timeout=15_000)
            page.wait_for_timeout(2000)

            screenshot(page, "login_success")

            # Verify we are logged in -- look for account menu or absence of sign-in link
            if page.locator("text=Invalid").count() > 0 or page.locator("text=incorrect").count() > 0:
                log.error("Login rejected -- bad credentials?")
                continue

            log.info("Login successful")
            return True

        except PlaywrightTimeout:
            log.warning(f"Login attempt {attempt} timed out")
            screenshot(page, f"login_timeout_{attempt}")
        except Exception as e:
            log.warning(f"Login attempt {attempt} failed: {e}")
            screenshot(page, f"login_error_{attempt}")

    log.error("All login attempts failed")
    return False


# ---------------------------------------------------------------------------
# Navigate to quick-reservation page for target date
# ---------------------------------------------------------------------------
def navigate_to_reservation(page, target_date: datetime, retries=3) -> bool:
    """Navigate to the quick reservation grid for the target date."""
    date_str = target_date.strftime("%Y-%m-%d")

    for attempt in range(1, retries + 1):
        log.info(f"Nav attempt {attempt}: loading reservation page for {date_str}")
        try:
            page.goto(QUICK_RES_URL, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_timeout(3000)

            screenshot(page, "quick_res_loaded")

            # The page defaults to today. We need to navigate to target_date.
            # Use the date picker: click the displayed date, then navigate the calendar.
            # First, try clicking forward arrow enough times.
            # Alternatively, type the date directly into any date input.

            # Strategy: click the date element to open the datepicker
            date_display = page.locator("[class*='date-display'], [class*='date-picker'], .an-date-picker, button[class*='date']").first
            if date_display.count() > 0:
                date_display.click()
                page.wait_for_timeout(1000)

                # Navigate forward day by day using the forward arrow
                today = datetime.now(PT).date()
                target = target_date.date() if hasattr(target_date, 'date') else target_date
                days_forward = (target - today).days

                if days_forward > 0:
                    # Click the "next day" / forward arrow
                    for _ in range(days_forward):
                        next_btn = page.locator(
                            "button[aria-label='Next Day'], "
                            "button[class*='next'], "
                            "button[class*='forward'], "
                            "[class*='arrow-right'], "
                            "[class*='chevron-right']"
                        ).first
                        if next_btn.count() > 0:
                            next_btn.click()
                            page.wait_for_timeout(300)
                        else:
                            break

                page.wait_for_timeout(2000)
                screenshot(page, "date_navigated")

            # Verify the grid loaded -- look for grid cells
            grid_cells = page.locator(".grid-cell, [class*='grid-cell']")
            grid_cells.first.wait_for(state="visible", timeout=15_000)
            cell_count = grid_cells.count()
            log.info(f"Grid loaded with {cell_count} cells")
            screenshot(page, "grid_ready")
            return True

        except PlaywrightTimeout:
            log.warning(f"Nav attempt {attempt} timed out")
            screenshot(page, f"nav_timeout_{attempt}")
        except Exception as e:
            log.warning(f"Nav attempt {attempt} failed: {e}")
            screenshot(page, f"nav_error_{attempt}")

    log.error("Failed to load reservation grid")
    return False


# ---------------------------------------------------------------------------
# Scan grid for available slots using aria-labels
# ---------------------------------------------------------------------------
def scan_availability(page) -> list[dict]:
    """
    Scan the grid using aria-labels to find available court+time combos.
    Returns a list of dicts: {court_name, resource_id, slot_24h, slot_display, element_index}
    sorted by preference (court priority, then time order).
    """
    results = []

    for court_name, resource_id in PREFERRED_COURTS:
        for slot_24h, (start_display, end_display) in zip(TARGET_SLOTS_24H, TARGET_SLOTS_DISPLAY):
            # aria-label pattern: "FTC Pickleball Court A 4:00 PM - 4:30 PM Available"
            available_label = f"{court_name} {start_display} - {end_display} Available"
            unavailable_label = f"{court_name} {start_display} - {end_display} Unavailable"

            # Check for available cell
            available_cell = page.locator(f"[aria-label='{available_label}']")
            if available_cell.count() > 0:
                log.info(f"  AVAILABLE: {court_name} @ {start_display}-{end_display}")
                results.append({
                    "court_name": court_name,
                    "resource_id": resource_id,
                    "slot_24h": slot_24h,
                    "start_display": start_display,
                    "end_display": end_display,
                    "aria_label": available_label,
                })
            else:
                # Check if unavailable (confirming the cell exists)
                unavail = page.locator(f"[aria-label='{unavailable_label}']")
                if unavail.count() > 0:
                    log.info(f"  Unavailable: {court_name} @ {start_display}-{end_display}")
                else:
                    log.info(f"  Not found: {court_name} @ {start_display}-{end_display}")

    return results


# ---------------------------------------------------------------------------
# Book via API (fast path) -- inject fetch from browser context
# ---------------------------------------------------------------------------
def book_via_api(page, target_date: datetime, resource_id: int, slot_24h_list, court_name: str) -> bool:
    """
    Fire the booking API directly from the browser context so cookies/CSRF
    are handled automatically. Two calls: availability check, then process.
    """
    date_str = target_date.strftime("%Y-%m-%d")

    # Step 1: Availability call (may be required to prime the session)
    avail_body = {
        "facility_group_id": 6,
        "customer_id": CUSTOMER_ID,
        "company_id": 0,
        "reserve_date": date_str,
        "start_time": "07:30:00",
        "end_time": "22:00:00",
        "resident": False,
        "reload": False,
        "change_time_range": False,
    }

    log.info(f"API: checking availability for {date_str} ...")
    avail_result = page.evaluate("""
        async (body) => {
            try {
                const resp = await fetch('/fremont/rest/reservation/quickreservation/availability', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body),
                    credentials: 'include',
                });
                const data = await resp.json();
                return {ok: resp.ok, status: resp.status, data: data};
            } catch (e) {
                return {ok: false, error: e.message};
            }
        }
    """, avail_body)

    log.info(f"API availability response: status={avail_result.get('status')}, ok={avail_result.get('ok')}")
    if not avail_result.get("ok"):
        log.warning(f"Availability call failed: {avail_result}")
        # Continue anyway -- the process call might still work

    # Step 2: Process (actual booking)
    process_body = {
        "facility_group_id": 6,
        "customer_id": CUSTOMER_ID,
        "company_id": 0,
        "reserve_date": date_str,
        "start_time": "07:30:00",
        "end_time": "22:00:00",
        "time_increment": 30,
        "selected_resources": [
            {
                "bookings": slot_24h_list if isinstance(slot_24h_list, list) else [slot_24h_list],
                "attendance": 1,
                "package_id": 0,
                "resource_id": resource_id,
            }
        ],
        "event_name": "Pickleball",
        "process_type": "INIT",
        "waiver_reservation_checked": False,
        "reno": -1,
        "last_modify_timestamp": -1,
    }

    slots_display = slot_24h_list if isinstance(slot_24h_list, list) else [slot_24h_list]
    log.info(f"API: booking {court_name} @ {slots_display} on {date_str} (resource_id={resource_id}) ...")
    process_result = page.evaluate("""
        async (body) => {
            try {
                const resp = await fetch('/fremont/rest/reservation/quickreservation/process', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body),
                    credentials: 'include',
                });
                const data = await resp.json();
                return {ok: resp.ok, status: resp.status, data: data};
            } catch (e) {
                return {ok: false, error: e.message};
            }
        }
    """, process_body)

    log.info(f"API process response: status={process_result.get('status')}, ok={process_result.get('ok')}")

    if process_result.get("ok"):
        resp_data = process_result.get("data", {})
        # Check for error in response body
        if isinstance(resp_data, dict):
            errors = resp_data.get("errors") or resp_data.get("error_messages") or resp_data.get("message")
            if errors:
                log.warning(f"API returned errors: {errors}")
                return False

            # Check for success indicators
            reno = resp_data.get("reno") or resp_data.get("reservation_number")
            if reno and reno != -1:
                log.info(f"BOOKING CONFIRMED via API! Reservation: {reno}")
                return True

            # Check for waiver step
            process_type = resp_data.get("process_type")
            if process_type == "WAIVER" or resp_data.get("waiver_required"):
                log.info("Waiver step detected, confirming waiver ...")
                return handle_waiver_api(page, process_body, resp_data)

            log.info(f"API response data: {json.dumps(resp_data, indent=2)[:2000]}")
            # If we got a 200 with data and no errors, likely success
            return True
    else:
        log.error(f"API booking failed: {process_result}")
        return False

    return False


def handle_waiver_api(page, original_body: dict, waiver_response: dict) -> bool:
    """Handle the waiver confirmation step via API."""
    waiver_body = dict(original_body)
    waiver_body["process_type"] = "CONFIRM"
    waiver_body["waiver_reservation_checked"] = True

    # Pull reno and timestamp from waiver response if available
    if "reno" in waiver_response:
        waiver_body["reno"] = waiver_response["reno"]
    if "last_modify_timestamp" in waiver_response:
        waiver_body["last_modify_timestamp"] = waiver_response["last_modify_timestamp"]

    log.info("API: confirming waiver ...")
    result = page.evaluate("""
        async (body) => {
            try {
                const resp = await fetch('/fremont/rest/reservation/quickreservation/process', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(body),
                    credentials: 'include',
                });
                const data = await resp.json();
                return {ok: resp.ok, status: resp.status, data: data};
            } catch (e) {
                return {ok: false, error: e.message};
            }
        }
    """, waiver_body)

    log.info(f"Waiver confirm response: {result.get('status')}, ok={result.get('ok')}")
    if result.get("ok"):
        resp_data = result.get("data", {})
        reno = resp_data.get("reno") or resp_data.get("reservation_number")
        if reno and reno != -1:
            log.info(f"BOOKING CONFIRMED after waiver! Reservation: {reno}")
        else:
            log.info(f"Waiver response: {json.dumps(resp_data, indent=2)[:1000]}")
        return True

    log.error(f"Waiver confirmation failed: {result}")
    return False


# ---------------------------------------------------------------------------
# Fallback: Book via UI clicks
# ---------------------------------------------------------------------------
def book_via_ui(page, aria_label: str, dry_run: bool) -> bool:
    """Click the grid cell, then Confirm, then handle waiver/Reserve."""
    log.info(f"UI fallback: clicking cell with aria-label='{aria_label}'")

    cell = page.locator(f"[aria-label='{aria_label}']").first
    cell.click()
    page.wait_for_timeout(2000)
    screenshot(page, "cell_clicked")

    if dry_run:
        log.info("DRY RUN -- stopping before confirm")
        return True

    # Look for "Confirm bookings" button
    confirm_btn = page.locator(
        "button:has-text('Confirm bookings'), "
        "button:has-text('Confirm Bookings'), "
        "button:has-text('Confirm'), "
        "button:has-text('Reserve')"
    )
    for attempt in range(5):
        if confirm_btn.count() > 0:
            break
        page.wait_for_timeout(1000)
        log.info(f"Waiting for Confirm button ... (attempt {attempt + 1})")

    if confirm_btn.count() > 0:
        log.info("Clicking 'Confirm bookings'")
        confirm_btn.first.click()
        page.wait_for_timeout(3000)
        screenshot(page, "after_confirm")
    else:
        log.warning("No confirm button found")
        screenshot(page, "no_confirm_btn")
        return False

    # Handle waiver checkbox if present
    waiver_cb = page.locator("input[type='checkbox']")
    if waiver_cb.count() > 0:
        log.info("Checking waiver checkbox")
        waiver_cb.first.check()
        page.wait_for_timeout(500)

    # Click Reserve / Submit
    reserve_btn = page.locator(
        "button:has-text('Reserve'), "
        "button:has-text('Submit'), "
        "button:has-text('Complete')"
    )
    if reserve_btn.count() > 0:
        log.info("Clicking 'Reserve'")
        reserve_btn.first.click()
        page.wait_for_timeout(5000)
        screenshot(page, "reserved")
        log.info("UI booking submitted!")
        return True

    log.warning("Could not find Reserve button")
    screenshot(page, "no_reserve_btn")
    return False


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------
def run(dry_run: bool = False, target_date=None, skip_wait: bool = False):
    if not USERNAME or not PASSWORD:
        log.error("Missing credentials. Set ACTIVENET_USERNAME and ACTIVENET_PASSWORD in .env")
        sys.exit(1)

    if not check_toggle():
        log.info("Toggle is OFF -- exiting without booking")
        return False

    # Determine target date (7 days from now by default)
    if target_date is None:
        target_date = datetime.now(PT) + timedelta(days=DAYS_AHEAD)
    elif target_date.tzinfo is None:
        target_date = target_date.replace(tzinfo=PT)

    date_str = target_date.strftime("%Y-%m-%d")
    log.info("=" * 60)
    log.info("Fremont Pickleball Auto-Booker v2")
    log.info(f"  Target date : {target_date.strftime('%A, %B %d, %Y')} ({date_str})")
    log.info(f"  Target slots: {', '.join(s[0] + '-' + s[1] for s in TARGET_SLOTS_DISPLAY)}")
    log.info(f"  Courts      : {', '.join(c[0] for c in PREFERRED_COURTS)}")
    log.info(f"  Dry run     : {dry_run}")
    log.info(f"  Skip wait   : {skip_wait}")
    log.info("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        page.set_default_timeout(20_000)

        try:
            # ----------------------------------------------------------
            # Phase 1: Pre-warm (login + navigate) -- do this BEFORE 7:30
            # ----------------------------------------------------------
            if not skip_wait:
                # We want to be ready by 7:28am, then wait for 7:30
                now_pt = datetime.now(PT)
                prewarm_time = now_pt.replace(hour=7, minute=28, second=0, microsecond=0)
                if now_pt < prewarm_time:
                    delta = (prewarm_time - now_pt).total_seconds()
                    log.info(f"Sleeping {delta:.0f}s until 7:28am PT for pre-warm ...")
                    time.sleep(max(0, delta))

            log.info("--- Phase 1: Login ---")
            if not login(page):
                log.error("Login failed, aborting")
                browser.close()
                return False

            log.info("--- Phase 2: Navigate to reservation page ---")
            if not navigate_to_reservation(page, target_date):
                log.error("Failed to load reservation grid, aborting")
                browser.close()
                return False

            # ----------------------------------------------------------
            # Phase 2: Wait for 7:30am sharp (if not --now)
            # ----------------------------------------------------------
            if not skip_wait:
                wait_for_launch_time()
                # Refresh the page right at 7:30 to get fresh availability
                log.info("Refreshing grid at launch time ...")
                page.reload(wait_until="domcontentloaded", timeout=15_000)
                page.wait_for_timeout(3000)
                screenshot(page, "grid_at_launch")

            # ----------------------------------------------------------
            # Phase 3: Scan availability
            # ----------------------------------------------------------
            log.info("--- Phase 3: Scan availability ---")
            available = scan_availability(page)

            if not available:
                log.warning("No available slots found in target window")
                screenshot(page, "no_availability")

                # Retry once -- reload and scan again
                log.info("Retrying after reload ...")
                page.reload(wait_until="domcontentloaded", timeout=15_000)
                page.wait_for_timeout(3000)
                available = scan_availability(page)

                if not available:
                    log.error("Still no availability after retry. Aborting.")
                    screenshot(page, "no_availability_retry")
                    browser.close()
                    return False

            # Find a court where ALL 4 slots (4:00-6:00pm) are available
            best_court = None
            best_slots = []
            for court_name, resource_id in PREFERRED_COURTS:
                court_slots = [s for s in available if s["court_name"] == court_name]
                if len(court_slots) == len(TARGET_SLOTS_24H):
                    best_court = (court_name, resource_id)
                    best_slots = court_slots
                    log.info(f"SELECTED: {court_name} -- all 4 slots available (4:00-6:00 PM)")
                    break
                elif court_slots:
                    log.info(f"  {court_name}: only {len(court_slots)}/{len(TARGET_SLOTS_24H)} slots available, skipping")

            if not best_court:
                log.error("No court has all 4 slots (4:00-6:00 PM) available")
                screenshot(page, "no_full_block")
                browser.close()
                return False

            if dry_run:
                log.info("DRY RUN -- would book:")
                log.info(f"  Court: {best_court[0]} (resource_id={best_court[1]})")
                log.info(f"  Date : {date_str}")
                for s in best_slots:
                    log.info(f"  Slot : {s['slot_24h']} ({s['start_display']}-{s['end_display']})")
                browser.close()
                return True

            # ----------------------------------------------------------
            # Phase 4: Book all 4 slots (API fast path, UI fallback)
            # ----------------------------------------------------------
            log.info("--- Phase 4: Booking 2-hour block ---")
            screenshot(page, "pre_booking")

            # Try API first (faster, no UI delays)
            api_success = False
            courts_to_try = [(best_court, best_slots)]
            # Build fallback list of courts with full blocks
            for court_name, resource_id in PREFERRED_COURTS:
                if court_name == best_court[0]:
                    continue
                court_slots = [s for s in available if s["court_name"] == court_name]
                if len(court_slots) == len(TARGET_SLOTS_24H):
                    courts_to_try.append(((court_name, resource_id), court_slots))

            for attempt, (court, slots) in enumerate(courts_to_try[:3]):
                log.info(f"API booking attempt {attempt + 1}/{min(len(courts_to_try), 3)} -- {court[0]}")
                try:
                    api_success = book_via_api(
                        page,
                        target_date,
                        court[1],
                        [s["slot_24h"] for s in slots],
                        court[0],
                    )
                    if api_success:
                        best_court = court
                        best_slots = slots
                        break
                except Exception as e:
                    log.warning(f"API attempt {attempt + 1} error: {e}")

            if api_success:
                log.info("=" * 60)
                log.info("BOOKING SUCCESSFUL (API) -- 2 hour block")
                log.info(f"  {best_court[0]} @ 4:00-6:00 PM")
                log.info(f"  Date: {date_str}")
                log.info("=" * 60)
                screenshot(page, "booking_success")
                browser.close()
                return True

            # Fallback to UI clicking -- select all 4 slots then confirm
            log.warning("API booking failed -- falling back to UI clicks")
            page.reload(wait_until="domcontentloaded", timeout=15_000)
            page.wait_for_timeout(3000)
            available = scan_availability(page)

            # Find court with full block again
            for court_name, resource_id in PREFERRED_COURTS:
                court_slots = [s for s in available if s["court_name"] == court_name]
                if len(court_slots) == len(TARGET_SLOTS_24H):
                    best_court = (court_name, resource_id)
                    best_slots = court_slots
                    break
            else:
                log.error("No full block available for UI fallback")
                browser.close()
                return False

            # Click all 4 slots on the same court
            for slot in best_slots:
                cell = page.locator(f"[aria-label='{slot['aria_label']}']").first
                cell.click()
                page.wait_for_timeout(500)
                log.info(f"  Clicked: {slot['aria_label']}")

            screenshot(page, "all_slots_selected")

            # Fill event name
            event_input = page.locator("input[type='text']").last
            event_input.fill("Pickleball")
            page.wait_for_timeout(500)

            # Click Confirm bookings
            confirm_btn = page.locator("button:has-text('Confirm bookings'), button:has-text('Confirm Bookings')")
            for _ in range(5):
                if confirm_btn.count() > 0:
                    break
                page.wait_for_timeout(1000)

            if confirm_btn.count() > 0:
                log.info("Clicking 'Confirm bookings'")
                confirm_btn.first.click()
                page.wait_for_timeout(3000)
                screenshot(page, "after_confirm")
            else:
                log.error("No confirm button found")
                browser.close()
                return False

            # Handle waiver
            waiver_cb = page.locator("input[type='checkbox']")
            if waiver_cb.count() > 0:
                waiver_cb.first.check()
                page.wait_for_timeout(500)

            reserve_btn = page.locator("button:has-text('Reserve'), button:has-text('Submit')")
            if reserve_btn.count() > 0:
                reserve_btn.first.click()
                page.wait_for_timeout(5000)
                screenshot(page, "reserved")
                log.info("=" * 60)
                log.info("BOOKING SUCCESSFUL (UI) -- 2 hour block")
                log.info(f"  {best_court[0]} @ 4:00-6:00 PM")
                log.info(f"  Date: {date_str}")
                log.info("=" * 60)
                browser.close()
                return True

            log.error("BOOKING FAILED -- both API and UI paths exhausted")
            screenshot(page, "booking_failed")
            browser.close()
            return False

        except PlaywrightTimeout as e:
            log.error(f"Timeout: {e}")
            screenshot(page, "timeout_error")
            browser.close()
            return False
        except Exception as e:
            log.error(f"Unexpected error: {e}", exc_info=True)
            screenshot(page, "unexpected_error")
            browser.close()
            return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fremont Pickleball Court Auto-Booker v2")
    parser.add_argument("--dry-run", action="store_true", help="Preview without booking")
    parser.add_argument("--date", type=str, help="Target date YYYY-MM-DD (default: 7 days out)")
    parser.add_argument("--now", action="store_true", help="Skip 7:30am wait, book immediately")
    args = parser.parse_args()

    target = None
    if args.date:
        target = datetime.strptime(args.date, "%Y-%m-%d").replace(tzinfo=PT)

    success = run(dry_run=args.dry_run, target_date=target, skip_wait=args.now)
    sys.exit(0 if success else 1)
