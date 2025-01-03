# Future Data Acquisition, Candlestick Plotting, and Intraday Performance Analysis

## Introduction
This project offers a robust suite of tools for financial data acquisition, candlestick plotting, and performance analysis tailored for intraday traders. It integrates data fetching from [yfinance](https://pypi.org/project/yfinance/) at custom intervals (e.g., every 1, 5 minutes) and leverages [plotly](https://plotly.com/) for dynamic visualizations. Key features include:

- **EMA 20, Pre-high, Pre-low, Pre-open, and Pre-close** support ONLY for Regular Trading Hours (RTH).
- **Replay functionality** from the first to the n th bar, enhancing analysis flexibility.
- **Compatibility with TopStepX** for downloading and visualizing intraday trading performance directly on the graph, including entry/exit points and P&L metrics.
- **Alternative to paid versions** of platforms like [TradingView](https://tradingview.com/), offering cost-effective solutions with similar functionalities.
- If you are using other platform other than TopStep, please open an issue and I will add more features based on demands.

Results are efficiently organized and saved in the `./html` directory for easy access.

![Screenshot](./img/sample1.png)
![Screenshot](./img/sample2.png)

## Getting Started
Begin by executing the following commands:

- `make`: Displays all available commands.
- `make data`: Retrieves data via yfinance.
- `make report`: Generates candlestick plots with specified intervals and includes performance statistics.
- `make clean`: Clears compiled files to ensure a clean setup.

## Configration
- You can find the all the configs in config.ini

## Setup Environment
Ensure proper tool functionality by setting up the correct environment using Conda:

```bash
conda create -f finance_env.yml
```

## TODO
1. UI Enhancement

## Contributing
Contributions are highly appreciated. Feel free to submit pull requests or open issues on GitHub to suggest improvements or new features. Your insights are invaluable in enhancing this tool for all users.

## License
This project is licensed under the [MIT License](LICENSE). For more information, please refer to the LICENSE file in the repository.

## Support
For assistance or inquiries, consult the `Issues` section on GitHub or contact me via email.