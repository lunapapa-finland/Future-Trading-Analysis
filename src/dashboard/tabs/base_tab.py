from dash import html, dcc
import dash_bootstrap_components as dbc

class BaseTab:
    def __init__(self, label, value, store_id):
        self.label = label
        self.value = value
        self.store_id = store_id

    def get_criteria_section(self):
        raise NotImplementedError("Criteria section must be implemented by subclass")

    def get_display_section(self):
        return dbc.Card([
            dbc.CardBody(id=f'{self.value}-section-2-content')
        ], className='mb-4')