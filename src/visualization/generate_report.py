import pandas as pd
from datetime import datetime
import os
import configparser
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
from src.utils.get_data import *
from src.utils.assemble_plot import *
from src.utils.summary_plot import *
from src.utils.summary_text import *
from src.utils.generate_html import *

# Function to gather daily trading data and perform analysis
def get_daily_data(logger, parameters_global, parameters_report, ticker):
    # Parse date and ticker from parameters
    date = datetime.strptime(parameters_report['date'], '%Y-%m-%d')
    ticker = ticker.split('.')[0]
    ticker = re.sub(r'\d+', '', ticker)
    date_previous = get_previous_date(date)

    # Load and preprocess data
    trade, df, df_previous = load_data(logger, date, ticker, date_previous, parameters_global)
    trade_rth = get_trade_rth(trade, parameters_report)
    df_rth = get_future_rth(df, parameters_report)
    df_previous_rth = get_future_rth(df_previous, parameters_report)
    pre_market = get_pre_market(df_previous_rth)
    df_rth = get_ema(df_rth, df_previous_rth, parameters_report)
    winning_trades, losing_trades = get_trades_sum(trade_rth)
    win_loss_counts = {'Winning Trades': len(winning_trades), 'Losing Trades': len(losing_trades)}
    all_trades_stats = get_trade_stats(trade_rth, parameters_report)
    winning_trades_stats = get_trade_stats(winning_trades, parameters_report)
    losing_trades_stats = get_trade_stats(losing_trades, parameters_report)

    return trade_rth, df_rth, df_previous_rth, pre_market, winning_trades, losing_trades, win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats

# Function to aggregate overall trading data
def get_overall_data(logger, parameters_global, parameters_report, ticker):
    dfs = []

    # Iterate through CSV files in the specified directory and load data
    for filename in os.listdir(parameters_global['performace_data_path']):
        if filename.endswith('.csv'):
            filepath = os.path.join(parameters_global['performace_data_path'], filename)
            df = pd.read_csv(filepath)
            dfs.append(df)

    # Combine all DataFrames into one
    df_overall = pd.concat(dfs, ignore_index=True)
    df_overall_rth = get_trade_rth(df_overall, parameters_report)
    overall_winning_trades, overall_losing_trades = get_trades_sum(df_overall_rth)
    overall_win_loss_counts = {'Winning Trades': len(overall_winning_trades), 'Losing Trades': len(overall_losing_trades)}
    overall_trades_stats = get_trade_stats(df_overall_rth, parameters_report)
    overall_winning_trades_stats = get_trade_stats(overall_winning_trades, parameters_report)
    overall_losing_trades_stats = get_trade_stats(overall_losing_trades, parameters_report)

    return df_overall_rth, overall_winning_trades, overall_losing_trades, overall_win_loss_counts, overall_trades_stats, overall_winning_trades_stats, overall_losing_trades_stats

# Function to get statistical future data
def get_statistical_future_data(ticker, logger, parameters_global, parameters_report):
    
    # Get the date from parameters_report['date']
    report_date = datetime.strptime(parameters_report['date'], '%Y-%m-%d').date()

    concatenated_df = pd.DataFrame()
    ticker = ticker.split('.')[0]
    ticker = re.sub(r'\d+', '', ticker)
    future_data_path = os.path.join(parameters_global['future_data_path'], ticker)
     # Iterate through CSV files in the specified directory and load data
    for filename in os.listdir(future_data_path):
        if '1min' in filename and filename.endswith('.csv'):
            # Extract date from the filename
            file_date_str = filename.split("_")[-1].split(".")[0]
            file_date = datetime.strptime(file_date_str, '%Y-%m-%d').date()
            # Compare the file date with the report date
            if file_date <= report_date:
                # Construct the full file path
                filepath = os.path.join(future_data_path, filename)
                # Read the CSV file into a DataFrame
                df = pd.read_csv(filepath)
                # Process the DataFrame
                df = get_future_rth(df, parameters_report)
                # Concatenate the DataFrame to the existing concatenated DataFrame along axis 0
                concatenated_df = pd.concat([concatenated_df, df], axis=0)
    aggregated_rth_data = concatenated_df.sort_index()
    aggregated_rth_data.to_csv(f"{parameters_global['future_aggdata_path']}{ticker}.csv")
    get_statistical_data(logger, parameters_global, parameters_report, aggregated_rth_data, ticker)

if __name__ == "__main__":
    # Configuration and logger setup
    config = configparser.ConfigParser()
    config.read('config.ini')
    parameters_global = remove_comments_and_convert(config, 'global')
    parameters_report = remove_comments_and_convert(config, 'report')
    logger = get_logger('data.log', parameters_global['log_path'])
    tickers = [tickers.strip() for tickers in parameters_report['tickers'].split(',')]
    for ticker in tickers:
        logger.info(f"==========Generating {ticker} Report for {parameters_report['date']}==========")
        print(f"Check log later in {parameters_global['log_path']}")

        # Daily data processing and plotting
        trade_rth, df_rth, df_previous_rth, pre_market, winning_trades, losing_trades, win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats = get_daily_data(logger, parameters_global, parameters_report,ticker)
        logger.info(f'Daily data preprocessing is done')
        fig_assemble = get_assemble_plot(ticker ,df_rth, trade_rth, pre_market, parameters_report, ['orange', 'purple', 'green', 'red'])
        fig_statistic = create_pie_chart(win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats)
        html_summary = create_summary(parameters_report['summary_md_file'], parameters_report['date'], False)
        logger.info(f'Daily plotly is done')
        generate_html(ticker = ticker, fig_assemble=fig_assemble, fig_statistic=fig_statistic, html_summary=html_summary, parameters_report=parameters_report)

        logger.info(f'Daily chart is done')

        # # Overall data processing and plotting
        df_overall_rth, overall_winning_trades, overall_losing_trades, overall_win_loss_counts, overall_trades_stats, overall_winning_trades_stats, overall_losing_trades_stats = get_overall_data(logger, parameters_global, parameters_report,ticker)
        logger.info(f'Aggregated data preprocessing is done')
        overall_html_summary = create_summary(parameters_report['summary_md_file'], parameters_report['date'], True)
        overall_fig_statistic = create_pie_chart(overall_win_loss_counts, overall_trades_stats, overall_winning_trades_stats, overall_losing_trades_stats)
        logger.info(f'Overall plotly is done')
        generate_html(ticker = ticker, fig_statistic=overall_fig_statistic, html_summary=overall_html_summary, parameters_report=parameters_report)
        logger.info(f'Overall Performance is done')
        generate_index(parameters_report)
        logger.info(f'Index Generation is done')

        # # statistical future data
        get_statistical_future_data(ticker, logger, parameters_global, parameters_report)
        logger.info(f'Statistical Future Data Generation is done')
