from dash import Input, Output, State, dash, callback_context
from dashboard.data.load_data import load_performance, load_future
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, PERFORMANCE_CSV, DEFAULT_DATA_SOURCE, CURRENT_DATE, DEFAULT_ANALYSIS, ANALYSIS_DROPDOWN
import pandas as pd

def register_data_callbacks(app):
    @app.callback(
        [
            Output('data-store-1', 'data'),
            Output('data-store-2', 'data'),
            Output('error-message-1', 'children'),
            Output('error-message-1', 'className'),
            Output('error-message-2', 'children'),
            Output('error-message-2', 'className'),
            Output('ticker-selector-1', 'value'),
            Output('start-date-picker-1', 'date'),
            Output('end-date-picker-1', 'date'),
            Output('ticker-selector-2', 'value'),
            Output('analysis-selector-2', 'value'),
            Output('start-date-picker-2', 'date'),
            Output('end-date-picker-2', 'date'),
            Output('end-date-picker-error-2', 'children'),
        ],
        [
            Input('confirm-button-1', 'n_clicks'),
            Input('confirm-button-2', 'n_clicks'),
            Input('tabs', 'value'),
        ],
        [
            State('ticker-selector-1', 'value'),
            State('start-date-picker-1', 'date'),
            State('end-date-picker-1', 'date'),
            State('ticker-selector-2', 'value'),
            State('category-selector-2', 'value'),
            State('analysis-selector-2', 'value'),
            State('granularity-selector-2', 'value'),
            State('window-selector-2', 'value'),  # New state for window
            State('start-date-picker-2', 'date'),
            State('end-date-picker-2', 'date'),
        ],
        prevent_initial_call=True
    )
    def manage_data_and_reset(
        confirm_1_clicks, confirm_2_clicks, active_tab,
        ticker_1, start_date_1, end_date_1,
        ticker_2, category_2, analysis_2, granularity_2, window_2, start_date_2, end_date_2
    ):
        ctx = callback_context
        if not ctx.triggered:
            raise dash.exceptions.PreventUpdate
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        data_store_1 = dash.no_update
        data_store_2 = dash.no_update
        error_message_1 = ''
        error_class_1 = 'text-red-600 mt-2 hidden'
        error_message_2 = ''
        error_class_2 = 'text-red-600 mt-2 hidden'
        end_date_error_2 = ''
        selection_reset = [
            DEFAULT_DATA_SOURCE,
            CURRENT_DATE,
            CURRENT_DATE,
            DEFAULT_DATA_SOURCE,
            DEFAULT_ANALYSIS,
            CURRENT_DATE,
            CURRENT_DATE
        ]
        selection_no_update = [dash.no_update] * 7

        if trigger_id == 'tabs':
            data_store_1 = None
            data_store_2 = None
            return [data_store_1, data_store_2, error_message_1, error_class_1,
                    error_message_2, error_class_2] + selection_reset + ['']

        elif trigger_id == 'confirm-button-1':
            if not ticker_1 or not start_date_1 or not end_date_1:
                return [data_store_1, data_store_2,
                        'Please select a ticker and both dates.', 'text-red-600 mt-2',
                        error_message_2, error_class_2] + selection_no_update + ['']
            try:
                csv_map = DATA_SOURCE_DROPDOWN
                future_csv = csv_map[ticker_1]
                performance_df = load_performance(ticker_1, start_date_1, end_date_1, PERFORMANCE_CSV)
                future_df = load_future(start_date_1, end_date_1, future_csv)
                data_store_1 = {
                    'performance': performance_df.to_dict('records'),
                    'future': future_df.to_dict('records'),
                    'ticker': ticker_1,
                }
                return [data_store_1, data_store_2, error_message_1, error_class_1,
                        error_message_2, error_class_2] + selection_no_update + ['']
            except Exception as e:
                return [data_store_1, data_store_2,
                        f"Error loading data: {str(e)}", 'text-red-600 mt-2',
                        error_message_2, error_class_2] + selection_no_update + ['']

        elif trigger_id == 'confirm-button-2':
            if not ticker_2 or not analysis_2 or not start_date_2 or not end_date_2:
                return [data_store_1, data_store_2,
                        error_message_1, error_class_1,
                        'Please select a ticker, analysis type, and both dates.', 'text-red-600 mt-2'] + selection_no_update + ['']
            try:
                start_date_2 = pd.to_datetime(start_date_2)
                end_date_2 = pd.to_datetime(end_date_2)
                if end_date_2 < start_date_2:
                    return [data_store_1, data_store_2,
                            error_message_1, error_class_1,
                            error_message_2, error_class_2] + selection_no_update + ['End date must be after start date.']
                
                csv_map = DATA_SOURCE_DROPDOWN
                future_csv = csv_map[ticker_2]
                performance_df = load_performance(ticker_2, start_date_2, end_date_2, PERFORMANCE_CSV)
                future_df = load_future(start_date_2, end_date_2, future_csv)
                if performance_df.empty:
                    return [data_store_1, data_store_2,
                            error_message_1, error_class_1,
                            'No trades found for the selected period.', 'text-red-600 mt-2'] + selection_no_update + ['']
                
                if 'ExitedAt' not in performance_df or 'PnL(Net)' not in performance_df:
                    return [data_store_1, data_store_2,
                            error_message_1, error_class_1,
                            'Invalid performance data: missing ExitedAt or PnL(Net).', 'text-red-600 mt-2'] + selection_no_update + ['']

                data_store_2 = {
                    'performance': performance_df.to_dict('records'),
                    'future': future_df.to_dict('records'),
                    'ticker': ticker_2,
                    'analysis': analysis_2,
                    'granularity': granularity_2 if category_2 == 'Period' else None,
                    'window': window_2 if category_2 == 'Rolling' else None,  # Add window only for Rolling
                    'start_date': start_date_2.isoformat(),
                    'end_date': end_date_2.isoformat(),
                }
                return [data_store_1, data_store_2, error_message_1, error_class_1,
                        error_message_2, error_class_2] + selection_no_update + ['']
            except Exception as e:
                return [data_store_1, data_store_2,
                        error_message_1, error_class_1,
                        f"Error loading data: {str(e)}", 'text-red-600 mt-2'] + selection_no_update + ['']

        raise dash.exceptions.PreventUpdate