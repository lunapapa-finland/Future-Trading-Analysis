import os
import re
from datetime import datetime
import pandas as pd
import configparser
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
from itertools import groupby
import matplotlib.pyplot as plt


def calculate_z_score(df):
    """Calculate Z-Score for all data."""
    # Count required values
    N = len(df)  # Total number of trades
    W = (df['WinOrLoss'] > 0).sum()  # Number of wins
    L = N - W  # Number of losses
    R = (df['WinOrLoss'] != df['WinOrLoss'].shift()).sum() + 1  # Number of streaks, including first streak
    X = 2 * W * L  # Intermediate value
    # Calculate Z-Score
    if N <= 1 or X <= 0:
        return None  # Not enough data or invalid configuration

    denominator = (X * (X - N) / (N - 1))
    if denominator <= 0:
        return None  # Prevent invalid square root

    z_score = (N * (R - 0.5) - X) / (denominator ** 0.5)
    return z_score

def calculate_winning_rate(df):
    """Calculate the winning rate of the trades."""
    winning_rate = (df['WinOrLoss'] > 0).sum() / len(df)
    return winning_rate

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

def plot_drawdown(df, base_path):
    """
    Plots the maximum drawdown and cumulative PnL.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'drawdown_analysis.png')

    df['CumulativePnL'] = df['PnL'].cumsum()
    df['Drawdown'] = df['CumulativePnL'] - df['CumulativePnL'].cummax()

    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['CumulativePnL'], label='Cumulative PnL')
    plt.fill_between(df.index, df['Drawdown'], 0, color='red', alpha=0.3, label='Drawdown')
    plt.title('Cumulative PnL and Drawdown Analysis')
    plt.xlabel('Trade Index')
    plt.ylabel('PnL')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def plot_profit_factor(df, base_path):
    """
    Plots the profit factor over time.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'profit_factor_analysis.png')

    df['CumulativeWins'] = df['PnL'].apply(lambda x: x if x > 0 else 0).cumsum()
    df['CumulativeLosses'] = df['PnL'].apply(lambda x: abs(x) if x < 0 else 0).cumsum()
    df['ProfitFactor'] = df['CumulativeWins'] / df['CumulativeLosses']

    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['ProfitFactor'], label='Profit Factor')
    plt.title('Profit Factor Over Time')
    plt.xlabel('Trade Index')
    plt.ylabel('Profit Factor')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def plot_streaks(df, base_path):
    """
    Plots streak patterns and saves to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with streak data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'streak_pattern.png')

    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['Streak'], marker='o', linestyle='-', label='Streak Pattern')
    plt.axhline(0, color='red', linestyle='--', linewidth=1, label='Zero Line')
    plt.title('Streak Pattern Over Trades')
    plt.xlabel('Trade Index')
    plt.ylabel('Streak Value')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def hourly_performance_trends(df, base_path):
    """
    Plots hourly performance trends showing Total PnL and Winning Rate, saving to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data, including 'EnteredAt' and 'PnL'.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'hourly_performance_trends.png')

    df['HourOfDay'] = df['EnteredAt'].dt.hour
    hourly_performance = df.groupby('HourOfDay').agg(
        TotalPnL=('PnL', 'sum'),
        WinningRate=('WinOrLoss', lambda x: (x > 0).mean()),
    )

    plt.figure(figsize=(10, 6))
    plt.plot(hourly_performance.index, hourly_performance['TotalPnL'], marker='o', label='Total PnL')
    plt.bar(hourly_performance.index, hourly_performance['WinningRate'], alpha=0.4, label='Winning Rate', color='orange')
    plt.axhline(0, color='red', linestyle='--', linewidth=1, label='Break-Even Line')
    plt.title('Hourly Performance Trends (GMT+2)')
    plt.xlabel('Hour of Day')
    plt.ylabel('Performance Metrics')
    plt.xticks(hourly_performance.index)
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def cumulative_pnl_over_trades(df, base_path):
    """
    Plots the cumulative PnL over trades, saving to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data, including 'PnL'.
        base_path (str): Base path to save images.
    """

    full_path = os.path.join(base_path, 'cumulative_pnl_over_trades.png')

    df['CumulativePnL'] = df['PnL'].cumsum()

    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['CumulativePnL'], marker='o', label='Cumulative PnL')
    plt.axhline(0, color='red', linestyle='--', linewidth=1, label='Break-Even Line')
    plt.title('Cumulative PnL Over Trades')
    plt.xlabel('Trade Index')
    plt.ylabel('Cumulative PnL')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def trade_size_impact_on_performance(df, base_path):
    """
    Plots the impact of trade size on Total PnL and Winning Rate, saving to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data, including 'Size' and 'PnL'.
        base_path (str): Base path to save images.
    """

    full_path = os.path.join(base_path, 'trade_size_impact_on_performance.png')

    trade_size_performance = df.groupby('Size').agg(
        TotalPnL=('PnL', 'sum'),
        WinningRate=('WinOrLoss', lambda x: (x > 0).mean()),
    )

    plt.figure(figsize=(10, 6))
    plt.bar(trade_size_performance.index, trade_size_performance['TotalPnL'], alpha=0.6, label='Total PnL')
    plt.plot(trade_size_performance.index, trade_size_performance['WinningRate'], marker='o', color='orange', label='Winning Rate')
    plt.title('Trade Size Impact on Performance')
    plt.xlabel('Trade Size')
    plt.ylabel('Performance Metrics')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def plot_all(df, base_path):
    """
    Generate plots for both overall and monthly performance.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    # Plot overall performance
    overall_base_path = os.path.join(base_path, 'overall')
    os.makedirs(overall_base_path, exist_ok=True)

    hourly_performance_trends(df, overall_base_path)
    # cumulative_pnl_over_trades(df, overall_base_path)
    trade_size_impact_on_performance(df, overall_base_path)
    plot_streaks(df, overall_base_path)
    plot_drawdown(df, overall_base_path)
    plot_profit_factor(df, overall_base_path)

    # Plot monthly performance
    df['YearMonth'] = df['EnteredAt'].dt.tz_localize(None).dt.to_period('M')
    for period, group in df.groupby('YearMonth'):
        monthly_base_path = os.path.join(base_path, str(period))
        os.makedirs(monthly_base_path, exist_ok=True)
        hourly_performance_trends(group, monthly_base_path)
        # cumulative_pnl_over_trades(group, monthly_base_path)
        trade_size_impact_on_performance(group, monthly_base_path)
        plot_streaks(group, monthly_base_path)
        plot_drawdown(group, monthly_base_path)
        plot_profit_factor(group, monthly_base_path)




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
        combined_df = pd.concat(valid_dataframes, ignore_index=True)
        logger.info("All valid files have been successfully concatenated.")
        
        # Sort the DataFrame by EnteredAt
        combined_df['EnteredAt'] = pd.to_datetime(combined_df['EnteredAt'])
        combined_df.sort_values(by='EnteredAt', inplace=True)

        # Reset the index after sorting
        combined_df.reset_index(drop=True, inplace=True)

        # Calculate streaks
        combined_df = calculate_streaks(combined_df)
        # Calculate Z-Score for all data

        z_score_all = calculate_z_score(combined_df)
        logger.info(f"Z-Score for all data: {z_score_all}")

        winning_rate = calculate_winning_rate(combined_df)
        logger.info(f"Winning rate in total {winning_rate}")


        plot_all(combined_df, performace_img_path)
        logger.info(f"Plots are done.")


        # Save the final DataFrame
        output_path = os.path.join(parameters_global['performace_data_path'], 'Combined_Performance_with_Streaks.csv')
        combined_df.to_csv(output_path, index=False)
        logger.info(f"Processed data saved to {output_path}")
    else:
        logger.warning("No valid data was found to concatenate.")


if __name__ == "__main__":

    main()