import configparser
import pandas as pd
from src.utils.configparser import remove_comments_and_convert
from src.utils.logger import get_logger
import yfinance as yf
from datetime import datetime
import os



def get_future_data(logger, parameters_global, parameters_future):

    start_date = datetime.strptime(parameters_future['start_date'], '%Y-%m-%d')
    end_date = start_date + pd.Timedelta(days=1)  
    intervals = [interval.strip() for interval in parameters_future['interval'].split(',')]
    tickers = [tickers.strip() for tickers in parameters_future['tickers'].split(',')]

    for ticker in tickers:
        for interval in intervals:
            # Download data
            df = yf.download(tickers=ticker, start=start_date, end=end_date, interval=f"{interval}m")
            # Extract the date from the first index
            date_str = str(df.index[0].date())

            # Define the folder path
            folder_path = f"{parameters_global['future_data_path']}{ticker.split('.')[0]}"

            # Create the folder if it doesn't exist
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)

            # Save the data to a CSV file with the date in the filename within the specified folder
            file_name = f"{ticker.split('.')[0]}_{interval}min_data_{date_str}.csv"
            file_path = os.path.join(folder_path, file_name)

            df.to_csv(file_path)
            logger.info(f'{file_name} saved to {file_path}')



if __name__ == "__main__":
    # Read configuration from file
    
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    # Access preprocessing variables and remove comments
    parameters_global = remove_comments_and_convert(config, 'global')
    parameters_future = remove_comments_and_convert(config, 'future')
 
    # Create a logger
    logger = get_logger('data.log', parameters_global['log_path'])
    logger.info(f'==========New Line==========')
    print(f"Check log later in {parameters_global['log_path']}")

    # Call the get_future_data function with parsed arguments
    get_future_data(logger, parameters_global, parameters_future)
