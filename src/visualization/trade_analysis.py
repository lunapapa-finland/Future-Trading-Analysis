import os
import re
from datetime import datetime
import pandas as pd
import configparser
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
from itertools import groupby
import matplotlib.pyplot as plt
import numpy as np
import pytz
import matplotlib

import matplotlib.dates as mdates
from scipy.stats import norm
from jinja2 import Environment, FileSystemLoader
import glob


def preprocess_dataframe(df):
    """
    Preprocesses the DataFrame by ensuring correct data types and derived columns.

    Args:
        df (DataFrame): Input DataFrame with trading data.

    Returns:
        DataFrame: Preprocessed DataFrame.
    """
    df = df.copy()
    df['EnteredAt'] = pd.to_datetime(df['EnteredAt'])
    df['ExitedAt'] = pd.to_datetime(df['ExitedAt'])
    df['YearMonth'] = df['EnteredAt'].dt.strftime('%Y-%m')
    df['DayOfWeek'] = df['EnteredAt'].dt.day_name()
    df['TradeDuration'] = (df['ExitedAt'] - df['EnteredAt']).dt.total_seconds() / 60  # Minutes
    return df

def chop_data(df):
    """
    Chops the DataFrame by year, month, and week.

    Args:
        df (DataFrame): Input DataFrame.

    Returns:
        dict: Dictionary with keys as folder names and values as DataFrames.
    """
    df = preprocess_dataframe(df)
    chopped = {}

    # By Year
    for year in df['EnteredAt'].dt.year.unique():
        year_df = df[df['EnteredAt'].dt.year == year]
        chopped[f'year_{year}'] = year_df

    # By Month
    for year_month in df['YearMonth'].unique():
        month_df = df[df['YearMonth'] == year_month]
        chopped[f'month_{year_month}'] = month_df

    # By Week
    df['Week'] = df['EnteredAt'].dt.isocalendar().week
    df['Year'] = df['EnteredAt'].dt.year
    for (year, week), group in df.groupby(['Year', 'Week']):
        chopped[f'week_{year}-{week:02d}'] = group

    return chopped

