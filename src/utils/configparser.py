def remove_comments_and_convert(config, section):
    """
    Removes comments from config values and converts them to appropriate numeric types if possible.

    Args:
        config (configparser.ConfigParser): The config parser object.
        section (str): The section of the config file to process.

    Returns:
        dict: A dictionary with keys and processed values from the config section.
    """
    def remove_comments(value):
        """
        Remove comments from a configuration value.
        
        Args:
            value (str): The configuration value.

        Returns:
            str: The value without comments.
        """
        return value.split('#', 1)[0].strip()

    def convert_numeric(value):
        """
        Convert a value to an int or float if possible.
        
        Args:
            value (str): The value to convert.

        Returns:
            int/float/str: The converted value, or the original value if conversion is not possible.
        """
        try:
            return int(value) if value.isdigit() else float(value)
        except ValueError:
            return value  # Return as is if not a valid numeric value

    processed_config = {}
    for key, value in config.items(section):
        cleaned_value = remove_comments(value)
        processed_value = convert_numeric(cleaned_value)
        processed_config[key] = processed_value

    return processed_config
