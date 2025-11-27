import glob
import logging
import os
import time
from collections import deque
from datetime import timedelta
from pathlib import Path

import pandas as pd
import pytz
import yfinance as yf

from dashboard.config.settings import PERFORMANCE_DIR, TIMEZONE, PERFORMANCE_CSV
from dashboard.config.env import LOGGING_PATH, BASE_DIR

# Configure logging
logging.basicConfig(
    filename=LOGGING_PATH,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def process_csv(file_path):
    # Read the CSV data
    df = pd.read_csv(file_path)

    # Convert 'Date/Time' to datetime
    df['Date/Time'] = pd.to_datetime(df['Date/Time'], format='%Y%m%d;%H%M%S')

    # Localize to Eastern Time (America/New_York)
    eastern_tz = pytz.timezone('America/New_York')
    df['Date/Time'] = df['Date/Time'].apply(lambda x: x.tz_localize(eastern_tz))

    # Sort by 'Date/Time' for FIFO
    df = df.sort_values('Date/Time').reset_index(drop=True)

    # Calculate per-unit fees
    def calculate_trade_fee(row):
        return (
            abs(row['BrokerExecutionCommission']) +
            abs(row['ThirdPartyExecutionCommission']) +
            abs(row['ThirdPartyRegulatoryCommission'])
        )

    df['TotalFee'] = df.apply(calculate_trade_fee, axis=1)
    df['FeePerUnit'] = df['TotalFee'] / df['Quantity'].abs()

    # Initialize round trips list
    round_trips = []

    # Group trades by symbol
    for symbol in df['Symbol'].unique():
        symbol_df = df[df['Symbol'] == symbol].copy()

        # Initialize queues for this symbol
        buy_trades = deque()
        sell_trades = deque()

        # Split trades into single-unit trades
        for _, row in symbol_df.iterrows():
            qty = int(row['Quantity'])
            fee_per_unit = row['TotalFee'] / abs(qty)
            trade = {
                'Time': row['Date/Time'],
                'Price': row['Price'],
                'FeePerUnit': fee_per_unit,
                'TradeDate': row['TradeDate'],
                'Symbol': row['Symbol'],
                'OriginalQty': qty
            }
            if qty > 0:
                for _ in range(qty):
                    buy_trades.append(trade.copy())
            else:
                for _ in range(-qty):
                    sell_trades.append(trade.copy())

        # Generate round trips for this symbol
        while buy_trades and sell_trades:
            buy = buy_trades.popleft()
            sell = sell_trades.popleft()
            
            # Determine trade type
            if buy['Time'] <= sell['Time']:
                trade_type = 'Long'
                entered_at = buy['Time']
                exited_at = sell['Time']
                entry_price = buy['Price']
                exit_price = sell['Price']
                fees = buy['FeePerUnit'] + sell['FeePerUnit']
                pnl = (exit_price - entry_price) * 5 - fees
            else:
                trade_type = 'Short'
                entered_at = sell['Time']
                exited_at = buy['Time']
                entry_price = sell['Price']
                exit_price = buy['Price']
                fees = buy['FeePerUnit'] + sell['FeePerUnit']
                pnl = (entry_price - exit_price) * 5 - fees

            # Calculate duration
            trade_duration_seconds = (exited_at - entered_at).total_seconds()
            trade_duration_days = trade_duration_seconds // (24 * 3600)
            trade_duration_seconds %= (24 * 3600)
            trade_duration_hours = trade_duration_seconds // 3600
            trade_duration_seconds %= 3600
            trade_duration_minutes = trade_duration_seconds // 60
            trade_duration_seconds %= 60
            trade_duration_seconds = int(trade_duration_seconds)
            trade_duration_str = f"{int(trade_duration_days)} days {int(trade_duration_hours):02}:{int(trade_duration_minutes):02}:{trade_duration_seconds:02}"

            # Convert to +03:00 timezone
            target_tz = pytz.timezone('US/Central')
            entered_at_tz = entered_at.astimezone(target_tz)
            exited_at_tz = exited_at.astimezone(target_tz)
            entered_at_str = entered_at_tz.strftime('%m/%d/%Y %H:%M:%S %z').replace('+0300', '+03:00')
            exited_at_str = exited_at_tz.strftime('%m/%d/%Y %H:%M:%S %z').replace('+0300', '+03:00')

            # Create round trip
            round_trip = {
                'ContractName': buy['Symbol'],
                'EnteredAt': entered_at_str,
                'ExitedAt': exited_at_str,
                'EntryPrice': entry_price,
                'ExitPrice': exit_price,
                'Fees': round(fees, 2),
                'PnL': round(pnl, 2),
                'Size': 1,
                'Type': trade_type,
                'TradeDay': entered_at_str,
                'TradeDuration': trade_duration_str
            }
            round_trips.append(round_trip)

        # Print unmatched buy trades
        if buy_trades:
            print(f"\nUnmatched BUY trades for symbol {symbol}:")
            for t in buy_trades:
                print(f"  Time: {t['Time']}, Price: {t['Price']}, Qty: 1, Symbol: {t['Symbol']}")

        # Print unmatched sell trades
        if sell_trades:
            print(f"\nUnmatched SELL trades for symbol {symbol}:")
            for t in sell_trades:
                print(f"  Time: {t['Time']}, Price: {t['Price']}, Qty: 1, Symbol: {t['Symbol']}")

    # Convert to DataFrame
    round_trips_df = pd.DataFrame(round_trips)

    # Combine round trips with identical EnteredAt and ExitedAt
    grouped = round_trips_df.groupby([
        'EnteredAt', 'ExitedAt', 'ContractName', 'Type', 'EntryPrice', 'ExitPrice'
    ]).agg({
        'Size': 'sum',
        'PnL': 'sum',
        'Fees': 'sum',
        'TradeDay': 'first',
        'TradeDuration': 'first'
    }).reset_index()

    # Assign Ids based on trade day
    grouped['TradeDate'] = pd.to_datetime(grouped['TradeDay'], format='%m/%d/%Y %H:%M:%S %z').dt.date
    grouped = grouped.sort_values(['TradeDate', 'EnteredAt']).reset_index(drop=True)
    
    # Reset Id for each unique trade date
    grouped['Id'] = 1
    for date in grouped['TradeDate'].unique():
        mask = grouped['TradeDate'] == date
        grouped.loc[mask, 'Id'] = range(1, mask.sum() + 1)

    # Drop temporary TradeDate column
    grouped = grouped.drop(columns=['TradeDate'])

    # Reorder columns
    output_columns = [
        'Id', 'ContractName', 'EnteredAt', 'ExitedAt', 'EntryPrice', 'ExitPrice',
        'Fees', 'PnL', 'Size', 'Type', 'TradeDay', 'TradeDuration'
    ]
    round_trips_df = grouped[output_columns]

    return round_trips_df

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
    past_performance_df = pd.read_csv(PERFORMANCE_CSV) if os.path.exists(PERFORMANCE_CSV) else pd.DataFrame()
    past_performance_df['EnteredAt'] = pd.to_datetime(past_performance_df['EnteredAt'], utc=True).dt.tz_convert(TIMEZONE)
    past_performance_df['ExitedAt'] = pd.to_datetime(past_performance_df['ExitedAt'], utc=True).dt.tz_convert(TIMEZONE)
    past_performance_df['TradeDay'] = pd.to_datetime(past_performance_df['EnteredAt'], utc=True).dt.tz_convert(TIMEZONE).dt.strftime('%Y-%m-%d')
    past_performance_df['DayOfWeek'] = past_performance_df['EnteredAt'].dt.day_name()
    past_performance_df['YearMonth'] = past_performance_df['EnteredAt'].dt.tz_localize(None).dt.to_period('M')
    past_performance_df['HourOfDay'] = past_performance_df['EnteredAt'].dt.hour

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
    combined_df['Comment'] = combined_df.get('Comment', '')
    desired_columns = [
            'YearMonth', 'TradeDay', 'DayOfWeek', 'HourOfDay', 'ContractName', 'IntradayIndex',
            'EnteredAt', 'ExitedAt', 'EntryPrice', 'ExitPrice', 'Fees', 'PnL(Net)',
            'Size', 'Type', 'TradeDuration', 'WinOrLoss', 'Streak', 'Comment'
        ]
    available_columns = [col for col in desired_columns if col in combined_df.columns]
    combined_df = combined_df[available_columns]

    # Keep all columns except Comment for comparison
    comparison_columns = [col for col in combined_df.columns if col not in ['Comment', 'Fees', 'PnL(Net)', 'TradeDuration', 'Streak'] and col in past_performance_df.columns]

    # Drop duplicates: only keep rows in combined_df that are not already in past_performance_df
    if not past_performance_df.empty:
        merged = combined_df.merge(
            past_performance_df[comparison_columns],
            on=comparison_columns,
            how='left',
            indicator=True
        )
        new_rows_df = merged[merged['_merge'] == 'left_only'].drop(columns=['_merge'])
        # Restore 'Comment' column, which may be dropped by merge
        if 'Comment' not in new_rows_df.columns:
            new_rows_df['Comment'] = ''
    else:
        new_rows_df = combined_df.copy()

    # Concatenate old and new
    final_df = pd.concat([past_performance_df, new_rows_df], ignore_index=True)
    if not new_rows_df.empty:
        print(f"New trades added: {new_rows_df}")
    else:
        logging.info("No new trades to add.")
    # Save and return
    final_df.to_csv(PERFORMANCE_CSV, index=False)
    logging.info(f"Processed data saved to {PERFORMANCE_CSV}")
    return final_df

def round_trip_converter():
    # Define the performance directory
    root_dir = os.path.join(BASE_DIR, 'data', 'temp_performance')
    target_dir = os.path.join(BASE_DIR, 'data', 'performance')
    # Find all CSV files starting with 'Raw_' in the root directory
    csv_files = glob.glob(os.path.join(root_dir, '*.csv'))

    # Process each CSV file
    for file_path in csv_files:
        print(f"Processing {file_path}...")
        
        # Generate round trips
        round_trips_df = process_csv(file_path)
        round_trips_df['TradeDay'] = pd.to_datetime(round_trips_df['TradeDay'])
        startdate=round_trips_df['TradeDay'].min().date()
        enddate=round_trips_df['TradeDay'].max().date()
        # Extract date range from the file name
        # Generate output filename in the same directory, removing 'Raw_' prefix
        output_filename = os.path.join(
            target_dir,
            f'Performance_{startdate}_to_{enddate}.csv'
            )
        
        # Save the output CSV
        round_trips_df.to_csv(output_filename, index=False)
        
        print(f"Saved output to {output_filename}\n")
        os.remove(file_path)  # Remove the original file after processing


def acquire_missing_performance():
    round_trip_converter()
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
