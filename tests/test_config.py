import os
import json
import pytest
from unittest.mock import patch, mock_open
from patchraptor.config import ConfigManager, ServerConfig

# Sample config data
SAMPLE_CONFIG = {
    "bot_token": "test_token",
    "channel_id": "123456",
    "app_id": "376030",
    "steamcmd_path": "steamcmd.exe",
    "server_dir": "servers/",
    "cluster_servers": [],
    "rcon_tool": "rcon.exe"
}

@pytest.fixture
def mock_config_file(tmp_path):
    """Create a temporary config file"""
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps(SAMPLE_CONFIG))
    return str(config_file)

def test_load_config(mock_config_file):
    """Test loading configuration from a file"""
    manager = ConfigManager(config_file=mock_config_file)
    assert manager.get("bot_token") == "test_token"
    assert manager.get("app_id") == "376030"

def test_config_validation_failure():
    """Test validation raises error on missing keys"""
    invalid_config = {"bot_token": "missing_others"}
    with patch("builtins.open", mock_open(read_data=json.dumps(invalid_config))):
        with pytest.raises(ValueError, match="Missing required config keys"):
            ConfigManager(config_file="dummy.json")

def test_save_config(tmp_path):
    """Test saving configuration"""
    config_file = tmp_path / "config.json"
    # Create valid initial config
    config_file.write_text(json.dumps(SAMPLE_CONFIG))
    
    manager = ConfigManager(config_file=str(config_file))
    
    # Modify config content directly
    manager.config["new_setting"] = "saved_value"
    manager.save()
    
    # Verify file content
    with open(config_file, "r") as f:
        saved_data = json.load(f)
    assert saved_data["new_setting"] == "saved_value"

def test_server_config_parsing(mock_config_file):
    """Test parsing of server configurations"""
    server_data = {
        "name": "TheIsland",
        "rcon_port": 27020,
        "rcon_password": "123",
        "rcon_ip": "127.0.0.1",
        "start_command": "ShooterGameServer.exe",
        "server_save_path": "/save/path",
        "server_log_path": "/log/path"
    }
    # Update config file with server data
    with open(mock_config_file, "w") as f:
        cfg = SAMPLE_CONFIG.copy()
        cfg["cluster_servers"] = [server_data]
        json.dump(cfg, f)
        
    manager = ConfigManager(config_file=mock_config_file)
    servers = manager.get_server_configs()
    
    assert len(servers) == 1
    assert servers[0].name == "TheIsland"
    assert servers[0].rcon_port == 27020
    assert servers[0].rcon_ip == "127.0.0.1"  # Default
