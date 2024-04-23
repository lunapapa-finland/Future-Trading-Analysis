import logging
import os 

def get_logger(log_file, filepath):
    # Set up the logger
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Create the target folder if it doesn't exist
    if not os.path.exists(filepath):
        os.makedirs(filepath)

    # Create a file handler and set the log file name
    log_file = filepath + '/' + log_file
    file_handler = logging.FileHandler(log_file)

    # Create a formatter and set the formatter for the file handler
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)

    # Add the file handler to the logger
    logger.addHandler(file_handler)


    return logger