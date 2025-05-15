# components/layout.py
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
from analysis.compute import filter_data, compute_analysis, get_interesting_fact
import plotly.express as px
import pandas as pd

def create_layout(app, data):
    layout = html.Div([
        # Header
        html.H1('Futures Trading Dashboard', className='text-3xl font-bold text-center text-gray-800 mb-6'),
        
        # Controls Section
        html.Div([
            html.Div([
                html.Label('Primary Date Range', className='text-sm font-medium text-gray-700'),
                dcc.DatePickerRange(
                    id='primary-date-picker',
                    min_date_allowed=data['TradeDay'].min(),
                    max_date_allowed=data['TradeDay'].max(),
                    start_date=data['TradeDay'].min(),
                    end_date=data['TradeDay'].max(),
                    className='mt-1'
                ),
            ], className='w-full md:w-1/3 px-2 mb-4'),
            
            html.Div([
                html.Label('Comparison Date Range', className='text-sm font-medium text-gray-700'),
                dcc.DatePickerRange(
                    id='compare-date-picker',
                    min_date_allowed=data['TradeDay'].min(),
                    max_date_allowed=data['TradeDay'].max(),
                    className='mt-1'
                ),
            ], className='w-full md:w-1/3 px-2 mb-4'),
            
            html.Div([
                html.Label('Analysis Type', className='text-sm font-medium text-gray-700'),
                dcc.Dropdown(
                    id='analysis-type',
                    options=[
                        {'label': 'Hourly PnL', 'value': 'hourly_pnl'},
                        {'label': 'Cumulative PnL', 'value': 'cumulative_pnl'},
                        {'label': 'Streaks', 'value': 'streaks'},
                        {'label': 'Trade Type', 'value': 'trade_type'}
                    ],
                    value='hourly_pnl',
                    className='mt-1'
                ),
            ], className='w-full md:w-1/3 px-2 mb-4'),
        ], className='flex flex-wrap -mx-2 mb-6 bg-gray-100 p-4 rounded-lg'),
        
        # Charts Section
        html.Div([
            html.Div([
                dcc.Graph(id='primary-chart', className='w-full')
            ], className='w-full md:w-1/2 p-4 bg-white rounded-lg shadow'),
            html.Div([
                dcc.Graph(id='compare-chart', className='w-full')
            ], className='w-full md:w-1/2 p-4 bg-white rounded-lg shadow'),
        ], className='flex flex-wrap -mx-4 mb-6'),
        
        # Table and Fact Section
        html.Div([
            html.H2('Summary Statistics', className='text-xl font-semibold text-gray-800 mb-4'),
            html.Div([
                dash_table.DataTable(
                    id='stats-table',
                    columns=[
                        {'name': 'Metric', 'id': 'metric'},
                        {'name': 'Value', 'id': 'value'}
                    ],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'padding': '8px'},
                    style_header={'backgroundColor': '#f3f4f6', 'fontWeight': 'bold'}
                )
            ], className='mb-6'),
            html.H2('Interesting Fact', className='text-xl font-semibold text-gray-800 mb-4'),
            html.P(id='interesting-fact', className='text-gray-600')
        ], className='p-4 bg-white rounded-lg shadow')
    ], className='container mx-auto p-6 bg-gray-50 min-h-screen')

    # Register callback
    @app.callback(
        [
            Output('primary-chart', 'figure'),
            Output('compare-chart', 'figure'),
            Output('stats-table', 'data'),
            Output('interesting-fact', 'children')
        ],
        [
            Input('primary-date-picker', 'start_date'),
            Input('primary-date-picker', 'end_date'),
            Input('compare-date-picker', 'start_date'),
            Input('compare-date-picker', 'end_date'),
            Input('analysis-type', 'value')
        ]
    )
    def update_dashboard(start_date, end_date, compare_start_date, compare_end_date, analysis_type):
        # Filter data
        filtered_data = filter_data(data, start_date, end_date)
        compare_data = filter_data(data, compare_start_date, compare_end_date)
        
        # Compute analysis
        chart_data = compute_analysis(filtered_data, analysis_type)
        compare_chart_data = compute_analysis(compare_data, analysis_type)
        
        # Create figures
        if analysis_type == 'hourly_pnl':
            primary_fig = px.bar(
                chart_data, x='hour', y='avgPnL', title='Primary: Average PnL by Hour',
                labels={'hour': 'Hour of Day', 'avgPnL': 'Average PnL ($)'},
                color_discrete_sequence=['#3b82f6']
            )
            compare_fig = px.bar(
                compare_chart_data, x='hour', y='avgPnL', title='Comparison: Average PnL by Hour',
                labels={'hour': 'Hour of Day', 'avgPnL': 'Average PnL ($)'},
                color_discrete_sequence=['#10b981']
            )
        elif analysis_type == 'cumulative_pnl':
            primary_fig = px.line(
                chart_data, x='date', y='cumulativePnL', title='Primary: Cumulative PnL',
                labels={'date': 'Date', 'cumulativePnL': 'Cumulative PnL ($)'},
                color_discrete_sequence=['#3b82f6']
            )
            compare_fig = px.line(
                compare_chart_data, x='date', y='cumulativePnL', title='Comparison: Cumulative PnL',
                labels={'date': 'Date', 'cumulativePnL': 'Cumulative PnL ($)'},
                color_discrete_sequence=['#10b981']
            )
        elif analysis_type == 'streaks':
            primary_fig = px.bar(
                chart_data, x='date', y='streak', title='Primary: Trade Streaks',
                labels={'date': 'Date', 'streak': 'Streak Length'},
                color_discrete_sequence=['#3b82f6']
            )
            compare_fig = px.bar(
                compare_chart_data, x='date', y='streak', title='Comparison: Trade Streaks',
                labels={'date': 'Date', 'streak': 'Streak Length'},
                color_discrete_sequence=['#10b981']
            )
        else:  # trade_type
            primary_fig = px.bar(
                chart_data, x='type', y='totalPnL', title='Primary: PnL by Trade Type',
                labels={'type': 'Trade Type', 'totalPnL': 'Total PnL ($)'},
                color='type', color_discrete_sequence=['#3b82f6', '#10b981']
            )
            compare_fig = px.bar(
                compare_chart_data, x='type', y='totalPnL', title='Comparison: PnL by Trade Type',
                labels={'type': 'Trade Type', 'totalPnL': 'Total PnL ($)'},
                color='type', color_discrete_sequence=['#3b82f6', '#10b981']
            )
        
        # Update layout for better visuals
        for fig in [primary_fig, compare_fig]:
            fig.update_layout(
                margin=dict(l=40, r=40, t=40, b=40),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(size=12),
                showlegend=True
            )
        
        # Compute summary stats
        avg_duration = 'N/A'
        if not filtered_data.empty and 'TradeDuration' in filtered_data.columns:
            try:
                # Convert TradeDuration (HH:MM:SS) to seconds for mean calculation
                durations = pd.to_timedelta(filtered_data['TradeDuration'].dropna())
                if not durations.empty:
                    mean_seconds = durations.mean().total_seconds()
                    # Format as HH:MM:SS
                    hours = int(mean_seconds // 3600)
                    minutes = int((mean_seconds % 3600) // 60)
                    seconds = int(mean_seconds % 60)
                    avg_duration = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            except Exception as e:
                print(f"Error calculating avg trade duration: {e}")
        
        stats = [
            {'metric': 'Total PnL', 'value': f"${filtered_data['PnL(Net)'].sum():.2f}"},
            {'metric': 'Number of Trades', 'value': len(filtered_data)},
            {'metric': 'Win Rate', 'value': f"{(filtered_data['WinOrLoss'] == 1).mean() * 100:.2f}%"},
            {'metric': 'Avg Trade Duration', 'value': avg_duration}
        ]
        
        # Get interesting fact
        fact = get_interesting_fact(filtered_data)
        
        return primary_fig, compare_fig, stats, fact

    return layout