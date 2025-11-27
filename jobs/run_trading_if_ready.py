from datetime import datetime, timedelta
from pathlib import Path
import os, sys

from dashboard.services.utils.data_acquisition import acquire_missing_data

STAMP_PATH = Path(os.environ.get("TRADING_STAMP_PATH", "/app/log/.trading_last_run"))
HOURS_DELAY = int(os.environ.get("HOURS_DELAY", "12"))

def now(): return datetime.now()

def ran_today():
    if not STAMP_PATH.exists():
        return False
    return STAMP_PATH.read_text().strip() == now().strftime("%Y-%m-%d")

def mark_ran():
    STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAMP_PATH.write_text(now().strftime("%Y-%m-%d"))

def main():
    n = now()
    if n < n.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=HOURS_DELAY):
        return 0
    if ran_today():
        return 0
    acquire_missing_data()
    mark_ran()
    return 0

if __name__ == "__main__":
    sys.exit(main())
