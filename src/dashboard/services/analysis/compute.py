import pandas as pd
from dashboard.config.settings import DEFAULT_GRANULARITY, DEFAULT_ROLLING_WINDOW
import numpy as np
from dashboard.services.analysis.schema import validate_performance_df

def pnl_growth(performance_df, granularity=DEFAULT_GRANULARITY, daily_compounding_rate=0.001902, initial_funding=10000):
    performance_df = validate_performance_df(performance_df)
    # Initialize empty result if performance_df is empty
    if performance_df.empty:
        return pd.DataFrame(columns=['Period', 'NetPnL', 'CumulativePnL', 'PassiveGrowth', 'CumulativePassive'])
    
    performance_df = performance_df.copy()
    # Convert ExitedAt to datetime and remove timezone
    performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'], errors='coerce').dt.tz_localize(None)
    
    # Check for invalid ExitedAt values
    if performance_df['ExitedAt'].isna().any():
        raise ValueError("Invalid datetime values in 'ExitedAt' column")
    
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
        
        # Create daily date range (all calendar days)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
        passive_df = pd.DataFrame({'Date': date_range})
        passive_df['Days'] = (passive_df['Date'] - start_date).dt.days + 1  # Include start date
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
        
        # Fill NaN for periods with no trades
        grouped = grouped.fillna({'NetPnL': 0, 'PassiveGrowth': 0, 'CumulativePassive': 0})
        grouped['CumulativePnL'] = grouped['NetPnL'].cumsum()
        
        return grouped[['Period', 'NetPnL', 'CumulativePnL', 'PassiveGrowth', 'CumulativePassive']]
    
    except Exception as e:
        raise ValueError(f"Failed to group by {granularity}: {str(e)}")
    

def drawdown(performance_df, granularity=DEFAULT_GRANULARITY):
    performance_df = validate_performance_df(performance_df)
    if performance_df.empty:
        return pd.DataFrame(columns=['Period', 'Drawdown'])
    
    performance_df = performance_df.copy()
    # Convert ExitedAt to datetime and remove timezone
    performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'], errors='coerce').dt.tz_localize(None)
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
        grouped['PeakPnL'] = grouped['CumulativePnL'].cummax()
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
        if 'HourOfDay' not in performance_df or 'DayOfWeek' not in performance_df or 'PnL(Net)' not in performance_df or 'Size' not in performance_df:
            raise ValueError("Required columns missing: HourOfDay, DayOfWeek, PnL(Net), Size")
        
        # Use HourOfDay directly and define weekday order
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
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
        
        # Create a full matrix of hours (0-23) and days (Monday to Friday)
        all_hours = np.arange(0, 24)  # Hours 0 to 23
        all_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
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
    performance_df = validate_performance_df(performance_df)
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
    performance_df = validate_performance_df(performance_df)
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
    # Convert TradeDay to datetime and remove timezone
    performance_df['TradeDay'] = pd.to_datetime(performance_df['TradeDay'], errors='coerce').dt.tz_localize(None)
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
    
def overtrading_detection(performance_df, cap_loss_per_trade=200, cap_trades_after_big_loss=5):
    # Initialize empty DataFrames if performance_df is empty
    daily_columns = ['TradeDay', 'TradesPerDay', 'DailyPnL']
    trade_columns = ['TradeIndex', 'R_multiple', 'IsPostLoss', 'TradeDay', 'ExitedAt', 'PnL(Net)', 'Size', 'Duration', 'TradeTag']
    if performance_df.empty:
        return pd.DataFrame(columns=daily_columns), pd.DataFrame(columns=trade_columns)
    
    performance_df = performance_df.copy()
    try:
        # Validate required columns
        required_cols = ['TradeDay', 'PnL(Net)', 'ExitedAt', 'EnteredAt', 'Size']
        if not all(col in performance_df for col in required_cols):
            raise ValueError(f"Required columns missing: {', '.join(set(required_cols) - set(performance_df.columns))}")
        
        # Ensure datetime columns are timezone-naive
        performance_df['TradeDay'] = pd.to_datetime(performance_df['TradeDay']).dt.tz_localize(None)
        performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'], errors='coerce').dt.tz_localize(None)
        performance_df['EnteredAt'] = pd.to_datetime(performance_df['EnteredAt'], errors='coerce').dt.tz_localize(None)
        
        # Check for invalid datetimes
        if performance_df[['ExitedAt', 'EnteredAt']].isna().any().any():
            raise ValueError("Invalid datetime values in 'ExitedAt' or 'EnteredAt' column")
        
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
        
        # Identify large loss trades and post-loss trades
        trade_df['IsLoss'] = trade_df['R_multiple'] <= -1
        trade_df['IsPostLoss'] = False
        for idx in trade_df[trade_df['IsLoss']].index:
            end_idx = min(idx + cap_trades_after_big_loss + 1, len(trade_df))
            trade_df.loc[idx + 1:end_idx - 1, 'IsPostLoss'] = True
        
        # Analyze post-loss trades for overtrading criteria
        trade_df['TradeTag'] = 'LightBlue'  # Default to Blue
        for idx in trade_df[trade_df['IsPostLoss']].index:
            loss_idx = trade_df.index[trade_df.index.get_loc(idx) - 1]
            if loss_idx in trade_df[trade_df['IsLoss']].index:
                # Get the 5 subsequent trades (including current) for this loss
                start_idx = loss_idx + 1
                end_idx = min(loss_idx + cap_trades_after_big_loss + 1, len(trade_df))
                subset = trade_df.iloc[start_idx:end_idx]
                
                # Calculate averages for the 5 subsequent trades
                avg_size = subset['Size'].mean()
                avg_duration = subset['Duration'].mean()
                
                # Current trade criteria
                current_trade = trade_df.loc[idx]
                r_criterion = current_trade['R_multiple'] < 0
                size_criterion = current_trade['Size'] > avg_size
                duration_criterion = current_trade['Duration'] < avg_duration
                
                # Update TradeTag
                if r_criterion and size_criterion and duration_criterion:
                    trade_df.loc[idx, 'TradeTag'] = 'DarkRed'
                elif r_criterion or size_criterion or duration_criterion:
                    trade_df.loc[idx, 'TradeTag'] = 'LightCoral'
        
        # Select relevant columns
        trade_df = trade_df[['TradeIndex', 'R_multiple', 'IsPostLoss', 'TradeDay', 'ExitedAt', 'PnL(Net)', 'Size', 'Duration', 'TradeTag']]
        
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
        if 'TradeDay' not in performance_df or 'PnL(Net)' not in performance_df:
            raise ValueError("Required columns missing: TradeDay, PnL(Net)")
        
        # Ensure TradeDay is in datetime format
        performance_df['TradeDay'] = pd.to_datetime(performance_df['TradeDay']).dt.tz_localize(None)
        
        # Ensure PnL(Net) is numeric, converting non-numeric to NaN
        performance_df['PnL(Net)'] = pd.to_numeric(performance_df['PnL(Net)'], errors='coerce')
        
        # Check for NaN values in PnL(Net)
        if performance_df['PnL(Net)'].isna().any():
            print(f"Warning: {performance_df['PnL(Net)'].isna().sum()} NaN values found in PnL(Net). Dropping these rows.")
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
