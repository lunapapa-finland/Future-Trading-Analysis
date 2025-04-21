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

def adjust_to_finnish_timezone(df):
    """Convert mixed time zone data to Finnish time zone (Europe/Helsinki)."""
    finland_tz = pytz.timezone('Europe/Helsinki')  # Finland uses Europe/Helsinki timezone
    
    def convert_to_finnish_timezone(col):
        """Helper function to convert a datetime column to Finnish time zone."""
        # Ensure the datetime column is parsed correctly with the timezone
        col = pd.to_datetime(col, errors='coerce', utc=True)  # Force to datetime and handle mixed time zones
        
        # If the datetime is already tz-aware, we just convert it to Finnish time zone
        if col.dt.tz is not None:
            col = col.dt.tz_convert(finland_tz)
        else:
            # If the datetime is naive (no time zone), we assume it's in UTC and localize to Finnish time zone
            col = col.dt.tz_localize('UTC').dt.tz_convert(finland_tz)
        
        return col

    # Apply the conversion to all relevant columns
    df['EnteredAt'] = convert_to_finnish_timezone(df['EnteredAt'])
    df['ExitedAt'] = convert_to_finnish_timezone(df['ExitedAt'])
    df['TradeDay'] = convert_to_finnish_timezone(df['TradeDay'])
    
    return df


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
    Plots the maximum drawdown and normalized cumulative PnL.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'drawdown_analysis.png')

    # Normalize PnL by the number of trades
    df['NormalizedPnL'] = df['PnL'] / df['PnL'].mean()

    # Calculate cumulative PnL and drawdown using normalized PnL
    df['CumulativePnL'] = df['NormalizedPnL'].cumsum()
    df['Drawdown'] = df['CumulativePnL'] - df['CumulativePnL'].cummax()

    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['CumulativePnL'], label='Cumulative Normalized PnL')
    plt.fill_between(df.index, df['Drawdown'], 0, color='red', alpha=0.3, label='Drawdown')
    plt.title('Normalized Cumulative PnL and Drawdown Analysis')
    plt.xlabel('Trade Index')
    plt.ylabel('Normalized PnL')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def plot_profit_factor(df, base_path):
    """
    Plots the profit factor using normalized cumulative PnL.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'profit_factor_analysis.png')

    # Normalize PnL
    df['NormalizedPnL'] = df['PnL'] / df['PnL'].mean()

    # Calculate normalized cumulative wins and losses
    df['CumulativeWins'] = df['NormalizedPnL'].apply(lambda x: x if x > 0 else 0).cumsum()
    df['CumulativeLosses'] = df['NormalizedPnL'].apply(lambda x: abs(x) if x < 0 else 0).cumsum()
    df['ProfitFactor'] = df['CumulativeWins'] / df['CumulativeLosses']

    plt.figure(figsize=(10, 6))
    plt.plot(df.index, df['ProfitFactor'], label='Normalized Profit Factor')
    plt.title('Normalized Profit Factor Over Time')
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
    Plots hourly performance trends normalized by trade frequency.

    Args:
        df (DataFrame): The combined dataframe with trading data, including 'EnteredAt' and 'PnL'.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'hourly_performance_trends.png')

    df['HourOfDay'] = df['EnteredAt'].dt.hour
    hourly_performance = df.groupby('HourOfDay').agg(
        TotalPnL=('PnL', 'sum'),
        TradeFrequency=('PnL', 'count'),
        WinningRate=('WinOrLoss', lambda x: (x > 0).mean()),
    )

    # Normalize Total PnL
    hourly_performance['NormalizedPnL'] = hourly_performance['TotalPnL'] / hourly_performance['TradeFrequency']

    plt.figure(figsize=(10, 6))
    plt.plot(hourly_performance.index, hourly_performance['NormalizedPnL'], marker='o', label='Normalized Total PnL')
    plt.bar(hourly_performance.index, hourly_performance['WinningRate'], alpha=0.4, label='Winning Rate', color='orange')
    plt.axhline(0, color='red', linestyle='--', linewidth=1, label='Break-Even Line')
    plt.title('Normalized Hourly Performance Trends (GMT+2)')
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

def plot_sharpe_ratio(df, base_path):
    """
    Plots the Sharpe Ratio over time and saves to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'sharpe_ratio.png')

    # Calculate rolling Sharpe Ratio
    risk_free_rate = 0.0  # Assume risk-free rate is 0 for simplicity
    df['RollingMeanPnL'] = df['PnL'].rolling(window=30).mean()
    df['RollingStdPnL'] = df['PnL'].rolling(window=30).std()
    df['SharpeRatio'] = (df['RollingMeanPnL'] - risk_free_rate) / df['RollingStdPnL']

    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['SharpeRatio'], label='Sharpe Ratio', marker='o', linestyle='-')
    plt.axhline(0, color='red', linestyle='--', linewidth=1, label='Zero Line')
    plt.title('Rolling Sharpe Ratio Over Trades')
    plt.xlabel('Trade Index')
    plt.ylabel('Sharpe Ratio')
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

    # Aggregate performance metrics by trade size
    trade_size_performance = df.groupby('Size').agg(
        TotalPnL=('PnL', 'sum'),
        WinningRate=('WinOrLoss', lambda x: (x > 0).mean()),
        TradeFrequency=('PnL', 'count')
    )

    # Normalize Total PnL by the frequency of trades
    trade_size_performance['NormalizedPnL'] = (
        trade_size_performance['TotalPnL'] / trade_size_performance['TradeFrequency']
    )

    # Create the plot with a secondary y-axis
    fig, ax1 = plt.subplots(figsize=(10, 6))

    # Plot Total PnL (normalized) as a bar chart
    ax1.bar(trade_size_performance.index, trade_size_performance['NormalizedPnL'], alpha=0.6, label='Normalized Total PnL', color='skyblue')
    ax1.set_xlabel('Trade Size')
    ax1.set_ylabel('Normalized Total PnL')
    ax1.set_title('Trade Size Impact on Performance (Normalized)')
    ax1.legend(loc='upper left')
    ax1.grid()

    # Create a secondary y-axis for the winning rate
    ax2 = ax1.twinx()
    ax2.plot(trade_size_performance.index, trade_size_performance['WinningRate'], marker='o', color='orange', label='Winning Rate')
    ax2.set_ylabel('Winning Rate')
    ax2.legend(loc='upper right')

    plt.savefig(full_path)
    plt.close()
