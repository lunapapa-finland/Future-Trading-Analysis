import datetime
import logging
import time
from datetime import timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf
from exchange_calendars import get_calendar

from dashboard.config.settings import (
    ACQUISITION_LAST_BUSINESS_DATE,
    CURRENT_DATE,
    DATA_SOURCE_DROPDOWN,
    LOGGING_PATH,
    SYMBOL_CATALOG,
    TIMEZONE,
    CMEHolidayCalendar,
)

# Configure logging
logging.basicConfig(
    filename=LOGGING_PATH,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
    except Exception as e:
        logging.error(f"Error reading last row of {csv_path}: {e}")
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
    except Exception as e:
        logging.warning(f"Falling back to holiday list for calendar {name}: {e}")
        _CALENDAR_CACHE[name] = None
        return None


def is_holiday(date, symbol_cfg=None):
    """Check if a date is a holiday for the symbol's calendar."""
    cal = _get_calendar(symbol_cfg)
    if cal is not None:
        try:
            return not cal.is_session(pd.Timestamp(date))
        except Exception as e:
            logging.warning(f"Calendar check failed for {date}: {e}. Falling back to static holidays.")
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

    except Exception as e:
        logging.error(f"Error determining active contract for {symbol}: {e}")
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
    except Exception as e:
        logging.error(f"Timezone conversion error for {day}: {e}")
        return pd.DataFrame()
    rth_start = pd.to_datetime(day.strftime('%Y-%m-%d') + f' {start_str}:00').tz_localize(tz)
    rth_end = pd.to_datetime(day.strftime('%Y-%m-%d') + f' {end_str}:00').tz_localize(tz)
    rth_data = df[(df.index >= rth_start) & (df.index <= rth_end)]
    actual_rows = len(rth_data)
    if actual_rows != expected_rows:
        missing_rows = expected_rows - actual_rows
        if 0 < missing_rows <= 6:
            rth_data = rth_data.resample('5min').mean().interpolate()
            logging.info(f"Interpolated {missing_rows} missing rows for {day}")
        elif missing_rows < 0:
            logging.warning(f"Excess rows ({actual_rows}) for {day}. Trimming to {expected_rows}.")
            rth_data = rth_data.iloc[:expected_rows]
        else:
            logging.warning(f"Excessive missing rows ({missing_rows}) for {day}. Data retained but flagged.")
    return rth_data

def acquire_missing_data(max_retries=5, retry_delay=10, fallback_source=None):
    """Acquire missing data with robust error handling and validation."""
    current_date = pd.to_datetime(CURRENT_DATE)
    target_date = pd.to_datetime(ACQUISITION_LAST_BUSINESS_DATE).date()
    for symbol, csv_path in DATA_SOURCE_DROPDOWN.items():
        last_date = get_last_date_in_csv(csv_path)
        if last_date is None:
            logging.info(f"No valid data in {csv_path}. Initializing last_date to 30 days before current_date.")
            last_date = (current_date - pd.Timedelta(days=20)).date()
            # continue

        # Find gap days from the day after the last date to target_date
        start_date = last_date + timedelta(days=1)
        if start_date > target_date:
            logging.info(f"Data for {symbol} up to {target_date} exists in {csv_path}. Skipping.")
            continue

        gap_dates = pd.date_range(start=start_date, end=target_date, freq='D')
        business_days = remove_weekends(gap_dates.date)
        sym_cfg = SYMBOL_CATALOG.get(symbol)
        valid_days = [day for day in business_days if not is_holiday(day, sym_cfg)]

        for day in valid_days:
            if is_date_in_csv(csv_path, day):
                logging.info(f"Data for {day} already exists in {csv_path}. Skipping.")
                continue

            ticker = get_active_contract(symbol, day, SYMBOL_CATALOG.get(symbol))
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
                        if attempt < max_retries - 1:
                            logging.warning(f"Empty DataFrame for {ticker} on {day}. Retrying ({attempt + 1}/{max_retries})...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            logging.error(f"Failed to fetch {ticker} on {day} after {max_retries} retries. Possible holiday or unavailability.")
                            if is_holiday(day):
                                logging.info(f"Confirmed {day} as holiday for {ticker}.")
                            break
                    else:
                        validated_df = validate_data(df, day, SYMBOL_CATALOG.get(symbol))
                        if not validated_df.empty:
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
                            logging.info(f"Data for {ticker} on {day} validated and saved to {csv_path}")
                        break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logging.warning(f"Error fetching {ticker} on {day}: {e}. Retrying ({attempt + 1}/{max_retries})...")
                        time.sleep(retry_delay)
                    else:
                        logging.error(f"Failed after {max_retries} retries for {ticker} on {day}: {e}")
                        if fallback_source:
                            logging.info(f"Attempting fallback source for {ticker} on {day}")
                            # Implement fallback logic here

if __name__ == "__main__":
    acquire_missing_data()
