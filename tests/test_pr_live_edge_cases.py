import pytest
from unittest.mock import MagicMock, patch, mock_open
import pr_live
import json
import os

def test_config_manager_file_error():
    # Simulate IO error
    with patch('builtins.open', side_effect=OSError("Read failed")):
        cm = pr_live.ConfigManager("dummy.json")
        assert cm.config == {}

def test_config_manager_json_error():
    # Simulate bad JSON
    with patch('builtins.open', mock_open(read_data="{invalid: json")), \
         patch('os.path.exists', return_value=True):
         # json.load will raise JSONDecodeError
         with patch('json.load', side_effect=json.JSONDecodeError("msg", "doc", 0)):
            cm = pr_live.ConfigManager("dummy.json")
            assert cm.config == {}

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

def test_uptime_tracker_load_error():
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', side_effect=OSError("Read error")):
        tracker = pr_live.UptimeTracker()
        assert tracker.data == {}

def test_uptime_tracker_save_error():
    tracker = pr_live.UptimeTracker()
    tracker._dirty = True
    with patch('builtins.open', side_effect=OSError("Write error")):
        # Should catch exception and log it
        tracker.save()
        # _dirty should remain True if we wanted to retry, or False if we swallow. 
        # Current logic: it swallows exception and does NOT set _dirty=False
        assert tracker._dirty is True

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
    data = {"cluster_servers": [{"name": "S1"}]} # Missing rcon_ip etc
    with patch('builtins.open', mock_open(read_data=json.dumps(data))), \
         patch('os.path.exists', return_value=True):
        cm = pr_live.ConfigManager()
        servers = cm.get_server_configs()
        assert len(servers) == 0 # Should have skipped the invalid one
