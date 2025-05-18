from dash import Input, Output, State, dash, callback_context
from dashboard.data.load_data import load_performance, load_future
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, PERFORMANCE_CSV, DEFAULT_DATA_SOURCE, CURRENT_DATE, DEFAULT_ANALYSIS

def register_data_callbacks(app):
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

        data_store_1 = dash.no_update
        data_store_2 = dash.no_update
        error_message_1 = ''
        error_class_1 = 'text-red-600 mt-2 hidden'
        error_message_2 = ''
        error_class_2 = 'text-red-600 mt-2 hidden'
        # Default reset values for selection criteria
        selection_reset = [
            DEFAULT_DATA_SOURCE,  # ticket-selector-1
            CURRENT_DATE,        # start-date-picker-1
            CURRENT_DATE,        # end-date-picker-1
            DEFAULT_DATA_SOURCE,  # ticket-selector-2
            DEFAULT_ANALYSIS,    # analysis-selector-2
            CURRENT_DATE,        # start-date-picker-2
            CURRENT_DATE         # end-date-picker-2
        ]
        selection_no_update = [dash.no_update, dash.no_update, dash.no_update,
                               dash.no_update, dash.no_update, dash.no_update, dash.no_update]

        if trigger_id == 'tabs':
            data_store_1 = None
            data_store_2 = None
            return [data_store_1, data_store_2, error_message_1, error_class_1,
                    error_message_2, error_class_2] + selection_reset

        elif trigger_id == 'confirm-button-1':
            if not ticket_1 or not start_date_1 or not end_date_1:
                return [data_store_1, data_store_2,
                        'Please select a ticket and both dates.', 'text-red-600 mt-2',
                        error_message_2, error_class_2] + selection_no_update
            try:
                csv_map = DATA_SOURCE_DROPDOWN
                future_csv = csv_map[ticket_1]
                performance_df = load_performance(ticket_1, start_date_1, end_date_1, PERFORMANCE_CSV)
                future_df = load_future(start_date_1, end_date_1, future_csv)
                data_store_1 = {
                    'performance': performance_df.to_dict('records'),
                    'future': future_df.to_dict('records'),
                    'ticket': ticket_1,
                }
                return [data_store_1, data_store_2, error_message_1, error_class_1,
                        error_message_2, error_class_2] + selection_reset  # Reset after success
            except Exception as e:
                return [data_store_1, data_store_2,
                        f"Error loading data: {str(e)}", 'text-red-600 mt-2',
                        error_message_2, error_class_2] + selection_no_update

        elif trigger_id == 'confirm-button-2':
            if not ticket_2 or not analysis_2 or not start_date_2 or not end_date_2:
                return [data_store_1, data_store_2,
                        error_message_1, error_class_1,
                        'Please select a ticket, analysis type, and both dates.', 'text-red-600 mt-2'] + selection_no_update
            try:
                csv_map = DATA_SOURCE_DROPDOWN
                future_csv = csv_map[ticket_2]
                performance_df = load_performance(ticket_2, start_date_2, end_date_2, PERFORMANCE_CSV)
                future_df = load_future(start_date_2, end_date_2, future_csv)
                data_store_2 = {
                    'performance': performance_df.to_dict('records'),
                    'future': future_df.to_dict('records'),
                    'ticket': ticket_2,
                    'analysis': analysis_2,
                }
                return [data_store_1, data_store_2, error_message_1, error_class_1,
                        error_message_2, error_class_2] + selection_reset  # Reset after success
            except Exception as e:
                return [data_store_1, data_store_2,
                        error_message_1, error_class_1,
                        f"Error loading data: {str(e)}", 'text-red-600 mt-2'] + selection_no_update

        raise dash.exceptions.PreventUpdate