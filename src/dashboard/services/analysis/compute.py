import pandas as pd
from dashboard.config.settings import DEFAULT_GRANULARITY, DEFAULT_ROLLING_WINDOW
from dashboard.config.analysis import ANALYSIS_TIMEZONE, rule_compliance_defaults
import numpy as np
from dashboard.services.analysis.schema import validate_performance_df
from dashboard.services.utils.day_plan import load_day_plan
import re

# Backward-compatible test/extension hook. Leave as None in normal runtime so
# rule defaults come from the live config loader on each operation.
RULE_COMPLIANCE_DEFAULTS = None


def _rule_defaults():
    return RULE_COMPLIANCE_DEFAULTS if isinstance(RULE_COMPLIANCE_DEFAULTS, dict) else rule_compliance_defaults()


def _coerce_window(window, fallback=DEFAULT_ROLLING_WINDOW):
    value = fallback if window is None else window
    try:
        value = int(value)
    except (TypeError, ValueError):
        raise ValueError("window must be a positive integer")
    if value < 1:
        raise ValueError("window must be a positive integer")
    return value


def _to_cme(series: pd.Series, column_name: str) -> pd.Series:
    ts = pd.to_datetime(series, utc=True, errors="coerce")
    if ts.isna().any():
        raise ValueError(f"Invalid datetime values in '{column_name}' column")
    return ts.dt.tz_convert(ANALYSIS_TIMEZONE)


