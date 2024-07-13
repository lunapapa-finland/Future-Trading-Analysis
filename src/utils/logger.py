import logging
import os

def get_logger(log_file, filepath, level=logging.INFO, console=False):
    """
    Set up a logger with a file handler and optional console handler.

    Args:
        log_file (str): The name of the log file.
        filepath (str): The directory path to save the log file.
        level (int, optional): The logging level. Defaults to logging.INFO.
        console (bool, optional): If True, also output logs to the console. Defaults to False.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(__name__)

    # Prevent adding multiple handlers if logger is already configured
    if not logger.hasHandlers():
        logger.setLevel(level)

        # Create the target folder if it doesn't exist
        if not os.path.exists(filepath):
            os.makedirs(filepath)

        # Create a file handler and set the log file name
        log_file_path = os.path.join(filepath, log_file)
        file_handler = logging.FileHandler(log_file_path)

        # Create a formatter and set the formatter for the file handler
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)

        # Add the file handler to the logger
        logger.addHandler(file_handler)

        # Optionally add a console handler
        if console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    return logger
