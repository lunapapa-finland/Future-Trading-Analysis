import datetime

import pandas as pd
import pytest

from dashboard.services.utils import data_acquisition as da


def test_get_active_contract_rolls_after_wednesday_before_third_friday():
    symbol_cfg = {
        "exchange": "CME",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "weds_before_third_friday",
            "months": [3, 6, 9, 12],
            "codes": ["H", "M", "U", "Z"],
        },
    }
    # March 20, 2024 is after the rollover date for March contract, expect June (M)
    ticker = da.get_active_contract("MES", datetime.date(2024, 3, 20), symbol_cfg)
    print(f"Ticker after rollover (MES): {ticker}")
    assert ticker == "MESM24.CME"


def test_validate_data_uses_symbol_trading_hours():
    symbol_cfg = {
        "trading_hours": {"start": "08:30", "end": "08:40", "timezone": "US/Central"},
        "expected_rows": 3,
    }
    idx = pd.date_range("2024-03-18 08:30", periods=3, freq="5min", tz="US/Central")
    df = pd.DataFrame({"Open": [1, 2, 3]}, index=idx)

    validated = da.validate_data(df, datetime.date(2024, 3, 18), symbol_cfg)
    print(f"Validated rows: {len(validated)}")
    assert len(validated) == symbol_cfg["expected_rows"]


def test_is_holiday_uses_exchange_calendar(monkeypatch):
    class DummyCal:
        def __init__(self, sessions):
            self.sessions = sessions

        def is_session(self, ts):
            return ts.normalize() in self.sessions

    # Patch calendar loader to return a calendar with no sessions => every day is holiday
    monkeypatch.setattr(da, "_get_calendar", lambda cfg=None: DummyCal(sessions=pd.DatetimeIndex([])))

    # Any date should be treated as a holiday by the dummy calendar
    assert da.is_holiday(datetime.date(2024, 3, 18), {"calendar": "cme"}) is True

    # Now patch to return a calendar with the date as a session => not a holiday
    sessions = pd.DatetimeIndex([pd.Timestamp("2024-03-18")])
    monkeypatch.setattr(da, "_get_calendar", lambda cfg=None: DummyCal(sessions=sessions))
    result = da.is_holiday(datetime.date(2024, 3, 18), {"calendar": "cme"})
    print(f"Holiday check for 2024-03-18: {result}")
    assert result is False


def test_api_config_includes_symbols_and_timeframes(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert "symbols" in payload and isinstance(payload["symbols"], list)
    assert any(s.get("symbol") == "MES" for s in payload["symbols"])
    assert "timeframes" in payload and isinstance(payload["timeframes"], list)


def test_get_active_contract_last_wednesday_rolls_forward():
    symbol_cfg = {
        "exchange": "CME",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "last_wednesday",
            "months": list(range(1, 13)),
            "codes": ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"],
        },
    }
    # After last Wednesday of March 2024 (which is 2024-03-27), should roll to April (code J)
    ticker = da.get_active_contract("MET", datetime.date(2024, 3, 28), symbol_cfg)
    print(f"Ticker after last-Wednesday roll (MET): {ticker}")
    assert ticker == "METJ24.CME"


def test_get_active_contract_crypto_last_trading_day_rolls_forward():
    symbol_cfg = {
        "exchange": "CME",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "crypto_last_trading_day",
            "months": list(range(1, 13)),
            "codes": ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"],
        },
    }
    assert da.get_active_contract("MBT", datetime.date(2026, 4, 23), symbol_cfg) == "MBTJ26.CME"
    assert da.get_active_contract("MBT", datetime.date(2026, 4, 24), symbol_cfg) == "MBTK26.CME"
    assert da.get_active_contract("MBT", datetime.date(2026, 4, 28), symbol_cfg) == "MBTK26.CME"


