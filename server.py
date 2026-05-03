"""
PickleBook Toggle Server
========================
FastAPI server that manages an auto-booking toggle for pickleball courts.
Reads/writes state to toggle.json and exposes simple REST endpoints.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TOGGLE_FILE = Path(__file__).parent / "toggle.json"
LOG_FILE = Path(__file__).parent / "logs" / "server.log"

app = FastAPI(title="PickleBook Toggle Server", version="1.0.0")

# Allow the iOS app (and any local client) to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class StatusResponse(BaseModel):
    enabled: bool
    next_booking_date: str
    last_run: Optional[str]
    last_result: Optional[str]


class LogEntry(BaseModel):
    line: str

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_toggle() -> dict:
    """Read the current toggle state from disk."""
    if not TOGGLE_FILE.exists():
        default = {"enabled": True, "last_run": None, "last_result": None}
        _write_toggle(default)
        return default
    with open(TOGGLE_FILE, "r") as f:
        return json.load(f)


def _write_toggle(data: dict) -> None:
    """Persist toggle state to disk."""
    with open(TOGGLE_FILE, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _next_booking_date() -> str:
    """Return the date 7 days from today in YYYY-MM-DD format."""
    return (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")


def _build_status(data: dict) -> StatusResponse:
    return StatusResponse(
        enabled=data["enabled"],
        next_booking_date=_next_booking_date(),
        last_run=data.get("last_run"),
        last_result=data.get("last_result"),
    )


def _read_logs(n: int = 10) -> list[str]:
    """Return the last *n* lines from the server log file."""
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text().strip().splitlines()
    return lines[-n:]

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Return the current toggle state and next booking date."""
    data = _read_toggle()
    return _build_status(data)


@app.post("/toggle", response_model=StatusResponse)
async def toggle():
    """Flip the enabled flag and return the new state."""
    data = _read_toggle()
    data["enabled"] = not data["enabled"]
    _write_toggle(data)
    return _build_status(data)


@app.post("/enable", response_model=StatusResponse)
async def enable():
    """Set enabled to true."""
    data = _read_toggle()
    data["enabled"] = True
    _write_toggle(data)
    return _build_status(data)


@app.post("/disable", response_model=StatusResponse)
async def disable():
    """Set enabled to false."""
    data = _read_toggle()
    data["enabled"] = False
    _write_toggle(data)
    return _build_status(data)


@app.get("/logs")
async def get_logs():
    """Return the last 10 log entries."""
    lines = _read_logs(10)
    return {"logs": [{"line": l} for l in lines]}


# ---------------------------------------------------------------------------
# Entry point (for `python server.py`)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8787, reload=True)
