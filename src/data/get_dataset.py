import configparser
import pandas as pd
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
import yfinance as yf
from datetime import datetime
import os
import sys
from io import StringIO
import re
from src.db.db import save_to_db


def get_future_data(logger, parameters_global, parameters_future):
    """
    Fetch future data from Yahoo Finance and save it as CSV files.

    Args:
        logger (logging.Logger): Logger instance for logging information and errors.
        parameters_global (dict): Global parameters from the configuration.
        parameters_future (dict): Future data-specific parameters from the configuration.
    """
    start_date = datetime.strptime(parameters_future['start_date'], '%Y-%m-%d')
    end_date = start_date + pd.Timedelta(days=1)
    intervals = [interval.strip() for interval in parameters_future['interval'].split(',')]
    tickers = [ticker.strip() for ticker in parameters_future['tickers'].split(',')]

    # Redirect stdout and stderr to capture output from yfinance
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = sys.stderr = mystdout = StringIO()

    try:
        for ticker in tickers:
            for interval in intervals:
                try:
                    # Attempt to download data
                    df = yf.download(tickers=ticker, start=start_date, end=end_date, interval=f"{interval}m")
                    # Logging the output from yfinance
                    captured_output = mystdout.getvalue()
                    cleaned_output = re.sub(r'\s+', ' ', captured_output).strip()
                    logger.info(cleaned_output)
                    mystdout.seek(0)
                    mystdout.truncate(0)
                    if not df.empty:
                        # Extract the date from the first index
                        date_str = str(df.index[0].date())
                        # Define the folder path
                        ticker_path = re.sub(r'\d+$', '', ticker.split('.')[0])
                        folder_path = os.path.join(parameters_global['future_data_path'], ticker_path)
                        # Create the folder if it doesn't exist
                        os.makedirs(folder_path, exist_ok=True)
                        # Save the data to a CSV file
                        file_name = f"{ticker_path}_{interval}min_data_{date_str}.csv"
                        file_path = os.path.join(folder_path, file_name)
                        df.to_csv(file_path)
                        logger.info(f'{file_name} saved to {file_path}')
                except Exception as e:
                    logger.error(f"Failed to download data for {ticker} at interval {interval} minutes on {start_date}: {str(e)}")
                # if interval == '1' and 'ES' in ticker:
                #     save_to_db(logger, df, 'es')
                # elif interval == '1' and 'NQ' in ticker:
                #     save_to_db(logger, df, 'nq')
    finally:
        # Restore stdout and stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr


if __name__ == "__main__":
    # Read configuration from file
    config = configparser.ConfigParser()
    config.read('config.ini')
    # Remove comments and convert the configuration into usable format
    parameters_global = remove_comments_and_convert(config, 'global')
    parameters_future = remove_comments_and_convert(config, 'future')
    # Initialize logger
    logger = get_logger('data.log', parameters_global['log_path'])
    logger.info(f"========== Starting Data Acquisition for {parameters_future['start_date']} ==========")
    print(f"Check log later in {parameters_global['log_path']} for details.")
    # Call the data acquisition function with the necessary parameters
    get_future_data(logger, parameters_global, parameters_future)
