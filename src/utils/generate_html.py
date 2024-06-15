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

def move_static_files(template_path, html_src_path):
    # Create the destination directory if it doesn't exist
    if not os.path.exists(html_src_path):
        os.makedirs(html_src_path)

    # Get a list of all files in the template directory
    files = os.listdir(template_path)
    
    # Iterate over the files and copy CSS and JS files to the HTML path
    for file in files:
        if file.endswith('.css'):
            src_file = os.path.join(template_path, file)
            dest_file = os.path.join(html_src_path + "css/", file)
            shutil.copy(src_file, dest_file)
        elif file.endswith('.js'):
            src_file = os.path.join(template_path, file)
            dest_file = os.path.join(html_src_path + "js/", file)
            shutil.copy(src_file, dest_file)


def generate_html(ticker, fig_statistic, html_summary, parameters_report, fig_assemble=None):
    env = Environment(loader=FileSystemLoader(parameters_report['template_path']))
    template = env.get_template('template.html')
    if fig_assemble is not None:
        fig_assemble_json = json.dumps(fig_assemble, cls=plotly.utils.PlotlyJSONEncoder)
    else: 
        fig_assemble_json = None
    fig_statistic_json = json.dumps(fig_statistic, cls=plotly.utils.PlotlyJSONEncoder)
    # Call the function to move static files
    move_static_files(parameters_report['template_path'], parameters_report['html_src_path'])

    html_content = template.render(fig_assemble_json=fig_assemble_json, fig_statistic_json=fig_statistic_json,
                                html_summary=html_summary)
    if fig_assemble is not None:    
        file_name = f"{parameters_report['html_path']}{ticker}_Candlestick_Chart_{parameters_report['date']}.html"
        with open(file_name, "w") as f:
            f.write(html_content)
    else:
        file_name = f"{parameters_report['html_path']}Overall_performance.html"
        with open(file_name, "w") as f:
            f.write(html_content)


def generate_index(parameters_report):

    env = Environment(loader=FileSystemLoader(parameters_report['template_path']))
    template = env.get_template('index_template.html')

    # List HTML files excluding index.html
    # Function to extract and concatenate parts of the filename
    def extract_and_concat(filename):
        first_part = filename.split('_')[0].split('.')[0]
        last_part = filename.split('_')[-1].split('.')[0]
        return first_part + last_part

    # List and sort the files
    files = sorted(
        [f for f in os.listdir(parameters_report['html_path']) if f.endswith('.html') and f != 'index.html'],
        key=lambda filename: extract_and_concat(filename)
    )

    # files = sorted([f for f in os.listdir(parameters_report['html_path']) if f.endswith('.html') and f != 'index.html'], key=lambda filename: filename.split('_')[-1].split('.')[0])

    index_html = template.render(files=files)

    # Write the rendered HTML to index.html
    index_file_path = os.path.join(parameters_report['html_path'], "index.html")
    with open(index_file_path, "w") as f:
        f.write(index_html)
