import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from plotly.subplots import make_subplots
import os
from jinja2 import Environment, FileSystemLoader
import json
import markdown2
from IPython.display import HTML
import plotly
import configparser
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
from src.utils.get_data import *
from src.utils.assemble_plot import *
from src.utils.summary_plot import *
from src.utils.summary_text import *
from src.utils.generate_html import *

def get_daily_data(logger, parameters_global, parameters_report):
    date = datetime.strptime(parameters_report['date'], '%Y-%m-%d')
    ticker = parameters_report['ticker']
    date_previous = get_previous_date(date)
    # load data
    trade, df, df_previous = load_data(logger, date, ticker, date_previous, parameters_global)
    # preprocess to RTH data
    trade_rth = get_trade_rth(trade)
    df_rth = get_future_rth(df)
    df_previous_rth = get_future_rth(df_previous)
    pre_market = get_pre_market(df_previous_rth)
    df_rth = get_ema(df_rth, df_previous_rth)
    winning_trades, losing_trades = get_trades_sum(trade_rth)
    win_loss_counts = {'Winning Trades': len(winning_trades), 'Losing Trades': len(losing_trades)}
    all_trades_stats = get_trade_stats(trade_rth)
    winning_trades_stats = get_trade_stats(winning_trades)
    losing_trades_stats = get_trade_stats(losing_trades)

    return trade_rth, df_rth, df_previous_rth, pre_market, winning_trades, losing_trades, win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats


def get_overall_data(logger, parameters_global):

    # Initialize an empty list to store DataFrames
    dfs = []

    # Iterate through all files in the directory
    for filename in os.listdir(parameters_global['performace_data_path']):
        if filename.endswith('.csv'):
            # Construct the full file path
            filepath = os.path.join(parameters_global['performace_data_path'], filename)
            
            # Read the CSV file into a DataFrame
            df = pd.read_csv(filepath)
            
            # Append the DataFrame to the list
            dfs.append(df)

    # Concatenate all DataFrames vertically
    df_overall = pd.concat(dfs, ignore_index=True)

    df_overall_rth = get_trade_rth(df_overall)

    overall_winning_trades, overall_losing_trades = get_trades_sum(df_overall_rth)
    overall_win_loss_counts = {'Winning Trades': len(overall_winning_trades), 'Losing Trades': len(overall_losing_trades)}
    overall_trades_stats = get_trade_stats(df_overall_rth)
    overall_winning_trades_stats = get_trade_stats(overall_winning_trades)
    overall_losing_trades_stats = get_trade_stats(overall_losing_trades)

    return df_overall_rth, overall_winning_trades, overall_losing_trades, overall_win_loss_counts, overall_trades_stats, overall_winning_trades_stats, overall_losing_trades_stats

if __name__ == "__main__":
    # Read configuration from file
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Access preprocessing variables and remove comments
    parameters_global = remove_comments_and_convert(config, 'global')
    parameters_report = remove_comments_and_convert(config, 'report')
 
    # Create a logger
    logger = get_logger('data.log', parameters_global['log_path'])
    logger.info(f'==========New Line==========')
    print(f"Check log later in {parameters_global['log_path']}")

    # Call the get_daily_data function with parsed arguments
    trade_rth, df_rth, df_previous_rth, pre_market, winning_trades, losing_trades, win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats = get_daily_data(logger, parameters_global, parameters_report)

    # get plotly figures
    fig_assemble = get_assemble_plot(df_rth, trade_rth, pre_market, parameters_report,['orange', 'purple', 'green', 'red'])
    fig_statistic = create_pie_chart(win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats)
    html_summary= create_summary(parameters_report['summary_md_file'], parameters_report['date'], False)

    # generate daily html
    generate_html(fig_assemble= fig_assemble, fig_statistic = fig_statistic, html_summary = html_summary, parameters_report=parameters_report)


    # Call the get_overall_data function with parsed arguments
    df_overall_rth, overall_winning_trades, overall_losing_trades, overall_win_loss_counts, overall_trades_stats, overall_winning_trades_stats, overall_losing_trades_stats = get_overall_data(logger, parameters_global)

    overall_html_summary= create_summary(parameters_report['summary_md_file'], parameters_report['date'], True)
    overall_fig_statistic = create_pie_chart(overall_win_loss_counts, overall_trades_stats, overall_winning_trades_stats, overall_losing_trades_stats)
    generate_html(fig_statistic=overall_fig_statistic, html_summary=overall_html_summary, parameters_report=parameters_report)

    generate_index(parameters_report)
