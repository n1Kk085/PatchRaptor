"""
Shared test fixtures and utilities for PatchRaptor tests.
"""
import pytest
import asyncio
from pathlib import Path


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary directory for config files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def mock_server_config():
    """Provide a mock server configuration."""
    return {
        "name": "TestServer",
        "display_name": "Test Server",
        "map_name": "TheIsland_WP",
        "rcon_port": 27020,
        "rcon_password": "test_password",
        "game_port": 7777,
        "query_port": 27015
    }


@pytest.fixture
def mock_config_data(mock_server_config):
    """Provide a complete mock configuration."""
    return {
        "discord_token": "test_token_123",
        "channel_id": "123456789012345678",
        "server_directory": "C:\\\\ARK\\\\Servers",
        "steamcmd_path": "C:\\\\SteamCMD\\\\steamcmd.exe",
        "servers": [mock_server_config]
    }





# Test utilities

def assert_no_secrets_in_string(text: str, secrets: list[str]):
    """Assert that none of the secrets appear in the text."""
    for secret in secrets:
        assert secret not in text, f"Secret '{secret}' found in output"


def create_mock_log_line(player_name: str, message: str, timestamp: str = "2026.02.03-12.00.00") -> str:
    """Create a mock ARK log line."""
    return f"[{timestamp}] {player_name}: {message}"
