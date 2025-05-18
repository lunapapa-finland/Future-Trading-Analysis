# config/settings.py
"""
Configuration settings for the Future Trading Analysis dashboard.

This file defines general settings, file paths, dropdown options, analysis configurations,
and plot settings used across the application. Organized into sections for clarity and
extensibility.
"""

# Standard library imports
import sys
from pathlib import Path
from datetime import date

# -----------------------------------
# Section 1: General Application Settings
# -----------------------------------
# General configuration settings for the application runtime.
DEBUG_FLAG = False  # Enable debug mode (e.g., for printing paths during development)
PORT = 8050  # Port number for the Dash server
TIMEZONE = 'Europe/Helsinki'  # Timezone for date/time handling (e.g., Helsinki time for candlestick plots)

# -----------------------------------
# Section 2: Project Directory Setup
# -----------------------------------
# Dynamically determine the project root directory (BASE_DIR) by searching sys.path.
# The root is identified as the directory named 'Future-Trading-Analysis' containing a 'src' subdirectory.
project_root = None
for path in sys.path:
    candidate = Path(path).resolve()
    if candidate.name == 'Future-Trading-Analysis' and (candidate / 'src').exists():
        project_root = candidate
        break
if project_root is None:
    raise RuntimeError("Could not find project root in sys.path. Please set BASE_DIR manually.")
BASE_DIR = project_root  # Base directory of the project (e.g., /path/to/Future-Trading-Analysis)

# -----------------------------------
# Section 3: Data File Paths
# -----------------------------------
# Define paths to data directories and files used for performance and future data.
PERFORMANCE_DIR = BASE_DIR / 'data' / 'performance'  # Directory for performance data
FUTURE_DIR = BASE_DIR / 'data' / 'future' / 'aggregated'  # Directory for aggregated future data

# File paths for performance and future data CSVs
PERFORMANCE_CSV = str(PERFORMANCE_DIR / 'Combined_Performance_with_Streaks.csv')  # Path to performance CSV
MES_CSV = str(FUTURE_DIR / 'MES.csv')  # Path to MES future data
MNQ_CSV = str(FUTURE_DIR / 'MNQ.csv')  # Path to MNQ future data
MGC_CSV = str(FUTURE_DIR / 'MGC.csv')  # Path to MGC future data

# -----------------------------------
# Section 4: Dropdown Configurations
# -----------------------------------
# Configurations for dropdown menus used in the dashboard UI.

# Data Source Dropdown: Maps ticket symbols to their corresponding CSV file paths.
DATA_SOURCE_DROPDOWN = {
    'MES': MES_CSV,
    'MNQ': MNQ_CSV,
    'MGC': MGC_CSV,
}
DEFAULT_DATA_SOURCE = 'MES'  # Default selection for the data source dropdown

# Current Date: Used as the default for date pickers (computed at runtime).
CURRENT_DATE = date.today().strftime('%Y-%m-%d')  # Format: 'YYYY-MM-DD', e.g., '2025-05-18'

# Granularity Dropdown: Options for splitting data into discrete groups (Chopped Data analysis).
# Each entry includes a timedelta for splitting and a display label.
GRANULARITY_DROPDOWN = {
    'Daily': {'timedelta': '1D', 'label': 'Daily'},
    'Weekly': {'timedelta': '7D', 'label': 'Weekly'},
    'Monthly': {'timedelta': '30D', 'label': 'Monthly'},  # Approximation (use pandas.Grouper for exact months)
    'Quarterly': {'timedelta': '90D', 'label': 'Quarterly'},
    'Yearly': {'timedelta': '365D', 'label': 'Yearly'},
}
DEFAULT_GRANULARITY = 'Monthly'  # Default granularity for chopped data analysis

# Rolling Window Dropdown: Options for the rolling window size (Rolling Data analysis).
# Each entry includes the number of days and a display label.
ROLLING_WINDOW_DROPDOWN = {
    '7 Days': {'days': 7, 'label': '7 Days'},
    '30 Days': {'days': 30, 'label': '30 Days'},
    '60 Days': {'days': 60, 'label': '60 Days'},
    '90 Days': {'days': 90, 'label': '90 Days'},
}
DEFAULT_ROLLING_WINDOW = '30 Days'  # Default rolling window size

# -----------------------------------
# Section 5: Analysis Configurations
# -----------------------------------
# Configurations for statistical analysis types, categorized into Chopped, Rolling, and Overall.
# Each analysis type includes its category and relevant parameters.
ANALYSIS_DROPDOWN = {
    # Chopped Data: Metrics split into discrete time periods (requires granularity).
    'Drawdown Analysis': {
        'category': 'Chopped',
        'granularity': DEFAULT_GRANULARITY,  # Default splitting interval
    },
    'Average Daily Return': {
        'category': 'Chopped',
        'granularity': DEFAULT_GRANULARITY,
    },
    # Rolling Data: Metrics computed over a rolling window (requires window size).
    'Rolling Winning Rate': {
        'category': 'Rolling',
        'window': DEFAULT_ROLLING_WINDOW,  # Default window size
    },
    'Sharpe Ratio': {
        'category': 'Rolling',
        'window': DEFAULT_ROLLING_WINDOW,
        'annualized': True,  # Annualize the Sharpe Ratio
        'risk_free_rate': 0.02,  # Risk-free rate (e.g., 2%)
    },
    'Hourly Performance': {
        'category': 'Rolling',
        'window': '7 Days',  # Shorter window suitable for hourly data
    },
    'Size and Risk Analysis': {
        'category': 'Rolling',
        'window': DEFAULT_ROLLING_WINDOW,
    },
    # Overall Data: Metrics computed over the entire dataset (no time segmentation).
    'PnL Distribution': {
        'category': 'Overall',
    },
    'Trade Duration Analysis': {
        'category': 'Overall',
    },
}
DEFAULT_ANALYSIS = 'Rolling Winning Rate'  # Default analysis type for the dropdown

# -----------------------------------
# Section 6: Plot Settings
# -----------------------------------
# Settings for plot configurations (e.g., candlestick plot).
TIMESTEP = 12  # Time step for candlestick plot x-axis (1 = 5 minutes, 12 = 1 hour)

# -----------------------------------
# Section 7: Debug Output
# -----------------------------------
# Debug print statements to verify paths (enabled only if DEBUG_FLAG is True).
if DEBUG_FLAG:
    print(f"BASE_DIR: {BASE_DIR}")
    print(f"PERFORMANCE_CSV: {PERFORMANCE_CSV}")