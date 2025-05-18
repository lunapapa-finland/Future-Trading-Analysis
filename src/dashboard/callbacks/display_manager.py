from dash import Input, Output, dash, callback_context, html, dcc, dash_table
import pandas as pd
import plotly.graph_objects as go

def register_display_callbacks(app):
    @app.callback(
        [
            Output('tab-1-section-2-content', 'children'),
            Output('tab-2-section-2-content', 'children'),
        ],
        [
            Input('data-store-1', 'data'),
            Input('data-store-2', 'data'),
            Input('tabs', 'value'),
        ],
        prevent_initial_call=True
    )
    def update_section_2(data_store_1, data_store_2, active_tab):
        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        default_content = html.P('No data loaded', className='text-gray-500')
        content_1 = default_content
        content_2 = default_content

        if trigger_id == 'tabs':
            return [default_content, default_content]

        elif trigger_id == 'data-store-1' and data_store_1:
            ticket = data_store_1.get('ticket', 'Unknown')
            performance_df = pd.DataFrame(data_store_1['performance'])
            if performance_df.empty:
                performance_table = html.P(f'No performance data for {ticket}', className='text-gray-500')
            else:
                performance_table = dash_table.DataTable(
                    data=performance_df.to_dict('records'),
                    columns=[{'name': col, 'id': col} for col in performance_df.columns],
                    style_table={'overflowX': 'auto'},
                    style_cell={'textAlign': 'left', 'padding': '5px'},
                    style_header={'fontWeight': 'bold'},
                    page_size=5
                )
            
            future_df = pd.DataFrame(data_store_1['future'])
            if future_df.empty:
                future_plot = html.P(f'No futures data for {ticket}', className='text-gray-500')
            else:
                future_df['Datetime'] = pd.to_datetime(future_df['Datetime'])
                future_df['x_index'] = range(1, len(future_df)+1)
                future_df['hover_text'] = future_df['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                future_df['formatted_hover'] = (
                    'Index: ' + future_df['x_index'].astype(str) + '<br>' +
                    'Open: ' + future_df['Open'].astype(str) + '<br>' +
                    'High: ' + future_df['High'].astype(str) + '<br>' +
                    'Low: ' + future_df['Low'].astype(str) + '<br>' +
                    'Close: ' + future_df['Close'].astype(str)
                )
                
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
                
                step = 6
                tickvals = future_df['x_index'][::step]
                ticktext = future_df['Datetime'].dt.strftime('%H:%M')[::step]
                
                fig.update_layout(
                    title=f'{ticket} Futures Candlestick (Helsinki Time)',
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
                    height=720,
                    autosize=False
                )
                future_plot = dcc.Graph(
                    figure=fig,
                    responsive=True,
                    style={'width': '100%'},
                    config={'scrollZoom': True}
                )

            content_1 = html.Div([
                html.H2(f'{ticket} Performance Data', className='text-xl font-semibold mb-4'),
                performance_table,
                html.H2(f'{ticket} Futures Data', className='text-xl font-semibold mt-6 mb-4'),
                future_plot
            ], className='mt-4 max-w-full overflow-x-auto')
            return [content_1, content_2]

        elif trigger_id == 'data-store-2' and data_store_2:
            ticket = data_store_2.get('ticket', 'Unknown')
            analysis = data_store_2.get('analysis', 'Unknown')
            content_2 = html.Div([
                html.H2(f'{ticket} - {analysis} Analysis', className='text-xl font-semibold mb-4'),
                html.P('Analysis content to be implemented later.', className='text-gray-500')
            ])
            return [content_1, content_2]

        return [content_1, content_2]