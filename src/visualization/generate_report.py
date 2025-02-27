import os
import re
from datetime import datetime
import pandas as pd
import configparser
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
from src.utils.get_data import *
from src.utils.assemble_plot import *
from src.utils.summary_plot import *
from src.utils.summary_text import *
from src.utils.generate_html import *
from src.data.get_dataset import get_paired_tickers


def get_daily_data(logger, parameters_global, parameters_report, paired_ticker):
    """Gather daily trading data and perform analysis."""
    date = datetime.strptime(parameters_report['date'], '%Y-%m-%d')
    date_previous = datetime.strptime(parameters_report['date_previous'], '%Y-%m-%d')
    # date_previous = get_previous_date(date)

    trade, df, df_previous = load_data(logger, date, paired_ticker, date_previous, parameters_global)
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
    if all_trades_stats['Count'] != 0:
        if (win_loss_counts['Winning Trades'] + win_loss_counts['Losing Trades']) == 0:
            winning_ratio = 1
        else:
            winning_ratio = round(win_loss_counts['Winning Trades'] / (win_loss_counts['Winning Trades'] + win_loss_counts['Losing Trades']),2)
        save_trade_stats(parameters_report, parameters_global, date, paired_ticker, logger, all_trades_stats, winning_ratio, winning_trades_stats, losing_trades_stats)

    return (
        trade_rth, df_rth, df_previous_rth, pre_market,
        winning_trades, losing_trades, win_loss_counts,
        all_trades_stats, winning_trades_stats, losing_trades_stats
    )


def get_overall_data(logger, parameters_global, parameters_report):
    """Aggregate overall trading data."""
    dfs = [
        pd.read_csv(os.path.join(parameters_global['performace_data_path'], filename))
        for filename in os.listdir(parameters_global['performace_data_path'])
        if filename.endswith('.csv')
    ]

    df_overall = pd.concat(dfs, ignore_index=True)
    df_overall_rth = get_trade_rth(df_overall, parameters_report)
    overall_winning_trades, overall_losing_trades = get_trades_sum(df_overall_rth)
    overall_win_loss_counts = {'Winning Trades': len(overall_winning_trades), 'Losing Trades': len(overall_losing_trades)}
    overall_trades_stats = get_trade_stats(df_overall_rth, parameters_report)
    overall_winning_trades_stats = get_trade_stats(overall_winning_trades, parameters_report)
    overall_losing_trades_stats = get_trade_stats(overall_losing_trades, parameters_report)

    return (
        df_overall_rth, overall_winning_trades, overall_losing_trades,
        overall_win_loss_counts, overall_trades_stats,
        overall_winning_trades_stats, overall_losing_trades_stats
    )


def save_all_rth(ticker, logger, parameters_global, parameters_report):
    """Save All RTH data to individual CSV file."""
    report_date = datetime.strptime(parameters_report['date'], '%Y-%m-%d').date()
    concatenated_df = pd.DataFrame()
    ticker = re.sub(r'\d+$', '', ticker.split('.')[0])
    future_data_path = os.path.join(parameters_global['future_data_path'], ticker)
    for filename in os.listdir(future_data_path):
        if '1min' in filename and filename.endswith('.csv'):
            file_date_str = filename.split("_")[3]
            file_date = datetime.strptime(file_date_str, '%Y-%m-%d').date()
            if file_date <= report_date:
                filepath = os.path.join(future_data_path, filename)
                df = pd.read_csv(filepath)
                df = get_future_rth(df, parameters_report)
                concatenated_df = pd.concat([concatenated_df, df], axis=0)
            if file_date == report_date:
                filepath = os.path.join(future_data_path, filename)
                df_report_date = pd.read_csv(filepath)
                df_report_date_rth = get_future_rth(df_report_date, parameters_report)

    aggregated_rth_data = concatenated_df.sort_index()
    aggregated_rth_data.to_csv(f"{parameters_global['future_aggdata_path']}{ticker}.csv")
    save_rth_statistical_data(logger, parameters_global, parameters_report, df_report_date_rth, ticker)


def main():
    """Main function to process and generate reports."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    parameters_global = remove_comments_and_convert(config, 'global')
    parameters_report = remove_comments_and_convert(config, 'report')
    parameters_future = remove_comments_and_convert(config, 'future')

    logger = get_logger('data.log', parameters_global['log_path'])
    tickers = [ticker.strip() for ticker in parameters_future['tickers'].split(',')]
    base_tickers = [base_ticker.strip() for base_ticker in parameters_future['base_tickers'].split(',')]
    paired_tickers = get_paired_tickers(tickers, base_tickers)

    for paired_ticker in paired_tickers:
        logger.info(f"==========Generating {paired_ticker[1]} Report for {parameters_report['date']}==========")
        print(f"Check log later in {parameters_global['log_path']} for {paired_ticker[1]}")

        trade_rth, df_rth, df_previous_rth, pre_market, winning_trades, losing_trades, win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats = get_daily_data(logger, parameters_global, parameters_report, paired_ticker)
        logger.info('Daily data preprocessing is done')
        
        fig_assemble = get_assemble_plot(paired_ticker[1], df_rth, trade_rth, pre_market, parameters_report, ['orange', 'purple', 'green', 'red'])
        fig_statistic = create_pie_chart(win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats)
        logger.info('Daily plotly is done')
        
        generate_html(ticker=paired_ticker[1], fig_assemble=fig_assemble, fig_statistic=fig_statistic, parameters_report=parameters_report)
        logger.info('Daily chart is done')
        
        generate_index(parameters_report)
        logger.info('Index Generation is done')

        save_all_rth(paired_ticker[1], logger, parameters_global, parameters_report)
        logger.info('Statistical Future Data Generation is done')


if __name__ == "__main__":
    main()
