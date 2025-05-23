import pandas as pd
from dashboard.config.settings import DEFAULT_GRANULARITY, DEFAULT_ROLLING_WINDOW
import numpy as np

def pnl_growth(performance_df, granularity=DEFAULT_GRANULARITY):
    if performance_df.empty:
        return pd.DataFrame(columns=['Period', 'NetPnL'])
    
    performance_df = performance_df.copy()
    performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'])
    performance_df = performance_df.sort_values('ExitedAt')
    
    try:
        # Use resample for weekly/monthly to handle fixed frequencies
        if granularity.startswith('1W'):
            # Group by week starting on Monday
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('W-MON').dt.start_time
        elif granularity == '1M':
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('M').dt.start_time
        else:  # Daily (1D)
            performance_df['Period'] = performance_df['ExitedAt'].dt.floor('D')
        
        grouped = performance_df.groupby('Period')['PnL(Net)'].sum().reset_index()
        grouped['Period'] = pd.to_datetime(grouped['Period'])
        return grouped.rename(columns={'PnL(Net)': 'NetPnL'})
    except Exception as e:
        raise ValueError(f"Failed to group by {granularity}: {str(e)}")
    
def drawdown(performance_df, granularity=DEFAULT_GRANULARITY):
    if performance_df.empty:
        return pd.DataFrame(columns=['Period', 'Drawdown'])
    
    performance_df = performance_df.copy()
    performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'])
    performance_df = performance_df.sort_values('ExitedAt')
    
    try:
        # Group by granularity
        if granularity.startswith('1W'):
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('W-MON').dt.start_time
        elif granularity == '1M':
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('M').dt.start_time
        else:  # Daily (1D)
            performance_df['Period'] = performance_df['ExitedAt'].dt.floor('D')
        
        # Sum PnL(Net) by period
        grouped = performance_df.groupby('Period')['PnL(Net)'].sum().reset_index()
        grouped['Period'] = pd.to_datetime(grouped['Period'])
        
        # Calculate cumulative PnL and drawdown
        grouped['CumulativePnL'] = grouped['PnL(Net)'].cumsum()
        grouped['PeakPnL'] = grouped['CumulativePnL'].cummax()
        grouped['Drawdown'] = grouped['CumulativePnL'] - grouped['PeakPnL']
        
        return grouped[['Period', 'Drawdown']]
    except Exception as e:
        raise ValueError(f"Failed to calculate drawdown for {granularity}: {str(e)}")
    

