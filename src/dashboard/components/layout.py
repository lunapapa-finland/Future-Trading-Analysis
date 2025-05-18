from dash import dcc, html, Input, Output, State, dash_table, dash, callback_context
from data.load_data import load_performance, load_future
from config.settings import PERFORMANCE_CSV, DATA_SOURCE_DROPDOWN, ANALYSIS_DROPDOWN
import pandas as pd
import plotly.graph_objects as go
import dash_bootstrap_components as dbc

def create_layout(app):
    layout = html.Div([
        dcc.Tabs([
            dcc.Tab(label='Trading Behavior', value='tab-1', children=[
                html.Div([
                    # Section 1: Selection Criteria
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                # Ticket Dropdown
                                html.Label('Ticket', className='text-sm font-medium text-gray-700 mr-2'),
                                dcc.Dropdown(
                                    id='ticket-selector-1',
                                    options=[{'label': ticket, 'value': ticket} for ticket in DATA_SOURCE_DROPDOWN.keys()],
                                    placeholder='Ticket Name',
                                    className='w-48',
                                    value=None
                                ),
                                # Start Date Picker
                                html.Label('Start Date', className='text-sm font-medium text-gray-700 ml-4 mr-2'),
                                dcc.DatePickerSingle(
                                    id='start-date-picker-1',
                                    placeholder='Start Date',
                                    className='w-32',
                                    date=None
                                ),
                                # End Date Picker
                                html.Label('End Date', className='text-sm font-medium text-gray-700 ml-4 mr-2'),
                                html.P(id='end-date-picker-error-1', className='text-red-600 mt-2 hidden'),
                                dcc.DatePickerSingle(
                                    id='end-date-picker-1',
                                    placeholder='End Date',
                                    className='w-32',
                                    date=None
                                ),
                                # Confirm Button
                                html.Button(
                                    'Confirm',
                                    id='confirm-button-1',
                                    n_clicks=0,
                                    className='ml-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700'
                                ),
                            ], className='flex items-center space-x-2 mt-2'),
                            # Error Message
                            html.P(id='error-message-1', className='text-red-600 mt-2 hidden'),
                        ])
                    ], className='mb-4'),
                    
                    # Section 2: Data Display
                    dbc.Card([
                        dbc.CardBody(id='tab-1-section-2-content')
                    ], className='mb-4')
                ])
            ]),
            dcc.Tab(label='Statistical Analysis', value='tab-2', children=[
                html.Div([
                    # Section 1: Selection Criteria
                    dbc.Card([
                        dbc.CardBody([
                            html.Div([
                                # Ticket Dropdown
                                html.Label('Ticket', className='text-sm font-medium text-gray-700 mr-2'),
                                dcc.Dropdown(
                                    id='ticket-selector-2',
                                    options=[{'label': ticket, 'value': ticket} for ticket in DATA_SOURCE_DROPDOWN.keys()],
                                    placeholder='Ticket Name',
                                    className='w-48',
                                    value=None
                                ),
                                # Analysis Dropdown
                                html.Label('Analysis', className='text-sm font-medium text-gray-700 mr-2'),
                                dcc.Dropdown(
                                    id='analysis-selector-2',
                                    options=[{'label': analysis, 'value': analysis} for analysis in ANALYSIS_DROPDOWN.keys()],
                                    placeholder='Analysis Type',
                                    className='w-60',
                                    value=None
                                ),
                                # Start Date Picker
                                html.Label('Start Date', className='text-sm font-medium text-gray-700 ml-4 mr-2'),
                                dcc.DatePickerSingle(
                                    id='start-date-picker-2',
                                    placeholder='Start Date',
                                    className='w-32',
                                    date=None
                                ),
                                # End Date Picker
                                html.Label('End Date', className='text-sm font-medium text-gray-700 ml-4 mr-2'),
                                html.P(id='end-date-picker-error-2', className='text-red-600 mt-2 hidden'),
                                dcc.DatePickerSingle(
                                    id='end-date-picker-2',
                                    placeholder='End Date',
                                    className='w-32',
                                    date=None
                                ),
                                # Confirm Button
                                html.Button(
                                    'Confirm',
                                    id='confirm-button-2',
                                    n_clicks=0,
                                    className='ml-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700'
                                ),
                            ], className='flex items-center space-x-2 mt-2'),
                            # Error Message
                            html.P(id='error-message-2', className='text-red-600 mt-2 hidden'),
                        ])
                    ], className='mb-4'),
                    
                    # Section 2: Data Display
                    dbc.Card([
                        dbc.CardBody(id='tab-2-section-2-content')
                    ], className='mb-4')
                ])
            ]),
        ], id='tabs', value='tab-1', className='mb-6'),
        
        # Hidden Stores for Data (Tab-specific)
        dcc.Store(id='data-store-1'),
        dcc.Store(id='data-store-2'),
    ], className='container mx-auto p-4 bg-gray-50 min-h-screen')

    @app.callback(
        [
            Output('data-store-1', 'data'),
            Output('data-store-2', 'data'),
            Output('error-message-1', 'children'),
            Output('error-message-1', 'className'),
            Output('error-message-2', 'children'),
            Output('error-message-2', 'className'),
            Output('ticket-selector-1', 'value'),
            Output('start-date-picker-1', 'date'),
            Output('end-date-picker-1', 'date'),
            Output('ticket-selector-2', 'value'),
            Output('analysis-selector-2', 'value'),
            Output('start-date-picker-2', 'date'),
            Output('end-date-picker-2', 'date'),
        ],
        [
            Input('confirm-button-1', 'n_clicks'),
            Input('confirm-button-2', 'n_clicks'),
            Input('tabs', 'value'),
        ],
        [
            State('ticket-selector-1', 'value'),
            State('start-date-picker-1', 'date'),
            State('end-date-picker-1', 'date'),
            State('ticket-selector-2', 'value'),
            State('analysis-selector-2', 'value'),
            State('start-date-picker-2', 'date'),
            State('end-date-picker-2', 'date'),
        ],
        prevent_initial_call=True
    )
    def manage_data_and_reset(
        confirm_1_clicks, confirm_2_clicks, active_tab,
        ticket_1, start_date_1, end_date_1,
        ticket_2, analysis_2, start_date_2, end_date_2
    ):
        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        # Default values for outputs
        data_store_1 = dash.no_update
        data_store_2 = dash.no_update
        error_message_1 = ''
        error_class_1 = 'text-red-600 mt-2 hidden'
        error_message_2 = ''
        error_class_2 = 'text-red-600 mt-2 hidden'
        selection_reset = [dash.no_update, dash.no_update, dash.no_update,
                         dash.no_update, dash.no_update, dash.no_update, dash.no_update]

        if trigger_id == 'tabs':
            # Reset everything on tab switch
            data_store_1 = None
            data_store_2 = None
            selection_reset = [None, None, None, None, None, None, None]
            return [data_store_1, data_store_2, error_message_1, error_class_1,
                    error_message_2, error_class_2] + selection_reset

        elif trigger_id == 'confirm-button-1':
            if not ticket_1 or not start_date_1 or not end_date_1:
                return [data_store_1, data_store_2,
                        'Please select a ticket and both dates.', 'text-red-600 mt-2',
                        error_message_2, error_class_2] + selection_reset
            try:
                csv_map = DATA_SOURCE_DROPDOWN
                future_csv = csv_map[ticket_1]
                performance_df = load_performance(start_date_1, end_date_1, PERFORMANCE_CSV)
                future_df = load_future(start_date_1, end_date_1, future_csv)
                data_store_1 = {
                    'performance': performance_df.to_dict('records'),
                    'future': future_df.to_dict('records'),
                    'ticket': ticket_1,
                }
                return [data_store_1, data_store_2, error_message_1, error_class_1,
                        error_message_2, error_class_2] + selection_reset
            except Exception as e:
                return [data_store_1, data_store_2,
                        f"Error loading data: {str(e)}", 'text-red-600 mt-2',
                        error_message_2, error_class_2] + selection_reset

        elif trigger_id == 'confirm-button-2':
            if not ticket_2 or not analysis_2 or not start_date_2 or not end_date_2:
                return [data_store_1, data_store_2,
                        error_message_1, error_class_1,
                        'Please select a ticket, analysis type, and both dates.', 'text-red-600 mt-2'] + selection_reset
            try:
                csv_map = DATA_SOURCE_DROPDOWN
                future_csv = csv_map[ticket_2]
                performance_df = load_performance(start_date_2, end_date_2, PERFORMANCE_CSV)
                future_df = load_future(start_date_2, end_date_2, future_csv)
                data_store_2 = {
                    'performance': performance_df.to_dict('records'),
                    'future': future_df.to_dict('records'),
                    'ticket': ticket_2,
                    'analysis': analysis_2,
                }
                return [data_store_1, data_store_2, error_message_1, error_class_1,
                        error_message_2, error_class_2] + selection_reset
            except Exception as e:
                return [data_store_1, data_store_2,
                        error_message_1, error_class_1,
                        f"Error loading data: {str(e)}", 'text-red-600 mt-2'] + selection_reset

        raise dash.exceptions.PreventUpdate

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

        # Default content for both tabs
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

    return layout