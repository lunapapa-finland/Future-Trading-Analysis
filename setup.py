from setuptools import find_packages, setup

setup(
    name="dashboard",
    version="0.1.0",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    author='Lunapapa',
    license='MIT',
    install_requires=[
        "dash",
        "dash-bootstrap-components",
        "plotly",
        "flask",
        "werkzeug",
        "jinja2",
        "markdown2",
        "pandas",
        "numpy",
        "yfinance",
        "matplotlib",
        "scipy",
        "pandas_market_calendars",
        "pytz",
        "opencv-python",
        "cookiecutter",
    ],
)
