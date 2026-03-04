from __future__ import annotations

from typing import Optional

import pandas as pd


def parse_timestamp_utc(value: object, field_name: str) -> pd.Timestamp:
    ts = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"{field_name} must be a valid datetime")
    return ts


def parse_optional_timestamp_utc(value: object, field_name: str) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return parse_timestamp_utc(value, field_name)


def parse_optional_date_utc(value: object, field_name: str) -> Optional[pd.Timestamp]:
    ts = parse_optional_timestamp_utc(value, field_name)
    if ts is None:
        return None
    return ts.normalize()


def normalize_series_utc(series: pd.Series, column_name: str) -> pd.Series:
    out = pd.to_datetime(series, utc=True, errors="coerce")
    if out.isna().any():
        raise ValueError(f"Invalid datetime values in '{column_name}' column")
    return out


def ensure_valid_range(start: Optional[pd.Timestamp], end: Optional[pd.Timestamp]) -> None:
    if start is not None and end is not None and start > end:
        raise ValueError("start must be <= end")


def iso_utc(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return ""
    if ts.tzinfo is None:
        return ts.tz_localize("UTC").isoformat()
    return ts.tz_convert("UTC").isoformat()


def normalize_series_to_timezone(series: pd.Series, column_name: str, timezone_name: str) -> pd.Series:
    out = pd.to_datetime(series, errors="coerce")
    if out.isna().any():
        raise ValueError(f"Invalid datetime values in '{column_name}' column")
    if out.dt.tz is None:
        return out.dt.tz_localize(timezone_name)
    return out.dt.tz_convert(timezone_name)


def parse_timestamp_in_timezone(value: object, field_name: str, timezone_name: str) -> pd.Timestamp:
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"{field_name} must be a valid datetime")
    if ts.tzinfo is None:
        return ts.tz_localize(timezone_name)
    return ts.tz_convert(timezone_name)


def parse_optional_date_in_timezone(value: object, field_name: str, timezone_name: str) -> Optional[pd.Timestamp]:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    return parse_timestamp_in_timezone(value, field_name, timezone_name).normalize()
