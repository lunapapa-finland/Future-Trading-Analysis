# Future Data Acquisition, Candlestick Plotting, and Intraday Performance Analysis

## Introduction
This project offers a robust suite of tools for financial data acquisition, candlestick plotting, and performance analysis tailored for intraday traders. It integrates data fetching from [yfinance](https://pypi.org/project/yfinance/) at custom intervals (e.g., every 1, 5 minutes) and leverages [plotly](https://plotly.com/) for dynamic visualizations. Key features include:

- **EMA 20, Pre-high, Pre-low, Pre-open, and Pre-close** support for Regular Trading Hours (RTH).
- **Replay functionality** from the first to the nth bar, enhancing analysis flexibility.
- **Compatibility with Tradovate and TopStepX** for downloading and visualizing intraday trading performance directly on the graph, including entry/exit points and P&L metrics.
- **Alternative to paid versions** of platforms like [TradingView](https://tradingview.com/), offering cost-effective solutions with similar functionalities.

Results are efficiently organized and saved in the `./html` directory for easy access.

![Screenshot](./img/sample.png)

## Getting Started
Begin by executing the following commands:

- `make`: Displays all available commands.
- `make data`: Retrieves data via yfinance.
- `make report`: Generates candlestick plots with specified intervals and includes performance summaries in `./html/Summary.md` for comprehensive HTML reports.
- `make clean`: Clears compiled files to ensure a clean setup.

## Configuration Settings
Configure the project settings through the `config.ini` file, detailed as follows:

### Global Configuration
- **log_path**: Sets the log file storage directory, defaulting to `./log`.
- **performance_data_path**: Specifies where performance data is stored, default from [Tradovate](https://www.tradovate.com/), default `./data/performance/`.
- **future_data_path**: Defines the directory for future data sourced from [yfinance](https://pypi.org/project/yfinance/), default `./data/future/`.

```ini
[global]
log_path = ./log
performance_data_path = ./data/performance/
future_data_path = ./data/future/
```

### Future Data Configuration
- **start_date**: Sets the initial date for data retrieval.
- **interval**: Defines the data intervals in minutes.
- **tickers**: Lists the ticker symbols for data acquisition.

```ini
[future]
start_date = 2024-04-22
interval = 1, 5
tickers = MESM24.CME, MNQM24.CME
```

### Report Configuration
- **date**: Specifies the date for analysis.
- **ticker**: Indicates the ticker symbol under analysis.
- **summary_md_file**: Path to the Markdown summary file.
- **html_path**: Directory for storing HTML reports.
- **html_src_path**: Directory for HTML source files.
- **template_path**: Location of Jinja2 template files for report generation.

```ini
[report]
date = 2024-04-12
ticker = MNQM24
summary_md_file = ./notes/Summary.md
html_path = ./html/
html_src_path = ./html/src/
template_path = ./src/jinja2/
```

Adjust these parameters in the `config.ini` file to tailor the data acquisition and analysis processes to your specific needs, optimizing the tool’s functionality across various trading scenarios.

## Setup Environment
Ensure proper tool functionality by setting up the correct environment using Conda:

```bash
conda create -f finance_env.yml
```

## Contributing
Contributions are highly appreciated. Feel free to submit pull requests or open issues on GitHub to suggest improvements or new features. Your insights are invaluable in enhancing this tool for all users.

## License
This project is licensed under the [MIT License](LICENSE). For more information, please refer to the LICENSE file in the repository.

## Support
For assistance or inquiries, consult the `Issues` section on GitHub or contact me via email.