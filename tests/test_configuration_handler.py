import pytest
import asyncio
import sys
import subprocess
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from patchraptor.configuration_handler import ConfigurationHandler
from patchraptor.exceptions import ConfigSaveError, ProcessOperationError

class TestConfigurationHandler:
    @pytest.fixture
    def mock_config_manager(self):
        cm = Mock()
        cm.config = {}
        cm.get.side_effect = lambda k, d=None: cm.config.get(k, d)
        cm.save = Mock()
        return cm

    @pytest.fixture
    def mock_discord_manager(self):
        dm = Mock()
        dm.send_temp_message = AsyncMock()
        dm.webhook_url = ""
        dm.delete_seconds = 10
        return dm

    @pytest.fixture
    def mock_raptorchat_manager(self):
        rc = Mock()
        rc.is_running.return_value = False
        rc.stop.return_value = True
        rc.reboot.return_value = True
        return rc

    @pytest.fixture
    def handler(self, mock_discord_manager, mock_config_manager, mock_raptorchat_manager):
        return ConfigurationHandler(
            discord_manager=mock_discord_manager,
            config_manager=mock_config_manager,
            raptorchat_manager=mock_raptorchat_manager
        )

    @pytest.fixture
    def mock_message(self):
        message = AsyncMock()
        message.channel = Mock()
        message.channel.send = AsyncMock() # Regular send
        return message


    @pytest.mark.asyncio
    async def test_cmd_discord_delete(self, handler, mock_message, mock_config_manager, mock_discord_manager):
        """Test .discord delete 0:30"""
        await handler.cmd_discord(mock_message, ".discord delete 0:30", ".discord delete 0:30")
        
        assert mock_discord_manager.delete_seconds == 1800
        assert mock_config_manager.config["backup_config"]["message_delete_seconds"] == 1800
        mock_config_manager.save.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_chat_status(self, handler, mock_message, mock_raptorchat_manager, mock_discord_manager):
        """Test .chat status"""
        mock_raptorchat_manager.is_running.return_value = True
        await handler.cmd_chat(mock_message, ".chat status", ".chat status")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "☑️ RaptorChat is Online" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_webpanel_on_script(self, handler, mock_message):
        """Test .webpanel on (script mode)"""
        with patch("sys.frozen", False, create=True), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen, \
             patch("asyncio.sleep", new_callable=AsyncMock):
             
             mock_process = Mock()
             mock_process.poll.return_value = None # Running
             mock_popen.return_value = mock_process
             
             await handler.cmd_webpanel(mock_message, ".webpanel on", ".webpanel on")
             
             # Should try to start tunnel AND webpanel
             assert mock_popen.call_count == 2
             handler.discord_manager.send_temp_message.assert_called()
             assert handler.webpanel_process is not None

    @pytest.mark.asyncio
    async def test_cmd_webpanel_off(self, handler, mock_message):
            """Test .webpanel off"""
            # Setup running state
            handler.webpanel_process = Mock()
            handler.webpanel_process.poll.return_value = None # Running
            handler.tunnel_process = Mock()
            handler.tunnel_process.terminate.side_effect = Exception("Terminated")
        
            with patch("sys.platform", "win32"), \
                 patch("psutil.Process"):
             
                await handler.cmd_webpanel(mock_message, ".webpanel off", ".webpanel off")
             
                assert handler.webpanel_process is None
                assert handler.tunnel_process is None

    # Discord command tests
    @pytest.mark.asyncio
    async def test_cmd_discord_no_args(self, handler, mock_message, mock_discord_manager):
        """Test .discord with no args"""
        await handler.cmd_discord(mock_message, ".discord", ".discord")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_discord_delete_show_current(self, handler, mock_message, mock_discord_manager):
        """Test .discord delete (show current)"""
        mock_discord_manager.delete_seconds = 7200  # 2 hours
        await handler.cmd_discord(mock_message, ".discord delete", ".discord delete")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "2:00" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_discord_delete_invalid_format(self, handler, mock_message, mock_discord_manager):
        """Test .discord delete with invalid format"""
        await handler.cmd_discord(mock_message, ".discord delete 1:2:3", ".discord delete 1:2:3")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Invalid time format" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_discord_delete_invalid_values(self, handler, mock_message, mock_discord_manager):
        """Test .discord delete with invalid values"""
        await handler.cmd_discord(mock_message, ".discord delete 1:70", ".discord delete 1:70")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Invalid time format" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_discord_delete_negative_time(self, handler, mock_message, mock_discord_manager):
        """Test .discord delete with negative time"""
        await handler.cmd_discord(mock_message, ".discord delete -1", ".discord delete -1")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Invalid time format" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_discord_delete_zero_time(self, handler, mock_message, mock_discord_manager):
        """Test .discord delete with zero time"""
        await handler.cmd_discord(mock_message, ".discord delete 0:00", ".discord delete 0:00")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "must be greater than 0" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_discord_delete_hours_format(self, handler, mock_message, mock_config_manager, mock_discord_manager):
        """Test .discord delete with hours format (backward compat)"""
        await handler.cmd_discord(mock_message, ".discord delete 2.5", ".discord delete 2.5")
        assert mock_discord_manager.delete_seconds == 9000  # 2.5 hours
        assert mock_config_manager.config["backup_config"]["message_delete_seconds"] == 9000
        mock_config_manager.save.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_discord_delete_config_save_error(self, handler, mock_message, mock_config_manager, mock_discord_manager):
        """Test .discord delete with config save error"""
        mock_config_manager.save.side_effect = ConfigSaveError("Write failed")
        await handler.cmd_discord(mock_message, ".discord delete 1:00", ".discord delete 1:00")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Failed to save config" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_discord_unknown_subcommand(self, handler, mock_message, mock_discord_manager):
        """Test .discord with unknown subcommand"""
        await handler.cmd_discord(mock_message, ".discord unknown", ".discord unknown")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Unknown .discord subcommand" in args[1]

    # Webpanel tests
    @pytest.mark.asyncio
    async def test_cmd_webpanel_status_running(self, handler, mock_message):
        """Test .webpanel (status when running)"""
        handler.webpanel_process = Mock()
        handler.webpanel_process.poll.return_value = None  # Running
        await handler.cmd_webpanel(mock_message, ".webpanel", ".webpanel")
        handler.discord_manager.send_temp_message.assert_called()
        args, _ = handler.discord_manager.send_temp_message.call_args
        assert "☑️ Web Panel is Online" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_webpanel_on_already_running(self, handler, mock_message):
        """Test .webpanel on when already running"""
        handler.webpanel_process = Mock()
        handler.webpanel_process.poll.return_value = None  # Running
        await handler.cmd_webpanel(mock_message, ".webpanel on", ".webpanel on")
        handler.discord_manager.send_temp_message.assert_called()
        args, _ = handler.discord_manager.send_temp_message.call_args
        assert "already" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_webpanel_on_frozen_mode(self, handler, mock_message):
        """Test .webpanel on in frozen mode"""
        with patch("sys.frozen", True, create=True), \
             patch("sys.executable", "C:\\app\\PatchRaptor.exe"), \
             patch("os.path.exists", return_value=False), \
             patch("subprocess.Popen") as mock_popen, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            
            mock_process = Mock()
            mock_process.poll.return_value = None
            mock_popen.return_value = mock_process
            
            await handler.cmd_webpanel(mock_message, ".webpanel on", ".webpanel on")
            
            # Should start WebPanel.exe
            assert mock_popen.called
            assert handler.webpanel_process is not None

    @pytest.mark.asyncio
    async def test_cmd_webpanel_on_tunnel_crash(self, handler, mock_message):
        """Test .webpanel on when tunnel crashes immediately"""
        with patch("sys.frozen", False, create=True), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            
            tunnel_mock = Mock()
            tunnel_mock.poll.return_value = 1  # Crashed
            webpanel_mock = Mock()
            webpanel_mock.poll.return_value = None
            mock_popen.side_effect = [tunnel_mock, webpanel_mock]
            
            await handler.cmd_webpanel(mock_message, ".webpanel on", ".webpanel on")
            
            assert handler.tunnel_process is None
            assert handler.webpanel_process is not None

    @pytest.mark.asyncio
    async def test_cmd_webpanel_on_tunnel_exception(self, handler, mock_message):
        """Test .webpanel on when tunnel raises exception"""
        with patch("sys.frozen", False, create=True), \
             patch("os.path.exists", return_value=True), \
             patch("subprocess.Popen") as mock_popen, \
             patch("asyncio.sleep", new_callable=AsyncMock):
            
            def popen_side_effect(*args, **kwargs):
                if "start_tunnel.bat" in str(args[0]):
                    raise Exception("Tunnel error")
                mock = Mock()
                mock.poll.return_value = None
                return mock
            
            mock_popen.side_effect = popen_side_effect
            
            await handler.cmd_webpanel(mock_message, ".webpanel on", ".webpanel on")
            
            assert handler.webpanel_process is not None

    @pytest.mark.asyncio
    async def test_cmd_webpanel_on_process_error(self, handler, mock_message):
        """Test .webpanel on with ProcessOperationError"""
        with patch("sys.frozen", False, create=True), \
             patch("os.path.exists", return_value=False), \
             patch("subprocess.Popen", side_effect=ProcessOperationError("start", "webpanel", "Failed")):
            
            await handler.cmd_webpanel(mock_message, ".webpanel on", ".webpanel on")
            
            handler.discord_manager.send_temp_message.assert_called()
            args, _ = handler.discord_manager.send_temp_message.call_args
            assert "Failed to start web panel" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_webpanel_off_already_stopped(self, handler, mock_message):
        """Test .webpanel off when already stopped"""
        handler.webpanel_process = None
        await handler.cmd_webpanel(mock_message, ".webpanel off", ".webpanel off")
        handler.discord_manager.send_temp_message.assert_called()
        args, _ = handler.discord_manager.send_temp_message.call_args
        assert "already" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_webpanel_off_with_tunnel_timeout(self, handler, mock_message):
            """Test .webpanel off with tunnel timeout"""
            handler.webpanel_process = Mock()
            handler.webpanel_process.poll.return_value = None
            tunnel_mock = Mock()
            tunnel_mock.wait.side_effect = subprocess.TimeoutExpired("cmd", 2)
            handler.tunnel_process = tunnel_mock
        
            # Create a psutil mock that passes through wait() errors
            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_parent.terminate.return_value = None
            mock_parent.wait.side_effect = subprocess.TimeoutExpired("process", 2)
        
            with patch("sys.platform", "win32"), \
                 patch("psutil.Process", return_value=mock_parent):
            
                await handler.cmd_webpanel(mock_message, ".webpanel off", ".webpanel off")
            
                assert handler.tunnel_process is None

    @pytest.mark.asyncio
    async def test_cmd_webpanel_off_tunnel_error(self, handler, mock_message):
            """Test .webpanel off with tunnel stop error"""
            handler.webpanel_process = Mock()
            handler.webpanel_process.poll.return_value = None
            handler.tunnel_process = Mock()
            handler.tunnel_process.terminate.side_effect = Exception("Stop error")
        
            with patch("sys.platform", "win32"), \
                 patch("psutil.Process"):
            
                await handler.cmd_webpanel(mock_message, ".webpanel off", ".webpanel off")
            
                # Should continue despite tunnel error and stop webpanel
                handler.discord_manager.send_temp_message.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_webpanel_off_webpanel_timeout(self, handler, mock_message):
            """Test .webpanel off with webpanel timeout"""
            # Create a psutil mock that simulates wait timeout
            webpanel_mock = Mock()
            webpanel_mock.poll.return_value = None
            webpanel_mock.wait.side_effect = subprocess.TimeoutExpired("cmd", 2)
            handler.webpanel_process = webpanel_mock
        
            # Create a psutil parent mock that passes through wait() errors
            mock_parent = Mock()
            mock_parent.children.return_value = []
            mock_parent.terminate.return_value = None
            mock_parent.wait.side_effect = subprocess.TimeoutExpired("process", 2)
        
            with patch("sys.platform", "win32"), \
                 patch("psutil.Process", return_value=mock_parent):
            
                await handler.cmd_webpanel(mock_message, ".webpanel off", ".webpanel off")
            
                assert handler.webpanel_process is None

    @pytest.mark.asyncio
    async def test_cmd_webpanel_off_process_error(self, handler, mock_message):
            """Test .webpanel off with ProcessOperationError"""
            handler.webpanel_process = Mock()
            handler.webpanel_process.poll.return_value = None
            handler.webpanel_process.terminate.side_effect = ProcessOperationError("stop", "webpanel", "Failed")
        
            with patch("sys.platform", "win32"), \
                 patch("psutil.Process"):
            
                await handler.cmd_webpanel(mock_message, ".webpanel off", ".webpanel off")
            
                handler.discord_manager.send_temp_message.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_webpanel_invalid_command(self, handler, mock_message):
        """Test .webpanel with invalid command"""
        await handler.cmd_webpanel(mock_message, ".webpanel invalid", ".webpanel invalid")
        handler.discord_manager.send_temp_message.assert_called()
        args, _ = handler.discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    # Chat command tests
    @pytest.mark.asyncio
    async def test_cmd_chat_no_args(self, handler, mock_message, mock_discord_manager):
        """Test .chat with no args"""
        await handler.cmd_chat(mock_message, ".chat", ".chat")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_chat_status_not_running(self, handler, mock_message, mock_raptorchat_manager, mock_discord_manager):
        """Test .chat status when not running"""
        mock_raptorchat_manager.is_running.return_value = False
        await handler.cmd_chat(mock_message, ".chat status", ".chat status")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "🛑 RaptorChat is Offline" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_chat_stop_success(self, handler, mock_message, mock_raptorchat_manager, mock_discord_manager):
        """Test .chat stop success"""
        mock_raptorchat_manager.is_running.return_value = True
        mock_raptorchat_manager.stop.return_value = True
        await handler.cmd_chat(mock_message, ".chat stop", ".chat stop")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "stopped" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_chat_stop_failure(self, handler, mock_message, mock_raptorchat_manager, mock_discord_manager):
        """Test .chat stop failure"""
        mock_raptorchat_manager.is_running.return_value = True
        mock_raptorchat_manager.stop.return_value = False
        await handler.cmd_chat(mock_message, ".chat stop", ".chat stop")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Failed to stop" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_chat_reboot_success(self, handler, mock_message, mock_raptorchat_manager, mock_discord_manager):
        """Test .chat reboot success"""
        mock_raptorchat_manager.reboot.return_value = True
        await handler.cmd_chat(mock_message, ".chat reboot", ".chat reboot")
        assert mock_discord_manager.send_temp_message.call_count == 2  # Starting + success

    @pytest.mark.asyncio
    async def test_cmd_chat_reboot_failure(self, handler, mock_message, mock_raptorchat_manager, mock_discord_manager):
        """Test .chat reboot failure"""
        mock_raptorchat_manager.reboot.return_value = False
        await handler.cmd_chat(mock_message, ".chat reboot", ".chat reboot")
        mock_discord_manager.send_temp_message.assert_called()
        # Check last call
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Failed to restart" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_chat_unknown_subcommand(self, handler, mock_message, mock_discord_manager):
        """Test .chat with unknown subcommand"""
        await handler.cmd_chat(mock_message, ".chat unknown", ".chat unknown")
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Unknown subcommand" in args[1]
