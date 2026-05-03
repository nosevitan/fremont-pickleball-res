# Fremont Pickleball Court Auto-Booker

Automatically books pickleball courts at Fremont Tennis Center via ActiveNet at 7:30am PT daily.

## Setup

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Configure credentials
cp .env.example .env
# Edit .env with your ActiveNet login
```

## Usage

```bash
# Dry run - see what would be booked
python book.py --dry-run

# Book for default date (2 days ahead)
python book.py

# Book for specific date
python book.py --date 2026-05-05
```

## Auto-Schedule (7:30am PT daily)

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

## Configuration (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `ACTIVENET_USERNAME` | - | Your ActiveNet login |
| `ACTIVENET_PASSWORD` | - | Your ActiveNet password |
| `PREFERRED_COURTS` | Court A-D | Comma-separated court names |
| `BOOK_START_HOUR` | 16 | Start of booking window (24h) |
| `BOOK_END_HOUR` | 18 | End of booking window (24h) |
| `DAYS_AHEAD` | 2 | How many days ahead to book |

## Logs & Debugging

- Logs: `logs/`
- Screenshots: `screenshots/` (captured at each step)
