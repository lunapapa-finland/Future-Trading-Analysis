"""
Configuration settings for the Future Trading Analysis dashboard.

This file defines general settings, file paths, dropdown options, analysis configurations,
and plot settings used across the application. Organized into sections for clarity and
extensibility.
"""

import logging
from datetime import date

import pandas as pd
from pandas.tseries.holiday import AbstractHolidayCalendar, Holiday

from dashboard.config.env import (
    BASE_DIR,
    LOG_DIR,
    DATA_DIR,
    PERFORMANCE_DIR,
    FUTURE_DIR,
    TEMP_PERF_DIR,
    DEBUG_FLAG,
    PORT,
    TIMEZONE,
    LOGGING_PATH,
    TIMEFRAME_OPTIONS,
)
from dashboard.config.symbols import (
    DEFAULT_EXCHANGE,
    resolve_symbol_catalog,
)

log = logging.getLogger(__name__)

# Define a custom CME holiday calendar
class CMEHolidayCalendar(AbstractHolidayCalendar):
    def _next_monday(self, d):
        return pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)

    def _next_thursday(self, d):
        return pd.offsets.CustomBusinessDay(n=1, weekmask='Thu').rollforward(d)

    rules = [
        Holiday("New Year's Day", month=1, day=1, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)),
        Holiday("Martin Luther King Jr. Day", month=1, day=15, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)),
        Holiday("Presidents' Day", month=2, day=15, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)),
        Holiday("Good Friday", month=1, day=1, offset=[pd.offsets.Easter(), pd.offsets.Day(-2)]),  # 2 days before Easter
        Holiday("Memorial Day", month=5, day=31, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)),
        Holiday("Independence Day", month=7, day=4, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)),
        Holiday("Labor Day", month=9, day=1, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)),
        Holiday("Thanksgiving Day", month=11, day=28, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Thu').rollforward(d)),  # Nearest Thursday
        Holiday("Christmas Day", month=12, day=25, observance=lambda d: pd.offsets.CustomBusinessDay(n=1, weekmask='Mon').rollforward(d)),
    ]


# -----------------------------------
# Section 3: Data File Paths & Symbols
# -----------------------------------
EXCHANGE = [DEFAULT_EXCHANGE]
PERFORMANCE_CSV = str(PERFORMANCE_DIR / "Combined_performance_for_dash_project.csv")

# Resolved symbol catalog (absolute paths, defaults applied)
SYMBOL_CATALOG = resolve_symbol_catalog(BASE_DIR)

SYMBOL_ASSET_CLASS = {symbol: cfg.get("asset_class", "unknown") for symbol, cfg in SYMBOL_CATALOG.items()}
DATA_SOURCE_DROPDOWN = {
    symbol: cfg["data_path"]
    for symbol, cfg in SYMBOL_CATALOG.items()
    if cfg.get("enabled", True)
}

DEFAULT_DATA_SOURCE = next(iter(DATA_SOURCE_DROPDOWN.keys()), "MES")
CURRENT_DATE = date.today().strftime('%Y-%m-%d')  # e.g., '2025-05-19'



# -----------------------------------
# Section 5: Analysis Configurations
# -----------------------------------
DEFAULT_GRANULARITY = '1W-MON'  # Changed to fixed frequency
DEFAULT_ROLLING_WINDOW = 7
DEFAULT_ANALYSIS = 'Rolling Win Rate'

GRANULARITY_OPTIONS = [
    {'label': 'Daily', 'value': '1D'},
    {'label': 'Weekly', 'value': '1W-MON'},  # Changed to fixed frequency
    {'label': 'Monthly', 'value': '1M'}
]
WINDOW_OPTIONS = [
    {'label': '7', 'value': 7},
    {'label': '14', 'value': 14},
    {'label': '30', 'value': 30}
]

ANALYSIS_DROPDOWN = {
    'Drawdown': {'category': 'Period', 'granularity': DEFAULT_GRANULARITY},
    'PnL Growth': {'category': 'Period', 'granularity': DEFAULT_GRANULARITY, 'daily_compounding_rate': 0.001902, 'initial_funding' : 10000}, # Daily Rate = (1 + Annual Rate)^(1/365) - 1,  where Annual Rate = 100%
    'Performance Envelope': {'category': 'Period', 'granularity': DEFAULT_GRANULARITY},
    'Rolling Win Rate': {'category': 'Rolling', 'window': DEFAULT_ROLLING_WINDOW},
    'Sharpe Ratio': {'category': 'Rolling', 'window': DEFAULT_ROLLING_WINDOW, 'risk_free_rate': 0.02}, # Risk-free rate for Sharpe Ratio calculation, standing for 2% annual rate
    'Trade Efficiency': {'category': 'Rolling', 'window': DEFAULT_ROLLING_WINDOW},
    'Hourly Performance': {'category': 'Rolling', 'window': DEFAULT_ROLLING_WINDOW},
    'PnL Distribution': {'category': 'Overall'},
    'Behavioral Patterns': {'category': 'Overall'},
    'Overtrading Detection': {'category': 'Overall', 'cap_loss_per_trade':200, 'cap_trades_after_big_loss': 5}, # cap_loss_per_trade: Maximum loss per trade, considering the fixed risk control; cap_trades_after_big_loss : Maximum number of trades that will be scrutinized after a big loss
    'Kelly Criterion': {'category': 'Overall'}  # New addition
}
# -----------------------------------
# Section 6: Plot Settings
# -----------------------------------
TIMESTEP = 12  # 1 = 5 minutes, 12 = 1 hour

# -----------------------------------
# Section 7: Debug Output
# -----------------------------------
if DEBUG_FLAG:
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"PERFORMANCE_CSV: {PERFORMANCE_CSV}")

# -----------------------------------
# Section 8: Data Acquisition
# -----------------------------------
def get_last_business_day(current_date):
    current = pd.to_datetime(current_date)
    calendar = CMEHolidayCalendar()
    holidays = calendar.holidays(start=current - pd.offsets.BDay(10), end=current)
    last_business_day = current - pd.offsets.BDay(1)
    while last_business_day in holidays:
        last_business_day -= pd.offsets.BDay(1)
    return last_business_day.strftime('%Y-%m-%d')

ACQUISITION_LAST_BUSINESS_DATE = get_last_business_day(CURRENT_DATE)
