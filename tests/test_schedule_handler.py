import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from patchraptor.schedule_handler import ScheduleHandler

class TestScheduleHandler:
    @pytest.fixture
    def mock_server_manager(self):
        sm = Mock()
        sm.find_server.return_value = Mock(name="TheIsland")
        sm.get_display_name.return_value = "The Island"
        return sm

    @pytest.fixture
    def mock_discord_manager(self):
        dm = Mock()
        dm.send_temp_message = AsyncMock()
        return dm

    @pytest.fixture
    def mock_schedule_manager(self):
        sm = Mock()
        sm.get_events.return_value = []
        sm.add_event.return_value = True
        sm.clear_events.return_value = 1
        return sm

    @pytest.fixture
    def handler(self, mock_server_manager, mock_discord_manager, mock_schedule_manager):
        return ScheduleHandler(
            mock_server_manager,
            mock_discord_manager,
            mock_schedule_manager
        )

    @pytest.fixture
    def mock_message(self):
        message = AsyncMock()
        message.channel = Mock()
        return message

    @pytest.mark.asyncio
    async def test_cmd_schedule_list_empty(self, handler, mock_message, mock_schedule_manager, mock_discord_manager):
        """Test listing events when empty"""
        mock_schedule_manager.get_events.return_value = []
        
        await handler.cmd_schedule(mock_message, ".schedule", ".schedule")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "No scheduled events" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_list_items(self, handler, mock_message, mock_schedule_manager, mock_discord_manager):
        """Test listing events with data"""
        mock_schedule_manager.get_events.return_value = [
            {"type": "reboot", "time": "12:00", "subtype": "all"},
            {"type": "backup", "time": "13:00", "subtype": "map", "map_name": "TheIsland", "days": ["mon"]}
        ]
        
        await handler.cmd_schedule(mock_message, ".schedule", ".schedule")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        msg = args[1]
        assert "Reboot all at 12:00" in msg
        assert "Backup The Island at 13:00" in msg
        assert "mon" in msg

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_valid_reboot(self, handler, mock_message, mock_schedule_manager):
        """Test adding reboot event"""
        await handler.cmd_schedule(mock_message, ".schedule add reboot 03:00", ".schedule add reboot 03:00")
        
        mock_schedule_manager.add_event.assert_called_with("reboot", "03:00", [], None, "all")

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_valid_backup_map(self, handler, mock_message, mock_schedule_manager):
        """Test adding backup event for specific map with days"""
        await handler.cmd_schedule(mock_message, ".schedule add backup TheIsland mon fri 04:00", ".schedule add backup theisland mon fri 04:00")
        
        # Args logic: backup target is "TheIsland", days are [mon, fri], time is 04:00
        mock_schedule_manager.add_event.assert_called_with(
            "backup", "04:00", ["mon", "fri"], "theisland", "map"
        )

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_invalid_type(self, handler, mock_message, mock_discord_manager):
        """Test adding invalid event type"""
        await handler.cmd_schedule(mock_message, ".schedule add invalid 03:00", ".schedule add invalid 03:00")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Invalid event type" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_invalid_time(self, handler, mock_message, mock_discord_manager):
        """Test adding invalid event time"""
        await handler.cmd_schedule(mock_message, ".schedule add reboot 25:00", ".schedule add reboot 25:00")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Invalid time format" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_clear_all(self, handler, mock_message, mock_schedule_manager):
        """Test clearing all events"""
        await handler.cmd_schedule(mock_message, ".schedule clear", ".schedule clear")
        
        mock_schedule_manager.clear_events.assert_called_with()

    @pytest.mark.asyncio
    async def test_cmd_schedule_clear_specific(self, handler, mock_message, mock_schedule_manager):
        """Test clearing specific event type"""
        await handler.cmd_schedule(mock_message, ".schedule clear reboot", ".schedule clear reboot")
        
        mock_schedule_manager.clear_events.assert_called_with("reboot")

    @pytest.mark.asyncio
    async def test_cmd_schedule_list_server_not_found(self, handler, mock_message, mock_schedule_manager, mock_server_manager):
        """Test listing events when server lookup fails"""
        from patchraptor.exceptions import ServerNotFoundError
        mock_schedule_manager.get_events.return_value = [
            {"type": "backup", "time": "13:00", "subtype": "map", "map_name": "UnknownMap"}
        ]
        mock_server_manager.find_server.side_effect = ServerNotFoundError("Not found")
        
        await handler.cmd_schedule(mock_message, ".schedule", ".schedule")
        
        # Should still display the event with the map name
        args, _ = handler.discord_manager.send_temp_message.call_args
        assert "UnknownMap" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_list_no_subtype(self, handler, mock_message, mock_schedule_manager):
        """Test listing events with no subtype"""
        mock_schedule_manager.get_events.return_value = [
            {"type": "update", "time": "02:00"}
        ]
        
        await handler.cmd_schedule(mock_message, ".schedule", ".schedule")
        
        args, _ = handler.discord_manager.send_temp_message.call_args
        assert "Update at 02:00" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_insufficient_args(self, handler, mock_message, mock_discord_manager):
        """Test add with insufficient arguments"""
        await handler.cmd_schedule(mock_message, ".schedule add reboot", ".schedule add reboot")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_backup_all(self, handler, mock_message, mock_schedule_manager):
        """Test adding backup for all servers"""
        await handler.cmd_schedule(mock_message, ".schedule add backup all 02:00", ".schedule add backup all 02:00")
        
        mock_schedule_manager.add_event.assert_called_with("backup", "02:00", [], None, "all")

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_backup_no_target(self, handler, mock_message, mock_schedule_manager):
        """Test adding backup with no target defaults to all"""
        await handler.cmd_schedule(mock_message, ".schedule add backup 02:00", ".schedule add backup 02:00")
        
        mock_schedule_manager.add_event.assert_called_with("backup", "02:00", [], None, "all")

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_backup_server_not_found(self, handler, mock_message, mock_server_manager, mock_discord_manager):
        """Test adding backup for non-existent server"""
        from patchraptor.exceptions import ServerNotFoundError
        mock_server_manager.find_server.side_effect = ServerNotFoundError("Not found")
        
        await handler.cmd_schedule(mock_message, ".schedule add backup UnknownMap 02:00", ".schedule add backup unknownmap 02:00")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "No server found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_event_fails(self, handler, mock_message, mock_schedule_manager, mock_discord_manager):
        """Test when add_event returns False"""
        mock_schedule_manager.add_event.return_value = False
        
        await handler.cmd_schedule(mock_message, ".schedule add reboot 03:00", ".schedule add reboot 03:00")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Failed to add" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_add_operation_error(self, handler, mock_message, mock_schedule_manager, mock_discord_manager):
        """Test when add_event raises ScheduleOperationError"""
        from patchraptor.exceptions import ScheduleOperationError
        mock_schedule_manager.add_event.side_effect = ScheduleOperationError("add_event", "Database error")
        
        await handler.cmd_schedule(mock_message, ".schedule add reboot 03:00", ".schedule add reboot 03:00")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Database error" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_clear_invalid_args(self, handler, mock_message, mock_discord_manager):
        """Test clear with too many arguments"""
        await handler.cmd_schedule(mock_message, ".schedule clear foo bar", ".schedule clear foo bar")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_clear_all_explicit(self, handler, mock_message, mock_schedule_manager):
        """Test clearing all events with explicit 'all' argument"""
        await handler.cmd_schedule(mock_message, ".schedule clear all", ".schedule clear all")
        
        mock_schedule_manager.clear_events.assert_called_with()

    @pytest.mark.asyncio
    async def test_cmd_schedule_clear_no_events_found(self, handler, mock_message, mock_schedule_manager, mock_discord_manager):
        """Test clearing specific type when none exist"""
        mock_schedule_manager.clear_events.return_value = 0
        
        await handler.cmd_schedule(mock_message, ".schedule clear backup", ".schedule clear backup")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "No scheduled 'backup' events found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_clear_invalid_type(self, handler, mock_message, mock_discord_manager):
        """Test clearing with invalid event type"""
        await handler.cmd_schedule(mock_message, ".schedule clear invalid", ".schedule clear invalid")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Invalid event type" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_schedule_unknown_command(self, handler, mock_message, mock_discord_manager):
        """Test unknown schedule subcommand"""
        await handler.cmd_schedule(mock_message, ".schedule unknown", ".schedule unknown")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Unknown .schedule command" in args[1]
