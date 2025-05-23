from dash import Input, Output, dash, callback_context, html, dcc, State, dash_table
import pandas as pd
import plotly.graph_objects as go
from dashboard.analysis.plots import *
from dashboard.config.settings import ANALYSIS_DROPDOWN, DEFAULT_GRANULARITY, GRANULARITY_OPTIONS, DEFAULT_ROLLING_WINDOW
from dashboard.analysis.compute import pnl_growth, drawdown, pnl_distribution, behavioral_patterns, rolling_win_rate, sharpe_ratio, trade_efficiency, hourly_performance

def register_display_callbacks(app):
    app.layout.children.insert(0, dcc.Store(id='current-trace-index-1', data=0))

    @app.callback(
        [
            Output('tab-1-section-2-content', 'children'),
            Output('tab-2-section-2-content', 'children'),
            Output('current-trace-index-1', 'data'),
        ],
        [
            Input('data-store-1', 'data'),
            Input('data-store-2', 'data'),
            Input('tabs', 'value'),
            Input('prev-button-1', 'n_clicks'),
            Input('next-button-1', 'n_clicks')
        ],
        [
            State('current-trace-index-1', 'data')
        ],
        prevent_initial_call=True
    )
    def update_section_2(data_store_1, data_store_2, active_tab, prev_clicks, next_clicks, current_trace_index):
        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        default_content = html.P('No data loaded', className='text-gray-500')
        content_1 = default_content
        content_2 = default_content
        new_trace_index = int(current_trace_index) if current_trace_index is not None else 0

        if trigger_id in ['prev-button-1', 'next-button-1'] and data_store_1:
            ticket = data_store_1.get('ticket', 'Unknown')
            performance_df = pd.DataFrame(data_store_1['performance'])
            future_df = pd.DataFrame(data_store_1['future'])
            num_traces = len(performance_df) if not performance_df.empty else 0

            if trigger_id == 'prev-button-1' and prev_clicks > 0:
                new_trace_index = max(0, new_trace_index - 1)
            elif trigger_id == 'next-button-1' and next_clicks > 0:
                new_trace_index = min(num_traces, new_trace_index + 1)

            if not future_df.empty:
                fig = get_candlestick_plot(ticket, future_df, performance_df, current_trace_index=new_trace_index)
                future_plot = dcc.Graph(
                    id='candlestick-plot',
                    figure=fig,
                    responsive=True,
                    style={'width': '100%', 'height': '700'},
                    config={'scrollZoom': True}
                )
                if not performance_df.empty and new_trace_index > 0:
                    visible_trades = performance_df.iloc[:new_trace_index][['EnteredAt', 'ExitedAt', 'Type', 'Size', 'PnL(Net)', 'EntryPrice', 'ExitPrice']]
                    trade_table = dash_table.DataTable(
                        id='trade-table-1',
                        columns=[
                            {'name': 'Entry Time', 'id': 'EnteredAt'},
                            {'name': 'Exit Time', 'id': 'ExitedAt'},
                            {'name': 'Type', 'id': 'Type'},
                            {'name': 'Size', 'id': 'Size'},
                            {'name': 'PnL(Net)', 'id': 'PnL(Net)'},
                            {'name': 'Entry Price', 'id': 'EntryPrice'},
                            {'name': 'Exit Price', 'id': 'ExitPrice'}
                        ],
                        data=visible_trades.to_dict('records'),
                        style_table={'overflowX': 'auto'},
                        style_cell={'textAlign': 'left', 'padding': '5px'},
                        style_header={'fontWeight': 'bold'}
                    )
                else:
                    trade_table = html.P("No trades visible.", className='text-gray-500')

                stats = get_statistics(performance_df)
                if not stats['win_loss_data']:
                    stats_content = html.P('No performance data available.', className='text-gray-500')
                else:
                    win_loss_fig = get_win_loss_pie_fig(stats)
                    win_loss_chart = dcc.Graph(
                        id='win-loss-pie-chart',
                        figure=win_loss_fig,
                        style={'width': '48%', 'verticalAlign': 'top'}
                    )

                    financial_fig = get_financial_metrics_fig(stats)
                    financial_chart = dcc.Graph(
                        id='financial-metrics-chart',
                        figure=financial_fig,
                        style={'width': '48%', 'verticalAlign': 'top'}
                    )

                    win_loss_type_fig = get_win_loss_by_type_fig(stats)
                    win_loss_type_chart = dcc.Graph(
                        id='win-loss-by-type-chart',
                        figure=win_loss_type_fig,
                        style={'width': '48%', 'verticalAlign': 'top'}
                    )

                    streak_fig = get_streak_pattern_fig(stats)
                    streak_chart = dcc.Graph(
                        id='streak-pattern-chart',
                        figure=streak_fig,
                        style={'width': '48%', 'verticalAlign': 'top'}
                    )

                    duration_fig = get_duration_distribution_plot(stats)
                    duration_chart = dcc.Graph(
                        id='trading-duration-distribution-chart',
                        figure=duration_fig,
                        style={'width': '48%', 'verticalAlign': 'top'}
                    )

                    size_fig = get_size_count_fig(stats)
                    size_chart = dcc.Graph(
                        id='trade-size-count-chart',
                        figure=size_fig,
                        style={'width': '48%', 'verticalAlign': 'top'}
                    )

                    stats_content = html.Div([
                        html.H3('Trade Statistics', className='text-lg font-semibold mt-6 mb-4'),
                        html.Div([
                            html.Div([win_loss_chart, financial_chart], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '20px'}),
                            html.Div([win_loss_type_chart, streak_chart], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '20px'}),
                            html.Div([duration_chart, size_chart], style={'display': 'flex', 'justifyContent': 'space-between'})
                        ], style={'width': '100%'})
                    ])

                content_1 = html.Div([
                    html.H2(f'{ticket} Futures Data', className='text-xl font-semibold mb-4'),
                    html.Div(future_plot, style={'width': '100%'}),
                    html.Div(trade_table, style={'marginTop': '20px'}),
                    html.Div(stats_content, style={'width': '100%'})
                ], style={'display': 'block', 'maxWidth': '100%', 'overflowX': 'auto'})
            return [content_1, content_2, new_trace_index]

        if trigger_id == 'tabs':
            return [default_content, content_2, new_trace_index]

        if trigger_id == 'data-store-1' and data_store_1:
            ticket = data_store_1.get('ticket', 'Unknown')
            performance_df = pd.DataFrame(data_store_1['performance'])
            future_df = pd.DataFrame(data_store_1['future'])

            if future_df.empty:
                future_plot = html.P(f'No futures data for {ticket}', className='text-gray-500')
            else:
                fig = get_candlestick_plot(ticket, future_df, performance_df, current_trace_index=new_trace_index)
                future_plot = dcc.Graph(
                    id='candlestick-plot',
                    figure=fig,
                    responsive=True,
                    style={'width': '100%', 'height': '700px'},
                    config={'scrollZoom': True}
                )

            stats = get_statistics(performance_df)
            if not stats['win_loss_data']:
                stats_content = html.P('No performance data available.', className='text-gray-500')
            else:
                win_loss_fig = get_win_loss_pie_fig(stats)
                win_loss_chart = dcc.Graph(
                    id='win-loss-pie-chart',
                    figure=win_loss_fig,
                    style={'width': '48%', 'verticalAlign': 'top'}
                )

                financial_fig = get_financial_metrics_fig(stats)
                financial_chart = dcc.Graph(
                    id='financial-metrics-chart',
                    figure=financial_fig,
                    style={'width': '48%', 'verticalAlign': 'top'}
                )

                win_loss_type_fig = get_win_loss_by_type_fig(stats)
                win_loss_type_chart = dcc.Graph(
                    id='win-loss-by-type-chart',
                    figure=win_loss_type_fig,
                    style={'width': '48%', 'verticalAlign': 'top'}
                )

                streak_fig = get_streak_pattern_fig(stats)
                streak_chart = dcc.Graph(
                    id='streak-pattern-chart',
                    figure=streak_fig,
                    style={'width': '48%', 'verticalAlign': 'top'}
                )

                duration_fig = get_duration_distribution_plot(stats)
                duration_chart = dcc.Graph(
                    id='trading-duration-distribution-chart',
                    figure=duration_fig,
                    style={'width': '48%', 'verticalAlign': 'top'}
                )

                size_fig = get_size_count_fig(stats)
                size_chart = dcc.Graph(
                    id='trade-size-count-chart',
                    figure=size_fig,
                    style={'width': '48%', 'verticalAlign': 'top'}
                )

                stats_content = html.Div([
                    html.H3('Trade Statistics', className='text-lg font-semibold mt-6 mb-4'),
                    html.Div([
                        html.Div([win_loss_chart, financial_chart], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '20px'}),
                        html.Div([win_loss_type_chart, streak_chart], style={'display': 'flex', 'justifyContent': 'space-between', 'marginBottom': '20px'}),
                        html.Div([duration_chart, size_chart], style={'display': 'flex', 'justifyContent': 'space-between'})
                    ], style={'width': '100%'})
                ])

            content_1 = html.Div([
                html.H2(f'{ticket} Futures Data', className='text-xl font-semibold mb-4'),
                html.Div(future_plot, style={'width': '100%'}),
                html.Div(stats_content, style={'width': '100%'})
            ], style={'display': 'block', 'maxWidth': '100%', 'overflowX': 'auto'})
            return [content_1, content_2, new_trace_index]

        if trigger_id == 'data-store-2' and data_store_2:
            ticket = data_store_2.get('ticket', 'Unknown')
            analysis = data_store_2.get('analysis', 'Unknown')
            performance_df = pd.DataFrame(data_store_2.get('performance', []))
            
            content_2 = html.P('No analysis selected.', className='text-gray-500')
            analysis_options = list(ANALYSIS_DROPDOWN.keys())
            if analysis in analysis_options and not performance_df.empty:
                try:
                    category = ANALYSIS_DROPDOWN[analysis]['category']
                    if category == 'Period':
                        granularity = data_store_2.get('granularity', DEFAULT_GRANULARITY)
                        granularity_map = {item['value']: item['label'] for item in GRANULARITY_OPTIONS}
                        granularity_label = granularity_map.get(granularity, granularity)
                        valid_values = {item['value'] for item in GRANULARITY_OPTIONS}
                        if granularity not in valid_values:
                            content_2 = html.P('Invalid granularity selected.', className='text-red-500')
                            return [content_1, content_2, new_trace_index]

                        if analysis == 'PnL Growth':
                            result = pnl_growth(performance_df, granularity=granularity)
                            y_col = 'NetPnL'
                            y_title = 'Net PnL ($)'
                            chart_title = f'{ticket} - PnL Growth ({granularity_label})'
                            line_color = 'blue'
                        elif analysis == 'Drawdown':
                            result = drawdown(performance_df, granularity=granularity)
                            y_col = 'Drawdown'
                            y_title = 'Drawdown ($)'
                            chart_title = f'{ticket} - Drawdown ({granularity_label})'
                            line_color = 'red'
                        else:
                            content_2 = html.P(f'Unsupported Period analysis: {analysis}', className='text-red-500')
                            return [content_1, content_2, new_trace_index]

                        if result.empty:
                            content_2 = html.P('No data available for the selected period.', className='text-gray-500')
                        else:
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                x=result['Period'],
                                y=result[y_col],
                                mode='lines+markers',
                                name=y_col,
                                line=dict(color=line_color, width=2),
                                marker=dict(size=8)
                            ))
                            fig.update_layout(
                                title=dict(text=chart_title, x=0.5, xanchor='center', font=dict(size=20)),
                                xaxis_title='Period',
                                yaxis_title=y_title,
                                template='plotly_white',
                                height=500,
                                xaxis=dict(showgrid=True, gridcolor='lightgray'),
                                yaxis=dict(showgrid=True, gridcolor='lightgray'),
                                hovermode='x unified'
                            )
                            content_2 = html.Div([
                                html.H2(f'{ticket} - {analysis}', className='text-xl font-semibold mb-4'),
                                dcc.Graph(id=f'{analysis.lower()}-chart', figure=fig, responsive=True, style={'width': '100%'})
                            ])

                    elif category == 'Overall':
                        if analysis == 'PnL Distribution':
                            result = pnl_distribution(performance_df)
                            chart_title = f'{ticket} - PnL Distribution'
                            if result.empty or 'PnL(Net)' not in result:
                                content_2 = html.P('No data available for the selected period.', className='text-gray-500')
                            else:
                                fig = go.Figure()
                                fig.add_trace(go.Histogram(
                                    x=result['PnL(Net)'],
                                    histnorm='',
                                    name='PnL Distribution',
                                    marker=dict(color='purple'),
                                    xbins=dict(size=25),
                                    opacity=0.7
                                ))
                                fig.update_layout(
                                    title=dict(text=chart_title, x=0.5, xanchor='center', font=dict(size=20)),
                                    xaxis_title='PnL ($)',
                                    yaxis_title='Number of Trades',
                                    template='plotly_white',
                                    height=500,
                                    xaxis=dict(showgrid=True, gridcolor='lightgray'),
                                    yaxis=dict(showgrid=True, gridcolor='lightgray'),
                                    hovermode='x unified',
                                    showlegend=True
                                )
                                content_2 = html.Div([
                                    html.H2(f'{ticket} - {analysis}', className='text-xl font-semibold mb-4'),
                                    dcc.Graph(id='pnl-distribution-chart', figure=fig, responsive=True, style={'width': '100%'})
                                ])
                        elif analysis == 'Behavioral Patterns':
                            result = behavioral_patterns(performance_df)
                            chart_title = f'{ticket} - Behavioral Patterns'
                            if result.empty or 'TradeCount' not in result or 'AvgPnL' not in result:
                                content_2 = html.P('No data available for the selected period.', className='text-gray-500')
                            else:
                                fig = go.Figure()
                                fig.add_trace(go.Bar(
                                    x=result['Hour'],
                                    y=result['TradeCount'],
                                    name='Trade Count',
                                    marker=dict(color='teal'),
                                    opacity=0.6
                                ))
                                fig.add_trace(go.Scatter(
                                    x=result['Hour'],
                                    y=result['AvgPnL'],
                                    name='Average PnL ($)',
                                    line=dict(color='orange', width=2),
                                    yaxis='y2'
                                ))
                                fig.update_layout(
                                    title=dict(text=chart_title, x=0.5, xanchor='center', font=dict(size=20)),
                                    xaxis_title='Hour of Day',
                                    yaxis=dict(title='Number of Trades', showgrid=True, gridcolor='lightgray'),
                                    yaxis2=dict(title='Average PnL ($)', overlaying='y', side='right', showgrid=False),
                                    template='plotly_white',
                                    height=500,
                                    xaxis=dict(showgrid=True, gridcolor='lightgray', tickmode='linear', dtick=1),
                                    hovermode='x unified',
                                    showlegend=True
                                )
                                content_2 = html.Div([
                                    html.H2(f'{ticket} - {analysis}', className='text-xl font-semibold mb-4'),
                                    dcc.Graph(id='behavioral-patterns-chart', figure=fig, responsive=True, style={'width': '100%'})
                                ])
                        else:
                            content_2 = html.P(f'Unsupported Overall analysis: {analysis}', className='text-gray-500')
                    
                    elif category == 'Rolling':
                        window = data_store_2.get('window', DEFAULT_ROLLING_WINDOW)  # Use window from data_store_2
                        
                        if analysis == 'Rolling Win Rate':
                            result = rolling_win_rate(performance_df, window=window)
                            if result.empty or 'WinRate' not in result:
                                content_2 = html.P('No data available for the selected period.', className='text-gray-500')
                            else:
                                performance_df_sorted = performance_df.sort_values('ExitedAt').reset_index(drop=True)
                                hover_data = []
                                for idx in result['TradeIndex']:
                                    trade = performance_df_sorted.iloc[idx]
                                    hover_data.append({
                                        'EnteredAt': trade['EnteredAt'],
                                        'ExitedAt': trade['ExitedAt']
                                    })
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=result['TradeIndex'],
                                    y=result['WinRate'],
                                    mode='lines+markers',
                                    name='Win Rate',
                                    line=dict(color='#3b82f6', width=2),
                                    marker=dict(size=8),
                                    customdata=hover_data,
                                    hoverinfo='none',
                                    hovertemplate=
                                    'Trade Index: %{x}<br>' +
                                    'Win Rate: %{y}%<br>' +
                                    'Entered At: %{customdata.EnteredAt}<br>' +
                                    'Exited At: %{customdata.ExitedAt}<br>'
                                ))
                                fig.add_trace(go.Scatter(
                                    x=[result['TradeIndex'].min(), result['TradeIndex'].max()],
                                    y=[50, 50],
                                    mode='lines',
                                    name='Win Rate = 50%',
                                    line=dict(color='#ef4444', width=2, dash='dash')
                                ))
                                fig.update_layout(
                                    title=dict(text=f'{ticket} - Rolling Win Rate Analysis (Window: {window} Trades)', x=0.5, xanchor='center', font=dict(size=20)),
                                    xaxis_title='Trade Index',
                                    yaxis_title='Win Rate (%)',
                                    template='plotly_white',
                                    height=500,
                                    xaxis=dict(showgrid=True, gridcolor='lightgray'),
                                    yaxis=dict(showgrid=True, gridcolor='lightgray', domain=[0, 1]),
                                    hovermode='x unified',
                                    showlegend=True
                                )
                                content_2 = html.Div([
                                    html.H2(f'{ticket} - Rolling Win Rate Analysis (Window: {window} Trades)', className='text-xl font-semibold mb-4'),
                                    dcc.Graph(id='rolling-win-rate-chart', figure=fig, responsive=True, style={'width': '100%'})
                                ])
                        
                        elif analysis == 'Sharpe Ratio':
                            risk_free_rate = ANALYSIS_DROPDOWN[analysis].get('risk_free_rate', 0)
                            result = sharpe_ratio(performance_df, window=window, risk_free_rate=risk_free_rate)
                            if result.empty or 'SharpeRatio' not in result:
                                content_2 = html.P('No data available for the selected period.', className='text-gray-500')
                            else:
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=result['Date'],
                                    y=result['SharpeRatio'],
                                    mode='lines+markers',
                                    name='Sharpe Ratio',
                                    line=dict(color='#10b981', width=2),
                                    marker=dict(size=8)
                                ))
                                fig.add_trace(go.Scatter(
                                    x=[result['Date'].min(), result['Date'].max()],
                                    y=[1, 1],
                                    mode='lines',
                                    name='Sharpe = 1',
                                    line=dict(color='#ef4444', width=2, dash='dash')
                                ))
                                fig.update_layout(
                                    title=dict(text=f'{ticket} - Sharpe Ratio Analysis (Window: {window} Days)', x=0.5, xanchor='center', font=dict(size=20)),
                                    xaxis_title='Date',
                                    yaxis_title='Sharpe Ratio',
                                    template='plotly_white',
                                    height=500,
                                    xaxis=dict(showgrid=True, gridcolor='lightgray', tickformat='%m/%d/%Y'),
                                    yaxis=dict(showgrid=True, gridcolor='lightgray', range=[-16, 16]),
                                    hovermode='x unified',
                                    showlegend=True
                                )
                                content_2 = html.Div([
                                    html.H2(f'{ticket} - Sharpe Ratio Analysis (Window: {window} Days)', className='text-xl font-semibold mb-4'),
                                    dcc.Graph(id='sharpe-ratio-chart', figure=fig, responsive=True, style={'width': '100%'})
                                ])
                        
                        elif analysis == 'Trade Efficiency':
                            result = trade_efficiency(performance_df, window=window)
                            if result.empty or 'Efficiency' not in result:
                                content_2 = html.P('No data available for the selected period.', className='text-gray-500')
                            else:
                                performance_df_sorted = performance_df.sort_values('ExitedAt').reset_index(drop=True)
                                hover_data = []
                                for idx in result['TradeIndex']:
                                    trade = performance_df_sorted.iloc[idx]
                                    hover_data.append({
                                        'EnteredAt': trade['EnteredAt'],
                                        'ExitedAt': trade['ExitedAt']
                                    })
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=result['TradeIndex'],
                                    y=result['Efficiency'],
                                    mode='lines+markers',
                                    name='Efficiency',
                                    line=dict(color='blue', width=2),
                                    marker=dict(size=8),
                                    customdata=hover_data,
                                    hoverinfo='none',
                                    hovertemplate=
                                    'Trade Index: %{x}<br>' +
                                    'Efficiency: %{y} $/Hour<br>' +
                                    'Entered At: %{customdata.EnteredAt}<br>' +
                                    'Exited At: %{customdata.ExitedAt}<br>'
                                ))
                                fig.update_layout(
                                    title=dict(text=f'{ticket} - Trade Efficiency Analysis (Window: {window} Trades)', x=0.5, xanchor='center', font=dict(size=20)),
                                    xaxis_title='Trade Index',
                                    yaxis_title='Efficiency ($/Hour)',
                                    template='plotly_white',
                                    height=500,
                                    xaxis=dict(showgrid=True, gridcolor='lightgray'),
                                    yaxis=dict(showgrid=True, gridcolor='lightgray'),
                                    hovermode='x unified',
                                    showlegend=True
                                )
                                content_2 = html.Div([
                                    html.H2(f'{ticket} - Trade Efficiency Analysis (Window: {window} Trades)', className='text-xl font-semibold mb-4'),
                                    dcc.Graph(id='trade-efficiency-chart', figure=fig, responsive=True, style={'width': '100%'})
                                ])             
                        elif analysis == 'Hourly Performance':
                            result = hourly_performance(performance_df, window=window)
                            if result.empty or 'HourlyPnL' not in result:
                                content_2 = html.P('No data available for the selected period.', className='text-gray-500')
                            else:
                                hover_data = [{'DateHour': date_hour} for date_hour in result['DateHour'].values]
                                fig = go.Figure()
                                fig.add_trace(go.Scatter(
                                    x=result['HourlyIndex'],
                                    y=result['HourlyPnL'],
                                    mode='lines+markers',
                                    name='Hourly PnL',
                                    line=dict(color='#8B4513', width=2),
                                    marker=dict(size=8),
                                    customdata=hover_data,
                                    hoverinfo='none',
                                    hovertemplate=
                                    'Hourly Index: %{x}<br>' +
                                    'Hourly PnL: %{y} $<br>' +
                                    'Date Hour: %{customdata.DateHour}<br>'
                                ))
                                fig.add_trace(go.Scatter(
                                    x=[result['HourlyIndex'].min(), result['HourlyIndex'].max()],
                                    y=[0, 0],
                                    mode='lines',
                                    name='PnL = 0',
                                    line=dict(color='#ef4444', width=2, dash='dash')
                                ))
                                fig.update_layout(
                                    title=dict(text=f'{ticket} - Hourly Performance Analysis (Window: {window} Hours)', x=0.5, xanchor='center', font=dict(size=20)),
                                    xaxis_title='Hourly Index',
                                    yaxis_title='Hourly PnL ($)',
                                    template='plotly_white',
                                    height=500,
                                    xaxis=dict(showgrid=True, gridcolor='lightgray'),
                                    yaxis=dict(showgrid=True, gridcolor='lightgray'),
                                    hovermode='x unified',
                                    showlegend=True
                                )
                                content_2 = html.Div([
                                    html.H2(f'{ticket} - Hourly Performance Analysis (Window: {window} Hours)', className='text-xl font-semibold mb-4'),
                                    dcc.Graph(id='hourly-performance-chart', figure=fig, responsive=True, style={'width': '100%'})
                                ])
                        
                        else:
                            content_2 = html.P(f'Unsupported Rolling analysis: {analysis}', className='text-gray-500')
                    
                    else:
                        content_2 = html.P(f'Unknown category: {category}', className='text-red-500')
                
                except Exception as e:
                    content_2 = html.P(f'Error generating chart: {str(e)}', className='text-red-500')
            
            return [content_1, content_2, new_trace_index]

        return [content_1, content_2, new_trace_index]

    @app.callback(
        Output('analysis-selector-2', 'options'),
        Input('category-selector-2', 'value')
    )
    def update_analysis_options(selected_category):
        if not selected_category:
            return []
        return [
            {'label': analysis, 'value': analysis}
            for analysis, config in ANALYSIS_DROPDOWN.items()
            if config['category'] == selected_category
        ]

    @app.callback(
        [
            Output('granularity-selector-2', 'style'),
            Output('granularity-label-2', 'style')
        ],
        Input('category-selector-2', 'value')
    )
    def toggle_granularity_visibility(category):
        if category == 'Period':
            return [{'display': 'block'}, {'display': 'block'}]
        return [{'display': 'none'}, {'display': 'none'}]

    @app.callback(
        [
            Output('window-selector-2', 'style'),
            Output('window-label-2', 'style')
        ],
        Input('category-selector-2', 'value')
    )
    def toggle_window_visibility(category):
        if category == 'Rolling':
            return [{'display': 'block'}, {'display': 'block'}]
        return [{'display': 'none'}, {'display': 'none'}]