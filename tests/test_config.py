
import pytest
import os
import json
from src.common.config import ConfigManager

def test_load_config_defaults(tmp_path):
    config_file = tmp_path / "test_config.json"
    defaults = {"key": "value"}
    cm = ConfigManager(str(config_file), default_config=defaults)
    
    assert cm.get("key") == "value"
    assert os.path.exists(config_file)
    with open(config_file, 'r') as f:
        data = json.load(f)
        assert data == defaults

def test_load_existing_config(tmp_path):
    config_file = tmp_path / "test_config_exist.json"
    existing = {"existing": "data"}
    with open(config_file, 'w') as f:
        json.dump(existing, f)
        
    cm = ConfigManager(str(config_file))
    assert cm.get("existing") == "data"
