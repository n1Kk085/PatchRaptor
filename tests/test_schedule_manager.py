"""
Test suite for Schedule Manager - validates scheduled event execution and persistence.
"""
import pytest
import asyncio
import json
import datetime
from unittest.mock import Mock, MagicMock, patch, AsyncMock, mock_open
from types import SimpleNamespace
from patchraptor.schedule_manager import ScheduleManager

class TestScheduleManager:
    @pytest.fixture
    def mock_handlers(self):
        return {
            "server_control": Mock(cmd_reboot=AsyncMock(), cmd_shutdown=AsyncMock()),
            "backup_restore": Mock(cmd_backup=AsyncMock()),
            "update_management": Mock(cmd_patch=AsyncMock()),
        }

    @pytest.fixture
    def manager(self):
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager(schedule_file="test_schedule.json")
            mgr.scheduled_events = [] # Ensure clean state
            return mgr

    def test_load_schedule_exists(self, manager):
        """Test loading existing schedule file"""
        mock_data = [{"type": "reboot", "time": "12:00"}]
        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", mock_open(read_data=json.dumps(mock_data))):
            
            manager.load_schedule()
            assert len(manager.scheduled_events) == 1
            assert manager.scheduled_events[0]["type"] == "reboot"

    def test_load_schedule_missing(self, manager):
        """Test loading when file missing"""
        with patch("os.path.isfile", return_value=False):
            manager.load_schedule()
            assert manager.scheduled_events == []

    def test_save_schedule(self, manager):
        """Test saving schedule to file"""
        manager.scheduled_events = [{"type": "reboot", "time": "12:00"}]
        with patch("builtins.open", MagicMock()) as mock_open_file:
            manager.save_schedule()
            mock_open_file.assert_called_with("test_schedule.json", 'w', encoding='utf-8')

    def test_add_event_valid(self, manager):
        """Test adding a valid event"""
        with patch.object(manager, 'save_schedule') as mock_save:
            result = manager.add_event("reboot", "12:00", days=["mon"])
            assert result is True
            assert len(manager.scheduled_events) == 1
            assert manager.scheduled_events[0]["days"] == ["mon"]
            mock_save.assert_called()

    def test_add_event_invalid_time(self, manager):
        """Test adding event with bad time format"""
        result = manager.add_event("reboot", "25:00")
        assert result is False
        assert len(manager.scheduled_events) == 0

    def test_clear_events(self, manager):
        """Test clearing events with and without filter"""
        manager.scheduled_events = [
            {"type": "reboot", "time": "12:00"},
            {"type": "backup", "time": "13:00"}
        ]
        
        # Filtered clear
        removed = manager.clear_events("reboot")
        assert removed == 1
        assert len(manager.scheduled_events) == 1
        assert manager.scheduled_events[0]["type"] == "backup"
        
        # Full clear
        removed = manager.clear_events()
        assert removed == 1
        assert len(manager.scheduled_events) == 0

    @pytest.mark.asyncio
    async def test_execute_reboot_global(self, manager, mock_handlers):
        """Test execution of global reboot event"""
        event = {"type": "reboot", "time": "12:00"}
        mock_channel = Mock()
        mock_discord = Mock(send_temp_message=AsyncMock())
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl:
            mock_sl.side_effect = lambda key: {
                "DiscordManager": mock_discord,
                "ServerControlHandler": mock_handlers["server_control"]
            }.get(key)
            
            await manager._execute_scheduled_event(event, mock_channel)
            
            mock_handlers["server_control"].cmd_reboot.assert_called_once()
            args, _ = mock_handlers["server_control"].cmd_reboot.call_args
            # Verify it used .reboot command
            assert ".reboot" in args[1]

    @pytest.mark.asyncio
    async def test_execute_backup_map(self, manager, mock_handlers):
        """Test execution of map-specific backup"""
        event = {"type": "backup", "subtype": "map", "map_name": "TheIsland", "time": "12:00"}
        mock_channel = Mock()
        mock_discord = Mock(send_temp_message=AsyncMock())
        mock_server_mgr = Mock()
        mock_server = Mock()
        mock_server.name = "TheIsland"
        mock_server_mgr.find_server.return_value = mock_server
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl:
            mock_sl.side_effect = lambda key: {
                "DiscordManager": mock_discord,
                "BackupRestoreHandler": mock_handlers["backup_restore"],
                "ServerManager": mock_server_mgr
            }.get(key)
            
            await manager._execute_scheduled_event(event, mock_channel)
            
            mock_handlers["backup_restore"].cmd_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_patch_global(self, manager, mock_handlers):
        """Test execution of global patch"""
        event = {"type": "patch", "time": "12:00"}
        mock_channel = Mock()
        mock_discord = Mock(send_temp_message=AsyncMock())
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl:
            mock_sl.side_effect = lambda key: {
                "DiscordManager": mock_discord,
                "UpdateManagementHandler": mock_handlers["update_management"]
            }.get(key)
            
            await manager._execute_scheduled_event(event, mock_channel)
            
            mock_handlers["update_management"].cmd_patch.assert_called_once()

