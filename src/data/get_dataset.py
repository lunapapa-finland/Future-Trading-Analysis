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
import pandas_market_calendars as mcal

def get_paired_tickers(tickers, base_tickers):
    """
    Pairs each ticker with its corresponding base ticker and extracts contract information.
    This function takes two lists: `tickers` and `base_tickers`. It pairs each ticker with its 
    corresponding base ticker and extracts the contract information by removing the base ticker 
    from the ticker. The function returns a list of tuples, where each tuple contains the ticker, 
    the base ticker, and the extracted contract information.
    Args:
        tickers (list of str): A list of full ticker symbols.
        base_tickers (list of str): A list of base ticker symbols.
    Returns:
        list of tuples: A list of tuples, where each tuple contains:
            - ticker (str): The full ticker symbol.
            - base_ticker (str): The base ticker symbol.
            - contract_info (str): The extracted contract information.
    Raises:
        ValueError: If the lengths of `tickers` and `base_tickers` do not match.
        ValueError: If a base ticker is not found in its corresponding full ticker.
    """

    if len(tickers) != len(base_tickers):
        raise ValueError(f"Cannot pair tickers and base_tickers: "
                         f"{len(tickers)} tickers and {len(base_tickers)} base_tickers found.")
    paired_tickers = []
    for ticker, base_ticker in zip(tickers, base_tickers):
        if base_ticker in ticker:
            contract_info = ticker.replace(base_ticker, '', 1)
            paired_tickers.append((ticker, base_ticker, contract_info.strip()))
        else:
            raise ValueError(f"Base ticker '{base_ticker}' not found in full ticker '{ticker}'")
    return paired_tickers


def download_and_save_data(paired_ticker, interval, start_date, end_date, parameters_global, logger):
    """
    Downloads historical trading data for a given ticker and saves it as a CSV file.
    Parameters:
    paired_ticker (tuple): A tuple containing the ticker symbol, a string for the folder name, and an additional identifier.
    interval (int): The interval in minutes for the data to be downloaded.
    start_date (str): The start date for the data download in 'YYYY-MM-DD' format.
    end_date (str): The end date for the data download in 'YYYY-MM-DD' format.
    parameters_global (dict): A dictionary containing global parameters, including the path to save the data.
    logger (logging.Logger): A logger instance to log information and errors.
    Returns:
    None
    Raises:
    Exception: If there is an error during the data download or file saving process, it logs the error message.
    """

    try:
        df = yf.download(tickers=paired_ticker[0], start=start_date, end=end_date, interval=f"{interval}m")
        if not df.empty:
            date_str = str(df.index[0].date())
            folder_path = os.path.join(parameters_global['future_data_path'], paired_ticker[1])
            os.makedirs(folder_path, exist_ok=True)
            file_name = f"{paired_ticker[1]}_{interval}min_data_{date_str}_{paired_ticker[2]}.csv"
            file_path = os.path.join(folder_path, file_name)
            df.to_csv(file_path)
            logger.info(f'{file_name} saved to {file_path}')
    except Exception as e:
        logger.error(f"Failed to download data for {paired_ticker[0]} at interval {interval} minutes on {start_date}: {str(e)}")


def get_future_data(logger, parameters_global, parameters_future):
    """
    Fetches and processes future trading data based on provided parameters.
    Args:
        logger (logging.Logger): Logger object for logging information.
        parameters_global (dict): Global parameters for data fetching.
        parameters_future (dict): Specific parameters for future data fetching, including:
            - 'start_date' (str): The start date for data fetching in 'YYYY-MM-DD' format.
            - 'interval' (str): Comma-separated intervals for data fetching.
            - 'tickers' (str): Comma-separated list of tickers to fetch data for.
            - 'base_tickers' (str): Comma-separated list of base tickers to pair with tickers.
    Returns:
        None
    """

    start_date = datetime.strptime(parameters_future['start_date'], '%Y-%m-%d')
    cme_calendar = mcal.get_calendar('CME_Equity')

    # Check if the input date is a trading day
    schedule = cme_calendar.schedule(start_date=start_date, end_date=start_date)
    if schedule.empty:
        raise ValueError(f"{start_date.date()} is not a CME trading day.")
    
    end_date = start_date + pd.Timedelta(days=1)
    intervals = [interval.strip() for interval in parameters_future['interval'].split(',')]
    tickers = [ticker.strip() for ticker in parameters_future['tickers'].split(',')]
    base_tickers = [base_ticker.strip() for base_ticker in parameters_future['base_tickers'].split(',')]
    paired_tickers = get_paired_tickers(tickers, base_tickers)

    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = mystdout = StringIO()

    try:
        for paired_ticker in paired_tickers:
            for interval in intervals:
                download_and_save_data(paired_ticker, interval, start_date, end_date, parameters_global, logger)
                captured_output = mystdout.getvalue()
                cleaned_output = re.sub(r'\s+', ' ', captured_output).strip()
                logger.info(cleaned_output)
                mystdout.seek(0)
                mystdout.truncate(0)
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


if __name__ == "__main__":
    config = configparser.ConfigParser()
    config.read('config.ini')
    parameters_global = remove_comments_and_convert(config, 'global')
    parameters_future = remove_comments_and_convert(config, 'future')
    logger = get_logger('data.log', parameters_global['log_path'])
    logger.info(f"========== Starting Data Acquisition for {parameters_future['start_date']} ==========")
    print(f"Check log later in {parameters_global['log_path']} for details.")
    get_future_data(logger, parameters_global, parameters_future)
