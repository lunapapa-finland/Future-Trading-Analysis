import datetime
import logging
import os
import time
import math
from datetime import timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from exchange_calendars import get_calendar

from dashboard.config.app_config import get_app_config
from dashboard.config.settings import (
    DATA_SOURCE_DROPDOWN,
    SYMBOL_CATALOG,
    TIMEZONE,
    CMEHolidayCalendar,
    get_last_business_day,
)

logger = logging.getLogger(__name__)

def _resolve_rate_limit_cooldown_minutes() -> int:
    cfg_default = get_app_config().get("data_fetch", {}).get("rate_limit_cooldown_minutes", 60)
    raw = os.environ.get("YF_RATE_LIMIT_COOLDOWN_MINUTES", str(cfg_default))
    try:
        val = int(raw)
    except (TypeError, ValueError):
        return 60
    return max(1, val)


RATE_LIMIT_COOLDOWN_MINUTES = _resolve_rate_limit_cooldown_minutes()
RATE_LIMIT_UNTIL_FILE = Path(os.environ.get("YF_RATE_LIMIT_UNTIL_FILE", "/app/log/.yf_rate_limited_until"))

def get_last_row_date(csv_path):
    """Helper function to read the last row of the CSV and extract the date."""
    try:
        df = pd.read_csv(csv_path, parse_dates=['Datetime'], date_format='%Y-%m-%d %H:%M:%S%z')
        if df.empty or 'Datetime' not in df:
            return None
        dt = pd.to_datetime(df['Datetime'], utc=True, errors='coerce').dropna()
        if dt.empty:
            return None
        return dt.max().date()
    except (FileNotFoundError, OSError, pd.errors.ParserError, ValueError, KeyError) as e:
        logger.error(f"Error reading last row of {csv_path}: {e}")
        return None

def is_date_in_csv(csv_path, target_date):
    """Check if the target date exists by comparing with the last row's date."""
    last_date = get_last_row_date(csv_path)
    if last_date is None:
        return False
    return target_date == last_date

def get_last_date_in_csv(csv_path):
    """Get the last date from the last row of the CSV file."""
    return get_last_row_date(csv_path)

def remove_weekends(date_list):
    """Remove weekends from a list of dates."""
    return [d for d in date_list if d.weekday() < 5]


def _read_rate_limit_until():
    try:
        if not RATE_LIMIT_UNTIL_FILE.exists():
            return None
        raw = RATE_LIMIT_UNTIL_FILE.read_text(encoding="utf-8").strip()
        if not raw:
            return None
        ts = pd.to_datetime(raw, utc=True, errors="coerce")
        if pd.isna(ts):
            return None
        return ts
    except OSError:
        return None


def _write_rate_limit_until(ts):
    RATE_LIMIT_UNTIL_FILE.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_UNTIL_FILE.write_text(ts.isoformat(), encoding="utf-8")


def get_rate_limit_status():
    now_utc = pd.Timestamp.utcnow().tz_localize("UTC") if pd.Timestamp.utcnow().tzinfo is None else pd.Timestamp.utcnow().tz_convert("UTC")
    cooldown_until = _read_rate_limit_until()
    if cooldown_until is None:
        return {"active": False, "cooldown_until": "", "remaining_seconds": 0}
    remaining_seconds = max(0, math.ceil((cooldown_until - now_utc).total_seconds()))
    return {
        "active": now_utc < cooldown_until,
        "cooldown_until": cooldown_until.isoformat(),
        "remaining_seconds": remaining_seconds,
    }


def _last_download_error_message(ticker):
    shared = getattr(yf, "shared", None)
    errors = getattr(shared, "_ERRORS", None)
    if not isinstance(errors, dict):
        return ""
    return str(errors.get(ticker, "") or "")


def _is_rate_limit_error_message(message):
    msg = str(message or "")
    return ("YFRateLimitError" in msg) or ("Too Many Requests" in msg)

_CALENDAR_CACHE = {}


def _get_calendar(symbol_cfg=None):
    name = None
    if symbol_cfg:
        name = (symbol_cfg.get("calendar") or "cme").lower()
    if not name:
        return None
    if name in _CALENDAR_CACHE:
        return _CALENDAR_CACHE[name]
    try:
        cal = get_calendar("CME") if name == "cme" else get_calendar(name.upper())
        _CALENDAR_CACHE[name] = cal
        return cal
    except (ValueError, KeyError, TypeError) as e:
        logger.warning(f"Falling back to holiday list for calendar {name}: {e}")
        _CALENDAR_CACHE[name] = None
        return None


