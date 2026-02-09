"""
Test suite for Configuration Manager - validates config loading and validation.
"""
import pytest
import json
import os
from pathlib import Path
from patchraptor.config import ConfigManager


class TestConfigLoading:
    """Test configuration file loading."""
    
    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD\\\\steamcmd.exe",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": [
                {
                    "name": "TheIsland",
                    "display_name": "The Island",
                    "map_name": "TheIsland_WP",
                    "rcon_port": 27020,
                    "rcon_password": "test123",
                    "rcon_ip": "127.0.0.1",
                    "start_command": "C:\\\\start.bat",
                    "log_dir": "C:\\\\logs"
                }
            ]
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        
        # Use .get() method instead of attributes
        assert config.get("bot_token") == "test_token"
        assert config.get("channel_id") == "123456789"
        assert len(config.get("cluster_servers")) == 1
        assert config.get("cluster_servers")[0]["name"] == "TheIsland"
    
    def test_missing_config_file_raises_error(self):
        """Test that missing config file raises error."""
        with pytest.raises(FileNotFoundError):
            ConfigManager("nonexistent_config.json")
    
    def test_invalid_json_raises_error(self, tmp_path):
        """Test that invalid JSON raises error."""
        config_file = tmp_path / "bad_config.json"
        config_file.write_text("{ invalid json }")
        
        with pytest.raises(ValueError):
            ConfigManager(str(config_file))


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_missing_required_field_raises_error(self, tmp_path):
        """Test that missing required fields raise errors."""
        config_data = {
            "bot_token": "test_token",
            # Missing channel_id and other required fields
            "server_dir": "C:\\\\ARK"
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        with pytest.raises(ValueError):
            ConfigManager(str(config_file))


class TestConfigMethods:
    """Test configuration methods."""
    
    def test_get_with_default(self, tmp_path):
        """Test getting config value with default."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": []
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
"""
Test suite for Configuration Manager - validates config loading and validation.
"""
import pytest
import json
import os
from pathlib import Path
from patchraptor.config import ConfigManager


class TestConfigLoading:
    """Test configuration file loading."""
    
    def test_load_valid_config(self, tmp_path):
        """Test loading a valid configuration file."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD\\\\steamcmd.exe",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": [
                {
                    "name": "TheIsland",
                    "display_name": "The Island",
                    "map_name": "TheIsland_WP",
                    "rcon_port": 27020,
                    "rcon_password": "test123",
                    "rcon_ip": "127.0.0.1",
                    "start_command": "C:\\\\start.bat",
                    "log_dir": "C:\\\\logs"
                }
            ]
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        
        # Use .get() method instead of attributes
        assert config.get("bot_token") == "test_token"
        assert config.get("channel_id") == "123456789"
        assert len(config.get("cluster_servers")) == 1
        assert config.get("cluster_servers")[0]["name"] == "TheIsland"
    
    def test_missing_config_file_raises_error(self):
        """Test that missing config file raises error."""
        with pytest.raises(FileNotFoundError):
            ConfigManager("nonexistent_config.json")
    
    def test_invalid_json_raises_error(self, tmp_path):
        """Test that invalid JSON raises error."""
        config_file = tmp_path / "bad_config.json"
        config_file.write_text("{ invalid json }")
        
        with pytest.raises(ValueError):
            ConfigManager(str(config_file))


