# data/load_data.py
import pandas as pd
from dashboard.config.settings import TIMEZONE
import pytz


def load_performance(ticket, start_date, end_date, csv_path):
    try:
        df = pd.read_csv(csv_path)

        # Convert TradeDay to datetime with MM/DD/YY format, localize to Helsinki
        tz = pytz.timezone(TIMEZONE)
        df['TradeDay'] = pd.to_datetime(df['TradeDay'], format='%Y-%m-%d').dt.tz_localize(tz)
        
        # Convert input dates to datetime, localize to Helsinki
        start_date = pd.to_datetime(start_date).tz_localize(tz)
        end_date = pd.to_datetime(end_date).tz_localize(tz)
        
        # Filter by date range
        mask = (df['TradeDay'] >= start_date) & (df['TradeDay'] <= end_date)
        df = df[mask]
        # Apply ticket prefix filter on ContractName
        df = df[df['ContractName'].str.startswith(ticket)]

        return df.reset_index(drop=True)
    
    except Exception as e:
        raise Exception(f"Failed to load performance data: {str(e)}")

def load_future(start_date, end_date, csv_path):
    try:
        # Read CSV
        df = pd.read_csv(csv_path)

        # Convert Datetime to UTC, then to Helsinki
        df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True)
        tz = pytz.timezone(TIMEZONE)
        df['Datetime'] = df['Datetime'].dt.tz_convert(tz)
        
        # Convert input dates to datetime, localize to Helsinki
        start_date = pd.to_datetime(start_date).tz_localize(tz)
        end_date = pd.to_datetime(end_date).tz_localize(tz) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        
        # Filter by date range
        mask = (df['Datetime'] >= start_date) & (df['Datetime'] <= end_date)
        return df[mask].reset_index(drop=True)
    
    except Exception as e:
        raise Exception(f"Failed to load future data: {str(e)}")