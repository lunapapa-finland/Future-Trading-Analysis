def remove_comments_and_convert(config, section):
    def remove_comments(value):
        return value.split('#', 1)[0].strip()

    def convert_numeric(value):
        try:
            return int(value) if value.isdigit() else float(value)
        except ValueError:
            return value  # Return as is if not a valid numeric value

    return {key: convert_numeric(remove_comments(value)) for key, value in config.items(section)}