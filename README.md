# Fremont Pickleball Court Auto-Booker

Automatically books pickleball courts at Fremont Tennis Center via ActiveNet at 7:30am PT daily, 7 days in advance. Includes iOS app to toggle auto-booking on/off.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   iOS App    │────▶│ Toggle Server│────▶│  toggle.json │
│  PickleBook  │     │  (FastAPI)   │     └──────────────┘
└──────────────┘     └──────────────┘            ▲
                          :8787                  │
                                          ┌──────┴───────┐
                     cron 7:30am PT ────▶ │   book.py    │
                                          │  (Playwright)│
                                          └──────────────┘
```

## Setup

```bash
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# Edit .env with your ActiveNet credentials
```

## Usage

```bash
# Book immediately (no 7:30am wait)
python book.py --now

# Dry run -- preview without booking
python book.py --now --dry-run

# Book for a specific date
python book.py --now --date 2026-05-09

# Normal mode -- waits until 7:30am PT, books 7 days out
python book.py
```

## Toggle Server

```bash
python server.py  # runs on port 8787
```

Endpoints:
- `GET /status` -- toggle state + next booking date
- `POST /toggle` -- flip on/off
- `POST /enable` / `POST /disable`
- `GET /logs` -- last 10 log entries

## Auto-Schedule (cron)

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

## iOS App (PickleBook)

SwiftUI app in `ios/PickleBook/`. Create an Xcode project, add the Swift files, set bundle ID to `com.nosevitan.picklebook`.

Features: toggle switch, next booking date, last result, manual Book Now.

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `ACTIVENET_USERNAME` | - | ActiveNet email |
| `ACTIVENET_PASSWORD` | - | ActiveNet password |
| `ACTIVENET_CUSTOMER_ID` | 86022 | Your customer ID |

## How It Works

1. **7:28am PT** -- Browser launches, logs in, navigates to reservation grid for date 7 days out
2. **7:30:00.000 PT** -- Refreshes page, scans grid for available 4-6pm slots
3. **Picks best court** -- Court A > B > C > D > Orange 1 > 2 > 3
4. **Books via API** -- Injects fetch() call using browser session (handles CSRF automatically)
5. **Falls back to UI** -- If API fails, clicks the slot + Confirm button

## Logs & Debugging

- Logs: `logs/`
- Screenshots: `screenshots/` (captured at each step)
