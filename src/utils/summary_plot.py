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

def create_pie_trace(win_loss_counts):
    """
    Create a pie chart trace for win/loss counts.
    
    Args:
        win_loss_counts (dict): A dictionary with win and loss counts.
        
    Returns:
        go.Pie: A Plotly pie chart object.
    """
    labels = list(win_loss_counts.keys())
    values = list(win_loss_counts.values())
    return go.Pie(labels=labels, values=values, showlegend=False, name="Win vs Loss")

def create_table_trace(data, header_color='lightgrey'):
    """
    Create a table trace for displaying statistics.
    
    Args:
        data (dict): A dictionary containing the data to be displayed in the table.
        header_color (str): Color for the table header.
        
    Returns:
        go.Table: A Plotly table object.
    """
    headers = list(data.keys())
    values = [[v] for v in data.values()]
    return go.Table(
        header=dict(values=headers, fill_color=header_color, align='left'),
        cells=dict(values=values, align='left')
    )

def create_pie_chart(win_loss_counts, all_trades_stats, winning_trades_stats, losing_trades_stats):
    """
    Create a pie chart with accompanying tables for trade statistics.
    
    Args:
        win_loss_counts (dict): A dictionary with win and loss counts.
        all_trades_stats (dict): Statistics for all trades.
        winning_trades_stats (dict): Statistics for winning trades.
        losing_trades_stats (dict): Statistics for losing trades.
        
    Returns:
        go.Figure: A Plotly figure containing the pie chart and tables.
    """
    # Define the layout with 1 column for the pie and 1 column for the tables, split into 3 rows
    fig = make_subplots(
        rows=3, cols=2,
        specs=[[{"type": "pie", "rowspan": 3}, {"type": "table"}],
               [None, {"type": "table"}],
               [None, {"type": "table"}]],
        column_widths=[0.4, 0.6],
        subplot_titles=(None, "All Trades", "Winning Trades", "Losing Trades")
    )

    # Add the pie chart in the first column, spanning all three rows
    pie_trace = create_pie_trace(win_loss_counts)
    fig.add_trace(pie_trace, row=1, col=1)

    # Add table for all trades statistics
    all_trades_table = create_table_trace(all_trades_stats)
    fig.add_trace(all_trades_table, row=1, col=2)

    # Add table for winning trades statistics
    winning_trades_table = create_table_trace(winning_trades_stats, header_color='lightgreen')
    fig.add_trace(winning_trades_table, row=2, col=2)

    # Add table for losing trades statistics
    losing_trades_table = create_table_trace(losing_trades_stats, header_color='salmon')
    fig.add_trace(losing_trades_table, row=3, col=2)

    # Update layout to fit the table sizes and remove empty subplot titles
    fig.update_layout(
        title='Trade Outcome Distribution and Statistics',
        showlegend=True
    )

    return fig
