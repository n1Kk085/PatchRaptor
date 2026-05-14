import pytest
from unittest.mock import MagicMock, patch, mock_open
import json
import os
import sys

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pr_live

# Valid minimal config for validation tests
VALID_CONFIG = {
    "bot_token": "token",
    "channel_id": 123,
    "app_id": 456,
    "steamcmd_path": "C:\\steamcmd.exe",
    "server_dir": "C:\\server",
    "rcon_tool": "C:\\rcon.exe",
    "cluster_servers": []
}

def test_config_manager_file_error():
    # Simulate IO error
    with patch('builtins.open', side_effect=OSError("Read failed")):
        with pytest.raises(OSError):
            pr_live.ConfigManager("dummy.json")

def test_config_manager_json_error():
    # Simulate bad JSON
    with patch('builtins.open', mock_open(read_data="{invalid: json")), \
         patch('os.path.exists', return_value=True):
         # json.load will raise JSONDecodeError
         with patch('json.load', side_effect=json.JSONDecodeError("msg", "doc", 0)):
            with pytest.raises(ValueError, match="Invalid JSON"):
                pr_live.ConfigManager("dummy.json")

def test_map_resolver_dir_missing():
    with patch('os.path.exists', return_value=False):
        resolver = pr_live.MapImageResolver('/tmp/missing')
        url = resolver.get_image_url('AnyMap')
        assert url == '/static/maps/default.jpg'

def test_map_resolver_os_error():
    with patch('os.path.exists', return_value=True), \
         patch('os.listdir', side_effect=OSError("Perm denied")):
        resolver = pr_live.MapImageResolver('/static')
        url = resolver.get_image_url('AnyMap')
        assert url == '/static/maps/default.jpg'

def test_main_fatal_error():
    # Test that main() catches fatal exceptions during init
    with patch('pr_live.PatchRaptorPanel', side_effect=Exception("Fatal Init Error")), \
         patch('sys.exit') as mock_exit:
        pr_live.main()
        mock_exit.assert_called_with(1)

def test_webpanel_config_load_error():
    # Mock ConfigManager so __init__ proceeds until _load_webpanel_config
    with patch('pr_live.ConfigManager'), \
         patch('builtins.open', side_effect=Exception("Config Missing")):
         
        # PatchRaptorPanel() calls _load_webpanel_config in __init__
        # It calls sys.exit(1) on failure.
        with pytest.raises(SystemExit) as excinfo:
             pr_live.PatchRaptorPanel()
        
        assert excinfo.value.code == 1

def test_server_config_invalid_key():
    # Test handling of partial/invalid server config in ConfigManager
    # The current CoreConfigManager RAISES KeyError if keys are missing in get_server_configs
    data = VALID_CONFIG.copy()
    data["cluster_servers"] = [{"name": "S1", "rcon_ip": "127.0.0.1"}] 
    
    with patch('builtins.open', mock_open(read_data=json.dumps(data))), \
         patch('os.path.exists', return_value=True):
        cm = pr_live.ConfigManager()
        
        # Manually inject an invalid server entry
        cm.config["cluster_servers"] = [{"name": "S1"}] # No rcon_ip
        
        # We expect a KeyError because the core ConfigManager doesn't handle it gracefully yet
        with pytest.raises(KeyError):
            cm.get_server_configs()
