import pytest
import asyncio
import json
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from patchraptor.schedule_manager import ScheduleManager

class TestScheduleManager:
    @pytest.fixture
    def mock_handlers(self):
        return {
            "server_control": Mock(cmd_reboot=AsyncMock(), cmd_shutdown=AsyncMock()),
            "backup_restore": Mock(cmd_backup=AsyncMock()),
            "update_management": Mock(cmd_update=AsyncMock()),
        }

    @pytest.fixture
    def manager(self, mock_handlers):
        with patch.object(ScheduleManager, 'load_schedule') as mock_load:
            mgr = ScheduleManager(
                schedule_file="test_schedule.json",
                server_control_handler=mock_handlers["server_control"],
                backup_restore_handler=mock_handlers["backup_restore"],
                update_management_handler=mock_handlers["update_management"]
            )
            mgr.scheduled_events = [] # Ensure clean state
            return mgr

    def test_load_schedule_exists(self, manager):
        """Test loading existing schedule file"""
        mock_data = [{"type": "reboot", "time": "12:00"}]
        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", new_callable=MagicMock) as mock_open, \
             patch("json.load", return_value=mock_data):
            
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
        with patch("builtins.open", new_callable=MagicMock) as mock_open:
            manager.save_schedule()
            mock_open.assert_called_with("test_schedule.json", 'w', encoding='utf-8')

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
        
        await manager._execute_scheduled_event(
            event, mock_channel, Mock(), Mock(), mock_discord, Mock(),
            manager.server_control_handler, manager.backup_restore_handler, manager.update_management_handler
        )
        
        # Verify call to server_control_handler
        mock_handlers["server_control"].cmd_reboot.assert_called_once()
        args, _ = mock_handlers["server_control"].cmd_reboot.call_args
        assert args[1] == ".reboot"

    @pytest.mark.asyncio
    async def test_execute_backup_map(self, manager, mock_handlers):
        """Test execution of map-specific backup"""
        event = {"type": "backup", "subtype": "map", "map_name": "TheIsland", "time": "12:00"}
        mock_channel = Mock()
        mock_discord = Mock(send_temp_message=AsyncMock())
        mock_server_mgr = Mock()
        mock_server_mgr.find_server.return_value = Mock(name="TheIsland")
        
        await manager._execute_scheduled_event(
            event, mock_channel, mock_server_mgr, Mock(), mock_discord, Mock(),
            manager.server_control_handler, manager.backup_restore_handler, manager.update_management_handler
        )
        
        # Verify call to backup_restore_handler
        mock_handlers["backup_restore"].cmd_backup.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_update_global(self, manager, mock_handlers):
        """Test execution of global update"""
        event = {"type": "update", "time": "12:00"}
        mock_channel = Mock()
        mock_discord = Mock(send_temp_message=AsyncMock())
        
        await manager._execute_scheduled_event(
            event, mock_channel, Mock(), Mock(), mock_discord, Mock(),
            manager.server_control_handler, manager.backup_restore_handler, manager.update_management_handler
        )
        
        # Verify call to update_management_handler
        mock_handlers["update_management"].cmd_update.assert_called_once()


class TestLoadScheduleExceptions:
    """Test exception handling in load_schedule."""
    
    def test_load_schedule_json_error(self):
        """Test handling of JSON decode errors."""
        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", new_callable=MagicMock), \
             patch("json.load", side_effect=json.JSONDecodeError("Invalid", "", 0)):
            
            mgr = ScheduleManager(schedule_file="bad.json")
            # Should handle error gracefully and start with empty list
            assert mgr.scheduled_events == []
    
    def test_load_schedule_file_error(self):
        """Test handling of file read errors."""
        with patch("os.path.isfile", return_value=True), \
             patch("builtins.open", side_effect=IOError("Cannot read")):
            
            mgr = ScheduleManager(schedule_file="error.json")
            # Should handle error gracefully
            assert mgr.scheduled_events == []


class TestSaveScheduleExceptions:
    """Test exception handling in save_schedule."""
    
    def test_save_schedule_error(self):
        """Test handling of save errors."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager(schedule_file="test.json")
            mgr.scheduled_events = [{"type": "reboot", "time": "12:00"}]
            
            with patch("builtins.open", side_effect=IOError("Cannot write")):
                # Should handle error gracefully (no exception raised)
                mgr.save_schedule()


class TestGetEvents:
    """Test get_events method."""
    
    def test_get_events_returns_copy(self):
        """Test that get_events returns a copy of events."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager()
            mgr.scheduled_events = [{"type": "reboot", "time": "12:00"}]
            
            events = mgr.get_events()
            assert events == mgr.scheduled_events
            assert events is not mgr.scheduled_events  # Should be a copy