def is_holiday(date, symbol_cfg=None):
    """Check if a date is a holiday for the symbol's calendar."""
    cal = _get_calendar(symbol_cfg)
    if cal is not None:
        try:
            return not cal.is_session(pd.Timestamp(date))
        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Calendar check failed for {date}: {e}. Falling back to static holidays.")
    # Fallback: static CME holiday list
    holidays = CMEHolidayCalendar().holidays(start=date, end=date)
    return date in holidays

def get_third_friday(year, month):
    """Calculate the third Friday of the given month and year."""
    first_day = datetime.date(year, month, 1)
    first_friday = first_day + datetime.timedelta(days=(4 - first_day.weekday() + 7) % 7)
    third_friday = first_friday + datetime.timedelta(weeks=2)
    return third_friday

def get_last_wednesday(year, month):
    """Calculate the last Wednesday of the given month and year."""
    next_month = month % 12 + 1
    next_year = year + (month // 12)
    first_day_next_month = datetime.date(next_year, next_month, 1)
    last_day = first_day_next_month - datetime.timedelta(days=1)
    days_to_wednesday = (last_day.weekday() - 2) % 7  # Wednesday = 2
    last_wednesday = last_day - datetime.timedelta(days=days_to_wednesday)
    return last_wednesday

def get_active_contract(symbol, current_date=None, symbol_cfg=None):
    """Determine the active futures contract using per-symbol roll rules."""
    try:
        if symbol_cfg is None:
            symbol_cfg = SYMBOL_CATALOG.get(symbol)
        if not symbol_cfg:
            raise ValueError(f"Invalid symbol: {symbol}. Must be one of {list(SYMBOL_CATALOG.keys())}")

        source = symbol_cfg.get("source", {})
        ticker_format = source.get("ticker_format", "{symbol}{month_code}{yy}.{exchange}")
        roll_rule = source.get("roll_rule", "weds_before_third_friday")
        months = source.get("months") or [3, 6, 9, 12]
        codes = source.get("codes") or ["H", "M", "U", "Z"]
        exchange = symbol_cfg.get("exchange", "CME")

        if current_date is None:
            current_date = datetime.date.today()
        elif isinstance(current_date, str):
            current_date = datetime.datetime.strptime(current_date, '%Y-%m-%d').date()
        elif isinstance(current_date, datetime.datetime):
            current_date = current_date.date()

        current_year = current_date.year
        current_month = current_date.month

        # pick nearest contract month; if we wrap around, bump the year
        base_idx = next((i for i, m in enumerate(months) if current_month <= m), 0)
        contract_year = current_year + (1 if base_idx == 0 and current_month > months[-1] else 0)
        contract_month = months[base_idx]

        # determine rollover date
        if roll_rule == "weds_before_third_friday":
            third_friday = get_third_friday(contract_year, contract_month)
            rollover_date = third_friday - datetime.timedelta(days=2)  # Wednesday before third Friday
        elif roll_rule == "last_wednesday":
            rollover_date = get_last_wednesday(contract_year, contract_month)
        else:
            rollover_date = None

        # if we've crossed rollover, move to next contract
        if rollover_date and current_date >= rollover_date:
            base_idx = (base_idx + 1) % len(months)
            if base_idx == 0:
                contract_year += 1
            contract_month = months[base_idx]

        month_code = codes[base_idx % len(codes)]
        contract_year_str = str(contract_year)[-2:]

        return ticker_format.format(symbol=symbol, month_code=month_code, yy=contract_year_str, exchange=exchange)

    except (ValueError, KeyError, TypeError) as e:
        logger.error(f"Error determining active contract for {symbol}: {e}")
        fallback_exchange = symbol_cfg.get("exchange", "CME") if symbol_cfg else "CME"
        fallback_year = (current_date.year if current_date else datetime.date.today().year) % 100
        return f"{symbol}M{fallback_year}.{fallback_exchange}"

def validate_data(df, day, symbol_cfg=None):
    """Validate fetched data for RTH completeness (expected rows/time window per symbol)."""
    tz = TIMEZONE
    expected_rows = 81
    start_str = "08:30"
    end_str = "15:10"
    if symbol_cfg:
        th = symbol_cfg.get("trading_hours") or {}
        tz = th.get("timezone", tz)
        start_str = th.get("start", start_str)
        end_str = th.get("end", end_str)
        expected_rows = symbol_cfg.get("expected_rows", expected_rows)
    try:
        df.index = pd.to_datetime(df.index).tz_convert(tz)
    except (TypeError, ValueError) as e:
        logger.error(f"Timezone conversion error for {day}: {e}")
        return pd.DataFrame()
    rth_start = pd.to_datetime(day.strftime('%Y-%m-%d') + f' {start_str}:00').tz_localize(tz)
    rth_end = pd.to_datetime(day.strftime('%Y-%m-%d') + f' {end_str}:00').tz_localize(tz)
    rth_data = df[(df.index >= rth_start) & (df.index <= rth_end)]
    actual_rows = len(rth_data)
    if actual_rows != expected_rows:
        missing_rows = expected_rows - actual_rows
        if 0 < missing_rows <= 6:
            rth_data = rth_data.resample('5min').mean().interpolate()
            logger.info(f"Interpolated {missing_rows} missing rows for {day}")
        elif missing_rows < 0:
            logger.warning(f"Excess rows ({actual_rows}) for {day}. Trimming to {expected_rows}.")
            rth_data = rth_data.iloc[:expected_rows]
        else:
            logger.warning(f"Excessive missing rows ({missing_rows}) for {day}. Data retained but flagged.")
    return rth_data

def acquire_missing_data(max_retries=5, retry_delay=300, fallback_source=None):
    """Acquire missing data with robust error handling and validation."""
    summary = {
        "symbols": 0,
        "days_attempted": 0,
        "saved": 0,
        "skipped": 0,
        "failed": 0,
        "rate_limited": False,
        "cooldown_until": "",
    }
    now_utc = pd.Timestamp.utcnow().tz_localize("UTC") if pd.Timestamp.utcnow().tzinfo is None else pd.Timestamp.utcnow().tz_convert("UTC")
    cooldown_until = _read_rate_limit_until()
    if cooldown_until is not None and now_utc < cooldown_until:
        summary["failed"] = 1
        summary["rate_limited"] = True
        summary["cooldown_until"] = cooldown_until.isoformat()
        logger.warning(
            "Skipping data acquisition due to active yfinance cooldown until %s",
            cooldown_until.isoformat(),
        )
        return summary

    current_ts = pd.Timestamp.now(tz=TIMEZONE)
    current_date = current_ts.normalize()
    target_date = pd.to_datetime(get_last_business_day(current_date.date().isoformat())).date()
    stop_all = False
    for symbol, csv_path in DATA_SOURCE_DROPDOWN.items():
        if stop_all:
            break
        summary["symbols"] += 1
        last_date = get_last_date_in_csv(csv_path)
        if last_date is None:
            logger.info(f"No valid data in {csv_path}. Initializing last_date to 30 days before current_date.")
            last_date = (current_date - pd.Timedelta(days=20)).date()
            # continue

        # Find gap days from the day after the last date to target_date
        start_date = last_date + timedelta(days=1)
        if start_date > target_date:
            logger.info(f"Data for {symbol} up to {target_date} exists in {csv_path}. Skipping.")
            summary["skipped"] += 1
            continue

        gap_dates = pd.date_range(start=start_date, end=target_date, freq='D')
        business_days = remove_weekends(gap_dates.date)
        sym_cfg = SYMBOL_CATALOG.get(symbol)
        valid_days = [day for day in business_days if not is_holiday(day, sym_cfg)]

        for day in valid_days:
            if stop_all:
                break
            if is_date_in_csv(csv_path, day):
                logger.info(f"Data for {day} already exists in {csv_path}. Skipping.")
                summary["skipped"] += 1
                continue

            ticker = get_active_contract(symbol, day, SYMBOL_CATALOG.get(symbol))
            summary["days_attempted"] += 1
            day_saved = False
            day_failed = False
            # end_day = day + timedelta(days=1)
            for attempt in range(max_retries):
                try:
                    df = yf.download(
                        tickers=ticker,
                        start=str(day),
                        # end=str(end_day),
                        period="1d",
                        auto_adjust=False,
                        interval="5m",
                        ignore_tz=False,
                        prepost=False,
                        multi_level_index=False,
                        progress=False
                    )
                    if df.empty:
                        err_msg = _last_download_error_message(ticker)
                        if _is_rate_limit_error_message(err_msg):
                            day_failed = True
                            summary["rate_limited"] = True
                            cooldown_until = pd.Timestamp.utcnow() + pd.Timedelta(minutes=RATE_LIMIT_COOLDOWN_MINUTES)
                            if cooldown_until.tzinfo is None:
                                cooldown_until = cooldown_until.tz_localize("UTC")
                            else:
                                cooldown_until = cooldown_until.tz_convert("UTC")
                            summary["cooldown_until"] = cooldown_until.isoformat()
                            _write_rate_limit_until(cooldown_until)
                            logger.error(
                                "Rate limited by yfinance for %s on %s. Entering cooldown until %s and stopping run.",
                                ticker,
                                day,
                                cooldown_until.isoformat(),
                            )
                            stop_all = True
                            break
                        if attempt < max_retries - 1:
                            logger.warning(f"Empty DataFrame for {ticker} on {day}. Retrying ({attempt + 1}/{max_retries})...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"Failed to fetch {ticker} on {day} after {max_retries} retries. Possible holiday or unavailability.")
                            if is_holiday(day, SYMBOL_CATALOG.get(symbol)):
                                logger.info(f"Confirmed {day} as holiday for {ticker}.")
                            else:
                                day_failed = True
                            break
                    else:
                        validated_df = validate_data(df, day, SYMBOL_CATALOG.get(symbol))
                        if validated_df.empty:
                            logger.error(f"Validated DataFrame empty for {ticker} on {day}.")
                            day_failed = True
                            break

                        # Reorder columns to match expected order
                        expected_order = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
                        validated_df = validated_df[expected_order]

                        # Format Datetime index with +HH:MM timezone
                        validated_df.index = validated_df.index.strftime('%Y-%m-%d %H:%M:%S%z').str.replace(r'(\d{2})(\d{2})$', r'\1:\2', regex=True)

                        # Write to CSV, appending contiguously for gap days
                        if not Path(csv_path).exists() or pd.read_csv(csv_path).empty:
                            validated_df.to_csv(csv_path, index_label='Datetime')
                        else:
                            # Ensure file ends with a newline before appending
                            with open(csv_path, 'rb+') as f:
                                f.seek(-1, 2)  # Move to last byte
                                if f.read(1) != b'\n':  # Check if file ends with newline
                                    f.write(b'\n')  # Add newline if missing
                            # Append data without extra newline
                            with open(csv_path, 'a', newline='') as f:
                                validated_df.to_csv(f, header=False, index_label='Datetime')
                        logger.info(f"Data for {ticker} on {day} validated and saved to {csv_path}")
                        day_saved = True
                        break
                except (RuntimeError, ValueError, OSError, KeyError) as e:
                    if _is_rate_limit_error_message(e):
                        day_failed = True
                        summary["rate_limited"] = True
                        cooldown_until = pd.Timestamp.utcnow() + pd.Timedelta(minutes=RATE_LIMIT_COOLDOWN_MINUTES)
                        if cooldown_until.tzinfo is None:
                            cooldown_until = cooldown_until.tz_localize("UTC")
                        else:
                            cooldown_until = cooldown_until.tz_convert("UTC")
                        summary["cooldown_until"] = cooldown_until.isoformat()
                        _write_rate_limit_until(cooldown_until)
                        logger.error(
                            "Rate limited by yfinance for %s on %s via exception. Entering cooldown until %s and stopping run.",
                            ticker,
                            day,
                            cooldown_until.isoformat(),
                        )
                        stop_all = True
                        break
                    if attempt < max_retries - 1:
                        logger.warning(f"Error fetching {ticker} on {day}: {e}. Retrying ({attempt + 1}/{max_retries})...")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"Failed after {max_retries} retries for {ticker} on {day}: {e}")
                        day_failed = True
                        if fallback_source:
                            logger.info(f"Attempting fallback source for {ticker} on {day}")
                            # Implement fallback logic here
            if day_saved:
                summary["saved"] += 1
            elif day_failed:
                summary["failed"] += 1
            else:
                summary["skipped"] += 1

    logger.info(
        "Data acquisition summary: symbols=%d, days_attempted=%d, saved=%d, skipped=%d, failed=%d",
        summary["symbols"],
        summary["days_attempted"],
        summary["saved"],
        summary["skipped"],
        summary["failed"],
    )
    return summary

if __name__ == "__main__":
    acquire_missing_data()
