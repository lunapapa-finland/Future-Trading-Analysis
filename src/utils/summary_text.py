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
    
    
    if summary: 
        section_found = False
        content = []
        
        with open(summary_file, 'r', encoding='utf-8') as file:
            capture = False
            content = []
            
            for line in file:
                # Check if we're at the start of any '##' header
                if line.startswith('##'):
                    if 'Summary' in line:
                        # Start capturing if it's the '## Summary' section
                        capture = True
                    elif capture:
                        # Stop capturing if another '##' section starts
                        break
                elif capture:
                    # Add the current line to content if we are in the capture mode
                    content.append(line)
                    
            # Convert the captured markdown content to HTML
        html_content = markdown2.markdown(''.join(content))
    else:   
        # Convert the provided date string to a datetime object for easier comparison
        target_date = datetime.strptime(date, '%Y-%m-%d').date()
        section_found = False
        content = []
        
        with open(summary_file, 'r', encoding='utf-8') as file:
            for line in file:
                # Check for section headers
                if line.startswith('## ') and not line.startswith('## Summary'):
                    # Extract the date from the section header
                    section_date = datetime.strptime(line.strip()[3:], '%Y-%m-%d').date()
                    if section_date == target_date:
                        section_found = True
                        continue
                    elif section_found:
                        # If another section starts, stop reading
                        break
                
                if section_found:
                    # Collect all lines after the target date section until another section starts
                    content.append(line)
        html_content = markdown2.markdown(''.join(content))

    return html_content