class TestClearEventsEdgeCases:
    """Test edge cases in clear_events."""
    
    def test_clear_events_no_match(self):
        """Test clearing when no events match filter."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager()
            mgr.scheduled_events = [{"type": "reboot", "time": "12:00"}]
            
            removed = mgr.clear_events("backup")
            assert removed == 0
            assert len(mgr.scheduled_events) == 1


class TestScheduleRunner:
    """Test schedule_runner background task."""
    
    @pytest.mark.asyncio
    async def test_schedule_runner_loop(self):
        """Test schedule runner main loop."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager()
            mgr.scheduled_events = []
            
            mock_client = Mock()
            mock_client.wait_until_ready = AsyncMock()
            mock_client.is_closed.return_value = False
            mock_client.get_channel.return_value = Mock()
            mock_client.config_manager.get.return_value = "123456"
            
            # Run for a short time then cancel
            call_count = 0
            async def mock_sleep(duration):
                nonlocal call_count
                call_count += 1
                if call_count >= 2:
                    raise asyncio.CancelledError()
            
            with patch('asyncio.sleep', side_effect=mock_sleep):
                try:
                    await mgr.schedule_runner(mock_client, Mock(), Mock(), Mock(), Mock())
                except asyncio.CancelledError:
                    pass
            
            assert call_count == 2


class TestExecuteScheduledEventTypes:
    """Test different event type executions."""
    
    @pytest.fixture
    def mock_deps(self):
        """Create mock dependencies."""
        return {
            "channel": Mock(),
            "server_manager": Mock(),
            "rcon_manager": Mock(),
            "discord_manager": Mock(send_temp_message=AsyncMock()),
            "command_handler": Mock(),
            "server_control": Mock(cmd_reboot=AsyncMock(), cmd_shutdown=AsyncMock()),
            "backup_restore": Mock(cmd_backup=AsyncMock()),
            "update_management": Mock(cmd_update=AsyncMock())
        }
    
    @pytest.mark.asyncio
    async def test_execute_shutdown_global(self, mock_deps):
        """Test global shutdown event."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager(server_control_handler=mock_deps["server_control"])
            
            event = {"type": "shutdown", "time": "12:00"}
            
            await mgr._execute_scheduled_event(
                event, mock_deps["channel"], mock_deps["server_manager"],
                mock_deps["rcon_manager"], mock_deps["discord_manager"],
                mock_deps["command_handler"], mock_deps["server_control"],
                mock_deps["backup_restore"], mock_deps["update_management"]
            )
            
            mock_deps["server_control"].cmd_shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_reboot_map(self, mock_deps):
        """Test map-specific reboot."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager(server_control_handler=mock_deps["server_control"])
            
            event = {"type": "reboot", "subtype": "map", "map_name": "TheIsland", "time": "12:00"}
            mock_server = Mock(name="TheIsland")
            mock_deps["server_manager"].find_server.return_value = mock_server
            
            await mgr._execute_scheduled_event(
                event, mock_deps["channel"], mock_deps["server_manager"],
                mock_deps["rcon_manager"], mock_deps["discord_manager"],
                mock_deps["command_handler"], mock_deps["server_control"],
                mock_deps["backup_restore"], mock_deps["update_management"]
            )
            
            mock_deps["server_control"].cmd_reboot.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_shutdown_map(self, mock_deps):
        """Test map-specific shutdown."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager(server_control_handler=mock_deps["server_control"])
            
            event = {"type": "shutdown", "subtype": "map", "map_name": "TheCenter", "time": "12:00"}
            mock_server = Mock(name="TheCenter")
            mock_deps["server_manager"].find_server.return_value = mock_server
            
            await mgr._execute_scheduled_event(
                event, mock_deps["channel"], mock_deps["server_manager"],
                mock_deps["rcon_manager"], mock_deps["discord_manager"],
                mock_deps["command_handler"], mock_deps["server_control"],
                mock_deps["backup_restore"], mock_deps["update_management"]
            )
            
            mock_deps["server_control"].cmd_shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_backup_global(self, mock_deps):
        """Test global backup."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager(backup_restore_handler=mock_deps["backup_restore"])
            
            event = {"type": "backup", "time": "12:00"}
            
            await mgr._execute_scheduled_event(
                event, mock_deps["channel"], mock_deps["server_manager"],
                mock_deps["rcon_manager"], mock_deps["discord_manager"],
                mock_deps["command_handler"], mock_deps["server_control"],
                mock_deps["backup_restore"], mock_deps["update_management"]
            )
            
            mock_deps["backup_restore"].cmd_backup.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_backup_server_not_found(self, mock_deps):
        """Test map-specific backup when server not found."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager(backup_restore_handler=mock_deps["backup_restore"])
            
            event = {"type": "backup", "subtype": "map", "map_name": "NonExistent", "time": "12:00"}
            mock_deps["server_manager"].find_server.return_value = None
            
            await mgr._execute_scheduled_event(
                event, mock_deps["channel"], mock_deps["server_manager"],
                mock_deps["rcon_manager"], mock_deps["discord_manager"],
                mock_deps["command_handler"], mock_deps["server_control"],
                mock_deps["backup_restore"], mock_deps["update_management"]
            )
            
            # Should send warning message, not call backup
            mock_deps["backup_restore"].cmd_backup.assert_not_called()
            assert mock_deps["discord_manager"].send_temp_message.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_execute_unknown_event_type(self, mock_deps):
        """Test handling of unknown event type."""
        with patch.object(ScheduleManager, 'load_schedule'):
            mgr = ScheduleManager()
            
            event = {"type": "unknown_type", "time": "12:00"}
            
            # Should handle gracefully without error
            await mgr._execute_scheduled_event(
                event, mock_deps["channel"], mock_deps["server_manager"],
                mock_deps["rcon_manager"], mock_deps["discord_manager"],
                mock_deps["command_handler"], mock_deps["server_control"],
                mock_deps["backup_restore"], mock_deps["update_management"]
            )
