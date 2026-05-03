#!/bin/bash
# Setup cron job to run the booker at 7:30am PT daily
#
# Usage: ./setup_cron.sh
# To remove: crontab -e and delete the fremont-pickleball line

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON_PATH="$(which python3)"

# 7:30 AM Pacific Time
# Note: cron uses system timezone. If your system is PT, use 7:30 directly.
# If UTC, use 14:30 (PDT) or 15:30 (PST).
CRON_LINE="30 7 * * * cd ${SCRIPT_DIR} && ${PYTHON_PATH} book.py >> ${SCRIPT_DIR}/logs/cron.log 2>&1"

# Check if already installed
if crontab -l 2>/dev/null | grep -q "fremont-pickleball-res"; then
    echo "Cron job already exists. Updating..."
    crontab -l 2>/dev/null | grep -v "fremont-pickleball-res" | crontab -
fi

# Add the cron job
(crontab -l 2>/dev/null; echo "# fremont-pickleball-res auto-booker"; echo "$CRON_LINE") | crontab -

echo "Cron job installed:"
echo "  $CRON_LINE"
echo ""
echo "Verify with: crontab -l"
echo "Logs will be at: ${SCRIPT_DIR}/logs/cron.log"
