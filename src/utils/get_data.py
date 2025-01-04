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
import re
import pandas_market_calendars as mcal


def get_previous_date(date):
    """
    Get the previous trading date.
    """
    cme_calendar = mcal.get_calendar('CME_Equity')

    # Check if the input date is a trading day
    schedule = cme_calendar.schedule(start_date=date, end_date=date)
    if schedule.empty:
        raise ValueError(f"{date.date()} is not a CME trading day.")
    
    month_shift_date = date - timedelta(days=30)
    # Check if the input date is a trading day
    schedule = cme_calendar.schedule(start_date=month_shift_date, end_date=date)
    trading_days = schedule.index

    current_index = trading_days.get_loc(date)
    if current_index == 0:
        raise ValueError("There is no previous trading day in the calendar.")
    
    previous_trading_date = trading_days[current_index - 1]

    return previous_trading_date



def load_data(logger, date, paired_ticker, date_previous, parameters_global):
    """
    Load trade and market data.
    """
    trade_file = os.path.join(parameters_global['performace_data_path'], f"Performance_{date.strftime('%Y-%m-%d')}.csv")
    ticker_name = paired_ticker[1]
    ticker_contract = paired_ticker[2]
    future_data_path = os.path.join(parameters_global['future_data_path'], ticker_name)
    
    trade = pd.read_csv(trade_file)
    trade = trade[trade['ContractName'].str.startswith(ticker_name)]
    
    df = pd.read_csv(os.path.join(future_data_path, f"{ticker_name}_1min_data_{date.strftime('%Y-%m-%d')}_{ticker_contract}.csv"))
    df_previous_path = os.path.join(future_data_path, f"{ticker_name}_1min_data_{date_previous.strftime('%Y-%m-%d')}_{ticker_contract}.csv")
    
    try:
        df_previous = pd.read_csv(df_previous_path)
    except FileNotFoundError as e:
        df_previous = df.copy()
        logger.info(f"Cannot find file '{e.filename}'")
    
    return trade, df, df_previous


def get_trade_rth(trade, parameters_report):
    """
    Preprocess trade data to get regular trading hours (RTH) trades.
    """
    trade = trade.drop(columns=['Id', 'TradeDay'])

    time_difference = int(parameters_report['time_difference'])

    # Parse the datetime fields, ensuring uniform timezone conversion to UTC
    trade['EnteredAt'] = pd.to_datetime(trade['EnteredAt'], utc=True) - pd.Timedelta(hours=time_difference)
    trade['ExitedAt'] = pd.to_datetime(trade['ExitedAt'], utc=True) - pd.Timedelta(hours=time_difference)
    
    # Filter trades during regular trading hours (RTH)
    trade_rth = trade[((trade['EnteredAt'].dt.time >= pd.Timestamp('09:30').time()) & (trade['EnteredAt'].dt.time <= pd.Timestamp('16:10').time())) |
                      ((trade['ExitedAt'].dt.time >= pd.Timestamp('09:30').time()) & (trade['ExitedAt'].dt.time <= pd.Timestamp('16:10').time()))].copy()
    
    trade_rth['EnteredAt'] = trade_rth['EnteredAt'].dt.floor(parameters_report['aggregated_length'])
    trade_rth['ExitedAt'] = trade_rth['ExitedAt'].dt.floor(parameters_report['aggregated_length'])
    trade_rth.reset_index(drop=True, inplace=True)
    
    return trade_rth



def get_aggregated_rth(df, parameters_report):
    """
    Aggregate data to specified intervals.
    """
    return df.resample(parameters_report['aggregated_length']).agg({
        'Open': 'first',
        'High': 'max',
        'Low': 'min',
        'Close': 'last',
        'Adj Close': 'last',
        'Volume': 'sum'
    })


def get_future_rth(df, parameters_report):
    """
    Preprocess future data to get regular trading hours (RTH) data.
    """
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df.set_index('Datetime', inplace=True)
    df_rth = df.between_time('09:30', '16:10')
    return get_aggregated_rth(df_rth, parameters_report)


def get_pre_market(df_previous_rth):
    """
    Get pre-market high, low, open, and close values.
    """
    return {
        'pre_high': df_previous_rth['High'].max(),
        'pre_low': df_previous_rth['Low'].min(),
        'pre_open': df_previous_rth['Open'].iloc[0],
        'pre_close': df_previous_rth['Close'].iloc[-1]
    }


def get_ema(df_rth, df_previous_rth, parameters_report):
    """
    Calculate the Exponential Moving Average (EMA).
    """
    ema_length = int(parameters_report['ema'])
    combined_df = pd.concat([df_previous_rth.tail(ema_length), df_rth])
    combined_df[f"EMA_{parameters_report['ema']}"] = combined_df['Close'].ewm(span=ema_length, adjust=False).mean().round(2)
    df_rth = df_rth.copy()
    df_rth[f"EMA_{parameters_report['ema']}"] = combined_df[f"EMA_{parameters_report['ema']}"].iloc[-len(df_rth):].values
    return df_rth


def get_trades_sum(trade_rth):
    """
    Calculate winning and losing trades.
    """
    winning_trades = trade_rth[trade_rth['PnL'] > 0]
    losing_trades = trade_rth[trade_rth['PnL'] <= 0]
    return winning_trades, losing_trades


