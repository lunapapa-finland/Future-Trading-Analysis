from dash import Dash, html, dcc, Output, Input, State
from dashboard.tabs.trading_tab import TradingTab
from dashboard.tabs.analysis_tab import AnalysisTab
from dashboard.callbacks.data_manager import register_data_callbacks
from dashboard.callbacks.display_manager import register_display_callbacks
from dashboard.config.settings import DEBUG_FLAG
from dashboard.components.sidebar import get_sidebar, get_sidebar_toggle
import dash_bootstrap_components as dbc

# Initialize Dash app with routes and requests pathname prefixes
app = Dash(
    __name__,
    external_stylesheets=[
        'https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css',
        'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css',  # Add Font Awesome
        dbc.themes.BOOTSTRAP,  # Add Bootstrap for better DBC compatibility
    ],
    routes_pathname_prefix='/',
    requests_pathname_prefix='/'
)

# Serve static assets (e.g., logo)
app.css.config.serve_locally = True

# Custom CSS to ensure OffCanvas width and behavior
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>Future Trading Analysis</title>
        {%favicon%}
        {%css%}
        <style>
            .offcanvas-custom {
                width: 250px !important;
                max-width: 250px !important;
                min-width: 250px !important;
            }
            .offcanvas-backdrop {
                opacity: 0.5 !important;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

tabs = [TradingTab(), AnalysisTab()]

# App layout with sidebar and main content
app.layout = html.Div([
    # Sidebar toggle button (positioned independently)
    get_sidebar_toggle(),
    # OffCanvas sidebar (does not affect main content)
    get_sidebar(),
    # Main content (unaffected by sidebar)
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

# Register callbacks
register_data_callbacks(app)
register_display_callbacks(app)

# Add callback to toggle the sidebar
@app.callback(
    Output('sidebar-offcanvas', 'is_open'),
    Input('sidebar-toggle', 'n_clicks'),
    State('sidebar-offcanvas', 'is_open'),
    prevent_initial_call=True
)
def toggle_sidebar(n_clicks, is_open):
    return not is_open

if __name__ == '__main__':
    app.run(debug=DEBUG_FLAG)