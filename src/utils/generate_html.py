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
import shutil
from flask import Flask, url_for


def move_static_files(template_path, html_src_path):
    """
    Move CSS and JS files from the template directory to the HTML source path.
    
    Args:
        template_path (str): The path to the template directory.
        html_src_path (str): The path to the HTML source directory.
    """
    try:
        # Create the destination directory if it doesn't exist
        os.makedirs(os.path.join(html_src_path, 'css'), exist_ok=True)
        os.makedirs(os.path.join(html_src_path, 'js'), exist_ok=True)

        # Get a list of all files in the template directory
        files = os.listdir(template_path)
        
        # Iterate over the files and copy CSS and JS files to the HTML path
        for file in files:
            if file.endswith('.css') or file.endswith('.js'):
                src_file = os.path.join(template_path, file)
                dest_file = os.path.join(html_src_path, 'css' if file.endswith('.css') else 'js', file)
                shutil.copy(src_file, dest_file)
    except Exception as e:
        print(f"Error moving static files: {e}")


def generate_html(ticker, fig_statistic, parameters_report, fig_assemble=None):
    """
    Generate an HTML report with the given plots and summary.

    Args:
        ticker (str): The ticker symbol.
        fig_statistic (go.Figure): The statistical figure.
        html_summary (str): The HTML summary content.
        parameters_report (dict): The parameters for the report.
        fig_assemble (go.Figure, optional): The assembled figure. Defaults to None.
    """
    env = Environment(loader=FileSystemLoader(parameters_report['template_path']))
    template = env.get_template('template.html')
    
    fig_assemble_json = json.dumps(fig_assemble, cls=plotly.utils.PlotlyJSONEncoder) if fig_assemble else None
    fig_statistic_json = json.dumps(fig_statistic, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Move static files
    move_static_files(parameters_report['template_path'], parameters_report['html_src_path'])

    html_content = template.render(fig_assemble_json=fig_assemble_json, fig_statistic_json=fig_statistic_json)
    
    file_name = f"{ticker}_Candlestick_Chart_{parameters_report['date']}.html" if fig_assemble else "Overall_performance.html"
    file_path = os.path.join(parameters_report['html_path'], file_name)
    
    with open(file_path, "w") as f:
        f.write(html_content)


def generate_index(parameters_report):
    """
    Generate an index HTML file listing all reports.

    Args:
        parameters_report (dict): The parameters for the report.
    """
    env = Environment(loader=FileSystemLoader(parameters_report['template_path']))

    def extract_date(filename):
        if "Overall_performance" in filename:
            return "Overall"
        return filename.rsplit('_', 1)[1].rsplit('.', 1)[0]

    files = [f for f in os.listdir(parameters_report['html_path']) if f.endswith('.html') and f != 'index.html']

    file_dict = {}
    for file in files:
        date = extract_date(file)
        if date not in file_dict:
            file_dict[date] = []
        file_dict[date].append(file)

    sorted_dates = sorted((d for d in file_dict if d != "Overall"), reverse=True)
    if "Overall" in file_dict:
        sorted_dates.insert(0, "Overall")

    sorted_file_dict = {date: sorted(file_dict[date], key=lambda f: f.lower()) for date in sorted_dates}

    template = env.get_template('index_template.html')
    index_html = template.render(file_dict=sorted_file_dict)

    index_file_path = os.path.join(parameters_report['html_path'], "index.html")
    with open(index_file_path, "w") as f:
        f.write(index_html)
