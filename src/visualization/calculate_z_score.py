import os
import re
from datetime import datetime
import pandas as pd
import configparser
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
from itertools import groupby
import matplotlib.pyplot as plt





def calculate_streaks(df, rolling_windows):
    """Calculate streaks for given rolling window sizes."""
    # Add Win/Loss column based on PnL
    df['WinOrLoss'] = df['PnL'].apply(lambda x: 1 if x > 0 else -1)

    # Global streak calculation
    df['Streak'] = 0
    streak_counter = 0

    for i in range(len(df)):
        if i == 0 or df['WinOrLoss'].iloc[i] != df['WinOrLoss'].iloc[i - 1]:
            streak_counter = 1
        else:
            streak_counter += 1
        df.loc[i, 'Streak'] = streak_counter * df['WinOrLoss'].iloc[i]


    # # Rolling streak calculation
    # for window in rolling_windows:
    #     rolling_column = f'Streak_{window}'
    #     df[rolling_column] = (
    #         df['WinOrLoss']
    #         .rolling(window=window, min_periods=1)
    #         .apply(
    #             lambda x: max(len(list(g)) for k, g in groupby(x)),
    #             raw=True
    #         )
    #     )

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

def plot_streaks(df, path):
    full_path = os.path.join(path, 'Streak_Pattern.png')
    # Plot the streak data
    plt.figure(figsize=(12, 6))
    plt.plot(df.index, df['Streak'], marker='o', linestyle='-', label='Streak Pattern')
    plt.axhline(0, color='red', linestyle='--', linewidth=1, label='Zero Line')
    plt.title('Streak Pattern Over Trades')
    plt.xlabel('Trade Index')
    plt.ylabel('Streak Value')
    plt.legend()
    plt.grid()
    plt.savefig(path)  # Save the figure to the specified path
    plt.close()  # Close the plot to free resources



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
    rolling_windows = [
        int(x.strip()) for x in parameters_report['rolling_windows'].split(',')
    ]

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
        combined_df = calculate_streaks(combined_df, rolling_windows)
        # Calculate Z-Score for all data
        z_score_all = calculate_z_score(combined_df)
        logger.info(f"Z-Score for all data: {z_score_all}")

        plot_streaks(combined_df, performance_data_path)

        # Save the final DataFrame
        output_path = os.path.join(parameters_global['performace_data_path'], 'Combined_Performance_with_Streaks.csv')
        combined_df.to_csv(output_path, index=False)
        logger.info(f"Processed data saved to {output_path}")
    else:
        logger.warning("No valid data was found to concatenate.")


if __name__ == "__main__":

    main()