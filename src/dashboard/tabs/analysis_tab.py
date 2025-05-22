from dash import html, dcc
from dashboard.config.settings import DATA_SOURCE_DROPDOWN, ANALYSIS_DROPDOWN, DEFAULT_DATA_SOURCE, CURRENT_DATE, DEFAULT_ANALYSIS, GRANULARITY_OPTIONS, DEFAULT_GRANULARITY
import dash_bootstrap_components as dbc
from dashboard.tabs.base_tab import BaseTab
from dashboard.styles.styles import CLASS_CARD, CLASS_FLEX, CLASS_LABEL, CLASS_DROPDOWN, CLASS_DATEPICKER, CLASS_BUTTON, CLASS_ERROR

class AnalysisTab(BaseTab):
    def __init__(self):
        super().__init__(label='Statistical Analysis', value='tab-2', store_id='data-store-2')

    def get_criteria_section(self):
        categories = sorted(set(config['category'] for config in ANALYSIS_DROPDOWN.values()))
        category_options = [
            {'label': 'Period-Based' if cat == 'Period' else cat.replace('_', ' ').title(), 'value': cat}
            for cat in categories
        ]

        return dbc.Card([
            dbc.CardBody([
                html.Div([
                    html.Label('Ticket', className=CLASS_LABEL),
                    dcc.Dropdown(
                        id='ticket-selector-2',
                        options=[{'label': ticket, 'value': ticket} for ticket in DATA_SOURCE_DROPDOWN.keys()],
                        placeholder='Ticket Name',
                        className=CLASS_DROPDOWN,
                        value=DEFAULT_DATA_SOURCE
                    ),
                    html.Label('Category', className=CLASS_LABEL),
                    dcc.Dropdown(
                        id='category-selector-2',
                        options=category_options,
                        placeholder='Category',
                        className=CLASS_DROPDOWN,
                        value='Rolling'
                    ),
                    html.Label('Analysis', className=CLASS_LABEL),
                    dcc.Dropdown(
                        id='analysis-selector-2',
                        options=[],
                        placeholder='Analysis Type',
                        className=CLASS_DROPDOWN,
                        value=DEFAULT_ANALYSIS
                    ),
                    html.Label('Granularity', className=CLASS_LABEL, id='granularity-label-2', style={'display': 'none'}),
                    dcc.Dropdown(
                        id='granularity-selector-2',
                        options=GRANULARITY_OPTIONS,
                        placeholder='Granularity',
                        className=CLASS_DROPDOWN,
                        value=DEFAULT_GRANULARITY,
                        style={'display': 'none'}
                    ),
                    html.Label('Start Date', className=CLASS_LABEL),
                    dcc.DatePickerSingle(
                        id='start-date-picker-2',
                        placeholder='Start Date',
                        className=CLASS_DATEPICKER,
                        date=CURRENT_DATE
                    ),
                    html.Label('End Date', className=CLASS_LABEL),
                    html.P(id='end-date-picker-error-2', className=CLASS_ERROR),
                    dcc.DatePickerSingle(
                        id='end-date-picker-2',
                        placeholder='End Date',
                        className=CLASS_DATEPICKER,
                        date=CURRENT_DATE
                    ),
                    html.Button(
                        'Confirm',
                        id='confirm-button-2',
                        n_clicks=0,
                        className=CLASS_BUTTON
                    ),
                ], className=CLASS_FLEX),
                html.P(id='error-message-2', className=CLASS_ERROR),
            ])
        ], className=CLASS_CARD)