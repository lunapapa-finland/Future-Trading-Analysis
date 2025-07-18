from dash import html, dcc
import dash_bootstrap_components as dbc
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, DEFAULT_DATA_SOURCE, CURRENT_DATE
from dashboard.tabs.base_tab import BaseTab
from dashboard.styles.styles import CLASS_CARD, CLASS_FLEX, CLASS_LABEL, CLASS_DROPDOWN, CLASS_DATEPICKER, CLASS_BUTTON, CLASS_ERROR

class TradingTab(BaseTab):
    def __init__(self):
        super().__init__(label='Trading Behavior', value='tab-1', store_id='data-store-1')

    def get_criteria_section(self):
        return dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Label('Ticker', className=CLASS_LABEL),
                    dcc.Dropdown(
                        id='ticker-selector-1',
                        options=[{'label': ticker, 'value': ticker} for ticker in DATA_SOURCE_DROPDOWN.keys()],
                        placeholder='Ticker Name',
                        className=CLASS_DROPDOWN,
                        value=DEFAULT_DATA_SOURCE
                    ),
                    html.Label('Start Date', className=CLASS_LABEL),
                    dcc.DatePickerSingle(
                        id='start-date-picker-1',
                        placeholder='Start Date',
                        className=CLASS_DATEPICKER,
                        date=CURRENT_DATE
                    ),
                    html.Label('End Date', className=CLASS_LABEL),
                    html.P(id='end-date-picker-error-1', className=CLASS_ERROR),
                    dcc.DatePickerSingle(
                        id='end-date-picker-1',
                        placeholder='End Date',
                        className=CLASS_DATEPICKER,
                        date=CURRENT_DATE
                    ),
                    html.Button(
                        'Confirm',
                        id='confirm-button-1',
                        n_clicks=0,
                        className=CLASS_BUTTON
                    ),
                    html.Button(
                        'Previous',
                        id='prev-button-1',
                        n_clicks=0,
                        className=CLASS_BUTTON
                    ),
                    html.Button(
                        'Next',
                        id='next-button-1',
                        n_clicks=0,
                        className=CLASS_BUTTON
                    ),
                    dcc.Store(
                        id='current-trace-index-1',
                        data=0
                    ),
                ], className=CLASS_FLEX),
                html.P(id='error-message-1', className=CLASS_ERROR),
            ])
        ], className=CLASS_CARD)