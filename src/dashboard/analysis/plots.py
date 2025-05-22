import pandas as pd
import plotly.graph_objects as go
from dashboard.config.settings import TIMESTEP, TIMEZONE
import pytz
def get_candlestick_plot(ticket, future_df, performance_df, current_trace_index=0):
    future_df['Datetime'] = pd.to_datetime(future_df['Datetime'])

    # Verify RTH data (8:30 AM to 3:10 PM CT, Monday to Friday)
    is_rth = (future_df['Datetime'].dt.time >= pd.Timestamp('08:30:00').time()) & \
             (future_df['Datetime'].dt.time <= pd.Timestamp('15:10:00').time()) & \
             (future_df['Datetime'].dt.weekday < 5)
    if not is_rth.all():
        raise ValueError("future_df contains non-RTH data")

    # Create continuous x_index for gap-free plotting
    future_df['x_index'] = range(1, len(future_df) + 1)

    # Create per-day index (1 to 80) for hover text (6h40m = 80 bars at 5min)
    future_df['date'] = future_df['Datetime'].dt.date
    future_df['day_index'] = future_df.groupby('date').cumcount() + 1  # Resets to 1 per day

    # Enhanced hover text with date, time (CT), and per-day index
    future_df['hover_text'] = future_df['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
    future_df['formatted_hover'] = (
        'Date: ' + future_df['Datetime'].dt.strftime('%Y-%m-%d') + '<br>' +
        'Time: ' + future_df['Datetime'].dt.strftime('%H:%M:%S') + ' CT<br>' +
        'Index: ' + future_df['day_index'].astype(str) + '<br>' +
        'Open: ' + future_df['Open'].astype(str) + '<br>' +
        'High: ' + future_df['High'].astype(str) + '<br>' +
        'Low: ' + future_df['Low'].astype(str) + '<br>' +
        'Close: ' + future_df['Close'].astype(str)
    )

    # Create candlestick chart
    fig = go.Figure(data=[
        go.Candlestick(
            x=future_df['x_index'],
            open=future_df['Open'],
            high=future_df['High'],
            low=future_df['Low'],
            close=future_df['Close'],
            name='OHLC',
            text=future_df['formatted_hover'],
            hoverinfo='text',
            hoverlabel=dict(
                bgcolor='white',
                font_size=12,
                font_family='Arial'
            )
        )
    ])

    # Add trade traces from performance_df
    if not performance_df.empty:
        performance_df['EnteredAt'] = pd.to_datetime(performance_df['EnteredAt'])
        performance_df['ExitedAt'] = pd.to_datetime(performance_df['ExitedAt'])
        performance_df['EnteredAt_5min'] = performance_df['EnteredAt'].dt.floor('5min')
        performance_df['ExitedAt_5min'] = performance_df['ExitedAt'].dt.floor('5min')

        def map_to_x_index(trade_day, day_of_week, time_5min):
            # Assume inputs: trade_day (date), day_of_week (str), time_5min (pd.Timestamp in America/Chicago)
            trade_day = pd.Timestamp(trade_day).date()
            time_5min = pd.Timestamp(time_5min)

            # Map weekend to next Monday
            if day_of_week in ['Saturday', 'Sunday']:
                days_to_add = 2 if day_of_week == 'Saturday' else 1
                trade_day = (pd.Timestamp(trade_day) + pd.Timedelta(days=days_to_add)).date()

            # Check if RTH (8:30 AM to 3:10 PM CT)
            is_rth = (time_5min.time() >= pd.Timestamp('08:30:00').time()) and \
                     (time_5min.time() <= pd.Timestamp('15:10:00').time())

            if is_rth:
                # Map to exact bar for RTH trades
                time_idx = future_df.index[
                    (future_df['date'] == trade_day) &
                    (future_df['Datetime'].dt.floor('5min') == time_5min.floor('5min'))
                ].tolist()
                if time_idx:
                    return future_df.loc[time_idx[0], 'x_index']

            # Non-RTH: Map to first or last bar of trade_day
            rth_start = pd.Timestamp(trade_day).tz_localize(TIMEZONE).replace(hour=8, minute=30)
            rth_end = pd.Timestamp(trade_day).tz_localize(TIMEZONE).replace(hour=15, minute=10)

            if time_5min < rth_start:
                # Before 8:30 AM CT: First bar (8:30 AM CT)
                time_idx = future_df.index[future_df['Datetime'].dt.floor('5min') == rth_start].tolist()
            else:
                # After 3:10 PM CT: Last bar (3:10 PM CT)
                time_idx = future_df.index[future_df['Datetime'].dt.floor('5min') == rth_end].tolist()

            if time_idx:
                return future_df.loc[time_idx[0], 'x_index']

            # Fallback: First x_index
            return future_df['x_index'].iloc[0]

        # Apply mapping using TradeDay, DayOfWeek, and time
        performance_df['x_entry'] = performance_df.apply(
            lambda row: map_to_x_index(row['TradeDay'], row['DayOfWeek'], row['EnteredAt_5min']), axis=1
        )
        performance_df['x_exit'] = performance_df.apply(
            lambda row: map_to_x_index(row['TradeDay'], row['DayOfWeek'], row['ExitedAt_5min']), axis=1
        )

        trade_traces = []
        for idx, row in performance_df.iterrows():
            color = 'green' if row['PnL(Net)'] > 0 else 'red'
            hover_text = (
                f"Type: {row['Type']}<br>"
                f"Size: {row['Size']}<br>"
                f"PnL(Net): {row['PnL(Net)']}<br>"
                f"Duration: {row['TradeDuration']}<br>"
                f"EntryPrice: {row['EntryPrice']}<br>"
                f"ExitPrice: {row['ExitPrice']}<br>"
                f"EnteredAt: {row['EnteredAt'].strftime('%Y-%m-%d %H:%M:%S')} CT<br>"
                f"ExitedAt: {row['ExitedAt'].strftime('%Y-%m-%d %H:%M:%S')} CT<br>"
                f"TradeDay: {row['TradeDay']}"
            )
            trace = go.Scatter(
                x=[row['x_entry'], row['x_exit']],
                y=[row['EntryPrice'], row['ExitPrice']],
                mode='lines+markers',
                line=dict(color=color, width=2),
                marker=dict(
                    size=8,
                    color=color,
                    symbol='circle',
                    line=dict(width=1, color='black')
                ),
                name=f'Trade {idx + 1}',
                text=hover_text,
                hoverinfo='text',
                hoverlabel=dict(bgcolor='white', font_size=12, font_family='Arial'),
                visible=(idx < current_trace_index)
            )
            trade_traces.append(trace)

        fig.add_traces(trade_traces)

    # Enhanced x-axis with day labels
    future_df['date'] = future_df['Datetime'].dt.date
    day_starts = future_df[future_df['Datetime'].dt.time == pd.Timestamp('08:30:00').time()]
    tickvals = future_df['x_index'][::TIMESTEP].tolist() + day_starts['x_index'].tolist()
    ticktext = future_df['Datetime'].dt.strftime('%H:%M')[::TIMESTEP].tolist() + day_starts['date'].astype(str).tolist()

    fig.update_layout(
        title=f'{ticket} Futures Candlestick (Chicago Time)',
        xaxis_title='Trading Session',
        yaxis_title='Price',
        xaxis=dict(
            tickvals=tickvals,
            ticktext=ticktext,
            tickangle=45,
            rangeslider_visible=False
        ),
        yaxis=dict(autorange=True),
        width=1280,
        height=1280,
        autosize=False,
        dragmode='pan'
    )

    return fig


def get_statistics(performance_df):
    if performance_df.empty:
        return {
            'win_loss_data': [],
            'financial_metrics': {},
            'win_loss_by_type': [],
            'streak_data': [],
            'duration_data': [],
            'size_counts': []
        }

    # Win/Loss Data
    total_trades = len(performance_df)
    winning_trades = len(performance_df[performance_df['WinOrLoss'] == 1])
    losing_trades = len(performance_df[performance_df['WinOrLoss'] == -1])
    win_loss_data = [
        {'label': f'Winning Trades', 'value': winning_trades},
        {'label': f'Lossing Trades', 'value': losing_trades}
    ]

    # Financial Metrics
    cumulative_pnl_net = performance_df['PnL(Net)'].sum()
    cumulative_fees = performance_df['Fees'].sum()
    cumulative_pnl_gross = cumulative_pnl_net + cumulative_fees
    avg_pnl_per_trade = cumulative_pnl_net / total_trades if total_trades > 0 else 0
    largest_win_row = performance_df.loc[performance_df['PnL(Net)'].idxmax()]
    largest_loss_row = performance_df.loc[performance_df['PnL(Net)'].idxmin()]
    financial_metrics = {
        'Cumulative PnL(Net)': cumulative_pnl_net,
        'Cumulative PnL(Gross)': cumulative_pnl_gross,
        'Average PnL per Trade': avg_pnl_per_trade,
        'Largest Win': largest_win_row['PnL(Net)'],
        'Largest Loss': largest_loss_row['PnL(Net)'],
        'Largest Win Time': largest_win_row['EnteredAt'],
        'Largest Loss Time': largest_loss_row['EnteredAt']
    }

    # Win/Loss by Type (unchanged)
    short_wins = len(performance_df[(performance_df['Type'] == 'Short') & (performance_df['WinOrLoss'] == 1)])
    short_losses = len(performance_df[(performance_df['Type'] == 'Short') & (performance_df['WinOrLoss'] == -1)])
    long_wins = len(performance_df[(performance_df['Type'] == 'Long') & (performance_df['WinOrLoss'] == 1)])
    long_losses = len(performance_df[(performance_df['Type'] == 'Long') & (performance_df['WinOrLoss'] == -1)])
    win_loss_by_type = [
        {'Type': 'Short', 'Wins': short_wins, 'Losses': short_losses},
        {'Type': 'Long', 'Wins': long_wins, 'Losses': long_losses}
    ]

    # Streak Data
    streak_data = performance_df[['TradeDay', 'Streak']].copy()
    streak_data['TradeIndex'] = range(1, len(streak_data) + 1)

    # Duration Data
    performance_df['TradeDuration'] = pd.to_timedelta(performance_df['TradeDuration'])
    duration_data = performance_df['TradeDuration'].dt.total_seconds() / 60  # Convert to minutes

    # Size Counts
    size_counts = performance_df['Size'].value_counts().reset_index()
    size_counts.columns = ['Size', 'Count']

    return {
        'win_loss_data': win_loss_data,
        'financial_metrics': financial_metrics,
        'win_loss_by_type': win_loss_by_type,
        'streak_data': streak_data,
        'duration_data': duration_data,
        'size_counts': size_counts
    }


def get_win_loss_pie_fig(stats):
    # Win/Loss Pie Chart
    win_loss_fig = go.Figure(data=[
        go.Pie(
            labels=[item['label'] for item in stats['win_loss_data']],
            values=[item['value'] for item in stats['win_loss_data']],
            textinfo='percent',
            hovertemplate='%{label}<br>Count: %{value}<br>Ratio: %{percent}<extra></extra>',
            marker=dict(colors=['#00FF00', '#FF0000'])  # Green for wins, red for losses
        )
    ])
    win_loss_fig.update_layout(
        title='Win/Loss Ratio',
        width=600,
        height=600,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return win_loss_fig




def get_financial_metrics_fig(stats):
    financial_fig = go.Figure()

    # Trace 1: Metrics without timestamps (Cumulative PnL(Net), Cumulative PnL(Gross), Average PnL per Trade)
    financial_fig.add_trace(
        go.Bar(
            x=[stats['financial_metrics']['Cumulative PnL(Net)'],
               stats['financial_metrics']['Cumulative PnL(Gross)'],
               stats['financial_metrics']['Average PnL per Trade']],
            y=['Cumulative PnL(Net)', 'Cumulative PnL(Gross)', 'Average PnL per Trade'],
            orientation='h',
            marker_color=['#1f77b4', '#ff7f0e', '#2ca02c'],
            hovertemplate='Metric: %{y}<br>Value: %{x:.2f}<extra></extra>',
            name=''  # Prevent trace label
        )
    )

    # Trace 2: Metrics with timestamps (Largest Win, Largest Loss)
    financial_fig.add_trace(
        go.Bar(
            x=[stats['financial_metrics']['Largest Win'],
               stats['financial_metrics']['Largest Loss']],
            y=['Largest Win', 'Largest Loss'],
            orientation='h',
            marker_color=['#00FF00', '#FF0000'],
            hovertemplate='Metric: %{y}<br>Value: %{x:.2f}<br>Time: %{customdata}<extra></extra>',
            customdata=[stats['financial_metrics']['Largest Win Time'],
                        stats['financial_metrics']['Largest Loss Time']],
            name=''  # Prevent trace label
        )
    )

    # Calculate x-axis range with padding for negative values
    all_x_values = [
        stats['financial_metrics']['Cumulative PnL(Net)'],
        stats['financial_metrics']['Cumulative PnL(Gross)'],
        stats['financial_metrics']['Average PnL per Trade'],
        stats['financial_metrics']['Largest Win'],
        stats['financial_metrics']['Largest Loss']
    ]
    x_min = min(all_x_values)
    x_max = max(all_x_values)
    padding = 0.1 * max(abs(x_min), abs(x_max))
    x_range_min = x_min - padding - 50 if x_min < 0 else x_min - padding
    x_range_max = x_max + padding

    financial_fig.update_layout(
        title='Financial Metrics',
        xaxis_title='Value',
        yaxis_title='Metric',
        width=600,
        height=600,
        margin=dict(l=70, r=20, t=40, b=20),
        showlegend=False
    )

    financial_fig.update_xaxes(
        range=[x_range_min, x_range_max]
    )

    return financial_fig



def get_win_loss_by_type_fig(stats):
    win_loss_type_fig = go.Figure(data=[
        go.Bar(
            name='Wins',
            x=[item['Type'] for item in stats['win_loss_by_type']],
            y=[item['Wins'] for item in stats['win_loss_by_type']],
            marker_color='#00FF00'
        ),
        go.Bar(
            name='Losses',
            x=[item['Type'] for item in stats['win_loss_by_type']],
            y=[item['Losses'] for item in stats['win_loss_by_type']],
            marker_color='#FF0000'
        )
    ])
    win_loss_type_fig.update_layout(
        barmode='stack',
        title='Win/Loss by Trade Type',
        xaxis_title='Trade Type',
        yaxis_title='Number of Trades',
        width=600,
        height=600,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return win_loss_type_fig

import plotly.graph_objects as go

def get_streak_pattern_fig(stats):
    streak_fig = go.Figure()

    # Group data by TradeDay
    grouped_data = stats['streak_data'].groupby('TradeDay')

    # Define a color scale (e.g., Plotly's Viridis)
    colors = ['#440154', '#b5de2b']

    for i, (trade_day, group) in enumerate(grouped_data):
        color = colors[i % len(colors)]
        streak_fig.add_trace(
            go.Scatter(
                x=group['TradeIndex'],
                y=group['Streak'],
                mode='lines+markers',
                line=dict(width=2, color=color),
                marker=dict(size=8, color=color),
                hovertemplate=(
                    f'Trade Index: %{{x}}<br>' +
                    f'Streak: %{{y}}<br>' +
                    f'Trade Day: {trade_day}<extra></extra>'
                ),
                name=trade_day  # Optional: for legend if needed
            )
        )

    streak_fig.update_layout(
        title='Streak Pattern',
        xaxis_title='Trade Index',
        yaxis_title='Streak Value',
        width=600,
        height=600,
        margin=dict(l=20, r=20, t=40, b=20),
        showlegend=False,
        shapes=[
            # Horizontal line at y=0
            dict(
                type='line',
                xref='paper',  # Use 'paper' to span the entire x-axis range
                x0=0,  # Start at the left edge
                x1=1,  # End at the right edge
                yref='y',
                y0=0,  # Position at y=0
                y1=0,
                line=dict(
                    color='red',
                    width=3,
                    dash='dash'
                )
            )
        ]
    )

    return streak_fig


def get_duration_distribution_plot(stats):
    duration_fig = go.Figure(data=[
        go.Histogram(
            x=stats['duration_data'],
            nbinsx=int(max(stats['duration_data']) + 1) if not stats['duration_data'].empty else 1,
            marker_color='#1f77b4',
            hovertemplate='Duration: %{x:.1f} mins<br>Count: %{y}<extra></extra>'
        )
    ])
    duration_fig.update_layout(
        title='Trading Duration Distribution (1-min bins)',
        xaxis_title='Duration (minutes)',
        yaxis_title='Number of Trades',
        width=600,
        height=600,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return duration_fig


def get_size_count_fig(stats):
    size_fig = go.Figure(data=[
        go.Bar(
            x=stats['size_counts']['Size'],
            y=stats['size_counts']['Count'],
            marker_color='#2ca02c',
            hovertemplate='Size: %{x}<br>Count: %{y}<extra></extra>'
        )
    ])
    size_fig.update_layout(
        title='Trade Size Distribution',
        xaxis_title='Trade Size',
        yaxis_title='Number of Trades',
        width=600,
        height=600,
        margin=dict(l=20, r=20, t=40, b=20)
    )
    return size_fig