class TestConfigValidation:
    """Test configuration validation."""
    
    def test_missing_required_field_raises_error(self, tmp_path):
        """Test that missing required fields raise errors."""
        config_data = {
            "bot_token": "test_token",
            # Missing channel_id and other required fields
            "server_dir": "C:\\\\ARK"
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        with pytest.raises(ValueError):
            ConfigManager(str(config_file))


class TestConfigMethods:
    """Test configuration methods."""
    
    def test_get_with_default(self, tmp_path):
        """Test getting config value with default."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": []
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        
        # Test get with existing key
        assert config.get("bot_token") == "test_token"
        
        # Test get with non-existing key and default
        assert config.get("nonexistent_key", "default_value") == "default_value"


class TestFrozenMode:
    """Test frozen mode configuration."""
    
    def test_frozen_mode_config_path(self, tmp_path):
        """Test config path adjustment in frozen mode."""
        from unittest.mock import patch, MagicMock
        
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": []
        }
        
        # Create config in temp directory
        exe_dir = tmp_path / "app"
        exe_dir.mkdir()
        config_file = exe_dir / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        # Mock frozen mode
        with patch('sys.frozen', True, create=True), \
             patch('sys.executable', str(exe_dir / "app.exe")):
            config = ConfigManager()
            
            # Should use config.json next to executable
            assert config.config_file == str(exe_dir / "config.json")


class TestLoadConfigExceptions:
    """Test exception handling in _load_config."""
    
    def test_load_config_unexpected_exception(self, tmp_path):
        """Test generic exception handling."""
        from unittest.mock import patch, MagicMock
        
        config_file = tmp_path / "config.json"
        config_file.write_text('{"bot_token": "test"}')
        
        # Mock open to raise unexpected exception
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with pytest.raises(PermissionError):
                ConfigManager(str(config_file))


class TestSaveConfig:
    """Test configuration saving."""
    
    def test_save_config_success(self, tmp_path):
        """Test successful config save."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": []
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        
        # Modify config
        config.config["bot_token"] = "new_token"
        
        # Save
        config.save()
        
        # Verify saved
        with open(config_file, 'r') as f:
            saved_data = json.load(f)
            assert saved_data["bot_token"] == "new_token"
    
    def test_save_config_failure(self, tmp_path):
        """Test save failure exception handling."""
        from unittest.mock import patch
        
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": []
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        
        # Mock open to raise exception during save
        with patch('builtins.open', side_effect=PermissionError("Access denied")):
            with pytest.raises(RuntimeError, match="Failed to save config"):
                config.save()


class TestGetServerConfigs:
    """Test server configuration parsing."""
    
    def test_get_server_configs_single_server(self, tmp_path):
        """Test parsing single server config."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": [
                {
                    "name": "TheIsland",
                    "display_name": "The Island",
                    "map_name": "TheIsland_WP",
                    "rcon_port": 27020,
                    "rcon_password": "secret123",
                    "rcon_ip": "127.0.0.1",
                    "start_command": "C:\\\\start.bat",
                    "log_dir": "C:\\\\logs"
                }
            ]
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        servers = config.get_server_configs()
        
        assert len(servers) == 1
        assert servers[0].name == "TheIsland"
        assert servers[0].display_name == "The Island"
        assert servers[0].rcon_port == 27020
        assert servers[0].log_dir == "C:\\\\logs"
    
    def test_get_server_configs_multiple_servers(self, tmp_path):
        """Test parsing multiple servers."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": [
                {
                    "name": "TheIsland",
                    "rcon_port": 27020,
                    "rcon_password": "secret1",
                    "rcon_ip": "127.0.0.1",
                    "start_command": "C:\\\\start1.bat",
                    "log_dir": "C:\\\\logs1"
                },
                {
                    "name": "TheCenter",
                    "rcon_port": 27021,
                    "rcon_password": "secret2",
                    "rcon_ip": "127.0.0.1",
                    "start_command": "C:\\\\start2.bat",
                    "log_dir": "C:\\\\logs2"
                }
            ]
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        servers = config.get_server_configs()
        
        assert len(servers) == 2
        assert servers[0].name == "TheIsland"
        assert servers[1].name == "TheCenter"
    
    def test_get_server_configs_with_defaults(self, tmp_path):
        """Test default value handling."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": [
                {
                    "name": "TheIsland",
                    # Missing display_name, map_name, install_dir
                    "rcon_port": 27020,
                    "rcon_password": "secret",
                    "rcon_ip": "127.0.0.1",
                    "start_command": "C:\\\\start.bat",
                    "log_dir": "C:\\\\logs"
                }
            ]
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        servers = config.get_server_configs()
        
        assert servers[0].display_name == "TheIsland"  # Defaults to name
        assert servers[0].map_name == ""  # Defaults to empty
        assert servers[0].install_dir == "C:\\\\ARK"  # Defaults to server_dir
    
    def test_get_server_configs_empty_list(self, tmp_path):
        """Test empty server list."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": []
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        servers = config.get_server_configs()
        
        assert len(servers) == 0
    
    def test_get_server_configs_log_dir_fallback(self, tmp_path):
        """Test log_dir fallback to server_log_dir."""
        config_data = {
            "bot_token": "test_token",
            "channel_id": "123456789",
            "server_dir": "C:\\\\ARK",
            "steamcmd_path": "C:\\\\SteamCMD",
            "rcon_tool": "C:\\\\rcon.exe",
            "app_id": "2430930",
            "cluster_servers": [
                {
                    "name": "TheIsland",
                    "rcon_port": 27020,
                    "rcon_password": "secret",
                    "rcon_ip": "127.0.0.1",
                    "start_command": "C:\\\\start.bat",
                    # Using server_log_dir instead of log_dir
                    "server_log_dir": "C:\\\\old_logs"
                }
            ]
        }
        
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(config_data))
        
        config = ConfigManager(str(config_file))
        servers = config.get_server_configs()
        
        assert servers[0].log_dir == "C:\\\\old_logs"