# app.py
from dash import Dash, html
from components.layout import create_layout
from config.settings import DEBUG

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[
    'https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css'
])

# Set layout (no data loaded initially)
app.layout = create_layout(app)

# Run server
if __name__ == '__main__':
    app.run(debug=DEBUG)