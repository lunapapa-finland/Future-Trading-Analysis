# components/layout.py
from dash import dcc, html, Input, Output, State, dash_table
from data.load_data import load_performance, load_future
from config.settings import PERFORMANCE_CSV, MES_CSV, MNQ_CSV, MGC_CSV
import pandas as pd
import plotly.graph_objects as go


def create_layout(app):
    layout = html.Div([
        # NAV Section
        html.Nav([
            html.H1('Futures Trading Dashboard', className='text-2xl font-bold text-gray-800'),
            html.Div([
                # Data Source Dropdown
                html.Label('Data Source', className='text-sm font-medium text-gray-700 mr-2'),
                dcc.Dropdown(
                    id='ticket-selector',
                    options=[
                        {'label': 'MES', 'value': 'MES'},
                        {'label': 'MNQ', 'value': 'MNQ'},
                        {'label': 'MGC', 'value': 'MGC'},
                    ],
                    placeholder='Select a ticket',
                    className='w-32'
                ),
                # Start Date Picker
                html.Label('Start Date', className='text-sm font-medium text-gray-700 ml-4 mr-2'),
                dcc.DatePickerSingle(
                    id='start-date-picker',
                    placeholder='Start Date',
                    className='w-32'
                ),
                # End Date Picker
                html.Label('End Date', className='text-sm font-medium text-gray-700 ml-4 mr-2'),
                html.P(id='end-date-picker-error', className='text-red-600 mt-2 hidden'),
                dcc.DatePickerSingle(
                    id='end-date-picker',
                    placeholder='End Date',
                    className='w-32'
                ),
                # Confirm Button
                html.Button(
                    'Confirm',
                    id='confirm-button',
                    n_clicks=0,
                    className='ml-4 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700'
                ),
            ], className='flex items-center space-x-2 mt-2'),
            # Error Message
            html.P(id='error-message', className='text-red-600 mt-2 hidden'),
        ], className='bg-gray-100 p-4 shadow mb-6'),
        
        # Section 1 (Blank)
        html.Div(
            id='section-1',
            className='bg-white p-4 shadow mb-6 min-h-[200px]'
        ),
        
        # Section 2 (Data Display)
        html.Div(
            id='section-2',
            className='bg-white p-4 shadow min-h-[200px]'
        ),
        
        # Hidden Store for Data
        dcc.Store(id='data-store'),
    ], className='container mx-auto p-4 bg-gray-50 min-h-screen')

    @app.callback(
        [
            Output('data-store', 'data'),
            Output('error-message', 'children'),
            Output('error-message', 'className'),
        ],
        Input('confirm-button', 'n_clicks'),
        [
            State('ticket-selector', 'value'),
            State('start-date-picker', 'date'),
            State('end-date-picker', 'date'),
        ]
    )
    def load_data(n_clicks, ticket, start_date, end_date):
        if n_clicks == 0:
            return None, '', 'text-red-600 mt-2 hidden'
        
        # Validate inputs
        if not ticket or not start_date or not end_date:
            return None, 'Please select a ticket and both dates.', 'text-red-600 mt-2'
        
        if ticket not in ['MES', 'MNQ', 'MGC']:
            return None, "Invalid ticket selected. Choose 'MES', 'MNQ', or 'MGC'.", 'text-red-600 mt-2'
        
        try:
            # Select CSV based on ticket
            csv_map = {'MES': MES_CSV, 'MNQ': MNQ_CSV, 'MGC': MGC_CSV}
            future_csv = csv_map[ticket]
            
            # Load data
            performance_df = load_performance(start_date, end_date, PERFORMANCE_CSV)
            future_df = load_future(start_date, end_date, future_csv)
            
            # Combine data
            data = {
                'performance': performance_df.to_dict('records'),
                'future': future_df.to_dict('records'),
                'ticket': ticket,
            }
            
            return data, '', 'text-red-600 mt-2 hidden'
        
        except Exception as e:
            return None, f"Error loading data: {str(e)}", 'text-red-600 mt-2'

    @app.callback(
        Output('section-2', 'children'),
        Input('data-store', 'data')
    )
    def display_data(data):
        if not data:
            return html.P('No data loaded', className='text-gray-500')
        
        ticket = data.get('ticket', 'Unknown')
        
        # Performance table
        performance_df = pd.DataFrame(data['performance'])
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
        
        # Futures candlestick plot
        future_df = pd.DataFrame(data['future'])
        if future_df.empty:
            future_plot = html.P(f'No futures data for {ticket}', className='text-gray-500')
        else:
            # Convert Datetime to datetime64
            future_df['Datetime'] = pd.to_datetime(future_df['Datetime'])
            # Create continuous x-axis index
            future_df['x_index'] = range(1, len(future_df)+1)
            # Format Datetime for hover text
            future_df['hover_text'] = future_df['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
            # Create formatted hover text
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
            
            # Set x-axis ticks at every 6th candlestick time
            step = 6
            tickvals = future_df['x_index'][::step]  # Every 6th index
            ticktext = future_df['Datetime'].dt.strftime('%H:%M')[::step]  # Every 6th time
            
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
                yaxis=dict(
                    autorange=True
                ),
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

        # Return layout with performance table and futures plot
        return html.Div([
            html.H2(f'{ticket} Performance Data', className='text-xl font-semibold mb-4'),
            performance_table,
            html.H2(f'{ticket} Futures Data', className='text-xl font-semibold mt-6 mb-4'),
            future_plot
        ], className='mt-4 max-w-full overflow-x-auto')

    return layout