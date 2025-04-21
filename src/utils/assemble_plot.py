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


def create_trade_lines(trade_df):
    """Create traces for trades."""
    trade_lines = []
    for index, row in trade_df.iterrows():
        entry_time, exit_time = sorted([row['EnteredAt'], row['ExitedAt']])
        entry_price, exit_price = (row['EntryPrice'], row['ExitPrice']) if entry_time == row['EnteredAt'] else (row['ExitPrice'], row['EntryPrice'])
        color = 'green' if row['PnL'] > 0 else 'red'
        trade_line = go.Scatter(
            x=[entry_time, exit_time],
            y=[entry_price, exit_price],
            mode='lines+markers',
            line=dict(color=color, width=2),
            marker=dict(color=color, size=8),
            name=f"Trade {index}",
            hoverinfo='text',
            hovertext=f"Entry: {entry_time}, Price: {entry_price} | Exit: {exit_time}, Price: {exit_price}, PnL: {row['PnL']}"
        )
        trade_lines.append(trade_line)
    return trade_lines


def create_ema_trace(df, parameters_report):
    """Create trace for EMA."""
    return go.Scatter(
        x=df.index.strftime('%Y-%m-%d %H:%M'),
        y=df[f"EMA_{parameters_report['ema']}"].astype(float).tolist(),
        mode='lines',
        line=dict(color='blue', width=2),
        name=f"EMA {parameters_report['ema']}"
    )


def create_horizontal_lines(df, values, colors, labels):
    """Create traces for horizontal lines."""
    return [
        go.Scatter(
            x=[df.index.min(), df.index.max()],
            y=[value] * 2,
            mode='lines',
            line=dict(color=color, width=2, dash='dash'),
            name=f'pre_{label.lower()}'
        ) for value, color, label in zip(values, colors, labels)
    ]


def create_candlestick_traces(df):
    """Create candlestick traces and annotations."""
    candle_data = []
    annotations = []
    low_points = df['Low']
    offset = low_points.min() * 0.001  # Small offset to place text below each candlestick

    for index, (idx, row) in enumerate(df.iterrows(), start=1):
        x_value = idx.strftime('%Y-%m-%d %H:%M')
        single_candle = go.Candlestick(
            x=[x_value],
            open=[round(row['Open'], 4)],
            high=[round(row['High'], 4)],
            low=[round(row['Low'], 4)],
            close=[round(row['Close'], 4)],
            name=f"Candle {index}",  # Enumerating candlesticks
            visible=True  # Initially visible
        )
        candle_data.append(single_candle)

        # Corresponding annotation for each candlestick
        annotation = {
            'x': x_value,
            'y': row['Low'] - offset,
            'xref': 'x',
            'yref': 'y',
            'text': str(index) if index % 2 != 0 else '',  # Text is index if odd, empty if even
            'showarrow': False,
            'font': {'family': 'Arial, sans-serif', 'size': 12, 'color': 'black'},
            'align': 'center',
            'visible': True
        }
        annotations.append(annotation)

    return candle_data, annotations


def get_assemble_plot(ticker, df, trade_df, pre_market, parameters_report, pre_colors):
    """Assemble the plot with candlestick data, EMA, and trade lines."""
    fig = go.Figure()
    
    # Add EMA trace
    fig.add_trace(create_ema_trace(df, parameters_report))
    
    # Add horizontal lines for pre-market values
    fig.add_traces(create_horizontal_lines(df, list(pre_market.values()), pre_colors, list(pre_market.keys())))
    
    # Add candlestick traces and annotations
    candle_traces, candle_annotations = create_candlestick_traces(df)
    fig.add_traces(candle_traces)
    
    # Add trade lines
    fig.add_traces(create_trade_lines(trade_df))
    
    # Add annotations
    for ann in candle_annotations:
        fig.add_annotation(ann)
    
    # Update layout
    fig.update_layout(
        title=f"{ticker} Candlestick Chart - {df.index.date[0]}",
        xaxis_title='Datetime',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        xaxis=dict(tickangle=-45),
        yaxis=dict(tickformat='none'),
        dragmode='pan'
    )
    
    return fig
