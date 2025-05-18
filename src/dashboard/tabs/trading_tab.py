from dash import html, dcc
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, DEFAULT_DATA_SOURCE, CURRENT_DATE
import dash_bootstrap_components as dbc
from dashboard.tabs.base_tab import BaseTab
from dashboard.styles.styles import CLASS_CARD, CLASS_FLEX, CLASS_LABEL, CLASS_DROPDOWN, CLASS_DATEPICKER, CLASS_BUTTON, CLASS_ERROR

class TradingTab(BaseTab):
    def __init__(self):
        super().__init__(label='Trading Behavior', value='tab-1', store_id='data-store-1')

    def get_criteria_section(self):
        return dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Label('Ticket', className=CLASS_LABEL),
                    dcc.Dropdown(
                        id='ticket-selector-1',
                        options=[{'label': ticket, 'value': ticket} for ticket in DATA_SOURCE_DROPDOWN.keys()],
                        placeholder='Ticket Name',
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
                ], className=CLASS_FLEX),
                html.P(id='error-message-1', className=CLASS_ERROR),
            ])
        ], className=CLASS_CARD)