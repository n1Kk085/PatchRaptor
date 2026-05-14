"""
Test suite for Player Manager - validates event-driven player tracking and ban management.
"""
import pytest
import datetime
import asyncio
import os
import sys
import json
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

from patchraptor.player_manager import PlayerManager
from patchraptor.models import ServerConfig

@pytest.fixture
def mock_servers():
    """Mock server list."""
    server = ServerConfig(
        name="TestServer",
        display_name="Test Server",
        map_name="TheIsland_WP",
        server_log_path="C:\\logs\\ShooterGame.log",
        rcon_ip="127.0.0.1",
        rcon_port=27015,
        rcon_password="password",
        start_command="start.bat",
        install_dir="C:\\ark",
        server_save_path="C:\\ark\\Saved"
    )
    return [server]

@pytest.fixture
def player_manager(mock_servers):
    """Create a PlayerManager instance with mock server."""
    return PlayerManager(servers=mock_servers, read_only=False)

@pytest.fixture
def mock_telemetry_manager():
    """Mock TelemetryManager with broadcaster."""
    tm = MagicMock()
    tm.broadcaster = MagicMock()
    tm.broadcaster.register_listener = MagicMock()
    return tm

class TestInit:
    """Test initialization logic."""
    
    @pytest.mark.asyncio
    async def test_initialize(self, player_manager, mock_telemetry_manager):
        """Test async initialization sequence and Telemetry registration."""
        player_manager._load_bans = AsyncMock()
        
        with patch('patchraptor.service_locator.ServiceLocator.get', return_value=mock_telemetry_manager):
            await player_manager.initialize()
            
            player_manager._load_bans.assert_called_once()
            # Verify listeners registered
            assert mock_telemetry_manager.broadcaster.register_listener.call_count == 2
            mock_telemetry_manager.broadcaster.register_listener.assert_any_call("join", player_manager.handle_on_player_join)
            mock_telemetry_manager.broadcaster.register_listener.assert_any_call("leave", player_manager.handle_on_player_leave)

    @pytest.mark.asyncio
    async def test_initialize_read_only(self, mock_telemetry_manager):
        """Test initialization in read-only mode."""
        pm = PlayerManager([], read_only=True)
        pm._load_bans = AsyncMock()
        
        with patch('patchraptor.service_locator.ServiceLocator.get', return_value=mock_telemetry_manager):
            await pm.initialize()
            pm._load_bans.assert_not_called()
            assert mock_telemetry_manager.broadcaster.register_listener.called

class TestEventHandlers:
    """Test response to Telemetry events."""

    @pytest.mark.asyncio
    async def test_handle_on_player_join(self, player_manager):
        """Test storing player data on join event."""
        event_data = {
            "server": "TestServer",
            "name": "SurvivorOne",
            "id": "12345678901234567890123456789012"
        }
        
        await player_manager.handle_on_player_join(event_data)
        
        assert "12345678901234567890123456789012" in player_manager.active_players["TestServer"]
        info = player_manager.active_players["TestServer"]["12345678901234567890123456789012"]
        assert info["name"] == "SurvivorOne"
        assert isinstance(info["join_time"], datetime.datetime)

    @pytest.mark.asyncio
    async def test_handle_on_player_join_banned(self, player_manager):
        """Test that banned players are rejected on join."""
        player_manager.banned_players.add("BannedID")
        
        event_data = {
            "server": "TestServer",
            "name": "BadGuy",
            "id": "BannedID"
        }
        
        await player_manager.handle_on_player_join(event_data)
        assert "BannedID" not in player_manager.active_players["TestServer"]

    @pytest.mark.asyncio
    async def test_handle_on_player_leave(self, player_manager):
        """Test removing player data on leave event."""
        uid = "123_uid"
        player_manager.active_players["TestServer"][uid] = {
            "name": "SurvivorOne",
            "join_time": datetime.datetime.now()
        }
        
        event_data = {
            "server": "TestServer",
            "id": uid
        }
        
        await player_manager.handle_on_player_leave(event_data)
        assert uid not in player_manager.active_players["TestServer"]

    @pytest.mark.asyncio
    async def test_handle_events_paused(self, player_manager):
        """Test that events are ignored when paused."""
        player_manager.pause()
        
        event_data = {
            "server": "TestServer",
            "name": "SurvivorOne",
            "id": "123_uid"
        }
        
        await player_manager.handle_on_player_join(event_data)
        assert "123_uid" not in player_manager.active_players["TestServer"]

