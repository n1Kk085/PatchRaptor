"""
Refactored Test Suite for SystemMonitoringHandler (v1.5.0 "Pulse")
Focuses on passive reporting delegations and command handling.
"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

from patchraptor.system_monitoring_handler import SystemMonitoringHandler
from patchraptor.service_locator import ServiceLocator

@pytest.fixture
def mock_telemetry():
    """Mock TelemetryManager and its state."""
    tm = MagicMock()
    # Mock current_state
    tm.current_state = MagicMock()
    tm.current_state.online_count = 1
    tm.current_state.server_count = 1
    tm.current_state.total_players = 5
    
    # Mock get_diagnostics with the exact expected dict structure
    diag_data = {
        "uptime_pc": "1 day",
        "cpu_usage": 15.0,
        "ram_used": 1.0,
        "ram_total": 8.0,
        "disk_info": {"used": 50.0, "total": 100.0, "percent": 50.0},
        "results": ["☑️ Config OK", "☑️ RCON OK"],
        "issues": []
    }
    tm.get_diagnostics = AsyncMock(return_value=diag_data)
    return tm

@pytest.fixture
def handler(mock_telemetry):
    """Create handler with mocked ServiceLocator."""
    ServiceLocator.clear()
    ServiceLocator.register("TelemetryManager", mock_telemetry)
    ServiceLocator.register("DiscordManager", AsyncMock())
    
    vm = MagicMock()
    vm.get_latest_build_id = AsyncMock()
    ServiceLocator.register("VersionManager", vm)
    
    return SystemMonitoringHandler()

@pytest.fixture
def mock_message():
    message = MagicMock()
    message.channel = MagicMock()
    return message

class TestSystemMonitoringCommands:
    """Test the passive command handlers."""

    @pytest.mark.asyncio
    async def test_cmd_status(self, handler, mock_message, mock_telemetry):
        """Test .status formatting and delegation."""
        # Add required average data to mock state
        mock_telemetry.current_state.total_7day_uptime_avg = 99.9
        mock_telemetry.current_state.total_7day_player_avg = 10.5
        
        await handler.cmd_status(mock_message, ".status", ".status")
        
        # Verify telemetry was consulted
        assert mock_telemetry.get_diagnostics.called
        
        # Verify discord message sent as embed
        mock_dm = ServiceLocator.get("DiscordManager")
        mock_dm.send_temp_message.assert_called_once()
        kwargs = mock_dm.send_temp_message.call_args[1]
        embed = kwargs.get('embed')
        assert embed is not None
        assert "15.0%" in embed.description
        assert "1 day" in embed.description

    @pytest.mark.asyncio
    async def test_cmd_diagnose(self, handler, mock_message, mock_telemetry):
        """Test .diagnose embed generation."""
        await handler.cmd_diagnose(mock_message, ".diagnose", ".diagnose")
        
        mock_dm = ServiceLocator.get("DiscordManager")
        mock_dm.send_temp_message.assert_called_once()
        kwargs = mock_dm.send_temp_message.call_args[1]
        embed = kwargs.get('embed')
        assert embed is not None
        assert embed.title == "Bot Health Diagnostic"
        # Check field values (from our mock)
        assert "☑️ Config" in embed.fields[0].value

    @pytest.mark.asyncio
    async def test_cmd_check(self, handler, mock_message):
        """Test .check update detection."""
        vm = ServiceLocator.get("VersionManager")
        vm.get_current_version = MagicMock(return_value="1.0.0")
        vm.get_latest_build_id.return_value = "1.1.0"
        
        await handler.cmd_check(mock_message, ".check", ".check")
        
        mock_dm = ServiceLocator.get("DiscordManager")
        mock_dm.send_temp_message.assert_called_once()
        call_args = mock_dm.send_temp_message.call_args
        # Could be args[1] or kwargs['content'] depending on how it's called
        content = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get('content')
        assert "Update available" in content

    @pytest.mark.asyncio
    async def test_cmd_debug(self, handler, mock_message):
        """Test .debug toggle."""
        with patch("patchraptor.system_monitoring_handler.logger.toggle_debug", return_value=True):
            await handler.cmd_debug(mock_message, ".debug", ".debug")
            
            mock_dm = ServiceLocator.get("DiscordManager")
            mock_dm.send_temp_message.assert_called_once()
            args = mock_dm.send_temp_message.call_args[0]
            assert "Debug logging is now **☑️ ON**" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_report(self, handler, mock_message):
        """Test .report generation from logs."""
        with patch("os.listdir", return_value=["patchraptor_1.log"]), \
             patch("os.path.getmtime", return_value=123), \
             patch("builtins.open", mock_open(read_data="Test Log Line")), \
             patch("tempfile.NamedTemporaryFile") as mock_temp, \
             patch("os.unlink"):
            
            mock_temp.return_value.__enter__.return_value.name = "temp.log"
            
            await handler.cmd_report(mock_message, ".report", ".report")
            
            mock_dm = ServiceLocator.get("DiscordManager")
            mock_dm.send_temp_message.assert_called_once()
            kwargs = mock_dm.send_temp_message.call_args[1]
            assert "file" in kwargs
            assert kwargs["file"].filename == "patchraptor_report.log"
