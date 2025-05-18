from dash import Dash, html, dcc
from dashboard.tabs.trading_tab import TradingTab
from dashboard.tabs.analysis_tab import AnalysisTab
from dashboard.callbacks.data_manager import register_data_callbacks
from dashboard.callbacks.display_manager import register_display_callbacks
from dashboard.config.settings import DEBUG_FLAG

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[
    'https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css'
])

tabs = [TradingTab(), AnalysisTab()]

app.layout = html.Div([
    html.Div([
        dcc.Tabs([
            dcc.Tab(label=tab.label, value=tab.value, children=[
                html.Div([
                    tab.get_criteria_section(),
                    tab.get_display_section()
                ])
            ]) for tab in tabs
        ], id='tabs', value='tab-1', className='mb-6'),
        dcc.Store(id='data-store-1'),
        dcc.Store(id='data-store-2'),
    ], className='container mx-auto p-4 bg-gray-50 min-h-screen')
])

register_data_callbacks(app)
register_display_callbacks(app)

if __name__ == '__main__':
    app.run(debug=DEBUG_FLAG)