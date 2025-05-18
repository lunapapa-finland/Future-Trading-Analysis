from dash import html, dcc
import dash_bootstrap_components as dbc

def get_sidebar():
    """
    Returns an OffCanvas sidebar component with a logo and information.

    The sidebar floats from the left and does not affect the main content layout.
    """
    # Logo (use local logo or fallback to placeholder)
    logo = html.Img(
        src='../static/assets/logo.png',  # Local logo; place in dashboard/static/assets/
        alt='Logo',
        style={'width': '100px', 'margin': '10px auto', 'display': 'block'}
    )

    # Sidebar content layout using dbc.Container and dbc.Row for structure
    sidebar_content = dbc.Container(
        [
            dbc.Row([dbc.Col(logo)]),  # Logo centered at the top
            dbc.Row([dbc.Col(html.H4('Future Trading Analysis', className='text-lg font-bold mt-4 text-center'))]),
            dbc.Row([dbc.Col(html.P('Version 0.1', className='text-sm text-gray-600 text-center'))]),
            dbc.Row([dbc.Col(html.P('Track and analyze your trading performance with advanced metrics.', className='text-sm mt-2 text-center'))]),
            dbc.Row([dbc.Col(dcc.Link('Learn More', href='#', className='text-blue-500 hover:text-blue-700 mt-4 block text-center'))]),
        ],
        fluid=True
    )

    # OffCanvas component
    sidebar = dbc.Offcanvas(
        sidebar_content,
        id='sidebar-offcanvas',
        title='Menu',
        is_open=False,
        placement='start',  # Slide in from the left
        style={'width': '250px'},  # Fixed width
        className='offcanvas-custom',  # Custom class for additional styling
        backdrop=True,  # Adds a backdrop to prevent interaction with the main content while open
    )
    return sidebar

def get_sidebar_toggle():
    """
    Returns a button to toggle the OffCanvas sidebar.
    """
    return html.Button(
        html.I(className='fas fa-bars'),  # Hamburger icon (requires Font Awesome)
        id='sidebar-toggle',
        n_clicks=0,
        className='p-2 bg-gray-200 rounded hover:bg-gray-300 fixed top-4 left-4 z-10'  # Fixed position
    )

