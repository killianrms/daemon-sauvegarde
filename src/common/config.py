
import json
import os
import logging
from pathlib import Path

class ConfigManager:
    """Base class for configuration management"""
    
    def __init__(self, config_file, default_config=None):
        self.config_file = config_file
        self.default_config = default_config or {}
        self.config = self.load_config()

    def load_config(self):
        """Loads configuration from JSON file or creates it with defaults"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Error loading config file {self.config_file}: {e}")
                return self.default_config
        else:
            if self.default_config:
                self.save_config(self.default_config)
            return self.default_config

    def save_config(self, config=None):
        """Saves configuration to JSON file"""
        if config:
            self.config = config
        
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logging.error(f"Error saving config file {self.config_file}: {e}")

    def get(self, key, default=None):
        """Gets a configuration value"""
        return self.config.get(key, default)
    
    def set(self, key, value):
        """Sets a configuration value and saves"""
        self.config[key] = value
        self.save_config()
