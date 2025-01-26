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

def dynamic_trade_sizing(df):
    """
    Assign dynamic trade sizes based on historical PnL performance and volatility.

    Args:
        df (DataFrame): Trading data with PnL and other metrics.

    Returns:
        DataFrame: Updated data with dynamic trade sizes.
    """
    df['RollingMeanPnL'] = df['PnL'].rolling(window=50).mean()
    df['RollingStdPnL'] = df['PnL'].rolling(window=50).std()

    conditions = [
        (df['RollingStdPnL'] < 50) & (df['RollingMeanPnL'] > 0),
        (df['RollingStdPnL'] >= 50) & (df['RollingStdPnL'] < 100),
        (df['RollingStdPnL'] >= 100),
    ]
    sizes = [14, 10, 6]  # Adjust sizes based on conditions
    df['DynamicSize'] = np.select(conditions, sizes, default=4)

    return df

def allocate_trades_by_time(df):
    """
    Adjust trade allocation based on day and hour performance.

    Args:
        df (DataFrame): Trading data with datetime information.

    Returns:
        DataFrame: Updated data with adjusted allocations.
    """
    df['DayOfWeek'] = df['EnteredAt'].dt.day_name()
    df['HourOfDay'] = df['EnteredAt'].dt.hour

    df['TradeWeight'] = 1.0
    df.loc[df['DayOfWeek'].isin(['Tuesday', 'Friday']), 'TradeWeight'] += 0.5
    df.loc[df['HourOfDay'].isin([15, 16, 23]), 'TradeWeight'] += 0.5

    return df

def apply_stop_loss(df, max_loss=200):
    """
    Apply stop-loss to cap maximum losses on individual trades.

    Args:
        df (DataFrame): Trading data with PnL.
        max_loss (int): Maximum allowable loss per trade.

    Returns:
        DataFrame: Updated data with stop-loss applied.
    """
    df['AdjustedPnL'] = df['PnL'].apply(lambda x: x if x > -max_loss else -max_loss)
    return df

def monte_carlo_validation(df, num_simulations=1000, num_trades=200, target_profit=500):
    """
    Validate strategy using Monte Carlo simulations.

    Args:
        df (DataFrame): Trading data with PnL values.
        num_simulations (int): Number of simulations to run.
        num_trades (int): Number of trades per simulation.
        target_profit (float): Target profit level.

    Returns:
        dict: Simulation results including success rate and distribution.
    """
    pnl_values = df['PnL'].values
    success_count = 0

    results = []
    for _ in range(num_simulations):
        simulated_trades = np.random.choice(pnl_values, size=num_trades, replace=True)
        cumulative_pnl = np.sum(simulated_trades)
        results.append(cumulative_pnl)
        if cumulative_pnl >= target_profit:
            success_count += 1

    success_rate = success_count / num_simulations
    return {'SuccessRate': success_rate, 'Results': results}

def backtest_strategy(df):
    """
    Perform a backtest of the adjusted trading strategy.

    Args:
        df (DataFrame): Trading data with all adjustments applied.

    Returns:
        dict: Backtest results including total PnL and Sharpe Ratio.
    """
    df = dynamic_trade_sizing(df)
    df = allocate_trades_by_time(df)
    df = apply_stop_loss(df)

    df['WeightedPnL'] = df['AdjustedPnL'] * df['TradeWeight']
    total_pnl = df['WeightedPnL'].sum()
    sharpe_ratio = df['WeightedPnL'].mean() / df['WeightedPnL'].std()

    return {'TotalPnL': total_pnl, 'SharpeRatio': sharpe_ratio}

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

    file_path = os.path.join(performance_data_path, "Combined_Performance_with_Streaks.csv")  
    img_path = os.path.join(performace_img_path, "monte_carlo_simulation.png")

    if not os.path.exists(file_path):
        logger.info("Error: Combined performance data file not found.")
        return

    combined_df = pd.read_csv(file_path)
    combined_df['EnteredAt'] = pd.to_datetime(combined_df['EnteredAt'])

    # Backtest the strategy
    backtest_results = backtest_strategy(combined_df)
    print("Backtest Results:", backtest_results)

    # Run Monte Carlo validation
    monte_carlo_results = monte_carlo_validation(combined_df)

    # Plot Monte Carlo simulation results
    plt.figure(figsize=(10, 6))
    plt.hist(monte_carlo_results['Results'], bins=50, alpha=0.7, color='skyblue', edgecolor='black')
    plt.axvline(x=0, color='red', linestyle='--', label='Break-Even Line')
    plt.title('Monte Carlo Simulation Results')
    plt.xlabel('Cumulative PnL')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid()
    plt.savefig(img_path)

if __name__ == "__main__":
    main()