def plot_day_of_week_performance(df, base_path):
    """
    Plots performance metrics by day of the week using two axes to handle scaling issues and saves to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'day_of_week_performance.png')

    # Extract day of the week and aggregate performance metrics
    df['DayOfWeek'] = df['EnteredAt'].dt.day_name()
    day_of_week_performance = df.groupby('DayOfWeek').agg(
        TotalPnL=('PnL', 'sum'),
        WinningRate=('WinOrLoss', lambda x: (x > 0).mean())
    ).reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])  # Ensure correct order

    # Create the plot with two y-axes
    fig, ax1 = plt.subplots(figsize=(12, 6))

    # Bar chart for Total PnL
    ax1.bar(day_of_week_performance.index, day_of_week_performance['TotalPnL'], alpha=0.6, label='Total PnL', color='skyblue')
    ax1.set_xlabel('Day of the Week')
    ax1.set_ylabel('Total PnL')
    ax1.grid()
    ax1.legend(loc='upper left')

    # Line chart for Winning Rate
    ax2 = ax1.twinx()
    ax2.plot(day_of_week_performance.index, day_of_week_performance['WinningRate'], marker='o', color='orange', label='Winning Rate')
    ax2.set_ylabel('Winning Rate')
    ax2.legend(loc='upper right')

    # Add a title
    plt.title('Performance by Day of the Week')

    # Save the plot
    plt.savefig(full_path)
    plt.close()


def plot_pnl_distribution(df, base_path):
    """
    Plots the distribution of PnL and saves to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'pnl_distribution.png')

    plt.figure(figsize=(12, 6))
    plt.hist(df['PnL'], bins=50, alpha=0.7, color='skyblue', edgecolor='black')
    plt.axvline(df['PnL'].mean(), color='red', linestyle='--', linewidth=1, label='Mean PnL')
    plt.axvline(0, color='black', linestyle='-', linewidth=1, label='Break-Even Line')
    plt.title('PnL Distribution')
    plt.xlabel('PnL')
    plt.ylabel('Frequency')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def plot_performance_heatmap(df, base_path):
    """
    Plots a heatmap of Total PnL by Hour and Trade Size and saves to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'performance_heatmap.png')

    df['HourOfDay'] = df['EnteredAt'].dt.hour
    heatmap_data = df.pivot_table(index='HourOfDay', columns='Size', values='PnL', aggfunc='sum').fillna(0)

    plt.figure(figsize=(12, 6))
    plt.imshow(heatmap_data, cmap='coolwarm', aspect='auto', origin='lower')
    plt.colorbar(label='Total PnL')
    plt.title('Heatmap of Performance by Hour and Trade Size')
    plt.xlabel('Trade Size')
    plt.ylabel('Hour of Day')
    plt.xticks(range(len(heatmap_data.columns)), heatmap_data.columns, rotation=45)
    plt.yticks(range(len(heatmap_data.index)), heatmap_data.index)
    plt.grid(False)
    plt.savefig(full_path)
    plt.close()

def plot_rolling_winning_rate(df, base_path):
    """
    Plots the rolling winning rate over trades and saves to appropriate directories.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'rolling_winning_rate.png')

    df['RollingWinningRate'] = df['WinOrLoss'].rolling(window=50).mean()

    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['RollingWinningRate'], marker='o', linestyle='-', label='Rolling Winning Rate')
    plt.axhline(0.5, color='red', linestyle='--', linewidth=1, label='50% Line')
    plt.title('Rolling Winning Rate Over Trades')
    plt.xlabel('Trade Index')
    plt.ylabel('Winning Rate')
    plt.legend()
    plt.grid()
    plt.savefig(full_path)
    plt.close()

