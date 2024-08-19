from importlib.resources import files

import yaml

CONFIG_PATH = files("configs").joinpath("warcli.yaml")


class KeyNotSetError(Exception):
    """Custom exception raised when trying to access a key that is not set."""

    def __init__(self, key):
        self.key = key
        self.message = f"Key '{key}' is not set in the configuration."
        super().__init__(self.message)


class Config:
    def __init__(self):
        self._load_config()

    def _load_config(self):
        with open(CONFIG_PATH) as file:
            self.config = yaml.safe_load(file)

    def _save_config(self):
        cleaned_config = {k: (v if v is not None else '') for k, v in self.config.items()}
        with open(CONFIG_PATH, "w") as file:
            yaml.safe_dump(cleaned_config, file)

    def read(self, key):
        if key in self.config and (self.config[key] is not None and self.config[key] != ''):
            return self.config[key]
        else:
            raise KeyNotSetError(key)

    def write(self, key, value):
        if key in self.config:
            if self.config[key] is None or self.config[key] == '':
                self.config[key] = value
                self._save_config()
            else:
                raise ValueError(f"Key '{key}' is already set. Cannot overwrite.")
        else:
            raise KeyError(f"Key '{key}' does not exist in the configuration.")
