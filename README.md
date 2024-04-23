# Future Data Acquiring, Candlestick Plotting, and Performance Analysis

## Introduction
This project provides tools for retrieving stock data at specified intervals (e.g., every n minutes) from [yfinance](https://pypi.org/project/yfinance/) and conducting analyses tailored for intraday traders. The results are conveniently saved in the `./html` directory, providing easy access and organization.

![Screenshot](./img/sample.png)

## Getting Started
To utilize the tools in this project, follow the steps outlined below:

- `make` - Lists all available commands.
- `make data` - Downloads data via yfinance.
- `make report` - Generates future data in the form of candlestick plots with 5-minute intervals, and plots performance metrics. Users can also include summaries by adding them to `./note/Summary.md`, which can be included in the HTML report.
- `make clean` - Cleans all compiled files necessary for a fresh start.

## Setup Environment
Setting up the correct environment is crucial for ensuring that the tools function properly. Use Conda to install the necessary dependencies:

```bash
conda create -f finance_env.yml
```

This will set up a Conda environment named `finance_env` based on the specifications in the `finance_env.yml` file.

## Contributing
We highly value contributions from the community. If you have suggestions for improvements or new features, feel free to submit a pull request or open an issue on GitHub. Your insights and enhancements help make this tool more effective for everyone.

## License
This project adheres to the [MIT License](LICENSE). For more details, please review the LICENSE file in the repository.

## Support
For any issues or assistance, refer to the `Issues` section on the GitHub repository page or contact the project maintainers via email.

