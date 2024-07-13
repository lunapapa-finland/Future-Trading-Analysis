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

def create_summary(summary_file, date, summary):
    """
    Create an HTML summary from a markdown file based on the specified date or summary section.

    Args:
        summary_file (str): The path to the markdown summary file.
        date (str): The target date for the summary.
        summary (bool): Flag to indicate if the summary section should be captured.

    Returns:
        str: The HTML content of the summary.
    """
    content = []

    if summary:
        capture = False
        with open(summary_file, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('##'):
                    if 'Summary' in line:
                        capture = True
                    elif capture:
                        break
                elif capture:
                    content.append(line)
    else:
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        section_found = False
        
        with open(summary_file, 'r', encoding='utf-8') as file:
            for line in file:
                if line.startswith('## ') and not line.startswith('## Summary'):
                    section_date = datetime.strptime(line.strip()[3:], '%Y-%m-%d').date()
                    if section_date == target_date:
                        section_found = True
                        continue
                    elif section_found:
                        break
                if section_found:
                    content.append(line)

    html_content = markdown2.markdown(''.join(content))
    return html_content