def pnl_growth(performance_df, granularity=DEFAULT_GRANULARITY, daily_compounding_rate=0.001902, initial_funding=10000):
    performance_df = validate_performance_df(performance_df)
    # Initialize empty result if performance_df is empty
    if performance_df.empty:
        return pd.DataFrame(columns=['Period', 'NetPnL', 'CumulativePnL', 'PassiveGrowth', 'CumulativePassive'])
    
    performance_df = performance_df.copy()
    # Normalize to CME and then remove tz for period bucketing.
    performance_df['ExitedAt'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt').dt.tz_localize(None)
    
    performance_df = performance_df.sort_values('ExitedAt')
    
    try:
        # Validate granularity
        valid_granularities = ['1D', '1W-MON', '1M']
        if granularity not in valid_granularities:
            raise ValueError(f"Unsupported granularity: {granularity}. Must be one of: {valid_granularities}")
        
        # Assign Period based on granularity
        if granularity == '1D':
            performance_df['Period'] = performance_df['ExitedAt'].dt.floor('D')
        elif granularity == '1W-MON':
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('W-MON').dt.start_time
        elif granularity == '1M':
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('M').dt.start_time
        
        # Group by Period and sum PnL
        grouped = performance_df.groupby('Period')['PnL(Net)'].sum().reset_index()
        grouped['Period'] = pd.to_datetime(grouped['Period'])
        grouped = grouped.rename(columns={'PnL(Net)': 'NetPnL'})
        grouped['CumulativePnL'] = grouped['NetPnL'].cumsum()
        
        # Calculate passive compounding growth
        start_date = pd.Timestamp(performance_df['ExitedAt'].dt.date.min())
        end_date = pd.Timestamp(performance_df['ExitedAt'].dt.date.max())
        
        # Use business days for trader-centric passive baseline.
        date_range = pd.bdate_range(start=start_date, end=end_date)
        passive_df = pd.DataFrame({'Date': date_range})
        # Day-0 baseline: passive curve starts at 0 growth on the first date.
        passive_df['Days'] = (passive_df['Date'] - start_date).dt.days
        passive_df['PassiveGrowth'] = (1 + daily_compounding_rate) ** passive_df['Days'] * initial_funding - initial_funding
        passive_df['Period'] = passive_df['Date']
        
        # Aggregate passive growth by granularity (take last value of period)
        if granularity == '1D':
            passive_df['Period'] = passive_df['Period'].dt.floor('D')
        elif granularity == '1W-MON':
            passive_df['Period'] = passive_df['Period'].dt.to_period('W-MON').dt.start_time
        elif granularity == '1M':
            passive_df['Period'] = passive_df['Period'].dt.to_period('M').dt.start_time
        
        passive_grouped = passive_df.groupby('Period').agg({'PassiveGrowth': 'last'}).reset_index()
        passive_grouped['CumulativePassive'] = passive_grouped['PassiveGrowth']  # No cumsum, already cumulative
        
        # Merge with grouped PnL
        grouped = pd.merge(grouped, passive_grouped[['Period', 'PassiveGrowth', 'CumulativePassive']],
                         on='Period', how='outer').sort_values('Period')
        
        # Keep passive growth curve continuous across periods with no trades.
        grouped['PassiveGrowth'] = grouped['PassiveGrowth'].ffill().fillna(0)
        grouped['CumulativePassive'] = grouped['CumulativePassive'].ffill().fillna(0)
        grouped['NetPnL'] = grouped['NetPnL'].fillna(0)
        grouped['CumulativePnL'] = grouped['NetPnL'].cumsum()
        
        return grouped[['Period', 'NetPnL', 'CumulativePnL', 'PassiveGrowth', 'CumulativePassive']]
    
    except Exception as e:
        raise ValueError(f"Failed to group by {granularity}: {str(e)}")
    

def drawdown(performance_df, granularity=DEFAULT_GRANULARITY):
    performance_df = validate_performance_df(performance_df)
    if performance_df.empty:
        return pd.DataFrame(columns=['Period', 'Drawdown'])
    
    performance_df = performance_df.copy()
    # Normalize to CME and then remove tz for period bucketing.
    performance_df['ExitedAt'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt').dt.tz_localize(None)
    performance_df = performance_df.sort_values('ExitedAt')
    
    try:
        # Validate granularity
        valid_granularities = ['1D', '1W-MON', '1M']
        if granularity not in valid_granularities:
            raise ValueError(f"Unsupported granularity: {granularity}. Must be one of {valid_granularities}")
        
        # Assign Period based on granularity
        if granularity == '1D':
            performance_df['Period'] = performance_df['ExitedAt'].dt.floor('D')
        elif granularity == '1W-MON':
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('W-MON').dt.start_time
        elif granularity == '1M':
            performance_df['Period'] = performance_df['ExitedAt'].dt.to_period('M').dt.start_time
        
        # Sum PnL(Net) by period
        grouped = performance_df.groupby('Period')['PnL(Net)'].sum().reset_index()
        grouped['Period'] = pd.to_datetime(grouped['Period'])
        
        # Calculate cumulative PnL and drawdown
        grouped['CumulativePnL'] = grouped['PnL(Net)'].cumsum()
        # Anchor drawdown to starting equity (0). Otherwise an initial losing period
        # incorrectly reports drawdown as 0 instead of a negative value.
        grouped['PeakPnL'] = grouped['CumulativePnL'].cummax().clip(lower=0)
        grouped['Drawdown'] = grouped['CumulativePnL'] - grouped['PeakPnL']
        
        return grouped[['Period', 'Drawdown']]
    except Exception as e:
        raise ValueError(f"Failed to calculate drawdown for {granularity}: {str(e)}")
    

def pnl_distribution(performance_df):
    performance_df = validate_performance_df(performance_df)
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
    performance_df = validate_performance_df(performance_df)
    if performance_df.empty:
        return pd.DataFrame(columns=['Hour', 'DayOfWeek', 'TradeCount', 'AvgPnL'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'Size' not in performance_df or 'EnteredAt' not in performance_df:
            raise ValueError("Required columns missing: EnteredAt, PnL(Net), Size")

        performance_df['EnteredAt'] = _to_cme(performance_df['EnteredAt'], 'EnteredAt')
        performance_df['HourOfDay'] = performance_df['EnteredAt'].dt.hour.astype(int)
        performance_df['DayOfWeek'] = performance_df['EnteredAt'].dt.day_name()
        
        # Use HourOfDay directly and define weekday order
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        performance_df['DayOfWeek'] = pd.Categorical(performance_df['DayOfWeek'], categories=weekday_order, ordered=True)
        
        # Group by and aggregate with multi-index
        grouped = performance_df.groupby(['HourOfDay', 'DayOfWeek'], observed=True).agg({
            'PnL(Net)': ['sum', 'count'],
            'Size': 'sum'
        }).reset_index()
        
        # Flatten multi-index columns and rename
        grouped.columns = ['Hour', 'DayOfWeek', 'TotalPnL', 'TradeCount', 'TotalSize']
        # Calculate AvgPnL per contract (size)
        grouped['AvgPnL'] = grouped['TotalPnL'] / grouped['TotalSize'].replace(0, 1e-10)  # Avoid division by zero
        grouped['AvgPnL'] = grouped['AvgPnL'].round(2)
        
        # Drop intermediate columns
        grouped = grouped[['Hour', 'DayOfWeek', 'TradeCount', 'AvgPnL']]
        
        # Create a full matrix of hours (0-23) and all weekdays.
        all_hours = np.arange(0, 24)  # Hours 0 to 23
        all_days = weekday_order
        # Create a MultiIndex with all combinations of Hour and DayOfWeek
        full_index = pd.MultiIndex.from_product([all_hours, all_days], names=['Hour', 'DayOfWeek'])
        full_df = pd.DataFrame(index=full_index).reset_index()
        
        # Merge with grouped data, filling missing values with 0
        grouped = full_df.merge(grouped, on=['Hour', 'DayOfWeek'], how='left')
        grouped['TradeCount'] = grouped['TradeCount'].fillna(0).astype(int)
        grouped['AvgPnL'] = grouped['AvgPnL'].fillna(0)
        
        # Ensure DayOfWeek is categorical with correct order
        grouped['DayOfWeek'] = pd.Categorical(grouped['DayOfWeek'], categories=weekday_order, ordered=True)
        
        return grouped
    except Exception as e:
        raise ValueError(f"Failed to compute behavioral patterns: {str(e)}")


def rolling_win_rate(performance_df, window=DEFAULT_ROLLING_WINDOW):
    performance_df = validate_performance_df(performance_df)
    window = _coerce_window(window)
    if performance_df.empty:
        return pd.DataFrame(columns=['TradeIndex', 'WinRate'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'ExitedAt' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), ExitedAt")
        
        # Derive WinOrLoss from PnL(Net)
        performance_df['WinOrLoss'] = np.where(performance_df['PnL(Net)'] > 0, 1, -1)
        
        # Sort by ExitedAt to ensure trade order
        performance_df['ExitedAt'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt')
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

def sharpe_ratio(performance_df, window=DEFAULT_ROLLING_WINDOW, risk_free_rate=0.02, initial_capital=10000):
    performance_df = validate_performance_df(performance_df)
    window = _coerce_window(window)
    if performance_df.empty:
        return pd.DataFrame(columns=['Date', 'SharpeRatio'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'ExitedAt' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), ExitedAt")
        
        # Aggregate PnL by TradeDay
        performance_df['TradeDay'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt').dt.tz_localize(None).dt.date
        daily_pnl = performance_df.groupby('TradeDay')['PnL(Net)'].sum().reset_index()
        daily_pnl['TradeDay'] = pd.to_datetime(daily_pnl['TradeDay'])
        daily_pnl = daily_pnl.sort_values('TradeDay')
        
        # Calculate capital-based daily returns.
        daily_pnl['CumPnL'] = daily_pnl['PnL(Net)'].cumsum()
        daily_pnl['Equity'] = initial_capital + daily_pnl['CumPnL']
        daily_pnl['PrevEquity'] = daily_pnl['Equity'].shift(1).fillna(initial_capital)
        daily_pnl['Returns'] = (
            daily_pnl['PnL(Net)'] / daily_pnl['PrevEquity'].replace(0, np.nan)
        ).replace([np.inf, -np.inf], np.nan).fillna(0)
        
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

# # 日内交易专属参数
# TRADING_DAYS = 252
# DEFAULT_WINDOWS = [7, 14, 30]  # 你最爱的三个窗口

# def sharpe_intraday_es(performance_df, 
#                        initial_capital=100000, 
#                        risk_free_rate=0.0483,  # 2025.11.06 SOFR = 4.83%，美股期货标配
#                        windows=DEFAULT_WINDOWS):
#     """
#     专为 ES/NQ 日内交易设计，一行代码出 7/14/30 天滚动Sharpe
#     performance_df 只需要两列：'PnL(Net)' 和 'ExitedAt'（任意时区时间）
#     """
#     if performance_df.empty:
#         return pd.DataFrame()
    
#     df = performance_df.copy()
#     df['date'] = pd.to_datetime(df['ExitedAt']).dt.date
    
#     # 1. 按天聚合（日内多笔自动合并）
#     daily = df.groupby('date')['PnL(Net)'].sum().reset_index()
#     daily['date'] = pd.to_datetime(daily['date'])
#     daily = daily.sort_values('date')
    
#     # 2. 资金曲线（日内交易最准做法）
#     capital = initial_capital
#     capital_series = [capital]
#     for pnl in daily['PnL(Net)']:
#         capital += pnl
#         capital_series.append(capital)
    
#     daily['capital'] = capital_series[1:]           # 当天结束时的资金
#     daily['prev_capital'] = capital_series[:-1]     # 开盘资金
#     daily['return'] = daily['PnL(Net)'] / daily['prev_capital']
    
#     # 3. 补全无交易日（防止周末跳空，√252 更准）
#     full_dates = pd.date_range(daily['date'].min(), daily['date'].max(), freq='B')
#     daily = daily.set_index('date').reindex(full_dates).fillna({'PnL(Net)': 0, 'return': 0})
#     daily = daily.reset_index().rename(columns={'index': 'date'})
#     daily['capital'] = initial_capital + daily['PnL(Net)'].cumsum()
#     daily['prev_capital'] = daily['capital'].shift(1).fillna(initial_capital)
#     daily['return'] = daily['PnL(Net)'] / daily['prev_capital']
    
#     # 4. 多窗口滚动Sharpe（向量化，飞快）
#     returns = daily['return'].values
#     dates = daily['date'].values
#     rf_daily = risk_free_rate / TRADING_DAYS
    
#     result_list = []
#     for window in windows:
#         sharpe_values = np.full(len(returns), np.nan)
        
#         for i in range(window - 1, len(returns)):
#             window_ret = returns[i - window + 1: i + 1]
#             excess_mean = np.mean(window_ret) - rf_daily
#             std_daily = np.std(window_ret, ddof=1)
            
#             if std_daily > 1e-8:  # 避免除0
#                 sharpe = excess_mean * TRADING_DAYS / (std_daily * np.sqrt(TRADING_DAYS))
#             else:
#                 sharpe = np.inf if excess_mean > 0 else -np.inf
                
#             sharpe_values[i] = round(sharpe, 3)
        
#         temp_df = pd.DataFrame({
#             'Date': dates,
#             f'Sharpe_{window}d': sharpe_values
#         })
#         result_list.append(temp_df)
    
#     # 5. 合并所有窗口
#     result = result_list[0]
#     for df in result_list[1:]:
#         result = result.merge(df[['Date', df.columns[1]]], on='Date', how='outer')
    
#     return result[result['Date'] >= daily['date'].iloc[window-1]]  # 去掉前window-1行无效值


def trade_efficiency(performance_df, window=DEFAULT_ROLLING_WINDOW):
    performance_df = validate_performance_df(performance_df)
    window = _coerce_window(window)
    if performance_df.empty:
        return pd.DataFrame(columns=['TradeIndex', 'Efficiency'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'EnteredAt' not in performance_df or 'ExitedAt' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), EnteredAt, ExitedAt")
        
        # Calculate trade duration in hours
        performance_df['EnteredAt'] = _to_cme(performance_df['EnteredAt'], 'EnteredAt')
        performance_df['ExitedAt'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt')
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

def hourly_performance(performance_df):
    performance_df = validate_performance_df(performance_df)
    if performance_df.empty:
        return pd.DataFrame(columns=['HourOfDay', 'HourlyPnL', 'TradeCount', 'TotalPnL'])
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df or 'EnteredAt' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net), EnteredAt")

        performance_df['EnteredAt'] = _to_cme(performance_df['EnteredAt'], 'EnteredAt')
        performance_df['HourOfDay'] = performance_df['EnteredAt'].dt.hour.astype(int)

        # Statistical view across selected lifecycle: aggregate by hour-of-day only.
        grouped = (
            performance_df.groupby('HourOfDay', observed=True)
            .agg(TotalPnL=('PnL(Net)', 'sum'), TradeCount=('PnL(Net)', 'size'))
            .reset_index()
            .sort_values('HourOfDay')
        )
        grouped['HourlyPnL'] = (grouped['TotalPnL'] / grouped['TradeCount'].replace(0, np.nan)).fillna(0).round(2)
        return grouped[['HourOfDay', 'HourlyPnL', 'TradeCount', 'TotalPnL']]
    except Exception as e:
        raise ValueError(f"Failed to compute hourly performance: {str(e)}")
    


def performance_envelope(performance_df, granularity=DEFAULT_GRANULARITY):
    # Part 1: Theoretical Envelope Curve
    winning_rates = np.arange(0, 101, 0.1)
    theoretical_data = pd.DataFrame({'WinningRate': winning_rates})
    theoretical_data['WinningRate'] = theoretical_data['WinningRate'].round(1)
    theoretical_data['TheoreticalWinToLoss'] = (100 - theoretical_data['WinningRate']) / theoretical_data['WinningRate'].replace(0, 1e-10)
    theoretical_data['TheoreticalWinToLoss'] = theoretical_data['TheoreticalWinToLoss'].clip(upper=20)
    theoretical_data = theoretical_data.drop_duplicates(subset=['WinningRate']).sort_values('WinningRate')

    # Part 2: Actual Data Points based on granularity
    if performance_df.empty:
        return theoretical_data, pd.DataFrame(columns=['WinningRate', 'AvgWinToAvgLoss', 'PeriodStart', 'PeriodEnd', 'AboveTheoretical'])

    performance_df = performance_df.copy()
    # Use CME-local trade day derived from ExitedAt to avoid stale/mismatched source columns.
    performance_df['TradeDay'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt').dt.tz_localize(None)
    performance_df['WinOrLoss'] = performance_df['WinOrLoss'].astype(int, errors='ignore')
    performance_df['Size'] = performance_df['Size'].astype(int, errors='ignore')
    performance_df = performance_df.sort_values('TradeDay')

    try:
        # Validate granularity
        valid_granularities = ['1D', '1W-MON', '1M']
        if granularity not in valid_granularities:
            raise ValueError(f"Unsupported granularity: {granularity}. Must be one of {valid_granularities}")

        # Assign Period based on granularity
        if granularity == '1D':
            performance_df['Period'] = performance_df['TradeDay'].dt.date
        elif granularity == '1W-MON':
            performance_df['Period'] = performance_df['TradeDay'].dt.to_period('W-MON')
        elif granularity == '1M':
            performance_df['Period'] = performance_df['TradeDay'].dt.to_period('M')

        # Group by Period to calculate metrics
        grouped = performance_df.groupby('Period').agg({
            'Size': 'sum',
            'WinOrLoss': lambda x: performance_df.loc[x.index, 'Size'][x == 1].sum(),
            'TradeDay': ['min', 'max']
        }).reset_index()

        grouped.columns = ['Period', 'TradeSizeSum', 'WinSizeSum', 'PeriodStart', 'PeriodEnd']
        grouped['WinningRate'] = grouped['WinSizeSum'] / grouped['TradeSizeSum'] * 100

        # Calculate Avg Win and Avg Loss for each period
        avg_metrics = []
        for period in grouped['Period']:
            period_trades = performance_df[performance_df['Period'] == period]
            wins = period_trades[period_trades['WinOrLoss'] == 1]
            losses = period_trades[period_trades['WinOrLoss'] == -1]

            if not wins.empty:
                total_pnl_wins = wins['PnL(Net)'].sum()
                total_size_wins = wins['Size'].sum()
                avg_win = total_pnl_wins / total_size_wins if total_size_wins > 0 else 0
            else:
                avg_win = 0

            if not losses.empty:
                total_pnl_losses = losses['PnL(Net)'].sum()
                total_size_losses = losses['Size'].sum()
                avg_loss = abs(total_pnl_losses / total_size_losses) if total_size_losses > 0 else 1e-10
            else:
                avg_loss = 1e-10

            avg_win_to_avg_loss = avg_win / avg_loss if avg_loss != 0 else 0
            avg_metrics.append(avg_win_to_avg_loss)

        grouped['AvgWinToAvgLoss'] = avg_metrics
        grouped['AvgWinToAvgLoss'] = grouped['AvgWinToAvgLoss'].clip(upper=20)

        # Create actual_data
        actual_data = grouped[['WinningRate', 'AvgWinToAvgLoss', 'PeriodStart', 'PeriodEnd']].copy()

        # Convert PeriodStart and PeriodEnd to string format
        actual_data['PeriodStart'] = pd.to_datetime(actual_data['PeriodStart'].apply(lambda x: x.start_time if hasattr(x, 'start_time') else x)).dt.strftime('%Y-%m-%d')
        actual_data['PeriodEnd'] = pd.to_datetime(actual_data['PeriodEnd'].apply(lambda x: x.end_time if hasattr(x, 'end_time') else x)).dt.strftime('%Y-%m-%d')

        # Dynamically calculate TheoreticalWinToLoss
        def get_theoretical_win_to_loss(winning_rate):
            if winning_rate == 0:
                return 20
            elif winning_rate == 100:
                return 0
            else:
                return min((100 - winning_rate) / winning_rate, 20)

        actual_data['TheoreticalWinToLoss'] = actual_data['WinningRate'].apply(get_theoretical_win_to_loss)
        actual_data['AboveTheoretical'] = actual_data['AvgWinToAvgLoss'] > actual_data['TheoreticalWinToLoss']

        return theoretical_data, actual_data
    except Exception as e:
        raise ValueError(f"Failed to compute Performance Envelope for {granularity}: {str(e)}")
    
def overtrading_detection(
    performance_df,
    cap_loss_per_trade=200,
    cap_trades_after_big_loss=5,
    max_consecutive_losses=3,
    include_eth=True,
    rth_start="08:30",
    rth_end="15:00",
):
    # Initialize empty DataFrames if performance_df is empty
    daily_columns = ['TradeDay', 'TradesPerDay', 'DailyPnL']
    trade_columns = [
        'TradeIndex',
        'R_multiple',
        'IsPostLoss',
        'IsConsecutiveLossBreach',
        'TradeDay',
        'ExitedAt',
        'PnL(Net)',
        'Size',
        'Duration',
        'Session',
        'BreachReason',
        'TradeTag',
    ]
    if performance_df.empty:
        return pd.DataFrame(columns=daily_columns), pd.DataFrame(columns=trade_columns)
    
    performance_df = performance_df.copy()
    try:
        # Validate required columns
        required_cols = ['PnL(Net)', 'ExitedAt', 'EnteredAt', 'Size']
        if not all(col in performance_df for col in required_cols):
            raise ValueError(f"Required columns missing: {', '.join(set(required_cols) - set(performance_df.columns))}")
        
        # Normalize all time references to CME local time.
        performance_df['ExitedAt'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt').dt.tz_localize(None)
        performance_df['EnteredAt'] = _to_cme(performance_df['EnteredAt'], 'EnteredAt').dt.tz_localize(None)
        performance_df['TradeDay'] = performance_df['ExitedAt'].dt.floor("D")
        start_t = pd.to_datetime(rth_start, format="%H:%M").time()
        end_t = pd.to_datetime(rth_end, format="%H:%M").time()
        performance_df['Session'] = np.where(
            performance_df['EnteredAt'].dt.time.between(start_t, end_t),
            'RTH',
            'ETH',
        )
        if not include_eth:
            performance_df = performance_df[performance_df['Session'] == 'RTH'].copy()
            if performance_df.empty:
                return pd.DataFrame(columns=daily_columns), pd.DataFrame(columns=trade_columns)
        
        # Daily aggregation for existing plots
        grouped = performance_df.groupby('TradeDay').agg({
            'PnL(Net)': 'sum',  # Sum of PnL(Net) for daily PnL
            'TradeDay': 'size'  # Count of rows (trades) per TradeDay
        }).rename(columns={'TradeDay': 'TradesPerDay', 'PnL(Net)': 'DailyPnL'}).reset_index()
        
        # Create full date range from min to max TradeDay
        date_range = pd.date_range(start=grouped['TradeDay'].min(), end=grouped['TradeDay'].max(), freq='D')
        full_df = pd.DataFrame({'TradeDay': date_range})
        
        # Merge with grouped data, filling missing days with 0
        daily_df = full_df.merge(grouped, on='TradeDay', how='left')
        daily_df['TradesPerDay'] = daily_df['TradesPerDay'].fillna(0).astype(int)
        daily_df['DailyPnL'] = daily_df['DailyPnL'].fillna(0).round(2)
        
        # Trade-level processing for revenge trading
        trade_df = performance_df[['TradeDay', 'PnL(Net)', 'ExitedAt', 'EnteredAt', 'Size']].copy()
        trade_df = trade_df.sort_values('ExitedAt').reset_index(drop=True)
        trade_df['TradeIndex'] = trade_df.index + 1
        
        # Compute R-multiple
        trade_df['R_multiple'] = trade_df['PnL(Net)'] / cap_loss_per_trade
        
        # Compute duration in minutes
        trade_df['Duration'] = (trade_df['ExitedAt'] - trade_df['EnteredAt']).dt.total_seconds() / 60
        
        # Identify large loss trades and explicit overtrading breaches.
        trade_df['IsLoss'] = trade_df['R_multiple'] <= -1
        trade_df['IsPostLoss'] = False
        trade_df['IsConsecutiveLossBreach'] = False
        trade_df['BreachReason'] = ""
        trade_df['Session'] = np.where(
            trade_df['EnteredAt'].dt.time.between(start_t, end_t),
            'RTH',
            'ETH',
        )

        # Consecutive loss breach: mark trades once streak exceeds max.
        streak = 0
        for idx in trade_df.index:
            if bool(trade_df.loc[idx, 'IsLoss']):
                streak += 1
            else:
                streak = 0
            if streak > int(max_consecutive_losses):
                trade_df.loc[idx, 'IsConsecutiveLossBreach'] = True

        # Post-big-loss window: any immediate re-entry within configured trade-count window.
        for idx in trade_df[trade_df['IsLoss']].index:
            end_idx = min(idx + cap_trades_after_big_loss + 1, len(trade_df))
            trade_df.loc[idx + 1:end_idx - 1, 'IsPostLoss'] = True

        # Explainable tags/reasons (no hidden heuristic scoring).
        trade_df['TradeTag'] = 'LightBlue'
        for idx in trade_df.index:
            reasons = []
            if bool(trade_df.loc[idx, 'IsConsecutiveLossBreach']):
                reasons.append('consecutive_losses')
            if bool(trade_df.loc[idx, 'IsPostLoss']):
                reasons.append('reentry_after_big_loss')
            if reasons:
                trade_df.loc[idx, 'BreachReason'] = ", ".join(reasons)
                trade_df.loc[idx, 'TradeTag'] = 'DarkRed' if len(reasons) > 1 else 'LightCoral'

        # Select relevant columns
        trade_df = trade_df[
            [
                'TradeIndex',
                'R_multiple',
                'IsPostLoss',
                'IsConsecutiveLossBreach',
                'TradeDay',
                'ExitedAt',
                'PnL(Net)',
                'Size',
                'Duration',
                'Session',
                'BreachReason',
                'TradeTag',
            ]
        ]
        
        return daily_df, trade_df
    
    except Exception as e:
        raise ValueError(f"Failed to compute overtrading detection: {str(e)}")
    


def kelly_criterion(performance_df):
    if performance_df.empty:
        return {
            "data": pd.DataFrame(columns=['TradeDay', 'KellyValue']),
            "metadata": {'Kelly Criterion': {'category': 'Overall'}}
        }
    
    performance_df = performance_df.copy()
    try:
        if 'PnL(Net)' not in performance_df:
            raise ValueError("Required columns missing: PnL(Net)")
        # Use CME-local day from ExitedAt when available; fallback to TradeDay.
        if 'ExitedAt' in performance_df:
            performance_df['TradeDay'] = _to_cme(performance_df['ExitedAt'], 'ExitedAt').dt.tz_localize(None).dt.floor("D")
        elif 'TradeDay' in performance_df:
            performance_df['TradeDay'] = pd.to_datetime(performance_df['TradeDay']).dt.tz_localize(None)
        else:
            raise ValueError("Required columns missing: ExitedAt or TradeDay")
        
        # Ensure PnL(Net) is numeric, converting non-numeric to NaN
        performance_df['PnL(Net)'] = pd.to_numeric(performance_df['PnL(Net)'], errors='coerce')
        
        # Check for NaN values in PnL(Net)
        if performance_df['PnL(Net)'].isna().any():
            performance_df = performance_df.dropna(subset=['PnL(Net)'])
        
        # Define a trade as a win if PnL(Net) > 0
        performance_df['IsWin'] = performance_df['PnL(Net)'] > 0
        
        # Aggregate daily metrics (only for days with trades)
        daily_metrics = performance_df.groupby('TradeDay').agg({
            'IsWin': 'sum',
            'PnL(Net)': list
        }).reset_index()
        daily_metrics['TotalTrades'] = daily_metrics['PnL(Net)'].apply(len)
        
        # Filter out days with no trades
        daily_metrics = daily_metrics[daily_metrics['TotalTrades'] > 0].copy()
        

        # Calculate metrics for each day
        daily_metrics['WinRate'] = daily_metrics['IsWin'] / daily_metrics['TotalTrades'].replace(0, np.nan)
        daily_metrics['AvgWin'] = daily_metrics['PnL(Net)'].apply(
            lambda x: np.mean([val for val in x if val > 0]) if any(val > 0 for val in x) else np.nan
        )
        daily_metrics['AvgLoss'] = -daily_metrics['PnL(Net)'].apply(
            lambda x: np.mean([val for val in x if val < 0]) if any(val < 0 for val in x) else np.nan
        )
        
        # Calculate RewardToRisk only where both AvgWin and AvgLoss are valid
        mask = (daily_metrics['AvgWin'].notna()) & (daily_metrics['AvgLoss'].notna()) & (daily_metrics['AvgLoss'] != 0)
        daily_metrics['RewardToRisk'] = np.where(
            mask,
            daily_metrics['AvgWin'] / daily_metrics['AvgLoss'],
            np.nan
        )
        
        # Calculate Kelly Criterion
        daily_metrics['KellyValue'] = np.where(
            mask,
            daily_metrics['WinRate'] - (1 - daily_metrics['WinRate']) / daily_metrics['RewardToRisk'],
            np.nan
        )
        
        # Fill NaN with 0 (optional, can be adjusted based on preference)
        daily_metrics['KellyValue'] = daily_metrics['KellyValue'].fillna(0)
        
        # Prepare the result with metadata
        result = {
            "data": daily_metrics[['TradeDay', 'KellyValue']],
            "metadata": {'Kelly Criterion': {'category': 'Overall'}}
        }
        
        return result
    
    except Exception as e:
        raise ValueError(f"Failed to compute Kelly Criterion: {str(e)}")


def _setup_series_with_source(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    # Only explicit setup/tag fields are considered setup labels.
    # Do not use trade direction/type as setup taxonomy.
    candidates = ["Setup", "setup", "Tag", "tag", "Strategy", "Pattern", "Playbook"]
    labels = pd.Series([pd.NA] * len(df), index=df.index, dtype="object")
    sources = pd.Series([pd.NA] * len(df), index=df.index, dtype="object")
    for col in candidates:
        if col not in df.columns:
            continue
        raw = df[col].astype(str).str.strip()
        cleaned = raw.where(raw != "", pd.NA)
        missing = labels.isna() & cleaned.notna()
        labels = labels.fillna(cleaned)
        sources.loc[missing] = col
    return labels.fillna("Unlabeled").astype(str), sources.fillna("Unlabeled").astype(str)


def _setup_series(df: pd.DataFrame) -> pd.Series:
    labels, _ = _setup_series_with_source(df)
    return labels


def _split_setup_labels(value: object) -> list[str]:
    raw = str(value or "").strip()
    if not raw or raw.lower() == "unlabeled":
        return ["Unlabeled"]
    parts = [p.strip() for p in re.split(r"[|,;/]+", raw) if p and p.strip()]
    deduped: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k in seen:
            continue
        seen.add(k)
        deduped.append(p)
    return deduped or ["Unlabeled"]


def _setup_label_quality(df: pd.DataFrame) -> dict[str, object]:
    if df.empty:
        return {"TotalTrades": 0, "LabeledTrades": 0, "UnlabeledTrades": 0, "LabeledPct": 0.0, "PrimarySource": "none"}
    labels, sources = _setup_series_with_source(df)
    total = int(len(labels))
    unlabeled = int((labels == "Unlabeled").sum())
    labeled = total - unlabeled
    source_counts = sources.value_counts().to_dict()
    ranked_sources = sorted(
        ((str(k), int(v)) for k, v in source_counts.items() if str(k) != "Unlabeled"),
        key=lambda x: x[1],
        reverse=True,
    )
    primary_source = ranked_sources[0][0] if ranked_sources else "none"
    return {
        "TotalTrades": total,
        "LabeledTrades": labeled,
        "UnlabeledTrades": unlabeled,
        "LabeledPct": round((labeled / total * 100.0) if total > 0 else 0.0, 2),
        "PrimarySource": primary_source,
        "SourceCounts": {k: v for k, v in ranked_sources},
    }


def setup_journal(performance_df, min_trades=3):
    df = validate_performance_df(performance_df).copy()
    if df.empty:
        return pd.DataFrame(columns=["Setup", "Trades", "WinRate", "NetPnL", "AvgPnL", "Expectancy"])
    setup_labels = _setup_series(df)
    df["SetupTag"] = setup_labels.apply(_split_setup_labels)
    df = df.explode("SetupTag").rename(columns={"SetupTag": "SetupLabel"})
    df["SetupLabel"] = df["SetupLabel"].fillna("Unlabeled").astype(str).str.strip().replace("", "Unlabeled")
    grouped = (
        df.groupby("SetupLabel", observed=True)
        .agg(
            Trades=("PnL(Net)", "size"),
            Wins=("PnL(Net)", lambda x: int((x > 0).sum())),
            NetPnL=("PnL(Net)", "sum"),
            AvgPnL=("PnL(Net)", "mean"),
        )
        .reset_index()
        .rename(columns={"SetupLabel": "Setup"})
    )
    grouped["WinRate"] = (grouped["Wins"] / grouped["Trades"] * 100).round(2)
    grouped["Expectancy"] = grouped["AvgPnL"].round(2)
    grouped["NetPnL"] = grouped["NetPnL"].round(2)
    grouped["AvgPnL"] = grouped["AvgPnL"].round(2)
    grouped = grouped[grouped["Trades"] >= int(min_trades)].sort_values(["Expectancy", "NetPnL"], ascending=False)
    return grouped[["Setup", "Trades", "WinRate", "NetPnL", "AvgPnL", "Expectancy"]]


def rule_compliance_score(
    performance_df,
    max_trades_per_day=None,
    max_consecutive_losses=None,
    max_daily_loss=None,
    big_loss_threshold=None,
    max_trades_after_big_loss=None,
):
    max_trades_per_day = int(
        _rule_defaults()["max_trades_per_day"]
        if max_trades_per_day is None
        else max_trades_per_day
    )
    max_consecutive_losses = int(
        _rule_defaults()["max_consecutive_losses"]
        if max_consecutive_losses is None
        else max_consecutive_losses
    )
    max_daily_loss = float(
        _rule_defaults()["max_daily_loss"] if max_daily_loss is None else max_daily_loss
    )
    big_loss_threshold = float(
        _rule_defaults()["big_loss_threshold"]
        if big_loss_threshold is None
        else big_loss_threshold
    )
    max_trades_after_big_loss = int(
        _rule_defaults()["max_trades_after_big_loss"]
        if max_trades_after_big_loss is None
        else max_trades_after_big_loss
    )

    df = validate_performance_df(performance_df).copy()
    if df.empty:
        return {
            "summary": {"OverallScore": 100, "RuleBreaches": 0, "DaysAnalyzed": 0},
            "daily": pd.DataFrame(columns=["TradeDay", "Trades", "DailyPnL", "BreachCount", "Score", "Breaches"]),
        }
    df["ExitedAt"] = _to_cme(df["ExitedAt"], "ExitedAt")
    df["TradeDay"] = df["ExitedAt"].dt.strftime("%Y-%m-%d")
    df = df.sort_values("ExitedAt")
    rows = []
    for day, g in df.groupby("TradeDay", observed=True):
        trades = int(len(g))
        daily_pnl = float(g["PnL(Net)"].sum())
        pnl_sign = (g["PnL(Net)"] < 0).astype(int).tolist()
        consec = 0
        max_consec = 0
        for v in pnl_sign:
            consec = consec + 1 if v == 1 else 0
            max_consec = max(max_consec, consec)
        breaches = []
        if trades > int(max_trades_per_day):
            breaches.append(f"trades>{int(max_trades_per_day)}")
        if max_consec > int(max_consecutive_losses):
            breaches.append(f"consecutive_losses>{int(max_consecutive_losses)}")
        if daily_pnl < -abs(float(max_daily_loss)):
            breaches.append(f"daily_loss>{abs(float(max_daily_loss)):.0f}")

        post_loss_breach = False
        pnl_values = g["PnL(Net)"].tolist()
        for idx, pnl in enumerate(pnl_values):
            if pnl <= -abs(float(big_loss_threshold)):
                remaining = len(pnl_values) - idx - 1
                if remaining > int(max_trades_after_big_loss):
                    post_loss_breach = True
                    break
        if post_loss_breach:
            breaches.append(f"trades_after_big_loss>{int(max_trades_after_big_loss)}")

        rule_count = 4
        score = round(max(0, 100 - (len(breaches) / rule_count * 100)), 2)
        rows.append(
            {
                "TradeDay": day,
                "Trades": trades,
                "DailyPnL": round(daily_pnl, 2),
                "BreachCount": len(breaches),
                "Score": score,
                "Breaches": ", ".join(breaches) if breaches else "none",
            }
        )
    daily = pd.DataFrame(rows).sort_values("TradeDay")
    summary = {
        "OverallScore": round(float(daily["Score"].mean()), 2) if not daily.empty else 100,
        "RuleBreaches": int(daily["BreachCount"].sum()) if not daily.empty else 0,
        "DaysAnalyzed": int(len(daily)),
    }
    return {"summary": summary, "daily": daily}


def execution_quality_layer(performance_df, min_trades=3):
    df = validate_performance_df(performance_df).copy()
    if df.empty:
        return {"by_entry_hour": [], "by_hold_bucket": []}

    df = df.copy()
    df["EnteredAt"] = _to_cme(df["EnteredAt"], "EnteredAt")
    df["ExitedAt"] = _to_cme(df["ExitedAt"], "ExitedAt")
    df["DurationMin"] = (df["ExitedAt"] - df["EnteredAt"]).dt.total_seconds().div(60).clip(lower=0)
    df["EntryHour"] = df["EnteredAt"].dt.hour
    df["HoldBucket"] = pd.cut(
        df["DurationMin"],
        bins=[-0.0001, 2, 5, 15, 30, 60, 10_000],
        labels=["0-2m", "2-5m", "5-15m", "15-30m", "30-60m", "60m+"],
        ordered=True,
    )

    agg = {
        "Trades": ("PnL(Net)", "size"),
        "WinRate": ("PnL(Net)", lambda x: float((x > 0).mean() * 100)),
        "AvgPnL": ("PnL(Net)", "mean"),
    }
    by_entry = df.groupby("EntryHour", observed=True).agg(**agg).reset_index()
    by_hold = df.groupby("HoldBucket", observed=True).agg(**agg).reset_index()

    by_entry = by_entry[by_entry["Trades"] >= int(min_trades)].copy()
    by_hold = by_hold[by_hold["Trades"] >= int(min_trades)].copy()
    for target in (by_entry, by_hold):
        if target.empty:
            continue
        target["WinRate"] = target["WinRate"].round(2)
        target["AvgPnL"] = target["AvgPnL"].round(2)

    return {"by_entry_hour": by_entry.to_dict("records"), "by_hold_bucket": by_hold.to_dict("records")}


def _collect_breach_counts(daily_df: pd.DataFrame) -> dict[str, int]:
    counts: dict[str, int] = {}
    if daily_df.empty or "Breaches" not in daily_df.columns:
        return counts
    for raw in daily_df["Breaches"].astype(str):
        if not raw or raw == "none":
            continue
        for token in raw.split(","):
            key = token.strip()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + 1
    return counts


def _top_action_items(
    *,
    breach_counts: dict[str, int],
    rules: dict[str, float],
    worst_entry=None,
    worst_hold=None,
    best_setup=None,
    weak_setup=None,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    if any(k.startswith("consecutive_losses>") for k in breach_counts):
        items.append(
            {
                "Priority": "High",
                "Why": f"Consecutive-loss breaches observed {sum(v for k, v in breach_counts.items() if k.startswith('consecutive_losses>'))} day(s).",
                "Action": f"Hard stop after {int(rules['max_consecutive_losses'])} consecutive losses; no re-entry that day.",
            }
        )
    if any(k.startswith("trades_after_big_loss>") for k in breach_counts):
        items.append(
            {
                "Priority": "High",
                "Why": f"Post-big-loss overtrading observed {sum(v for k, v in breach_counts.items() if k.startswith('trades_after_big_loss>'))} day(s).",
                "Action": (
                    f"After loss <= -{abs(float(rules['big_loss_threshold'])):.0f}, allow max "
                    f"{int(rules['max_trades_after_big_loss'])} additional trade(s)."
                ),
            }
        )
    if any(k.startswith("daily_loss>") for k in breach_counts):
        items.append(
            {
                "Priority": "High",
                "Why": f"Daily loss cap breached {sum(v for k, v in breach_counts.items() if k.startswith('daily_loss>'))} day(s).",
                "Action": f"Stop trading when intraday realized PnL reaches -{abs(float(rules['max_daily_loss'])):.0f}.",
            }
        )
    if any(k.startswith("trades>") for k in breach_counts):
        items.append(
            {
                "Priority": "Medium",
                "Why": f"Trade-count limit breached {sum(v for k, v in breach_counts.items() if k.startswith('trades>'))} day(s).",
                "Action": f"Set hard cap at {int(rules['max_trades_per_day'])} trades/day.",
            }
        )
    if worst_entry:
        items.append(
            {
                "Priority": "Medium",
                "Why": f"Entry hour {worst_entry.get('EntryHour')} has weakest AvgPnL ({worst_entry.get('AvgPnL')}).",
                "Action": f"Trade half-size or skip hour {worst_entry.get('EntryHour')} until 10-trade recheck.",
            }
        )
    if worst_hold:
        items.append(
            {
                "Priority": "Medium",
                "Why": f"Hold bucket {worst_hold.get('HoldBucket')} has weakest AvgPnL ({worst_hold.get('AvgPnL')}).",
                "Action": f"Reduce exposure in {worst_hold.get('HoldBucket')} holds; tighten invalidation.",
            }
        )
    if best_setup:
        items.append(
            {
                "Priority": "Medium",
                "Why": f"{best_setup.get('Setup')} leads expectancy ({best_setup.get('Expectancy')}).",
                "Action": f"Reserve first A-grade opportunity for {best_setup.get('Setup')} setup only.",
            }
        )
    if weak_setup:
        items.append(
            {
                "Priority": "Medium",
                "Why": f"{weak_setup.get('Setup')} trails expectancy ({weak_setup.get('Expectancy')}).",
                "Action": f"Pause {weak_setup.get('Setup')} for next 20 trades unless criteria is revised.",
            }
        )
    if not items:
        items.append(
            {
                "Priority": "Low",
                "Why": "No major pattern concentration detected.",
                "Action": "Keep current rules unchanged and re-evaluate after 20 additional trades.",
            }
        )
    return items[:8]


def playbook_builder(
    performance_df,
    *,
    compliance_daily=None,
    execution_quality=None,
    rules=None,
    min_trades=5,
):
    journal = setup_journal(performance_df, min_trades=min_trades)
    rules = rules or _rule_defaults()
    execution_quality = execution_quality or {"by_entry_hour": [], "by_hold_bucket": []}
    compliance_daily = compliance_daily if isinstance(compliance_daily, pd.DataFrame) else pd.DataFrame(compliance_daily or [])
    if journal.empty:
        return {
            "highlights": [],
            "stop_doing": [],
            "action_items": [
                {
                    "Priority": "Medium",
                    "Why": "Too few labeled setup records for robust setup-level guidance.",
                    "Action": "Label each trade with setup/context, then re-run insights after 20+ tagged trades.",
                }
            ],
            "rationale": {
                "breach_counts": {},
                "worst_entry_hour": None,
                "worst_hold_bucket": None,
                "best_setup": None,
                "weak_setup": None,
            },
        }

    winners = journal[journal["Expectancy"] > 0].head(3)
    losers = journal[journal["Expectancy"] < 0].sort_values("Expectancy").head(3)

    highlights = [
        {
            "Setup": row["Setup"],
            "Trades": int(row["Trades"]),
            "WinRate": float(row["WinRate"]),
            "Expectancy": float(row["Expectancy"]),
            "Action": "Scale this setup gradually and keep execution consistent.",
        }
        for _, row in winners.iterrows()
    ]
    stop_doing = [
        {
            "Setup": row["Setup"],
            "Trades": int(row["Trades"]),
            "WinRate": float(row["WinRate"]),
            "Expectancy": float(row["Expectancy"]),
            "Action": "Pause this setup until expectancy improves over next review window.",
        }
        for _, row in losers.iterrows()
    ]

    entry_rows = execution_quality.get("by_entry_hour", []) or []
    hold_rows = execution_quality.get("by_hold_bucket", []) or []
    worst_entry = min(entry_rows, key=lambda r: float(r.get("AvgPnL", 0))) if entry_rows else None
    worst_hold = min(hold_rows, key=lambda r: float(r.get("AvgPnL", 0))) if hold_rows else None
    best_setup = highlights[0] if highlights else None
    weak_setup = stop_doing[0] if stop_doing else None
    breach_counts = _collect_breach_counts(compliance_daily)

    action_items = _top_action_items(
        breach_counts=breach_counts,
        rules={
            "max_trades_per_day": int(rules.get("max_trades_per_day", 8)),
            "max_consecutive_losses": int(rules.get("max_consecutive_losses", 3)),
            "max_daily_loss": float(rules.get("max_daily_loss", 500)),
            "big_loss_threshold": float(rules.get("big_loss_threshold", 200)),
            "max_trades_after_big_loss": int(rules.get("max_trades_after_big_loss", 2)),
        },
        worst_entry=worst_entry,
        worst_hold=worst_hold,
        best_setup=best_setup,
        weak_setup=weak_setup,
    )

    return {
        "highlights": highlights,
        "stop_doing": stop_doing,
        "action_items": action_items,
        "rationale": {
            "breach_counts": breach_counts,
            "worst_entry_hour": worst_entry,
            "worst_hold_bucket": worst_hold,
            "best_setup": best_setup,
            "weak_setup": weak_setup,
        },
    }


def monthly_review_report(performance_df, month=None, min_trades=3, applied_config=None, analysis_scope=None):
    df = validate_performance_df(performance_df).copy()
    if df.empty:
        return {"summary": {}, "focus_points": []}

    df["ExitedAt"] = _to_cme(df["ExitedAt"], "ExitedAt")
    df["Month"] = df["ExitedAt"].dt.tz_localize(None).dt.to_period("M").astype(str)
    target_month = month or df["Month"].max()
    mdf = df[df["Month"] == target_month].copy()
    if mdf.empty:
        return {"summary": {"Month": target_month, "Trades": 0}, "focus_points": []}

    mdf["TradeDay"] = mdf["ExitedAt"].dt.strftime("%Y-%m-%d")
    daily = mdf.groupby("TradeDay", observed=True)["PnL(Net)"].sum().reset_index()
    daily["Equity"] = daily["PnL(Net)"].cumsum()
    daily["Peak"] = daily["Equity"].cummax()
    daily["Drawdown"] = daily["Equity"] - daily["Peak"]

    wins = mdf[mdf["PnL(Net)"] > 0]["PnL(Net)"]
    losses = mdf[mdf["PnL(Net)"] < 0]["PnL(Net)"]

    setup_summary = setup_journal(mdf, min_trades=min_trades)
    top_setup = setup_summary.iloc[0]["Setup"] if not setup_summary.empty else "n/a"
    worst_setup = setup_summary.sort_values("Expectancy").iloc[0]["Setup"] if not setup_summary.empty else "n/a"

    summary = {
        "Month": target_month,
        "Trades": int(len(mdf)),
        "NetPnL": round(float(mdf["PnL(Net)"].sum()), 2),
        "WinRate": round(float((mdf["PnL(Net)"] > 0).mean() * 100), 2),
        "AvgWin": round(float(wins.mean() if not wins.empty else 0), 2),
        "AvgLoss": round(float(losses.mean() if not losses.empty else 0), 2),
        "MaxDrawdown": round(float(daily["Drawdown"].min() if not daily.empty else 0), 2),
        "TopSetup": str(top_setup),
        "WorstSetup": str(worst_setup),
    }

    focus_points = [
        f"Top setup: {summary['TopSetup']}. Keep size discipline and preserve entry criteria.",
        f"Worst setup: {summary['WorstSetup']}. Reduce frequency until positive expectancy returns.",
        f"Max drawdown this month: {summary['MaxDrawdown']:.2f}. Enforce daily stop rules.",
    ]
    setup_lines = []
    for rec in setup_summary.head(5).to_dict("records"):
        setup_lines.append(
            f"- {rec['Setup']}: trades={int(rec['Trades'])}, win_rate={float(rec['WinRate']):.2f}%, expectancy={float(rec['Expectancy']):.2f}"
        )
    markdown = (
        f"# Monthly Review ({summary['Month']})\n\n"
        f"## Applied Config\n{applied_config if applied_config is not None else {}}\n\n"
        f"## Analysis Scope\n{analysis_scope if analysis_scope is not None else {}}\n\n"
        f"- Trades: {summary['Trades']}\n"
        f"- Net PnL: {summary['NetPnL']}\n"
        f"- Win Rate: {summary['WinRate']}%\n"
        f"- Avg Win / Avg Loss: {summary['AvgWin']} / {summary['AvgLoss']}\n"
        f"- Max Drawdown: {summary['MaxDrawdown']}\n"
        f"- Top Setup: {summary['TopSetup']}\n"
        f"- Worst Setup: {summary['WorstSetup']}\n\n"
        "## Focus Points\n"
        + "\n".join([f"- {p}" for p in focus_points])
        + "\n\n## Setup Summary\n"
        + ("\n".join(setup_lines) if setup_lines else "- Not enough setup-tagged trades.")
    )

    return {
        "summary": summary,
        "focus_points": focus_points,
        "markdown": markdown,
        "applied_config": applied_config if applied_config is not None else {},
        "analysis_scope": analysis_scope if analysis_scope is not None else {},
    }


def day_plan_review(performance_df, month=None):
    df = validate_performance_df(performance_df).copy()
    if df.empty:
        return {"summary": {}, "daily": []}

    df["ExitedAt"] = _to_cme(df["ExitedAt"], "ExitedAt")
    df["TradeDay"] = df["ExitedAt"].dt.strftime("%Y-%m-%d")
    if month:
        period = df["ExitedAt"].dt.tz_localize(None).dt.to_period("M").astype(str)
        df = df[period == str(month)].copy()
    daily = (
        df.groupby("TradeDay", observed=True)
        .agg(
            DayPnL=("PnL(Net)", "sum"),
            Trades=("PnL(Net)", "size"),
            WinRate=("PnL(Net)", lambda s: float((s > 0).mean() * 100) if len(s) else 0.0),
        )
        .reset_index()
        .rename(columns={"TradeDay": "Date"})
    )

    plan = load_day_plan()
    if month and not plan.empty:
        p = pd.to_datetime(plan["Date"], errors="coerce").dt.to_period("M").astype(str)
        plan = plan[p == str(month)].copy()
    plan_cols = ["Date", "Bias", "ExpectedDayType", "ActualDayType", "KeyLevelsHTFContext", "PrimaryPlan", "AvoidancePlan"]
    for col in plan_cols:
        if col not in plan.columns:
            plan[col] = ""
    plan = plan[plan_cols].copy()

    merged = daily.merge(plan, on="Date", how="outer")
    merged["DayPnL"] = pd.to_numeric(merged.get("DayPnL"), errors="coerce").fillna(0.0)
    merged["Trades"] = pd.to_numeric(merged.get("Trades"), errors="coerce").fillna(0).astype(int)
    merged["WinRate"] = pd.to_numeric(merged.get("WinRate"), errors="coerce").fillna(0.0)
    for col in ["Bias", "ExpectedDayType", "ActualDayType", "KeyLevelsHTFContext", "PrimaryPlan", "AvoidancePlan"]:
        merged[col] = merged[col].fillna("").astype(str).str.strip()
    merged["HasPlan"] = (
        (merged["Bias"] != "")
        | (merged["ExpectedDayType"] != "")
        | (merged["ActualDayType"] != "")
        | (merged["PrimaryPlan"] != "")
        | (merged["AvoidancePlan"] != "")
        | (merged["KeyLevelsHTFContext"] != "")
    )
    merged["HasTrades"] = merged["Trades"] > 0
    merged["BiasAligned"] = "n/a"
    bullish = (merged["Bias"].str.lower() == "bullish") & merged["HasTrades"]
    bearish = (merged["Bias"].str.lower() == "bearish") & merged["HasTrades"]
    merged.loc[bullish, "BiasAligned"] = np.where(merged.loc[bullish, "DayPnL"] > 0, "yes", "no")
    merged.loc[bearish, "BiasAligned"] = np.where(merged.loc[bearish, "DayPnL"] < 0, "yes", "no")
    merged["DayTypeMatched"] = np.where(
        (merged["ExpectedDayType"] != "") & (merged["ActualDayType"] != ""),
        np.where(
            merged["ExpectedDayType"].str.strip().str.lower() == merged["ActualDayType"].str.strip().str.lower(),
            "yes",
            "no",
        ),
        "n/a",
    )
    merged = merged.sort_values("Date", kind="stable")

    plan_days = merged[merged["HasPlan"]]
    plan_trade_days = plan_days[plan_days["HasTrades"]]
    unplanned_trade_days = merged[(~merged["HasPlan"]) & (merged["HasTrades"])]
    planned_no_trade = merged[(merged["HasPlan"]) & (~merged["HasTrades"])]
    match_mask = (plan_days["ExpectedDayType"] != "") & (plan_days["ActualDayType"] != "")
    bias_mask = plan_trade_days["BiasAligned"].isin(["yes", "no"])
    expected_group = plan_trade_days[plan_trade_days["ExpectedDayType"] != ""].groupby("ExpectedDayType", observed=True)["DayPnL"].mean()
    best_expected = expected_group.idxmax() if not expected_group.empty else "n/a"
    worst_expected = expected_group.idxmin() if not expected_group.empty else "n/a"
    expected_match_rate = float((plan_days.loc[match_mask, "DayTypeMatched"] == "yes").mean() * 100) if match_mask.any() else 0.0
    bias_alignment_rate = float((plan_trade_days.loc[bias_mask, "BiasAligned"] == "yes").mean() * 100) if bias_mask.any() else 0.0

    summary = {
        "DaysWithPlan": int(len(plan_days)),
        "PlanDaysWithTrades": int(len(plan_trade_days)),
        "UnplannedTradeDays": int(len(unplanned_trade_days)),
        "PlannedNoTradeDays": int(len(planned_no_trade)),
        "ExpectedVsActualMatchRatePct": round(expected_match_rate, 2),
        "BiasAlignmentRatePct": round(bias_alignment_rate, 2),
        "NetPnLPlannedDays": round(float(plan_trade_days["DayPnL"].sum()) if not plan_trade_days.empty else 0.0, 2),
        "NetPnLUnplannedDays": round(float(unplanned_trade_days["DayPnL"].sum()) if not unplanned_trade_days.empty else 0.0, 2),
        "AvgPlannedDayPnL": round(float(plan_trade_days["DayPnL"].mean()) if not plan_trade_days.empty else 0.0, 2),
        "BestExpectedDayType": str(best_expected),
        "WorstExpectedDayType": str(worst_expected),
    }
    cols = [
        "Date",
        "HasPlan",
        "HasTrades",
        "Bias",
        "ExpectedDayType",
        "ActualDayType",
        "DayPnL",
        "Trades",
        "WinRate",
        "BiasAligned",
        "DayTypeMatched",
        "KeyLevelsHTFContext",
        "PrimaryPlan",
        "AvoidancePlan",
    ]
    return {"summary": summary, "daily": merged[cols].to_dict("records")}


def _filter_by_month(performance_df, month=None):
    df = validate_performance_df(performance_df).copy()
    if df.empty or not month:
        return df
    period = _to_cme(df["ExitedAt"], "ExitedAt").dt.tz_localize(None).dt.to_period("M").astype(str)
    return df[period == str(month)].copy()


def _filter_by_tags(performance_df, params=None):
    params = params or {}
    df = validate_performance_df(performance_df).copy()
    if df.empty:
        return df

    def _selection_set(value):
        vals: list[str] = []
        if isinstance(value, list):
            vals = [str(v).strip() for v in value if str(v).strip()]
        elif isinstance(value, str):
            vals = [p.strip() for p in re.split(r"[|,;/]+", value) if p.strip()]
        elif value is not None:
            raw = str(value).strip()
            if raw:
                vals = [raw]
        return {v.lower() for v in vals}

    phase_sel = _selection_set(params.get("phase"))
    context_sel = _selection_set(params.get("context"))
    setup_sel = _selection_set(params.get("setup"))
    signal_sel = _selection_set(params.get("signal_bar"))
    intent_sel = _selection_set(params.get("trade_intent"))

    if phase_sel and "Phase" in df.columns:
        df = df[df["Phase"].fillna("").astype(str).str.strip().str.lower().isin(phase_sel)].copy()
        if df.empty:
            return df
    if context_sel and "Context" in df.columns:
        df = df[df["Context"].fillna("").astype(str).str.strip().str.lower().isin(context_sel)].copy()
        if df.empty:
            return df
    if signal_sel and "SignalBar" in df.columns:
        df = df[df["SignalBar"].fillna("").astype(str).str.strip().str.lower().isin(signal_sel)].copy()
        if df.empty:
            return df
    if setup_sel and "Setup" in df.columns:
        parts = df["Setup"].fillna("").astype(str).apply(_split_setup_labels)
        mask = parts.apply(lambda vals: any(str(v).strip().lower() in setup_sel for v in vals))
        df = df[mask].copy()
        if df.empty:
            return df
    if intent_sel and "TradeIntent" in df.columns:
        df = df[df["TradeIntent"].fillna("").astype(str).str.strip().str.lower().isin(intent_sel)].copy()
    return df


def _normalized_selection(params, key: str) -> list[str]:
    raw = (params or {}).get(key)
    if raw is None:
        return []
    if isinstance(raw, list):
        vals = [str(v).strip() for v in raw if str(v).strip()]
    elif isinstance(raw, str):
        vals = [p.strip() for p in re.split(r"[|,;/]+", raw) if p.strip()]
    else:
        v = str(raw).strip()
        vals = [v] if v else []
    out: list[str] = []
    seen: set[str] = set()
    for v in vals:
        k = v.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(v)
    return out


def _build_applied_config(params, defaults):
    params = params or {}
    defaults = defaults or {}
    return {
        "min_trades": int(params.get("min_trades", 3)),
        "month": str(params.get("month", "") or ""),
        "filters": {
            "phase": _normalized_selection(params, "phase"),
            "context": _normalized_selection(params, "context"),
            "setup": _normalized_selection(params, "setup"),
            "signal_bar": _normalized_selection(params, "signal_bar"),
            "trade_intent": _normalized_selection(params, "trade_intent"),
        },
        "rule_thresholds": {
            "max_trades_per_day": int(params.get("max_trades_per_day", defaults.get("max_trades_per_day", 8))),
            "max_consecutive_losses": int(params.get("max_consecutive_losses", defaults.get("max_consecutive_losses", 3))),
            "max_daily_loss": float(params.get("max_daily_loss", defaults.get("max_daily_loss", 500))),
            "big_loss_threshold": float(params.get("big_loss_threshold", defaults.get("big_loss_threshold", 200))),
            "max_trades_after_big_loss": int(
                params.get("max_trades_after_big_loss", defaults.get("max_trades_after_big_loss", 2))
            ),
        },
    }


def insights_bundle(performance_df, params=None):
    params = params or {}
    rules = _rule_defaults()
    applied_config = _build_applied_config(params, rules)
    min_trades = int(applied_config["min_trades"])

    base_df = validate_performance_df(performance_df).copy()
    month_df = _filter_by_month(base_df, month=applied_config.get("month"))
    scoped_df = _filter_by_tags(month_df, params=applied_config.get("filters"))
    analysis_scope = {
        "total_trades_input": int(len(base_df)),
        "after_month_filter": int(len(month_df)),
        "after_tag_filters": int(len(scoped_df)),
    }

    setup = setup_journal(scoped_df, min_trades=min_trades)
    setup_quality = _setup_label_quality(scoped_df)
    compliance = rule_compliance_score(
        scoped_df,
        max_trades_per_day=int(applied_config["rule_thresholds"]["max_trades_per_day"]),
        max_consecutive_losses=int(applied_config["rule_thresholds"]["max_consecutive_losses"]),
        max_daily_loss=float(applied_config["rule_thresholds"]["max_daily_loss"]),
        big_loss_threshold=float(applied_config["rule_thresholds"]["big_loss_threshold"]),
        max_trades_after_big_loss=int(applied_config["rule_thresholds"]["max_trades_after_big_loss"]),
    )
    execution_quality = execution_quality_layer(scoped_df, min_trades=min_trades)
    playbook = playbook_builder(
        scoped_df,
        compliance_daily=compliance["daily"],
        execution_quality=execution_quality,
        rules=applied_config["rule_thresholds"],
        min_trades=max(min_trades, 5),
    )
    monthly = monthly_review_report(
        scoped_df,
        month=applied_config.get("month"),
        min_trades=min_trades,
        applied_config=applied_config,
        analysis_scope=analysis_scope,
    )
    plan_review = day_plan_review(scoped_df, month=applied_config.get("month"))
    llm_prompt_markdown = _build_llm_prompt_markdown(
        setup=setup,
        setup_quality=setup_quality,
        compliance=compliance,
        execution_quality=execution_quality,
        playbook=playbook,
        monthly=monthly,
        day_plan=plan_review,
        applied_config=applied_config,
        analysis_scope=analysis_scope,
    )
    return {
        "applied_config": applied_config,
        "analysis_scope": analysis_scope,
        "setup_journal": setup.to_dict("records"),
        "setup_quality": setup_quality,
        "rule_compliance": {
            "summary": compliance["summary"],
            "daily": compliance["daily"].to_dict("records"),
        },
        "execution_quality": execution_quality,
        "playbook": playbook,
        "day_plan_review": plan_review,
        "monthly_report": monthly,
        "llm_prompt_markdown": llm_prompt_markdown,
    }


def _build_llm_prompt_markdown(setup, setup_quality, compliance, execution_quality, playbook, monthly, day_plan, applied_config, analysis_scope):
    setup_rows = setup.head(10).to_dict("records") if hasattr(setup, "head") else []
    compliance_daily = compliance.get("daily")
    if hasattr(compliance_daily, "tail"):
        compliance_rows = compliance_daily.tail(15).to_dict("records")
    else:
        compliance_rows = []
    quality_entry_rows = execution_quality.get("by_entry_hour", [])[:10]
    quality_hold_rows = execution_quality.get("by_hold_bucket", [])[:10]
    playbook_actions = playbook.get("action_items", [])[:8]
    monthly_summary = monthly.get("summary", {})
    monthly_focus = monthly.get("focus_points", [])
    day_plan_summary = (day_plan or {}).get("summary", {})
    day_plan_rows = (day_plan or {}).get("daily", [])[:15]

    def _rows_to_md(rows):
        if not rows:
            return "- none"
        lines = []
        for row in rows:
            items = [f"{k}={row[k]}" for k in row.keys()]
            lines.append(f"- {', '.join(items)}")
        return "\n".join(lines)

    return (
        "# Trading Behavior Analysis Prompt Pack\n\n"
        "You are a performance coach for intraday futures trading. Use the structured data below and avoid generic advice.\n\n"
        "## Requested Output From LLM\n"
        "- 1) Root-cause diagnosis of losses, with evidence from the tables\n"
        "- 2) Rule changes with concrete numeric thresholds (not vague language)\n"
        "- 3) RTH-first execution plan and ETH policy recommendation\n"
        "- 4) Next 5 trading-day checklist with measurable pass/fail criteria\n"
        "- 5) Position-sizing and stop logic changes after consecutive losses\n\n"
        "## Constraints\n"
        "- Prioritize preserving downside and reducing behavioral mistakes.\n"
        "- Do not propose increasing risk before breach frequency improves.\n"
        "- Separate strategy edge issues from execution discipline issues.\n\n"
        f"## Applied Config\n```json\n{applied_config}\n```\n\n"
        f"## Analysis Scope\n```json\n{analysis_scope}\n```\n\n"
        "## Setup Label Quality\n```json\n"
        + f"{setup_quality}\n```\n"
        + "\n\n"
        "## Setup Journal (Top Rows)\n"
        + _rows_to_md(setup_rows)
        + "\n\n## Rule Compliance Summary\n```json\n"
        + f"{compliance.get('summary', {})}\n```\n"
        + "\n\n## Rule Compliance Daily (Recent)\n"
        + _rows_to_md(compliance_rows)
        + "\n\n## Execution Quality By Entry Hour\n"
        + _rows_to_md(quality_entry_rows)
        + "\n\n## Execution Quality By Hold Bucket\n"
        + _rows_to_md(quality_hold_rows)
        + "\n\n## Playbook Actions\n"
        + _rows_to_md(playbook_actions)
        + "\n\n## Day Plan Review Summary\n```json\n"
        + f"{day_plan_summary}\n```\n"
        + "\n\n## Day Plan Review Daily\n"
        + _rows_to_md(day_plan_rows)
        + "\n\n## Monthly Summary\n```json\n"
        + f"{monthly_summary}\n```\n"
        + "\n\n## Monthly Focus Points\n"
        + ("\n".join([f"- {line}" for line in monthly_focus]) if monthly_focus else "- none")
        + "\n"
    )