class TestBanManagement:
    """Test player ban functionality."""
    
    @pytest.mark.asyncio
    async def test_ban_player(self, player_manager):
        """Test banning a player and removing them if online."""
        player_manager._save_bans = AsyncMock()
        uid = "123_uid"
        player_manager.active_players["TestServer"][uid] = {"name": "BadGuy", "join_time": datetime.datetime.now()}
        
        assert await player_manager.ban_player("BadGuy") is True
        assert "BadGuy" in player_manager.banned_players
        assert uid not in player_manager.active_players["TestServer"]
        player_manager._save_bans.assert_called_once()

    @pytest.mark.asyncio
    async def test_unban_player(self, player_manager):
        """Test unbanning a player."""
        player_manager._save_bans = AsyncMock()
        player_manager.banned_players.add("GoodGuy")
        
        assert await player_manager.unban_player("GoodGuy") is True
        assert "GoodGuy" not in player_manager.banned_players
        player_manager._save_bans.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_bans(self, player_manager):
        """Test loading bans from file."""
        mock_data = '["Banned1", "Banned2"]'
        with patch('builtins.open', mock_open(read_data=mock_data)), \
             patch('os.path.exists', return_value=True):
            
            await player_manager._load_bans()
            assert "Banned1" in player_manager.banned_players
            assert len(player_manager.banned_players) == 2

class TestStateManagement:
    """Test player state reporting and cleanup."""

    @pytest.mark.asyncio
    async def test_get_total_players(self, player_manager):
        """Test getting total player counts and details."""
        player_manager.active_players["TestServer"] = {
            "uid1": {"name": "P1", "join_time": datetime.datetime.now() - datetime.timedelta(minutes=10)},
            "uid2": {"name": "P2", "join_time": datetime.datetime.now() - datetime.timedelta(minutes=5)}
        }
        
        total, details = await player_manager.get_total_players()
        
        assert total == 2
        assert len(details["Test Server"]) == 2
        assert details["Test Server"][0]["name"] in ["P1", "P2"]
        assert "10m" in [p["session_time"] for p in details["Test Server"]]

    @pytest.mark.asyncio
    async def test_cleanup_old_player_data(self, player_manager):
        """Test removing stale player sessions (e.g. ghost players)."""
        stale_time = datetime.datetime.now() - datetime.timedelta(hours=25)
        player_manager.active_players["TestServer"]["stale"] = {"name": "Old", "join_time": stale_time}
        player_manager.active_players["TestServer"]["fresh"] = {"name": "New", "join_time": datetime.datetime.now()}
        
        await player_manager.cleanup_old_player_data(max_session_time_hours=24)
        
        assert "stale" not in player_manager.active_players["TestServer"]
        assert "fresh" in player_manager.active_players["TestServer"]

    @pytest.mark.asyncio
    async def test_clear_server_players(self, player_manager):
        """Test clearing player data."""
        player_manager.active_players["TestServer"]["uid"] = {}
        await player_manager.clear_server_players("TestServer")
        assert len(player_manager.active_players["TestServer"]) == 0

class TestValidation:
    """Test validation logic."""

    def test_validate_player_data(self, player_manager):
        """Test identity validation."""
        valid_id = "12345678901234567890123456789012"
        assert player_manager._validate_player_data("ValidName", valid_id) is True
        assert player_manager._validate_player_data("A", valid_id) is False # Too short
        assert player_manager._validate_player_data("Server", valid_id) is False # Reserved

    def test_validate_player_name(self, player_manager):
        """Test name validation helper."""
        assert player_manager._validate_player_name("Survivor") is True
        assert player_manager._validate_player_name("System") is False

class TestUtilityMethods:
    """Test pause/resume and other utilities."""

    def test_pause_resume(self, player_manager):
        """Test pause state control."""
        player_manager.pause()
        assert player_manager._paused is True
        player_manager.resume()
        assert player_manager._paused is False
