# app.py
from dash import Dash, html
from components.layout import create_layout
from data.load_data import load_data

# Initialize Dash app
app = Dash(__name__, external_stylesheets=[
    'https://cdn.jsdelivr.net/npm/tailwindcss@2.2.19/dist/tailwind.min.css'
])
# Load data once at startup
data = load_data('../../data/performance/Combined_Performance_with_Streaks.csv')

# Set layout and register callbacks
app.layout = create_layout(app, data)

# Run server
if __name__ == '__main__':
    app.run(debug=True)