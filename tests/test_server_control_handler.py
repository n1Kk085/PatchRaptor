import pytest
import asyncio
import psutil
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from patchraptor.server_control_handler import ServerControlHandler
from patchraptor.exceptions import ServerNotFoundError, RCONConnectionError, RCONCommandError, ServerOperationError, ServerAlreadyRunningError

class TestServerControlHandler:
    @pytest.fixture
    def mock_server_manager(self):
        sm = Mock()
        sm.servers = []
        sm.get_display_name = Mock(return_value="The Island")
        sm.is_specific_server_running = Mock(return_value=True)
        sm.start_server = Mock()
        sm.wait_for_server_shutdown = AsyncMock(return_value=True)
        sm.wait_for_servers_online = AsyncMock(return_value=True)
        return sm

    @pytest.fixture
    def mock_rcon_manager(self):
        rm = Mock()
        rm.execute_for_server = AsyncMock()
        return rm

    @pytest.fixture
    def mock_discord_manager(self):
        dm = Mock()
        dm.send_temp_message = AsyncMock()
        return dm

    @pytest.fixture
    def mock_player_manager(self):
        pm = Mock()
        pm.pause = Mock()
        pm.resume = Mock()
        pm.clear_server_players = AsyncMock()
        pm.reset_file_positions = AsyncMock()
        pm.trigger_log_file_detection_on_restart = AsyncMock()
        return pm

    @pytest.fixture
    def mock_raptorchat_manager(self):
        rcm = Mock()
        rcm.is_running = Mock(return_value=True)
        rcm.stop = Mock()
        rcm.start = Mock()
        rcm.start_with_delay = AsyncMock(return_value=True)
        rcm.start_maintenance = Mock()
        rcm.end_maintenance = Mock()
        
        # Mock maintenance_scope async context manager
        scope_mock = MagicMock()
        scope_mock.__aenter__ = AsyncMock()
        scope_mock.__aexit__ = AsyncMock()
        rcm.maintenance_scope = MagicMock(return_value=scope_mock)
        
        return rcm

    @pytest.fixture
    def mock_telemetry_manager(self):
        tm = Mock()
        tm.current_state = Mock()
        tm.current_state.servers = []
        tm.reset = AsyncMock()
        tm.trigger_log_file_detection_on_restart = AsyncMock()
        tm.get_diagnostics = AsyncMock(return_value={
            'uptime_pc': '1d 2h',
            'cpu_usage': 15.5,
            'ram_used': 8.0,
            'ram_total': 16.0,
            'disk_info': {'used': 100, 'total': 500, 'percent': 20},
            'results': ['All good'],
            'issues': []
        })
        return tm

    @pytest.fixture
    def handler(self, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_player_manager, mock_raptorchat_manager, mock_telemetry_manager):
        return ServerControlHandler(
            server_manager=mock_server_manager,
            rcon_manager=mock_rcon_manager,
            discord_manager=mock_discord_manager,
            player_manager=mock_player_manager,
            raptorchat_manager=mock_raptorchat_manager,
            telemetry_manager=mock_telemetry_manager
        )

    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.name = "TestServer"
        server.map_name = "TheIsland"
        server.rcon_ip = "127.0.0.1"
        server.rcon_port = 27020
        server.server_save_path = "C:/Ark/Saved"
        return server

    @pytest.fixture
    def mock_message(self):
        message = AsyncMock()
        message.channel = Mock()
        return message


    @pytest.mark.asyncio
    async def test_cmd_shutdown_all(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_raptorchat_manager, mock_server, mock_message):
        """Test .shutdown command for all servers"""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=True)
        
        await handler.cmd_shutdown(mock_message, ".shutdown", ".shutdown")
        
        # Verify message sent
        assert any("Pausing Telemetry and Chat Relay" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)
        
        # Verify RaptorChat stopped
        mock_raptorchat_manager.stop.assert_called_once()
        
        # Verify DoExit sent
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, "DoExit")
        
        # Verify wait for shutdown
        mock_server_manager.wait_for_server_shutdown.assert_called_with(mock_server, 300)

    @pytest.mark.asyncio
    async def test_cmd_reboot_all(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_raptorchat_manager, mock_server, mock_message):
        """Test .reboot command for all servers"""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = True
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=True)
        
        # Mock wait_for_servers_online to return True immediately
        handler._wait_for_servers_online = AsyncMock(return_value=True)
        # Mock _delayed_raptorchat_restart
        handler._delayed_raptorchat_restart = AsyncMock()
        
        # Mock internal restart helpers
        handler._restart_all_servers = AsyncMock()
        
        await handler.cmd_reboot(mock_message, ".reboot", ".reboot")
        
        # Verify RaptorChat stopped
        mock_raptorchat_manager.stop.assert_called_once()
        
        # Verify PlayerManager paused
        mock_player_manager.pause.assert_called_once()
        
        # Verify DoExit sent
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, "DoExit")
        
        # Verify restart called
        handler._restart_all_servers.assert_called_once()
        
        # Verify RaptorChat restart triggered
        handler._delayed_raptorchat_restart.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_reboot_all_offline_starts_servers(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_raptorchat_manager, mock_server, mock_message):
        """Test .reboot when no servers are currently running still starts all configured servers"""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = False
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=True)
        mock_server_manager.wait_for_servers_online = AsyncMock(return_value=True)
        handler._restart_all_servers = AsyncMock()
        handler._delayed_raptorchat_restart = AsyncMock()

        await handler.cmd_reboot(mock_message, ".reboot", ".reboot")

        mock_rcon_manager.execute_for_server.assert_not_called()
        handler._restart_all_servers.assert_called_once()
        handler._delayed_raptorchat_restart.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_reboot_specific_server_offline_starts_server(self, handler, mock_server_manager, mock_rcon_manager, mock_server, mock_message):
        """Test .reboot specific server starts it when the server is currently offline"""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_server_manager.is_specific_server_running.return_value = False
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=True)
        mock_server_manager.wait_for_servers_online = AsyncMock(return_value=True)

        handler._restart_one_server = AsyncMock()
        handler._wait_for_servers_online = AsyncMock(return_value=True)
        handler._delayed_raptorchat_restart = AsyncMock()

        await handler.cmd_reboot(mock_message, ".reboot TheIsland", ".reboot theisland")

        mock_server_manager.find_server.assert_called_with("TheIsland")
        mock_rcon_manager.execute_for_server.assert_not_called()
        handler._restart_one_server.assert_called_once_with(mock_server, mock_message)

    @pytest.mark.asyncio
    async def test_cmd_reboot_specific_server(self, handler, mock_server_manager, mock_rcon_manager, mock_server, mock_message):
        """Test .reboot command for a specific server (TheIsland)"""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_server_manager.is_specific_server_running.return_value = True
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=True)
        
        handler._restart_one_server = AsyncMock()
        handler._wait_for_servers_online = AsyncMock(return_value=True)
        handler._delayed_raptorchat_restart = AsyncMock()
        
        await handler.cmd_reboot(mock_message, ".reboot TheIsland", ".reboot theisland")
        
        mock_server_manager.find_server.assert_called_with("TheIsland")
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, "DoExit")
        handler._restart_one_server.assert_called_with(mock_server, mock_message)

    @pytest.mark.asyncio
    async def test_cmd_send_specific(self, handler, mock_server_manager, mock_rcon_manager, mock_server, mock_message):
        """Test .send <map> <message>"""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        
        await handler.cmd_send(mock_message, ".send TheIsland Hello World", ".send theisland hello world")
        
        mock_server_manager.find_server.assert_called_with("TheIsland")
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, "ServerChat Hello World")

    @pytest.mark.asyncio
    async def test_cmd_servers_parsing(self, handler, mock_server_manager, mock_telemetry_manager, mock_server, mock_message, mock_discord_manager):
        """Test .servers command parsing of psutil processes"""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.get_display_name.return_value = "The Island"
        
        # Mock psutil.process_iter
        mock_proc = MagicMock()
        mock_proc.info = {
            'name': 'ArkAscendedServer.exe',
            'create_time': 1600000000,
            'cmdline': ['ArkAscendedServer.exe', 'TheIsland_WP', '?listen'],
            'memory_info': MagicMock(rss=1024*1024*1024) # 1GB
        }
        mock_proc.cpu_percent.return_value = 5.0
        
        with patch('psutil.process_iter', return_value=[mock_proc]), \
             patch('asyncio.sleep', new_callable=AsyncMock), \
             patch('os.path.exists', return_value=True), \
             patch('os.walk', return_value=[]), \
             patch('psutil.disk_usage', return_value=MagicMock(total=100, used=50)): 
             
             # Ensure servers list is populated BEFORE call
             mock_server_manager.servers = [mock_server]
             mock_server_manager.get_display_name.return_value = "The Island"
             mock_server_manager.get_server_process.return_value = mock_proc
             
             # Populate telemetry state
             mock_telemetry_manager.current_state.servers = [{
                 'name': 'TestServer',
                 'status': 'online',
                 'playerCount': 5,
                 'cpu': 10,
                 'ram': 4.5
             }]
             
             await handler.cmd_servers(mock_message, ".servers", ".servers")
             
        # Verify output contains key info in embed
        _, kwargs = mock_discord_manager.send_temp_message.call_args
        embed = kwargs.get('embed')
        assert embed is not None
        assert "Server Details" in embed.title
        
        # Verify output contains key info in embed description
        _, kwargs = mock_discord_manager.send_temp_message.call_args
        embed = kwargs.get('embed')
        assert embed is not None
        assert "Server Details" in embed.title
        
        description = embed.description
        assert "The Island" in description
        assert "Online" in description
        assert "Process CPU" in description
        assert "Process RAM" in description