def ensure_directory(path):
    """Creates directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)

def plot_hourly_performance(df, base_path):
    """Plots average PnL and win rate by hour of day."""
    if df.empty:
        print("No data for hourly performance.")
        return
    full_path = os.path.join(base_path, 'hourly_performance.png')
    hourly_stats = df.groupby('HourOfDay').agg({
        'PnL(Net)': 'mean',
        'WinOrLoss': lambda x: (x == 1).mean()  # Win rate
    }).rename(columns={'PnL(Net)': 'AvgPnL', 'WinOrLoss': 'WinRate'})

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.bar(hourly_stats.index, hourly_stats['AvgPnL'], color='blue', alpha=0.6, label='Average PnL')
    ax1.set_xlabel('Hour of Day')
    ax1.set_ylabel('Average PnL(USD)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx()
    ax2.plot(hourly_stats.index, hourly_stats['WinRate'], color='red', marker='o', label='Win Rate')
    ax2.set_ylabel('Win Rate', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.title(f'Hourly Performance Analysis')
    fig.legend(loc='upper right', bbox_to_anchor=(0.9, 0.9))
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_streaks(df, base_path):
    """Plots streak patterns."""
    if df.empty:
        print("No data for streaks.")
        return
    full_path = os.path.join(base_path, 'streak_pattern.png')
    x = np.arange(1, len(df) + 1)
    unique_dates = df['TradeDay'].unique()
    n_dates = len(unique_dates)
    cmap = plt.colormaps['tab20']
    date_to_color = {date: cmap(i % 20) for i, date in enumerate(unique_dates)}

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(x, df['Streak'], linestyle='-', color='gray', alpha=0.3, label='Streak Pattern')
    for date in unique_dates:
        mask = df['TradeDay'] == date
        label = f'TradeDay {date}' if n_dates <= 5 else None
        ax.scatter(x[mask], df['Streak'][mask], color=date_to_color[date], marker='o', label=label)
    ax.axhline(0, color='red', linestyle='--', linewidth=1, label='Zero Line')
    ax.set_xlabel('Trade Number')
    ax.set_ylabel('Streak Value')
    start_date = df['EnteredAt'].dt.date.min()
    end_date = df['EnteredAt'].dt.date.max()
    ax.set_title(f'Streak Pattern Over Trades ({start_date} to {end_date})')
    if len(df) > 20:
        step = len(df) // 10 or 1
        ax.set_xticks(x[::step])
    else:
        ax.set_xticks(x)
    if n_dates > 5:
        ax.legend(['Streak Pattern', 'Zero Line'])
    elif n_dates > 0:
        ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_drawdown(df, base_path, use_gross_pnl=False, normalized=False):
    """
    Plots cumulative PnL and drawdown, either normalized or in raw USD.

    Args:
        df (DataFrame): Input DataFrame with trading data.
        base_path (str): Directory to save the plot.
        use_gross_pnl (bool): If True, use gross PnL (PnL + Fees); else, use net PnL.
        normalized (bool): If True, normalize PnL by mean absolute PnL; else, use raw USD.
    """
    if df.empty:
        print("No data for drawdown.")
        return
    # Adjust file name based on PnL type and normalization
    pnl_type = 'gross' if use_gross_pnl else 'net'
    norm_suffix = '_normalized' if normalized else ''
    full_path = os.path.join(base_path, f'drawdown_analysis_{pnl_type}{norm_suffix}.png')
    
    # Select PnL type
    if use_gross_pnl:
        df['AnalysisPnL'] = df['PnL(Net)'] + df['Fees']
        pnl_label = 'Gross PnL'
    else:
        df['AnalysisPnL'] = df['PnL(Net)']
        pnl_label = 'Net PnL'

    # Normalize or use raw PnL
    if normalized:
        mean_pnl = abs(df['AnalysisPnL']).mean()
        df['PlotPnL'] = df['AnalysisPnL'] / mean_pnl if mean_pnl != 0 else df['AnalysisPnL']
        unit_label = f'Normalized {pnl_label}'
    else:
        df['PlotPnL'] = df['AnalysisPnL']
        unit_label = f'{pnl_label} (USD)'

    # Compute cumulative PnL and drawdown
    df['CumulativePnL'] = df['PlotPnL'].cumsum()
    df['PeakPnL'] = df['CumulativePnL'].cummax()
    df['Drawdown'] = df['CumulativePnL'] - df['PeakPnL']
    df['DrawdownPct'] = df['Drawdown'] / df['PeakPnL'].replace(0, np.nan) * 100

    # Compute max and average drawdown
    max_drawdown = df['Drawdown'].min()
    max_drawdown_idx = df['Drawdown'].idxmin()
    avg_drawdown = df['Drawdown'][df['Drawdown'] < 0].mean() if df['Drawdown'].lt(0).any() else 0
    unit_suffix = '' if normalized else ' USD'
    print(f"Maximum Drawdown ({pnl_label}, {'Normalized' if normalized else 'Raw'}): {max_drawdown:.2f}{unit_suffix} at index {max_drawdown_idx}")
    print(f"Average Drawdown ({pnl_label}, {'Normalized' if normalized else 'Raw'}): {avg_drawdown:.2f}{unit_suffix}")

    # Plotting
    plt.figure(figsize=(12, 6))
    plt.plot(df['EnteredAt'], df['CumulativePnL'], label=f'Cumulative {unit_label}', color='blue')
    plt.fill_between(df['EnteredAt'], df['Drawdown'], 0, color='red', alpha=0.3, label='Drawdown')
    plt.axhline(0, color='black', linestyle='--', linewidth=1, label='Zero Line')
    losing_trades = df['WinOrLoss'] == -1
    plt.scatter(df['EnteredAt'][losing_trades], df['CumulativePnL'][losing_trades], 
                color='black', marker='x', label='Losing Trades')
    plt.annotate(f'Max Drawdown: {max_drawdown:.2f}{unit_suffix}', 
                 xy=(df['EnteredAt'][max_drawdown_idx], max_drawdown), 
                 xytext=(10, 10), textcoords='offset points', 
                 arrowprops=dict(arrowstyle='->'), color='red')
    # Annotate the last point's y-value
    last_pnl = df['CumulativePnL'].iloc[-1]
    last_date = df['EnteredAt'].iloc[-1]
    plt.annotate(f'{last_pnl:.2f}{unit_suffix}', 
                 xy=(last_date, last_pnl), 
                 xytext=(10, 10), textcoords='offset points', 
                 arrowprops=dict(arrowstyle='->'), color='blue')
    plt.title(f'Cumulative {unit_label} and Drawdown ({df["EnteredAt"].dt.date.min()} to {df["EnteredAt"].dt.date.max()})')
    plt.xlabel('Trade Date')
    plt.ylabel(unit_label)
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_profit_factor(df, base_path):
    """Plots profit factor over time."""
    if df.empty or len(df) < 2:
        print("Insufficient data for profit factor.")
        return
    full_path = os.path.join(base_path, 'profit_factor.png')
    df['GrossProfit'] = df['PnL(Net)'].where(df['PnL(Net)'] > 0, 0)
    df['GrossLoss'] = -df['PnL(Net)'].where(df['PnL(Net)'] < 0, 0)
    df['CumGrossProfit'] = df['GrossProfit'].cumsum()
    df['CumGrossLoss'] = df['GrossLoss'].cumsum()
    df['ProfitFactor'] = df['CumGrossProfit'] / df['CumGrossLoss'].replace(0, np.nan)

    plt.figure(figsize=(10, 6))
    plt.plot(df['EnteredAt'], df['ProfitFactor'], label='Profit Factor', color='green')
    plt.axhline(1, color='red', linestyle='--', label='Break-even (1)')
    plt.title(f'Profit Factor Over Time')
    plt.xlabel('Trade Date and Time')
    plt.ylabel('Profit Factor')
    plt.legend()
    plt.grid(True, alpha=0.3)
    # Use timestamps for weekly chops, dates for others
    if 'week' in base_path.lower():
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))  # Show every 4 hours
    else:
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_sharpe_ratio(df, base_path):
    """Plots rolling Sharpe ratio."""
    if df.empty or len(df) < 10:
        print("Insufficient data for Sharpe ratio.")
        return
    full_path = os.path.join(base_path, 'sharpe_ratio.png')
    window = min(20, len(df))
    df['Returns'] = df['PnL(Net)'] / abs(df['PnL(Net)']).mean()  # Normalized returns
    df['RollingMean'] = df['Returns'].rolling(window=window, min_periods=1).mean()
    df['RollingStd'] = df['Returns'].rolling(window=window, min_periods=1).std()
    df['SharpeRatio'] = (df['RollingMean'] / df['RollingStd'] * np.sqrt(252)).replace([np.inf, -np.inf], np.nan)

    plt.figure(figsize=(10, 6))
    plt.plot(df['EnteredAt'], df['SharpeRatio'], label='Rolling Sharpe Ratio', color='purple')
    plt.axhline(0, color='black', linestyle='--', label='Zero')
    plt.title(f'Rolling Sharpe Ratio (Window={window} Trades)')
    plt.xlabel('Trade Date and Time')
    plt.ylabel('Sharpe Ratio')
    plt.legend()
    plt.grid(True, alpha=0.3)
    # Use timestamps for weekly chops, dates for others
    if 'week' in base_path.lower():
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))  # Show every 4 hours
    else:
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_day_of_week_performance(df, base_path):
    """Plots PnL and win rate by day of week."""
    if df.empty:
        print("No data for day of week performance.")
        return
    full_path = os.path.join(base_path, 'day_of_week_performance.png')
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    day_stats = df.groupby('DayOfWeek').agg({
        'PnL(Net)': 'mean',
        'WinOrLoss': lambda x: (x == 1).mean()
    }).reindex(day_order).rename(columns={'PnL(Net)': 'AvgPnL', 'WinOrLoss': 'WinRate'})

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.bar(day_stats.index, day_stats['AvgPnL'], color='blue', alpha=0.6, label='Average PnL')
    ax1.set_xlabel('Day of Week')
    ax1.set_ylabel('Average PnL', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.set_xticks(range(len(day_stats.index)))  # Set ticks explicitly
    ax1.set_xticklabels(day_stats.index, rotation=45)

    ax2 = ax1.twinx()
    ax2.plot(day_stats.index, day_stats['WinRate'], color='red', marker='o', label='Win Rate')
    ax2.set_ylabel('Win Rate', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.title(f'Day of Week Performance')
    fig.legend(loc='upper right', bbox_to_anchor=(0.9, 0.9))
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_pnl_distribution(df, base_path):
    """Plots histogram of PnL distribution with fitted normal curve."""
    if df.empty:
        print("No data for PnL distribution.")
        return
    full_path = os.path.join(base_path, 'pnl_distribution.png')
    plt.figure(figsize=(10, 6))
    plt.hist(df['PnL(Net)'], bins=30, density=True, alpha=0.6, color='blue', label='PnL Distribution')
    mu, sigma = df['PnL(Net)'].mean(), df['PnL(Net)'].std()
    x = np.linspace(df['PnL(Net)'].min(), df['PnL(Net)'].max(), 100)
    plt.plot(x, norm.pdf(x, mu, sigma), 'r-', lw=2, label=f'Normal Fit (μ={mu:.2f}, σ={sigma:.2f})')
    plt.title(f'PnL Distribution')
    plt.xlabel('PnL (Net)')
    plt.ylabel('Density')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_rolling_winning_rate(df, base_path):
    """Plots rolling winning rate."""
    if df.empty or len(df) < 10:
        print("Insufficient data for rolling winning rate.")
        return
    full_path = os.path.join(base_path, 'rolling_winning_rate.png')
    window = min(20, len(df))
    df['RollingWinRate'] = df['WinOrLoss'].rolling(window=window, min_periods=1).apply(lambda x: (x == 1).mean())

    plt.figure(figsize=(10, 6))
    plt.plot(df['EnteredAt'], df['RollingWinRate'], label=f'Rolling Win Rate (Window={window})', color='orange')
    plt.axhline(0.5, color='red', linestyle='--', label='50% Win Rate')
    plt.title(f'Rolling Winning Rate')
    plt.xlabel('Trade Date and Time')
    plt.ylabel('Win Rate')
    plt.legend()
    plt.grid(True, alpha=0.3)
    # Use timestamps for weekly chops, dates for others
    if 'week' in base_path.lower():
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))  # Show every 4 hours
    else:
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.gca().xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_size_and_risk_analysis(df, base_path):
    """Plots PnL by trade size and risk metrics."""
    if df.empty:
        print("No data for size and risk analysis.")
        return
    full_path = os.path.join(base_path, 'size_and_risk.png')
    size_stats = df.groupby('Size').agg({
        'PnL(Net)': 'mean',
        'WinOrLoss': lambda x: (x == 1).mean()
    }).rename(columns={'PnL(Net)': 'AvgPnL', 'WinOrLoss': 'WinRate'})

    fig, ax1 = plt.subplots(figsize=(10, 6))
    ax1.bar(size_stats.index, size_stats['AvgPnL'], color='blue', alpha=0.6, label='Average PnL')
    ax1.set_xlabel('Trade Size')
    ax1.set_ylabel('Average PnL(USD)', color='blue')
    ax1.tick_params(axis='y', labelcolor='blue')

    ax2 = ax1.twinx()
    ax2.plot(size_stats.index, size_stats['WinRate'], color='red', marker='o', label='Win Rate')
    ax2.set_ylabel('Win Rate', color='red')
    ax2.tick_params(axis='y', labelcolor='red')

    plt.title(f'PnL and Win Rate by Trade Size')
    fig.legend(loc='upper right', bbox_to_anchor=(0.9, 0.9))
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_trade_duration_analysis(df, base_path):
    """Plots trade duration distribution by win/loss."""
    if df.empty:
        print("No data for trade duration analysis.")
        return
    full_path = os.path.join(base_path, 'trade_duration.png')
    wins = df[df['WinOrLoss'] == 1]['TradeDuration']
    losses = df[df['WinOrLoss'] == -1]['TradeDuration']

    plt.figure(figsize=(10, 6))
    plt.hist(wins, bins=30, alpha=0.5, color='green', label='Winning Trades', density=True)
    plt.hist(losses, bins=30, alpha=0.5, color='red', label='Losing Trades', density=True)
    plt.title(f'Trade Duration Distribution')
    plt.xlabel('Trade Duration (Minutes)')
    plt.ylabel('Density')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_win_loss_ratio_by_hour(df, base_path):
    """Plots win/loss ratio by hour of day."""
    if df.empty:
        print("No data for win/loss ratio by hour.")
        return
    full_path = os.path.join(base_path, 'win_loss_ratio_by_hour.png')
    hourly_counts = df.groupby('HourOfDay')['WinOrLoss'].value_counts().unstack(fill_value=0)
    hourly_counts['WinLossRatio'] = hourly_counts.get(1, 0) / hourly_counts.get(-1, 0).replace(0, np.nan)

    plt.figure(figsize=(10, 6))
    plt.plot(hourly_counts.index, hourly_counts['WinLossRatio'], marker='o', color='teal', label='Win/Loss Ratio')
    plt.axhline(1, color='red', linestyle='--', label='Equal Win/Loss')
    plt.title(f'Win/Loss Ratio by Hour of Day')
    plt.xlabel('Hour of Day')
    plt.ylabel('Win/Loss Ratio')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(full_path, bbox_inches='tight')
    plt.close()

def plot_all(combined_df, performance_img_path):
    """
    Chops data by year, month, and week, then generates all performance analyses.

    Args:
        combined_df (DataFrame): Input DataFrame with trading data.
        performance_img_path (str): Base path to save performance images.
    """
    # Chop data
    chopped_data = chop_data(combined_df)

    # Analysis functions
    analyses = [
        plot_hourly_performance,
        plot_streaks,
        plot_drawdown,
        plot_profit_factor,
        plot_sharpe_ratio,
        plot_day_of_week_performance,
        plot_pnl_distribution,
        plot_rolling_winning_rate,
        plot_size_and_risk_analysis,
        plot_trade_duration_analysis,
        plot_win_loss_ratio_by_hour
    ]

    # Process each chopped dataset
    for folder_name, df in chopped_data.items():
        folder_path = os.path.join(performance_img_path, folder_name)
        ensure_directory(folder_path)
        print(f"Generating plots for {folder_name}...")

        for analysis_func in analyses:
            if analysis_func == plot_drawdown:
                # Run drawdown with net PnL (both normalized and raw)
                analysis_func(df, folder_path, use_gross_pnl=False, normalized=False)
                analysis_func(df, folder_path, use_gross_pnl=False, normalized=True)
                # Run drawdown with gross PnL (both normalized and raw)
                analysis_func(df, folder_path, use_gross_pnl=True, normalized=False)
                analysis_func(df, folder_path, use_gross_pnl=True, normalized=True)
            else:
                analysis_func(df, folder_path)

def calculate_streaks(df):
    """
    Calculate streaks for given rolling window sizes.

    Args:
        df (DataFrame): The combined dataframe with trading data.

    Returns:
        DataFrame: Updated dataframe with streak values.
    """
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

def generate_aggregated_data(valid_dataframes, logger, parameters_global):
    combined_df = pd.concat(valid_dataframes, ignore_index=True)
    logger.info("All valid files have been successfully concatenated.")
    # Sort the DataFrame by EnteredAt
    # Replace adjust_to_finnish_timezone function
    combined_df['EnteredAt'] = pd.to_datetime(combined_df['EnteredAt'], utc=True).dt.tz_convert('Europe/Helsinki')
    combined_df['ExitedAt'] = pd.to_datetime(combined_df['ExitedAt'], utc=True).dt.tz_convert('Europe/Helsinki')
    combined_df['TradeDay'] = pd.to_datetime(combined_df['EnteredAt'], utc=True).dt.tz_convert('Europe/Helsinki').dt.strftime('%Y-%m-%d')
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
    output_path = os.path.join(parameters_global['performace_data_path'], 'Combined_Performance_with_Streaks.csv')
    combined_df.to_csv(output_path, index=False)
    logger.info(f"Processed data saved to {output_path}")
    return combined_df

def generate_html_index(performace_img_path, chopped_data):
    """
    Generates static HTML index pages for each folder in performace_img_path using Jinja2.

    Args:
        performace_img_path (str): Path to the performance images directory.
        chopped_data (dict): Dictionary from chop_data with folder names and DataFrames.
    """
    # Initialize Jinja2 environment
    env = Environment(loader=FileSystemLoader('./src/jinja2'))
    template = env.get_template('analysis.html.j2')

    # Define analysis categories and image mappings
    analysis_categories = {
        'Performance Over Time': [
            'profit_factor.png',
            'rolling_winning_rate.png',
            'sharpe_ratio.png'
        ],
        'Drawdown Analysis': [
            'drawdown_analysis_net.png',
            'drawdown_analysis_net_normalized.png',
            'drawdown_analysis_gross.png',
            'drawdown_analysis_gross_normalized.png'
        ],
        'Time-Based Performance': [
            'hourly_performance.png',
            'day_of_week_performance.png',
            'win_loss_ratio_by_hour.png'
        ],
        'Trade Characteristics': [
            'pnl_distribution.png',
            'size_and_risk.png',
            'trade_duration.png'
        ],
        'Streaks': [
            'streak_pattern.png'
        ]
    }

    # List of folders (from chopped_data)
    folders = list(chopped_data.keys())  # e.g., ['year_2025', 'month_2025-04', 'week_2025-16']

    # Generate index.html for root performace_img_path
    root_categorized_images = {}
    for category, image_names in analysis_categories.items():
        root_categorized_images[category] = []
        for folder in folders:
            folder_path = os.path.join(performace_img_path, folder)
            for image_name in image_names:
                image_path = os.path.join(folder_path, image_name)
                if os.path.exists(image_path):
                    relative_path = os.path.join(folder, image_name)
                    root_categorized_images[category].append({
                        'path': relative_path,
                        'name': image_name,
                        'folder': folder
                    })

    # Render root index.html
    root_html = template.render(
        title='Performance Analysis - All Periods',
        folders=folders,
        current_folder=None,
        is_root=True,
        categorized_images=root_categorized_images
    )
    root_html_path = os.path.join(performace_img_path, 'index.html')
    with open(root_html_path, 'w') as f:
        f.write(root_html)

    # Generate index.html for each subfolder
    for folder in folders:
        folder_path = os.path.join(performace_img_path, folder)
        categorized_images = {}
        for category, image_names in analysis_categories.items():
            categorized_images[category] = []
            for image_name in image_names:
                image_path = os.path.join(folder_path, image_name)
                if os.path.exists(image_path):
                    relative_path = image_name  # Relative to the folder
                    categorized_images[category].append({
                        'path': relative_path,
                        'name': image_name,
                        'folder': folder
                    })

        # Render folder index.html
        folder_html = template.render(
            title=f'Performance Analysis - {folder}',
            folders=folders,
            current_folder=folder,
            is_root=False,
            categorized_images=categorized_images
        )
        folder_html_path = os.path.join(folder_path, 'index.html')
        with open(folder_html_path, 'w') as f:
            f.write(folder_html)

def main():
    # Load configuration
    config = configparser.ConfigParser()
    config.read('config.ini')
    parameters_global = remove_comments_and_convert(config, 'global')
    parameters_report = remove_comments_and_convert(config, 'report')

    # Load logger
    logger = get_logger('data.log', parameters_global['log_path'])

    # Path to performance data
    performance_data_path = parameters_global['performace_data_path']
    performace_img_path = parameters_global['performace_img_path']

    # Ensure the performance image path exists
    if not os.path.exists(performace_img_path):
        os.makedirs(performace_img_path)

    # List to store dataframes
    all_dataframes = []

    for filename in os.listdir(performance_data_path):
        if filename.startswith('Performance_') and filename.endswith('.csv'):
            file_path = os.path.join(performance_data_path, filename)
            try:
                df = pd.read_csv(file_path)
                if not df.empty:
                    all_dataframes.append(df)
            except Exception as e:
                logger.error(f"Failed to read {filename}: {e}")

    # Concatenate all dataframes
    valid_dataframes = [df for df in all_dataframes if not df.empty]
    if valid_dataframes:
        combined_df = generate_aggregated_data(valid_dataframes, logger, parameters_global)
    else:
        logger.warning("No valid data was found to concatenate.")

   # Chop data for folder structure
    chopped_data = chop_data(combined_df)

    plot_all(combined_df, performace_img_path)

    # Generate HTML index pages
    generate_html_index(performace_img_path, chopped_data)

if __name__ == "__main__":

    main()