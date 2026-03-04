from __future__ import annotations

import pandas as pd
from dashboard.config.settings import TIMEZONE
from dashboard.services.utils.datetime_utils import (
    ensure_valid_range,
    normalize_series_utc,
    normalize_series_to_timezone,
    parse_timestamp_in_timezone,
)


def load_performance(ticker, start_date, end_date, csv_path):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"performance data file not found: {csv_path}") from exc
    except pd.errors.EmptyDataError as exc:
        raise ValueError("performance data file is empty") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"failed to parse performance data: {exc}") from exc

    try:
        if "TradeDay" not in df.columns:
            raise ValueError("TradeDay column missing")
        if "ContractName" not in df.columns:
            raise ValueError("ContractName column missing")
        df["TradeDay"] = normalize_series_to_timezone(df["TradeDay"], "TradeDay", TIMEZONE).dt.normalize()
        start_ts = parse_timestamp_in_timezone(start_date, "start_date", TIMEZONE).normalize()
        end_ts = parse_timestamp_in_timezone(end_date, "end_date", TIMEZONE).normalize()
        ensure_valid_range(start_ts, end_ts)
        mask = (df["TradeDay"] >= start_ts) & (df["TradeDay"] <= end_ts)
        df = df[mask]
        df = df[df["ContractName"].astype(str).str.startswith(ticker)]
        return df.reset_index(drop=True)
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"Failed to load performance data: {exc}") from exc

def load_future(start_date, end_date, csv_path):
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"future data file not found: {csv_path}") from exc
    except pd.errors.EmptyDataError as exc:
        raise ValueError("future data file is empty") from exc
    except pd.errors.ParserError as exc:
        raise ValueError(f"failed to parse future data: {exc}") from exc

    try:
        if "Datetime" not in df.columns:
            raise ValueError("Datetime column missing")
        datetime_raw = df["Datetime"].astype(str)
        pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[-+]\d{2}:\d{2}"
        if not datetime_raw.str.match(pattern).all():
            invalid_rows = df[~datetime_raw.str.match(pattern)]
            raise ValueError(f"Invalid datetime format in CSV at rows: {invalid_rows.index.tolist()}")

        df["Datetime"] = normalize_series_utc(df["Datetime"], "Datetime")
        df["Datetime"] = df["Datetime"].dt.tz_convert(TIMEZONE)
        start_ts = parse_timestamp_in_timezone(start_date, "start_date", TIMEZONE).normalize()
        end_ts = parse_timestamp_in_timezone(end_date, "end_date", TIMEZONE).normalize() + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        ensure_valid_range(start_ts, end_ts)
        mask = (df["Datetime"] >= start_ts) & (df["Datetime"] <= end_ts)
        return df[mask].reset_index(drop=True)
    except (TypeError, ValueError, KeyError) as exc:
        raise ValueError(f"Failed to load future data: {exc}") from exc