class TestServerControlHandlerErrorHandling:
    """Test error handling and edge cases."""
    
    @pytest.fixture
    def mock_server_manager(self):
        sm = Mock()
        sm.servers = []
        sm.get_display_name = Mock(return_value="The Island")
        sm.is_specific_server_running = Mock(return_value=True)
        sm.start_server = Mock()
        sm.wait_for_server_shutdown = AsyncMock(return_value=True)
        sm.wait_for_servers_online = AsyncMock(return_value=True)
        return sm

    @pytest.fixture
    def mock_rcon_manager(self):
        rm = Mock()
        rm.execute_for_server = AsyncMock()
        return rm

    @pytest.fixture
    def mock_discord_manager(self):
        dm = Mock()
        dm.send_temp_message = AsyncMock()
        return dm

    @pytest.fixture
    def mock_player_manager(self):
        pm = Mock()
        pm.pause = Mock()
        pm.resume = Mock()
        pm.clear_server_players = AsyncMock()
        pm.reset_file_positions = AsyncMock()
        pm.trigger_log_file_detection_on_restart = AsyncMock()
        return pm

    @pytest.fixture
    def mock_raptorchat_manager(self):
        rcm = Mock()
        rcm.is_running = Mock(return_value=True)
        rcm.stop = Mock()
        rcm.start = Mock()
        rcm.start_with_delay = AsyncMock(return_value=True)
        rcm.start_maintenance = Mock()
        rcm.end_maintenance = Mock()
        
        # Mock maintenance_scope async context manager
        scope_mock = MagicMock()
        scope_mock.__aenter__ = AsyncMock()
        scope_mock.__aexit__ = AsyncMock()
        rcm.maintenance_scope = MagicMock(return_value=scope_mock)
        
        return rcm

    @pytest.fixture
    def mock_telemetry_manager(self):
        tm = Mock()
        tm.current_state = Mock()
        tm.current_state.servers = []
        tm.reset = AsyncMock()
        tm.trigger_log_file_detection_on_restart = AsyncMock()
        tm.get_diagnostics = AsyncMock(return_value={
            'uptime_pc': '1d 2h',
            'cpu_usage': 15.5,
            'ram_used': 8.0,
            'ram_total': 16.0,
            'disk_info': {'used': 100, 'total': 500, 'percent': 20},
            'results': ['All good'],
            'issues': []
        })
        return tm

    @pytest.fixture
    def handler(self, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_player_manager, mock_raptorchat_manager, mock_telemetry_manager):
        return ServerControlHandler(
            server_manager=mock_server_manager,
            rcon_manager=mock_rcon_manager,
            discord_manager=mock_discord_manager,
            player_manager=mock_player_manager,
            raptorchat_manager=mock_raptorchat_manager,
            telemetry_manager=mock_telemetry_manager
        )

    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.name = "TestServer"
        server.map_name = "TheIsland"
        server.rcon_ip = "127.0.0.1"
        server.rcon_port = 27020
        server.server_save_path = "C:/Ark/Saved"
        return server

    @pytest.fixture
    def mock_message(self):
        message = AsyncMock()
        message.channel = Mock()
        return message


    @pytest.mark.asyncio
    async def test_cmd_reboot_raptorchat_stop_error(self, handler, mock_server_manager, mock_raptorchat_manager, mock_discord_manager, mock_message):
        """Test cmd_reboot handles RaptorChat stop errors."""
        mock_server_manager.servers = []
        mock_raptorchat_manager.stop.side_effect = Exception("Stop failed")
        
        await handler.cmd_reboot(mock_message, ".reboot", ".reboot")
        
        # Should send error message
        assert any("Error stopping RaptorChat" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_cmd_reboot_raptorchat_not_running(self, handler, mock_server_manager, mock_raptorchat_manager, mock_message):
        """Test cmd_reboot when RaptorChat is not running."""
        mock_server_manager.servers = []
        mock_raptorchat_manager.is_running.return_value = False
        
        await handler.cmd_reboot(mock_message, ".reboot", ".reboot")
        
        # Should not call stop
        mock_raptorchat_manager.stop.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_reboot_server_not_found(self, handler, mock_server_manager, mock_discord_manager, mock_message):
        """Test cmd_reboot with server not found."""
        mock_server_manager.find_server.side_effect = ServerNotFoundError("Server not found")
        
        await handler.cmd_reboot(mock_message, ".reboot InvalidMap", ".reboot invalidmap")
        
        # Should send error message
        mock_discord_manager.send_temp_message.assert_called()
        args = mock_discord_manager.send_temp_message.call_args[0]
        assert "No server found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_reboot_specific_rcon_error(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test cmd_reboot specific server with RCON error."""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_server_manager.is_specific_server_running.return_value = True
        mock_rcon_manager.execute_for_server.side_effect = RCONCommandError("DoExit", "TestServer", "Command failed")
        
        await handler.cmd_reboot(mock_message, ".reboot TheIsland", ".reboot theisland")
        
        # Should send error message and return early
        assert any("Failed to send shutdown command" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_cmd_shutdown_specific_server(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_raptorchat_manager, mock_server, mock_message):
        """Test .shutdown command for specific server."""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=True)
        
        await handler.cmd_shutdown(mock_message, ".shutdown TheIsland", ".shutdown theisland")
        
        # Verify message sent
        assert any("Sending shutdown command" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)
        
        # Verify DoExit sent
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, "DoExit")

    @pytest.mark.asyncio
    async def test_cmd_shutdown_specific_server_not_found(self, handler, mock_server_manager, mock_discord_manager, mock_message):
        """Test .shutdown with server not found."""
        mock_server_manager.find_server.side_effect = ServerNotFoundError("Server not found")
        
        await handler.cmd_shutdown(mock_message, ".shutdown InvalidMap", ".shutdown invalidmap")
        
        # Should send error message
        args = mock_discord_manager.send_temp_message.call_args[0]
        assert "No server found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_shutdown_specific_rcon_error(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .shutdown specific server with RCON error."""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_rcon_manager.execute_for_server.side_effect = RCONConnectionError("TestServer", "Connection failed")
        
        await handler.cmd_shutdown(mock_message, ".shutdown TheIsland", ".shutdown theisland")
        
        # Should send error message and return
        assert any("Failed to send shutdown command" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_cmd_shutdown_specific_timeout(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .shutdown specific server with shutdown timeout."""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=False)
        
        await handler.cmd_shutdown(mock_message, ".shutdown TheIsland", ".shutdown theisland")
        
        # Should send Ghost Recovery message
        assert any("Initiating Ghost Recovery" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)
        mock_server_manager.force_stop_server.assert_called_with(mock_server)

    @pytest.mark.asyncio
    async def test_cmd_shutdown_all_rcon_errors(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .shutdown all with RCON errors."""
        mock_server_manager.servers = [mock_server]
        mock_rcon_manager.execute_for_server.side_effect = RCONCommandError("DoExit", "TestServer", "Command failed")
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=True)
        
        await handler.cmd_shutdown(mock_message, ".shutdown", ".shutdown")
        
        # Should send error message but continue
        assert any("Failed to send shutdown" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_cmd_shutdown_all_timeout(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .shutdown all with shutdown timeout."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.wait_for_server_shutdown = AsyncMock(return_value=False)
        
        await handler.cmd_shutdown(mock_message, ".shutdown", ".shutdown")
        
        # Should send Ghost Recovery message
        assert any("Initiating Ghost Recovery" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)
        mock_server_manager.force_stop_server.assert_called_with(mock_server)

    @pytest.mark.asyncio
    async def test_cmd_send_all(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .send all command."""
        mock_server_manager.servers = [mock_server]
        
        await handler.cmd_send(mock_message, ".send all Test message", ".send all test message")
        
        # Verify message sent to all servers
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, "ServerChat Test message")
        mock_discord_manager.send_temp_message.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_send_all_rcon_error(self, handler, mock_server_manager, mock_rcon_manager, mock_server, mock_message):
        """Test .send all with RCON error."""
        mock_server_manager.servers = [mock_server]
        mock_rcon_manager.execute_for_server.side_effect = RCONConnectionError("TestServer", "Connection failed")
        
        # Should not raise exception
        await handler.cmd_send(mock_message, ".send all Test", ".send all test")

    @pytest.mark.asyncio
    async def test_cmd_send_invalid_usage(self, handler, mock_discord_manager, mock_message):
        """Test .send with invalid usage."""
        await handler.cmd_send(mock_message, ".send TheIsland", ".send theisland")
        
        # Should send usage message
        args = mock_discord_manager.send_temp_message.call_args[0]
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_send_server_not_found(self, handler, mock_server_manager, mock_discord_manager, mock_message):
        """Test .send with server not found."""
        mock_server_manager.find_server.side_effect = ServerNotFoundError("Server not found")
        
        await handler.cmd_send(mock_message, ".send InvalidMap Test", ".send invalidmap test")
        
        # Should send error message
        args = mock_discord_manager.send_temp_message.call_args[0]
        assert "No server found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_send_rcon_error(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .send with RCON error."""
        mock_server_manager.find_server.return_value = mock_server
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_rcon_manager.execute_for_server.side_effect = RCONCommandError("ServerChat", "TestServer", "Command failed")
        
        await handler.cmd_send(mock_message, ".send TheIsland Test", ".send theisland test")
        
        # Should send error message
        assert any("Failed to send to" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_restart_all_servers(self, handler, mock_player_manager, mock_telemetry_manager, mock_server_manager, mock_server, mock_message):
        """Test _restart_all_servers method."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.start_server = Mock()
        mock_server_manager.get_display_name.return_value = "The Island"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await handler._restart_all_servers(mock_message)
        
        # Should clear player data
        mock_player_manager.clear_server_players.assert_called_once()
        mock_telemetry_manager.trigger_log_file_detection_on_restart.assert_called_once()
        
        # Should start server
        mock_server_manager.start_server.assert_called_with(mock_server)

    @pytest.mark.asyncio
    async def test_restart_all_servers_clear_error(self, handler, mock_player_manager, mock_server_manager, mock_message):
        """Test _restart_all_servers with player data clear error."""
        mock_server_manager.servers = []
        mock_player_manager.clear_server_players.side_effect = Exception("Clear failed")
        
        # Should not raise exception
        await handler._restart_all_servers(mock_message)

    @pytest.mark.asyncio
    async def test_restart_one_server_success(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test _restart_one_server successful start."""
        mock_server_manager.start_server = Mock()
        mock_server_manager.get_display_name.return_value = "The Island"
        
        await handler._restart_one_server(mock_server, mock_message)
        
        # Should start server and send message
        mock_server_manager.start_server.assert_called_with(mock_server)
        assert any("is now starting" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_restart_one_server_already_running(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test _restart_one_server when already running."""
        mock_server_manager.start_server.side_effect = ServerAlreadyRunningError("Already running")
        mock_server_manager.get_display_name.return_value = "The Island"
        
        await handler._restart_one_server(mock_server, mock_message)
        
        # Should send already running message
        assert any("already running" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_restart_one_server_operation_error_actually_running(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test _restart_one_server with operation error but server actually running."""
        mock_server_manager.start_server.side_effect = ServerOperationError("start", "TestServer", "Start error")
        mock_server_manager.is_specific_server_running.return_value = True
        mock_server_manager.get_display_name.return_value = "The Island"
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await handler._restart_one_server(mock_server, mock_message)
        
        # Should send starting message
        assert any("is now starting" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_restart_one_server_operation_error_not_running(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test _restart_one_server with operation error and server not running."""
        mock_server_manager.start_server.side_effect = ServerOperationError("start", "TestServer", "Start error")
        mock_server_manager.is_specific_server_running.return_value = False
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await handler._restart_one_server(mock_server, mock_message)
        
        # Should send failure message
        assert any("Failed to start" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)

    @pytest.mark.asyncio
    async def test_restart_one_server_unexpected_error(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test _restart_one_server with unexpected error."""
        mock_server_manager.start_server.side_effect = Exception("Unexpected error")
        
        await handler._restart_one_server(mock_server, mock_message)
        
        # Should send unexpected error message
        assert any("Unexpected error" in str(call) for call in mock_discord_manager.send_temp_message.call_args_list)


    @pytest.mark.asyncio
    async def test_delayed_raptorchat_restart(self, handler, mock_player_manager, mock_telemetry_manager, mock_raptorchat_manager, mock_message):
        """Test _delayed_raptorchat_restart method."""
        mock_raptorchat_manager.is_running.return_value = False
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await handler._delayed_raptorchat_restart(120, mock_message.channel)
        
        # Should resume player manager
        mock_player_manager.resume.assert_called_once()
        
        # Should trigger log detection on telemetry_manager
        mock_telemetry_manager.trigger_log_file_detection_on_restart.assert_called_once()
        
        # Should call RaptorChat start_with_delay
        mock_raptorchat_manager.start_with_delay.assert_called_once_with(120)

    @pytest.mark.asyncio
    async def test_cmd_servers_offline_server(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test .servers command with offline server."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_server_manager.get_server_process.return_value = None
        
        with patch('psutil.process_iter', return_value=[]), \
             patch('os.path.exists', return_value=True), \
             patch('os.walk', return_value=[("C:/Ark/Saved", [], ["file.ark"])]), \
             patch('os.path.getsize', return_value=1024*1024*1024), \
             patch('os.path.splitdrive', return_value=("C:", "")), \
             patch('psutil.disk_usage', return_value=MagicMock(total=100*1024*1024*1024, used=50*1024*1024*1024)):
            await handler.cmd_servers(mock_message, ".servers", ".servers")
        
        # Should send message with OFFLINE status in embed description
        _, kwargs = mock_discord_manager.send_temp_message.call_args
        embed = kwargs.get('embed')
        assert embed is not None
        assert "Offline" in embed.description
        assert "The Island" in embed.description

    @pytest.mark.asyncio
    async def test_cmd_servers_disk_error(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test .servers command with disk error."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.get_display_name.return_value = "The Island"
        mock_server_manager.get_server_process.return_value = None
        
        with patch('psutil.process_iter', return_value=[]), \
             patch('os.path.exists', return_value=True), \
             patch('patchraptor.system_utils.SystemUtils.get_directory_size', side_effect=Exception("Disk error")):
            await handler.cmd_servers(mock_message, ".servers", ".servers")
        
        # Should send message with Error in embed description
        _, kwargs = mock_discord_manager.send_temp_message.call_args
        embed = kwargs.get('embed')
        assert embed is not None
        assert "Error" in embed.description
        assert "The Island" in embed.description

    @pytest.mark.asyncio
    async def test_cmd_servers_psutil_error(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test .servers command with psutil error."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.get_display_name.return_value = "The Island"
        
        with patch('psutil.process_iter', side_effect=psutil.NoSuchProcess(123)):
            await handler.cmd_servers(mock_message, ".servers", ".servers")
        
        # Should complete without error
        mock_discord_manager.send_temp_message.assert_called()
