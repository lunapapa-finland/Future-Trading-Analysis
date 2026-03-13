from datetime import datetime, timedelta
from pathlib import Path
import os, sys
import logging
import fcntl

from dashboard.config.env import LOGGING_PATH
from dashboard.services.utils.data_acquisition import acquire_missing_data

STAMP_PATH = Path(os.environ.get("TRADING_STAMP_PATH", "/app/log/.trading_last_run"))
LOCK_PATH = Path(os.environ.get("TRADING_LOCK_PATH", "/app/log/.trading_fetch.lock"))
HOURS_DELAY = int(os.environ.get("HOURS_DELAY", "12"))
FETCH_MAX_RETRIES = int(os.environ.get("FETCH_MAX_RETRIES", "5"))
FETCH_RETRY_DELAY_SECONDS = int(os.environ.get("FETCH_RETRY_DELAY_SECONDS", "300"))

logging.basicConfig(
    filename=LOGGING_PATH,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

def now(): return datetime.now()

def ran_today():
    if not STAMP_PATH.exists():
        return False
    return STAMP_PATH.read_text().strip() == now().strftime("%Y-%m-%d")

def mark_ran():
    STAMP_PATH.parent.mkdir(parents=True, exist_ok=True)
    STAMP_PATH.write_text(now().strftime("%Y-%m-%d"))

def acquire_run_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_fh = open(LOCK_PATH, "w", encoding="utf-8")
    try:
        fcntl.flock(lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock_fh.close()
        return None
    lock_fh.write(str(os.getpid()))
    lock_fh.flush()
    return lock_fh

def main():
    lock_fh = acquire_run_lock()
    if lock_fh is None:
        logging.info("Trading fetch already running. Skipping overlapping run.")
        return 0

    n = now()
    try:
        if n < n.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=HOURS_DELAY):
            return 0
        if ran_today():
            return 0
        summary = acquire_missing_data(
            max_retries=FETCH_MAX_RETRIES,
            retry_delay=FETCH_RETRY_DELAY_SECONDS,
        )
        if summary.get("failed", 0) == 0:
            mark_ran()
        else:
            logging.warning(
                "Trading fetch completed with failures; .trading_last_run not updated. summary=%s",
                summary,
            )
        return 0
    finally:
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_UN)
        finally:
            lock_fh.close()

if __name__ == "__main__":
    sys.exit(main())
