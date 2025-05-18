# config/settings.py
import sys
from pathlib import Path


# General settings
DEBUG_FLAG = True
PORT = 8050
TIMEZONE = 'Europe/Helsinki'

# Data sources
project_root = None
for path in sys.path:
    candidate = Path(path).resolve()
    print(candidate)
    if candidate.name == 'Future-Trading-Analysis' and (candidate / 'src').exists():
        project_root = candidate
        break
if project_root is None:
    raise RuntimeError("Could not find project root in sys.path. Please set BASE_DIR manually.")
BASE_DIR = project_root

# Define data directories relative to project root
PERFORMANCE_DIR = BASE_DIR / 'data' / 'performance'
FUTURE_DIR = BASE_DIR / 'data' / 'future' / 'aggregated'

PERFORMANCE_CSV = str(PERFORMANCE_DIR / 'Combined_Performance_with_Streaks.csv')
MES_CSV = str(FUTURE_DIR / 'MES.csv')
MNQ_CSV = str(FUTURE_DIR / 'MNQ.csv')
MGC_CSV = str(FUTURE_DIR / 'MGC.csv')


# Layout settings
DATA_SOURCE_DROPDOWN = {
    'MES': MES_CSV,
    'MNQ': MNQ_CSV,
    'MGC': MGC_CSV
}

ANALYSIS_DROPDOWN = {
    'Rolling Winning Rate': {},
    'Sharpe Ratio': {
        'window': '30d',  # Rolling window for calculation (e.g., 30 days)
        'annualized': True,  # Whether to annualize the ratio
        'risk_free_rate': 0.02,  # Risk-free rate (e.g., 2%)
    },
    'Max Drawdown': {},
    'Hourly Performance': {},
    'Average Daily Return': {},
    'W/L Ratio': {},
    'P%L Distribution': {},
    'Size and Risk Analysis': {},
    'Trade Duration Analysis': {},
}

# Debug print to verify path
# if DEBUG_FLAG:
    # print(f"BASE_DIR: {BASE_DIR}")
    # print(f"PERFORMANCE_CSV: {PERFORMANCE_CSV}")