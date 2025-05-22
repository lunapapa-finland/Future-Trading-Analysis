from dash import Input, Output, dash, callback_context, html, dcc, State, dash_table
import pandas as pd
import plotly.graph_objects as go
from dashboard.analysis.plots import *
from dashboard.config.settings import ANALYSIS_DROPDOWN, DEFAULT_GRANULARITY  # Added for ANALYSIS_DROPDOWN
from dashboard.analysis.compute import pnl_growth, drawdown

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
            if analysis in ['PnL Growth', 'Drawdown'] and not performance_df.empty:
                granularity = data_store_2.get('granularity', DEFAULT_GRANULARITY)
                granularity_label = {'1D': 'Daily', '1W-MON': 'Weekly', '1M': 'Monthly'}.get(granularity, granularity)
                if granularity not in ['1D', '1W-MON', '1M']:
                    content_2 = html.P('Invalid granularity selected.', className='text-red-500')
                else:
                    try:
                        if analysis == 'PnL Growth':
                            result = pnl_growth(performance_df, granularity=granularity)
                            y_col = 'NetPnL'
                            y_title = 'Net PnL ($)'
                            chart_title = f'{ticket} - PnL Growth ({granularity_label})'
                            line_color = 'blue'
                        else:  # Drawdown
                            result = drawdown(performance_df, granularity=granularity)
                            y_col = 'Drawdown'
                            y_title = 'Drawdown ($)'
                            chart_title = f'{ticket} - Drawdown ({granularity_label})'
                            line_color = 'red'

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