def trade_size_and_risk_analysis(df, base_path):
    """
    Analyzes the relationship between trade size and risk metrics (PnL standard deviation and drawdown).

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'trade_size_risk_analysis.png')

    # Group by trade size
    trade_size_stats = df.groupby('Size').agg(
        AveragePnL=('PnL', 'mean'),
        StdPnL=('PnL', 'std'),
        MaxDrawdown=('PnL', lambda x: x.cumsum().min() - x.cumsum().max())
    )

    # Plot the results
    fig, ax1 = plt.subplots(figsize=(12, 6))

    ax1.bar(trade_size_stats.index, trade_size_stats['StdPnL'], alpha=0.6, label='Standard Deviation of PnL', color='skyblue')
    ax1.set_xlabel('Trade Size')
    ax1.set_ylabel('Standard Deviation of PnL')
    ax1.set_title('Trade Size and Risk Analysis')
    ax1.legend(loc='upper left')
    ax1.grid()

    ax2 = ax1.twinx()
    ax2.plot(trade_size_stats.index, trade_size_stats['MaxDrawdown'], marker='o', color='orange', label='Maximum Drawdown')
    ax2.set_ylabel('Maximum Drawdown')
    ax2.legend(loc='upper right')

    plt.savefig(full_path)
    plt.close()

def correlation_analysis(df, base_path):
    """
    Performs correlation analysis between trade size, PnL, winning rate, and time of day.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
    """
    full_path = os.path.join(base_path, 'correlation_analysis.png')

    # Add hour of day and winning rate
    df['HourOfDay'] = df['EnteredAt'].dt.hour
    df['WinningRate'] = (df['WinOrLoss'] > 0).astype(int)

    # Select relevant columns for correlation
    correlation_data = df[['Size', 'PnL', 'HourOfDay', 'WinningRate']]

    # Compute correlation matrix
    correlation_matrix = correlation_data.corr()

    # Plot the heatmap
    plt.figure(figsize=(10, 8))
    plt.imshow(correlation_matrix, cmap='coolwarm', aspect='auto', origin='lower')
    plt.colorbar(label='Correlation Coefficient')
    plt.xticks(range(len(correlation_matrix.columns)), correlation_matrix.columns, rotation=45)
    plt.yticks(range(len(correlation_matrix.index)), correlation_matrix.index)
    plt.title('Correlation Analysis')
    plt.savefig(full_path)
    plt.close()


def monte_carlo_simulation(df, base_path, num_simulations=1000, num_trades=200):
    """
    Performs Monte Carlo simulation to assess the robustness of the strategy.

    Args:
        df (DataFrame): The combined dataframe with trading data.
        base_path (str): Base path to save images.
        num_simulations (int): Number of simulations to run.
        num_trades (int): Number of trades per simulation.
    """
    full_path = os.path.join(base_path, 'monte_carlo_simulation.png')

    # Extract PnL values for simulation
    pnl_values = df['PnL'].values

    # Run Monte Carlo simulations
    results = []
    for _ in range(num_simulations):
        simulated_trades = np.random.choice(pnl_values, size=num_trades, replace=True)
        cumulative_pnl = np.cumsum(simulated_trades)
        results.append(cumulative_pnl)

    # Plot results
    plt.figure(figsize=(12, 6))
    for simulation in results:
        plt.plot(simulation, alpha=0.2, color='gray')
    plt.axhline(0, color='red', linestyle='--', label='Break-Even Line')
    plt.title(f'Monte Carlo Simulation ({num_simulations} Simulations, {num_trades} Trades)')
    plt.xlabel('Trade Index')
    plt.ylabel('Cumulative PnL')
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
    plot_sharpe_ratio(df, overall_base_path)
    plot_day_of_week_performance(df, overall_base_path)
    plot_pnl_distribution(df, overall_base_path)
    plot_performance_heatmap(df, overall_base_path)
    plot_rolling_winning_rate(df, overall_base_path)
    trade_size_and_risk_analysis(df, overall_base_path)
    correlation_analysis(df, overall_base_path)
    monte_carlo_simulation(df, overall_base_path)

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
        plot_sharpe_ratio(group, monthly_base_path)
        plot_day_of_week_performance(group, monthly_base_path)
        plot_pnl_distribution(group, monthly_base_path)
        plot_performance_heatmap(group, monthly_base_path)
        plot_rolling_winning_rate(group, monthly_base_path)
        trade_size_and_risk_analysis(df, overall_base_path)
        correlation_analysis(df, overall_base_path)
        monte_carlo_simulation(df, overall_base_path)



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

        combined_df = adjust_to_finnish_timezone(combined_df)

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