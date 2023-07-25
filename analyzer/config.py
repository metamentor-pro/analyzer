import yaml


def read_config(path):
    try:
        with open(path, "r") as file:
            config_data = yaml.safe_load(file)
        print(f"{path} is now current config")
        return config_data
    except FileNotFoundError:
        print(f"{path} file not found")
config = read_config('config.yaml')