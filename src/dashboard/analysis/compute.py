import pandas as pd
from dashboard.config.settings import DEFAULT_GRANULARITY

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