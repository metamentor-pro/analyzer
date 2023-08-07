"""
This module provides functionality for reading a configuration file in YAML format and storing the configuration data in a dictionary.

It contains one main function:
- read_config: This function reads a configuration file in YAML format and returns a dictionary containing the configuration data.
"""

import yaml
from typing import Any, Dict


def read_config(path: str) -> Dict[str, Any]:
    """
    Reads a configuration file in YAML format.

    Parameters:
    path (str): The path to the configuration file.

    Returns:
    dict: A dictionary containing the configuration data.

    Raises:
    FileNotFoundError: If the configuration file does not exist.
    yaml.YAMLError: If the configuration file is not a valid YAML file.
    """
    try:
        if not path.endswith('.yaml'):
            raise ValueError(f"{path} is not a YAML file")
        with open(path, 'r') as file:
            config_data = yaml.safe_load(file)
        print(f"{path} is now current config")
        if 'bot_name' not in config_data or 'bot_api' not in config_data:
            raise ValueError("Missing required configuration data")
        return config_data
    except FileNotFoundError:
        print(f"{path} file not found")
        raise
    except yaml.YAMLError as e:
        print(f"Error parsing {path}: {e}")
        raise


config = read_config('config.yaml')