def test_get_active_contract_crypto_last_trading_day_handles_holidays():
    symbol_cfg = {
        "exchange": "CME",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "crypto_last_trading_day",
            "months": list(range(1, 13)),
            "codes": ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"],
        },
    }
    # March 29, 2024 was Good Friday, so crypto futures LTD moves to Thursday.
    assert da.get_active_contract("MBT", datetime.date(2024, 3, 27), symbol_cfg) == "MBTH24.CME"
    assert da.get_active_contract("MBT", datetime.date(2024, 3, 28), symbol_cfg) == "MBTJ24.CME"

    # December 25, 2026 is the last Friday and a holiday, so LTD moves to Thursday.
    assert da.get_active_contract("MBT", datetime.date(2026, 12, 23), symbol_cfg) == "MBTZ26.CME"
    assert da.get_active_contract("MBT", datetime.date(2026, 12, 24), symbol_cfg) == "MBTF27.CME"


def test_get_active_contract_equity_index_rolls_three_sessions_before_ltd():
    symbol_cfg = {
        "exchange": "CME",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "equity_index_3bd_before_ltd",
            "months": [3, 6, 9, 12],
            "codes": ["H", "M", "U", "Z"],
        },
    }
    # March 2026 equity index LTD is Friday 2026-03-20; roll date is Tuesday 2026-03-17.
    assert da.get_active_contract("MES", datetime.date(2026, 3, 16), symbol_cfg) == "MESH26.CME"
    assert da.get_active_contract("MES", datetime.date(2026, 3, 17), symbol_cfg) == "MESM26.CME"


def test_get_active_contract_fx_rolls_three_sessions_before_ltd():
    symbol_cfg = {
        "exchange": "CME",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "fx_3bd_before_ltd",
            "months": [3, 6, 9, 12],
            "codes": ["H", "M", "U", "Z"],
        },
    }
    # June 2026 FX LTD is Monday 2026-06-15; roll date is Wednesday 2026-06-10.
    assert da.get_active_contract("M6E", datetime.date(2026, 6, 9), symbol_cfg) == "M6EM26.CME"
    assert da.get_active_contract("M6E", datetime.date(2026, 6, 10), symbol_cfg) == "M6EU26.CME"


def test_get_active_contract_crypto_rolls_three_sessions_before_ltd():
    symbol_cfg = {
        "exchange": "CME",
        "source": {
            "type": "yfinance",
            "ticker_format": "{symbol}{month_code}{yy}.{exchange}",
            "roll_rule": "crypto_3bd_before_ltd",
            "months": list(range(1, 13)),
            "codes": ["F", "G", "H", "J", "K", "M", "N", "Q", "U", "V", "X", "Z"],
        },
    }
    # April 2026 crypto LTD is Friday 2026-04-24; roll date is Tuesday 2026-04-21.
    assert da.get_active_contract("MBT", datetime.date(2026, 4, 20), symbol_cfg) == "MBTJ26.CME"
    assert da.get_active_contract("MBT", datetime.date(2026, 4, 21), symbol_cfg) == "MBTK26.CME"

    # December 2026 crypto LTD is Thursday 2026-12-24; roll date is Monday 2026-12-21.
    assert da.get_active_contract("MBT", datetime.date(2026, 12, 18), symbol_cfg) == "MBTZ26.CME"
    assert da.get_active_contract("MBT", datetime.date(2026, 12, 21), symbol_cfg) == "MBTF27.CME"


def test_validate_data_trims_excess_rows():
    symbol_cfg = {
        "trading_hours": {"start": "08:30", "end": "08:40", "timezone": "US/Central"},
        "expected_rows": 2,
    }
    idx = pd.date_range("2024-03-18 08:30", periods=3, freq="5min", tz="US/Central")
    df = pd.DataFrame({"Open": [1, 2, 3]}, index=idx)
    validated = da.validate_data(df, datetime.date(2024, 3, 18), symbol_cfg)
    print(f"Trimmed rows: {len(validated)}")
    assert len(validated) == symbol_cfg["expected_rows"]


def test_is_holiday_fallback_to_static_calendar(monkeypatch):
    # Force calendar loader to None to exercise fallback
    monkeypatch.setattr(da, "_get_calendar", lambda cfg=None: None)
    result = da.is_holiday(datetime.date(2024, 3, 18), {"calendar": "cme"})
    print(f"Fallback holiday check for 2024-03-18: {result}")
    # March 18, 2024 is not a CME holiday in static list; expect False
    assert result is False
