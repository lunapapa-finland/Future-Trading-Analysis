# analysis/compute.py
import pandas as pd

def filter_data(df, start_date, end_date):
    if not start_date or not end_date or df.empty:
        print("filter_data: Invalid date range or empty DataFrame")
        return pd.DataFrame()
    try:
        # Convert to timezone-aware datetime (UTC+03:00 to match df['EnteredAt'])
        start = pd.to_datetime(start_date).tz_localize('UTC+03:00')
        end = pd.to_datetime(end_date).tz_localize('UTC+03:00')
        filtered = df[(df['EnteredAt'] >= start) & (df['EnteredAt'] <= end)]
        print(f"filter_data: Filtered {len(filtered)} rows, columns: {filtered.columns.tolist()}")
        return filtered
    except Exception as e:
        print(f"filter_data error: {e}")
        return pd.DataFrame()

def compute_analysis(filtered_data, analysis_type):
    print(f"compute_analysis: Analysis type: {analysis_type}, rows: {len(filtered_data)}, columns: {filtered_data.columns.tolist()}")
    
    if filtered_data.empty:
        print("compute_analysis: Empty filtered_data, returning empty result")
        return [] if analysis_type != 'hourly_pnl' else [{'hour': h, 'avgPnL': 0} for h in range(24)]
    
    required_columns = ['HourOfDay', 'PnL(Net)', 'EnteredAt', 'Streak', 'Type', 'WinOrLoss']
    missing_columns = [col for col in required_columns if col not in filtered_data.columns]
    if missing_columns:
        print(f"compute_analysis: Missing columns: {missing_columns}")
        return [] if analysis_type != 'hourly_pnl' else [{'hour': h, 'avgPnL': 0} for h in range(24)]

    if analysis_type == 'hourly_pnl':
        hourly = pd.DataFrame({'hour': range(24), 'pnL': 0.0, 'count': 0})
        for hour in range(24):
            trades = filtered_data[filtered_data['HourOfDay'] == hour]
            hourly.loc[hour, 'pnL'] = trades['PnL(Net)'].sum()
            hourly.loc[hour, 'count'] = len(trades)
        hourly['avgPnL'] = hourly.apply(lambda x: x['pnL'] / x['count'] if x['count'] > 0 else 0, axis=1)
        return hourly[['hour', 'avgPnL']].to_dict('records')
    
    elif analysis_type == 'cumulative_pnl':
        cumulative = 0
        sorted_data = filtered_data.sort_values('EnteredAt')
        result = [{'date': row['EnteredAt'], 'cumulativePnL': (cumulative := cumulative + row['PnL(Net)'])} 
                  for _, row in sorted_data.iterrows()]
        return result
    
    elif analysis_type == 'streaks':
        return [{'date': row['EnteredAt'], 'streak': row['Streak']} 
                for _, row in filtered_data.iterrows()]
    
    elif analysis_type == 'trade_type':
        types = ['Long', 'Short']
        result = []
        for t in types:
            trades = filtered_data[filtered_data['Type'] == t]
            total_pnl = trades['PnL(Net)'].sum()
            wins = len(trades[trades['WinOrLoss'] == 1])
            result.append({
                'type': t,
                'totalPnL': total_pnl,
                'winRate': wins / len(trades) if len(trades) > 0 else 0
            })
        return result
    
    print(f"compute_analysis: Unknown analysis type: {analysis_type}")
    return []

def get_interesting_fact(filtered_data):
    if filtered_data.empty:
        print("get_interesting_fact: Empty filtered_data")
        return 'No data available'
    max_streak = filtered_data['Streak'].abs().max()
    max_streak_row = filtered_data[filtered_data['Streak'].abs() == max_streak].iloc[0]
    return f"Longest streak: {max_streak} trades on {max_streak_row['EnteredAt'].strftime('%Y-%m-%d')}"