def get_trade_stats(trades, parameters_report):
    """
    Generate trade statistics.
    """
    if len(trades) == 0:
        return {'AveragePnL': 0, 'MaxPnL': 0, 'MinPnL': 0, 'TotalPnL': 0, 'Count': 0}
    
    return {
        'AveragePnL': round(trades['PnL'].mean(), 2),
        'MaxPnL': round(trades['PnL'].max(), 2),
        'MinPnL': round(trades['PnL'].min(), 2),
        'PnL(Gross)': round(trades['PnL'].sum(), 2),
        'PnL(Net)': round(trades['PnL'].sum(), 2) - round(trades['Fees'].sum(), 2),
        'Count': len(trades),
        'AverageSize': round(trades['Size'].mean(), 2),
        'LongCount': len(trades[trades['Type'] == 'Long']),
        'ShortCount': len(trades[trades['Type'] == 'Short']),
    }


def save_trade_stats(parameters_report, parameters_global, date, paired_ticker, logger,  all_trades_stats, winning_ratio, winning_trades_stats, losing_trades_stats):
    """
    Save trade statistics to a CSV file.
    """    
    date_str = pd.to_datetime(date).strftime('%Y-%m-%d')

    if all_trades_stats['LongCount'] > all_trades_stats['ShortCount']:
        sentiment = 'Bullish'
    elif all_trades_stats['LongCount'] < all_trades_stats['ShortCount']:
        sentiment = 'Bearish'
    else:
        sentiment = 'Neutral'


    stats = {
        'Date': [date_str],
        'Ticker': [paired_ticker[1]],
        'AveragePnL': [all_trades_stats['AveragePnL']],
        'MaxPnL': [all_trades_stats['MaxPnL']],
        'MinPnL(Neg)': [all_trades_stats['MinPnL']],
        'PnL(Gross)': [all_trades_stats['PnL(Gross)']],
        'PnL(Net)': [all_trades_stats['PnL(Net)']],
        'AverageSize': [all_trades_stats['AverageSize']],
        'Total Trade Count': [all_trades_stats['Count']],
        'WinningTradesCount': [winning_trades_stats['Count']],
        'LosingTradesCount': [losing_trades_stats['Count']],
        'Sentiment': [sentiment],
        'LongCount': [all_trades_stats['LongCount']],
        'ShortCount': [all_trades_stats['ShortCount']],
        'WinningRatio': [winning_ratio],
        'ProfitFactor': [round(winning_trades_stats['PnL(Net)'] / abs(losing_trades_stats['PnL(Net)']), 2)],
        'Avg Win / Avg Loss': [round(winning_trades_stats['AveragePnL'] / abs(losing_trades_stats['AveragePnL']), 2)],
    }
    stats_df = pd.DataFrame(stats)
    if not os.path.exists(parameters_global['future_aggdata_path']):
        os.makedirs(parameters_global['future_aggdata_path'])
        
    file_path = os.path.join(parameters_global['future_aggdata_path'], "DailyStats.csv")
    
    if os.path.exists(file_path):
        existing_df = pd.read_csv(file_path)
        existing_df.drop_duplicates(inplace=True)
        match_condition = (existing_df['Date'] == date_str) & (existing_df['Ticker'] == paired_ticker[1])
        
        if match_condition.any():
            logger.info(f"Record for Date: {date_str} and Ticker: {paired_ticker[1]} already exists.")
        else:
            existing_df = pd.concat([existing_df, stats_df], ignore_index=True)
            existing_df.to_csv(file_path, index=False)
            logger.info(f"Appending new record for Date: {date_str} and Ticker: {paired_ticker[1]}.")
    else:
        stats_df.to_csv(file_path, index=False)
        logger.info(f"Creating new file and saving record for Date: {date_str} and Ticker: {paired_ticker[1]}.")


def save_rth_statistical_data(logger, parameters_global, parameters_report, df, ticker):
    """
    Generate and save statistical data.
    """
    file_path = os.path.join(parameters_global['future_aggdata_path'], f"{ticker}_statistics.csv")
    
    if os.path.exists(file_path):
        try:
            result_df = pd.read_csv(file_path, index_col=0)
        except pd.errors.EmptyDataError:
            result_df = pd.DataFrame()
    else:
        result_df = pd.DataFrame()
    
    high_low_diff = df['High'] - df['Low']
    open_close_diff = abs(df['Open'] - df['Close'])
    data = {
        'high_low_mean': round(high_low_diff.mean(), 2),
        'high_low_max': round(high_low_diff.max(), 2),
        'high_low_min': round(high_low_diff.min(), 2),
        'high_low_std': round(high_low_diff.std(), 2),
        'open_close_mean': round(open_close_diff.mean(), 2),
        'open_close_max': round(open_close_diff.max(), 2),
        'open_close_min': round(open_close_diff.min(), 2),
        'open_close_std': round(open_close_diff.std(), 2)
    }
    
    new_row = pd.DataFrame(data, index=[parameters_report['date']])
    
    if parameters_report['date'] in result_df.index:
        result_df.loc[parameters_report['date']] = new_row.iloc[0]
    else:
        result_df = pd.concat([result_df, new_row])
    
    result_df.sort_index(inplace=True)
    result_df.index.name = 'DateTime'
    result_df.to_csv(file_path)
