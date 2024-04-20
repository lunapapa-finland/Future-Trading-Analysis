import dash
from dash import html, dcc, Input, Output, callback
import plotly.express as px
import pandas as pd

def create_pie_chart():
    data = {'Results': ['Win', 'Loss', 'Draw'], 'Counts': [10, 5, 1]}
    df = pd.DataFrame(data)
    fig = px.pie(df, values='Counts', names='Results', title='Overall Trading Performance')
    return fig

app = dash.Dash(__name__)
app.layout = html.Div(children=[
    html.H1("Trading Report"),
    dcc.Graph(id='plot_statistic', figure=create_pie_chart()),
    dcc.Markdown(id='plot_summary', children='''
        ## Summary
        Detailed summary goes here. Use Markdown for formatted text.
        ''', style={'display': 'none'}),
    html.Button("Toggle Trading Details", id='toggle-trades', n_clicks=0),
    html.Button("Toggle Summary", id='toggle-summary', n_clicks=0)
])

@callback(
    Output('plot_statistic', 'style'),
    Input('toggle-trades', 'n_clicks')
)
def toggle_trading_details(n):
    return {'display': 'block' if n % 2 == 1 else 'none'}

@callback(
    Output('plot_summary', 'style'),
    Input('toggle-summary', 'n_clicks')
)
def toggle_summary(n):
    return {'display': 'block' if n % 2 == 1 else 'none'}

if __name__ == '__main__':
    app.run_server(debug=True)