def pnl_distribution(performance_df):
    if performance_df.empty:
        return pd.DataFrame(columns=['PnL(Net)'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df:
            raise ValueError("PnL(Net) column missing")
        return performance_df[['PnL(Net)']]
    except Exception as e:
        raise ValueError(f"Failed to compute PnL distribution: {str(e)}")
    
def behavioral_patterns(performance_df):
    if performance_df.empty:
        return pd.DataFrame(columns=['Hour', 'TradeCount', 'AvgPnL'])
    
    performance_df = performance_df.copy()
    try:
        if 'EnteredAt' not in performance_df or 'PnL(Net)' not in performance_df:
            raise ValueError("Required columns missing: EnteredAt, PnL(Net)")
        
        performance_df['EnteredAt'] = pd.to_datetime(performance_df['EnteredAt'])
        performance_df['Hour'] = performance_df['EnteredAt'].dt.hour
        
        grouped = performance_df.groupby('Hour').agg({
            'PnL(Net)': ['count', 'mean']
        }).reset_index()
        
        grouped.columns = ['Hour', 'TradeCount', 'AvgPnL']
        grouped['AvgPnL'] = grouped['AvgPnL'].round(2)
        
        return grouped
    except Exception as e:
        raise ValueError(f"Failed to compute behavioral patterns: {str(e)}")


def rolling_win_rate(performance_df, window=DEFAULT_ROLLING_WINDOW):
    if performance_df.empty:
        return pd.DataFrame(columns=['TradeIndex', 'WinRate'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'ExitedAt' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), ExitedAt")
        
        # Derive WinOrLoss from PnL(Net)
        performance_df['WinOrLoss'] = np.where(performance_df['PnL(Net)'] > 0, 1, -1)
        
        # Sort by ExitedAt to ensure trade order
        performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'])
        performance_df = performance_df.sort_values('ExitedAt').reset_index(drop=True)
        
        # Calculate rolling win rate per trade
        win_rate_data = []
        for i in range(window - 1, len(performance_df)):
            window_data = performance_df['WinOrLoss'].iloc[i - window + 1:i + 1]
            total_wins = (window_data == 1).sum()
            total_trades = len(window_data)
            win_rate = (total_wins / total_trades * 100) if total_trades > 0 else 0
            win_rate_data.append({
                'TradeIndex': i,
                'WinRate': round(win_rate, 2)
            })
        
        return pd.DataFrame(win_rate_data)
    except Exception as e:
        raise ValueError(f"Failed to compute rolling win rate: {str(e)}")

def sharpe_ratio(performance_df, window=DEFAULT_ROLLING_WINDOW, risk_free_rate=0.02):
    if performance_df.empty:
        return pd.DataFrame(columns=['Date', 'SharpeRatio'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'ExitedAt' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), ExitedAt")
        
        # Aggregate PnL by TradeDay
        performance_df['TradeDay'] = pd.to_datetime(performance_df['ExitedAt']).dt.date
        daily_pnl = performance_df.groupby('TradeDay')['PnL(Net)'].sum().reset_index()
        daily_pnl['TradeDay'] = pd.to_datetime(daily_pnl['TradeDay'])
        daily_pnl = daily_pnl.sort_values('TradeDay')
        
        # Calculate daily returns (assuming starting capital is the cumulative sum)
        daily_pnl['CumPnL'] = daily_pnl['PnL(Net)'].cumsum()
        daily_pnl['Returns'] = daily_pnl['PnL(Net)'].pct_change().fillna(0)
        
        # Calculate rolling Sharpe Ratio
        trading_days_per_year = 252
        dates = daily_pnl['TradeDay'].values
        sharpe_data = []
        
        for i in range(window - 1, len(daily_pnl)):
            start_idx = i - window + 1
            end_idx = i + 1
            if start_idx >= 0:
                window_returns = daily_pnl.iloc[start_idx:end_idx]['Returns'].values
                mean_return = np.mean(window_returns)
                std_dev = np.std(window_returns, ddof=1) if len(window_returns) > 1 else 0
                annualized_return = mean_return * trading_days_per_year
                annualized_std = std_dev * np.sqrt(trading_days_per_year) if std_dev > 0 else 0
                sharpe = (annualized_return - risk_free_rate) / annualized_std if annualized_std > 0 else 0
                sharpe_data.append({
                    'Date': dates[i],
                    'SharpeRatio': round(sharpe, 2)
                })
        
        return pd.DataFrame(sharpe_data)
    except Exception as e:
        raise ValueError(f"Failed to compute Sharpe ratio: {str(e)}")

def trade_efficiency(performance_df, window=DEFAULT_ROLLING_WINDOW):
    if performance_df.empty:
        return pd.DataFrame(columns=['TradeIndex', 'Efficiency'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'EnteredAt' not in performance_df or 'ExitedAt' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), EnteredAt, ExitedAt")
        
        # Calculate trade duration in hours
        performance_df['EnteredAt'] = pd.to_datetime(performance_df['EnteredAt'])
        performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'])
        performance_df['Duration'] = (performance_df['ExitedAt'] - performance_df['EnteredAt']).dt.total_seconds() / 3600  # Hours
        performance_df['Efficiency'] = performance_df['PnL(Net)'] / performance_df['Duration'].replace(0, np.nan)
        
        # Sort by ExitedAt to ensure trade order
        performance_df = performance_df.sort_values('ExitedAt').reset_index(drop=True)
        
        # Calculate rolling average efficiency per trade
        efficiency_data = []
        for i in range(window - 1, len(performance_df)):
            window_data = performance_df['Efficiency'].iloc[i - window + 1:i + 1]
            rolling_avg = np.mean(window_data)
            efficiency_data.append({
                'TradeIndex': i,
                'Efficiency': round(rolling_avg, 2)
            })
        
        result = pd.DataFrame(efficiency_data)
        result['Efficiency'] = result['Efficiency'].fillna(0)
        return result
    except Exception as e:
        raise ValueError(f"Failed to compute trade efficiency: {str(e)}")

def hourly_performance(performance_df, window=DEFAULT_ROLLING_WINDOW):
    if performance_df.empty:
        return pd.DataFrame(columns=['HourlyIndex', 'HourlyPnL'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'TradeDay' not in performance_df or 'HourOfDay' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), TradeDay, HourOfDay")
        
        # Convert TradeDay to datetime and parse EnteredAt as timezone-aware
        performance_df['TradeDay'] = pd.to_datetime(performance_df['TradeDay'])
        performance_df['EnteredAt'] = pd.to_datetime(performance_df['EnteredAt'], utc=True)
        performance_df['HourOfDay'] = performance_df['HourOfDay'].astype(int)  # Ensure integer
        
        # Get timezone from first EnteredAt
        tz = performance_df['EnteredAt'].iloc[0].tzinfo
        
        # Create DateHour using TradeDay, HourOfDay, and timezone
        performance_df['DateHour'] = performance_df.apply(
            lambda row: pd.Timestamp(row['TradeDay']).replace(
                hour=row['HourOfDay'], minute=0, second=0, tzinfo=tz
            ), axis=1
        )
        
        # Aggregate PnL by DateHour
        hourly_pnl = performance_df.groupby('DateHour')['PnL(Net)'].sum().reset_index()
        hourly_pnl = hourly_pnl.sort_values('DateHour')
        
        # Assign sequential HourlyIndex
        hourly_pnl['HourlyIndex'] = range(len(hourly_pnl))
        
        # Calculate rolling average PnL over the window
        hourly_data = []
        for i in range(window - 1, len(hourly_pnl)):
            start_idx = i - window + 1
            end_idx = i + 1
            if start_idx >= 0:
                window_pnl = hourly_pnl.iloc[start_idx:end_idx]['PnL(Net)'].values
                rolling_avg_pnl = np.mean(window_pnl)
                hourly_data.append({
                    'HourlyIndex': hourly_pnl['HourlyIndex'].iloc[i],
                    'HourlyPnL': round(rolling_avg_pnl, 2),
                    'DateHour': hourly_pnl['DateHour'].iloc[i].strftime('%Y-%m-%d %H:00:00%z')
                })
        
        return pd.DataFrame(hourly_data)
    except Exception as e:
        raise ValueError(f"Failed to compute hourly performance: {str(e)}")