import pandas as pd
import yfinance as yf
import logging
import time
from datetime import timedelta
from pathlib import Path
from dashboard.config.settings import  LOGGING_PATH, PERFORMANCE_DIR, TIMEZONE, PERFORMANCE_CSV
import os

# Configure logging
logging.basicConfig(
    filename=LOGGING_PATH,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def calculate_streaks(df):
    df['WinOrLoss'] = df['PnL'].apply(lambda x: 1 if x > 0 else -1)
    df['Streak'] = 0
    streak_counter = 0

    for i in range(len(df)):
        if i == 0 or df['WinOrLoss'].iloc[i] != df['WinOrLoss'].iloc[i - 1]:
            streak_counter = 1
        else:
            streak_counter += 1
        df.loc[i, 'Streak'] = streak_counter * df['WinOrLoss'].iloc[i]

    return df

def generate_aggregated_data(valid_dataframes):
    combined_df = pd.concat(valid_dataframes, ignore_index=True)
    logging.info("All valid files have been successfully concatenated.")
    # Sort the DataFrame by EnteredAt
    # Replace adjust_to_finnish_timezone function
    combined_df['EnteredAt'] = pd.to_datetime(combined_df['EnteredAt'], utc=True).dt.tz_convert(TIMEZONE)
    combined_df['ExitedAt'] = pd.to_datetime(combined_df['ExitedAt'], utc=True).dt.tz_convert(TIMEZONE)
    combined_df['TradeDay'] = pd.to_datetime(combined_df['EnteredAt'], utc=True).dt.tz_convert(TIMEZONE).dt.strftime('%Y-%m-%d')
    combined_df.sort_values(by='EnteredAt', inplace=True)
    combined_df.reset_index(drop=True, inplace=True)
    combined_df = calculate_streaks(combined_df)
    combined_df['DayOfWeek'] = combined_df['EnteredAt'].dt.day_name()
    combined_df['YearMonth'] = combined_df['EnteredAt'].dt.tz_localize(None).dt.to_period('M')
    combined_df['HourOfDay'] = combined_df['EnteredAt'].dt.hour
    combined_df = combined_df.rename(columns={'Id': 'IntradayIndex'})
    combined_df = combined_df.rename(columns={'PnL': 'PnL(Net)'})
    desired_columns = [
            'YearMonth', 'TradeDay', 'DayOfWeek', 'HourOfDay', 'ContractName', 'IntradayIndex',
            'EnteredAt', 'ExitedAt', 'EntryPrice', 'ExitPrice', 'Fees', 'PnL(Net)',
            'Size', 'Type', 'TradeDuration', 'WinOrLoss', 'Streak'
        ]
    available_columns = [col for col in desired_columns if col in combined_df.columns]
    combined_df = combined_df[available_columns]

    # Save the final DataFrame

    combined_df.to_csv(PERFORMANCE_CSV, index=False)
    logging.info(f"Processed data saved to {PERFORMANCE_CSV}")
    return combined_df

def acquire_missing_performance():
    """Acquire missing performace data"""
    all_dataframes = []
    for filename in os.listdir(PERFORMANCE_DIR):
        if filename.startswith('Performance_') and filename.endswith('.csv'):
            file_path = os.path.join(PERFORMANCE_DIR, filename)
            try:
                df = pd.read_csv(file_path)
                if not df.empty:
                    all_dataframes.append(df)
            except Exception as e:
                logging.error(f"Failed to read {filename}: {e}")
    # Concatenate all dataframes
    valid_dataframes = [df for df in all_dataframes if not df.empty]
    if valid_dataframes:
        generate_aggregated_data(valid_dataframes)
    else:
        logging.warning("No valid data was found to concatenate.")


if __name__ == "__main__":
    acquire_missing_performance()