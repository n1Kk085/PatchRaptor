import pytest
import asyncio
import os
import datetime
from unittest.mock import Mock, MagicMock, patch, AsyncMock, ANY
from patchraptor.backup_restore_handler import BackupRestoreHandler
from patchraptor.exceptions import ServerNotFoundError, BackupCreationError, BackupRestoreError, RCONConnectionError, ServerOperationError


class TestBackupRestoreHandler:
    @pytest.fixture
    def mock_deps(self):
        deps = {
            "server_manager": Mock(),
            "rcon_manager": Mock(),
            "backup_manager": Mock(),
            "discord_manager": Mock(),
            "config_manager": Mock(),
            "raptorchat_manager": Mock(),
            "player_manager": Mock(),
            "telemetry_manager": Mock(),
        }
        deps["discord_manager"].send_temp_message = AsyncMock()
        deps["rcon_manager"].execute_for_server = AsyncMock()
        deps["server_manager"].wait_for_server_shutdown = AsyncMock()
        deps["server_manager"].start_server = Mock() # start_server is synchronous.
        # start_server handles process creation synchronously.
        # But wait, lines 280 in backup_restore_handler.py: self.server_manager.start_server(server) (not awaited)
        
        deps["config_manager"].config = {}
        deps["config_manager"].save = Mock()
        deps["backup_manager"].retention_count = 5
        deps["backup_manager"].backup_path = "/backups"
        return deps

    @pytest.fixture
    def handler(self, mock_deps):
        return BackupRestoreHandler(
            server_manager=mock_deps["server_manager"],
            rcon_manager=mock_deps["rcon_manager"],
            backup_manager=mock_deps["backup_manager"],
            discord_manager=mock_deps["discord_manager"],
            config_manager=mock_deps["config_manager"],
            raptorchat_manager=mock_deps["raptorchat_manager"],
            player_manager=mock_deps["player_manager"],
            telemetry_manager=mock_deps["telemetry_manager"]
        )

    @pytest.fixture
    def mock_message(self):
        msg = AsyncMock()
        msg.channel = Mock()
        return msg

    @pytest.mark.asyncio
    async def test_cmd_backup_amount(self, handler, mock_message, mock_deps):
        """Test .backup amount setting"""
        await handler.cmd_backup(mock_message, ".backup amount 10", ".backup amount 10")
        
        assert mock_deps["backup_manager"].retention_count == 10
        assert mock_deps["config_manager"].config["backup_config"]["backup_retention_count"] == 10
        mock_deps["discord_manager"].send_temp_message.assert_called()
        assert "updated to 10" in mock_deps["discord_manager"].send_temp_message.call_args[0][1]

    @pytest.mark.asyncio
    async def test_cmd_backup_invalid_amount(self, handler, mock_message, mock_deps):
        """Test .backup amount with invalid input"""
        await handler.cmd_backup(mock_message, ".backup amount -5", ".backup amount -5")
        assert "positive number" in mock_deps["discord_manager"].send_temp_message.call_args[0][1]
        
        await handler.cmd_backup(mock_message, ".backup amount foo", ".backup amount foo")
        assert "Invalid amount" in mock_deps["discord_manager"].send_temp_message.call_args[0][1]

    @pytest.mark.asyncio
    async def test_cmd_backup_all(self, handler, mock_message, mock_deps):
        """Test .backup all"""
        s1 = Mock(name="Server1")
        s2 = Mock(name="Server2")
        s1.name = "Server1"
        s2.name = "Server2"
        mock_deps["server_manager"].servers = [s1, s2]
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        mock_deps["backup_manager"].backup_server = AsyncMock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await handler.cmd_backup(mock_message, ".backup all", ".backup all")

        # Should backup both
        assert mock_deps["backup_manager"].backup_server.call_count == 2
        mock_deps["rcon_manager"].execute_for_server.assert_called_with(ANY, "SaveWorld")

    @pytest.mark.asyncio
    async def test_backup_single_server(self, handler, mock_message, mock_deps):
        """Test .backup TheIsland"""
        server = Mock(name="TheIsland")
        server.name = "TheIsland"
        mock_deps["server_manager"].find_server.return_value = server
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        mock_deps["backup_manager"].backup_server = AsyncMock()

        with patch("asyncio.sleep", new_callable=AsyncMock):
            await handler.cmd_backup(mock_message, ".backup TheIsland", ".backup theisland")

        mock_deps["rcon_manager"].execute_for_server.assert_called_with(server, "SaveWorld")
        mock_deps["backup_manager"].backup_server.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_restore_list(self, handler, mock_message, mock_deps):
        """Test .restore <map> listing backups"""
        server = Mock(name="TheIsland")
        server.name = "TheIsland"
        mock_deps["server_manager"].find_server.return_value = server
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TheIsland_1.zip", "TheIsland_2.zip", "Other_1.zip"]), \
             patch("os.path.getctime", side_effect=[1000, 2000]), \
             patch("os.path.getsize", return_value=1024*1024):
             
             await handler.cmd_restore(mock_message, ".restore TheIsland", ".restore theisland")
             
             # Should verify the output contains list
             mock_deps["discord_manager"].send_temp_message.assert_called()
             msg = mock_deps["discord_manager"].send_temp_message.call_args[0][1]
             assert "1. " in msg
             assert "2. " in msg
             assert "TheIsland_2.zip" in msg # Verifies "TheIsland_2.zip" is present in message.

    @pytest.mark.asyncio
    async def test_cmd_restore_flow(self, handler, mock_message, mock_deps):
        """Test full .restore flow"""
        server = Mock(name="TheIsland")
        server.name = "TheIsland"
        server.server_save_path = "/saved/TheIsland"
        mock_deps["server_manager"].find_server.return_value = server
        mock_deps["server_manager"].is_specific_server_running.return_value = True # Simulate running
        mock_deps["server_manager"].wait_for_server_shutdown = AsyncMock(return_value=True)
        
        # Mocking RaptorChatUtils
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TheIsland_backup.zip"]), \
             patch("os.path.getctime", return_value=1234), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.exists", return_value=True), \
             patch("shutil.copytree") as mock_copy, \
             patch("shutil.rmtree") as mock_rm, \
             patch("patchraptor.backup_restore_handler.BackupRestoreHandler.safe_extract") as mock_extract:
             
             mock_deps["server_manager"].wait_for_servers_online = AsyncMock(return_value=True)
             
             await handler.cmd_restore(mock_message, ".restore TheIsland 1", ".restore theisland 1")
             
             # Verify sequence:
             # 1. Shutdown
             mock_deps["rcon_manager"].execute_for_server.assert_any_call(server, "DoExit")
             mock_deps["server_manager"].wait_for_server_shutdown.assert_awaited()
             
             # 2. Backup current
             mock_copy.assert_called() # Backup of current save
             
             # 3. Wipe and Extract
             mock_rm.assert_called_with(server.server_save_path)
             mock_extract.assert_called()
             
             # 4. Restart
             mock_deps["server_manager"].start_server.assert_called_with(server)
             
             # 5. Wait for online
             mock_deps["server_manager"].wait_for_servers_online.assert_awaited()
    
    def test_safe_extract_path_traversal(self):
        """Test safe_extract prevents traversal"""
        # Mock zipfile
        with patch("zipfile.ZipFile") as mock_zip:
            mock_inst = MagicMock()
            mock_zip.return_value.__enter__.return_value = mock_inst
            
            # Case 1: '..' in filename
            bad_member = Mock()
            bad_member.filename = "../etc/passwd"
            mock_inst.infolist.return_value = [bad_member]
            
            from patchraptor.backup_restore_handler import BackupRestoreHandler
            with pytest.raises(BackupRestoreError) as exc:
                BackupRestoreHandler.safe_extract("test.zip", "/dest")
            assert "Invalid or corrupted" in str(exc.value)

    @pytest.mark.asyncio
    async def test_trigger_save_rcon_error(self, handler, mock_deps, mock_message):
        """Test _trigger_save_and_wait with RCON error."""
        server = Mock(name="TestServer")
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        mock_deps["rcon_manager"].execute_for_server.side_effect = RCONConnectionError("connect", "Connection refused")
        
        # Should handle error gracefully
        await handler._trigger_save_and_wait(server, mock_message.channel)
        
        mock_deps["discord_manager"].send_temp_message.assert_called()

    @pytest.mark.asyncio
    async def test_trigger_save_server_offline(self, handler, mock_deps, mock_message):
        """Test _trigger_save_and_wait when server is offline."""
        server = Mock(name="TestServer")
        mock_deps["server_manager"].is_specific_server_running.return_value = False
        
        await handler._trigger_save_and_wait(server, mock_message.channel)
        
        # Should not call RCON
        mock_deps["rcon_manager"].execute_for_server.assert_not_called()

    @pytest.mark.asyncio
    async def test_cmd_backup_insufficient_args(self, handler, mock_message, mock_deps):
        """Test .backup with insufficient arguments."""
        await handler.cmd_backup(mock_message, ".backup", ".backup")
        
        mock_deps["discord_manager"].send_temp_message.assert_called()
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_backup_amount_no_value(self, handler, mock_message, mock_deps):
        """Test .backup amount without value shows current count."""
        mock_deps["backup_manager"].retention_count = 7
        
        await handler.cmd_backup(mock_message, ".backup amount", ".backup amount")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "7" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_backup_server_not_found(self, handler, mock_message, mock_deps):
        """Test .backup with non-existent server."""
        mock_deps["server_manager"].find_server.side_effect = ServerNotFoundError("Not found")
        
        await handler.cmd_backup(mock_message, ".backup UnknownMap", ".backup unknownmap")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "No server found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_backup_creation_error(self, handler, mock_message, mock_deps):
        """Test .backup with BackupCreationError."""
        server = Mock(name="TestServer")
        mock_deps["server_manager"].find_server.return_value = server
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        mock_deps["backup_manager"].backup_server.side_effect = BackupCreationError("TestServer", "Disk full")
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await handler.cmd_backup(mock_message, ".backup TestServer", ".backup testserver")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "Failed to create backup" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_backup_filesystem_error(self, handler, mock_message, mock_deps):
        """Test .backup with FileSystemError."""
        from patchraptor.exceptions import FileSystemError
        server = Mock(name="TestServer")
        mock_deps["server_manager"].find_server.return_value = server
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        mock_deps["backup_manager"].backup_server.side_effect = FileSystemError("/path", "Permission denied")
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await handler.cmd_backup(mock_message, ".backup TestServer", ".backup testserver")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "File system error" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_insufficient_args(self, handler, mock_message, mock_deps):
        """Test .restore with insufficient arguments."""
        await handler.cmd_restore(mock_message, ".restore", ".restore")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_server_not_found(self, handler, mock_message, mock_deps):
        """Test .restore with non-existent server."""
        mock_deps["server_manager"].find_server.side_effect = ServerNotFoundError("Not found")
        
        await handler.cmd_restore(mock_message, ".restore UnknownMap", ".restore unknownmap")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "No server found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_no_backup_dir(self, handler, mock_message, mock_deps):
        """Test .restore when backup directory doesn't exist."""
        server = Mock(name="TestServer")
        mock_deps["server_manager"].find_server.return_value = server
        
        with patch("os.path.isdir", return_value=False):
            await handler.cmd_restore(mock_message, ".restore TestServer", ".restore testserver")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "No backups directory" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_no_backups_found(self, handler, mock_message, mock_deps):
        """Test .restore when no backups exist for server."""
        server = Mock(name="TestServer")
        server.name = "TestServer"
        mock_deps["server_manager"].find_server.return_value = server
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=[]):
            await handler.cmd_restore(mock_message, ".restore TestServer", ".restore testserver")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "No backups found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_invalid_index(self, handler, mock_message, mock_deps):
        """Test .restore with invalid backup index."""
        server = Mock(name="TestServer")
        server.name = "TestServer"
        mock_deps["server_manager"].find_server.return_value = server
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TestServer_1.zip"]), \
             patch("os.path.getctime", return_value=1000), \
             patch("os.path.getsize", return_value=1024):
            await handler.cmd_restore(mock_message, ".restore TestServer 99", ".restore testserver 99")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "Invalid backup number" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_invalid_save_path(self, handler, mock_message, mock_deps):
        """Test .restore when server save path is invalid."""
        server = Mock(name="TestServer")
        server.name = "TestServer"
        server.server_save_path = None
        mock_deps["server_manager"].find_server.return_value = server
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TestServer_1.zip"]), \
             patch("os.path.getctime", return_value=1000), \
             patch("os.path.getsize", return_value=1024):
            await handler.cmd_restore(mock_message, ".restore TestServer 1", ".restore testserver 1")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "Save path not found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_rcon_shutdown_error(self, handler, mock_message, mock_deps):
        """Test .restore when RCON shutdown fails."""
        server = Mock(name="TestServer")
        server.name = "TestServer"
        server.server_save_path = "/saved/TestServer"
        mock_deps["server_manager"].find_server.return_value = server
        
        # First call: server is running (for shutdown check)
        # Second call onwards: server comes back online
        mock_deps["server_manager"].is_specific_server_running.side_effect = [True, False, True]
        mock_deps["rcon_manager"].execute_for_server.side_effect = [
            RCONConnectionError("connect", "Connection refused"),  # Shutdown command fails
            None  # SaveWorld succeeds (server online check)
        ]
        mock_deps["server_manager"].wait_for_server_shutdown = AsyncMock(return_value=True)
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TestServer_1.zip"]), \
             patch("os.path.getctime", return_value=1000), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.exists", return_value=True), \
             patch("asyncio.sleep", new_callable=AsyncMock), \
             patch("patchraptor.backup_restore_handler.BackupRestoreHandler.safe_extract"):
            
            mock_deps["server_manager"].wait_for_servers_online = AsyncMock(return_value=True)
            await handler.cmd_restore(mock_message, ".restore TestServer 1", ".restore testserver 1")
        
        # Should still proceed with restore
        mock_deps["server_manager"].wait_for_server_shutdown.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_restore_timeout_waiting_online(self, handler, mock_message, mock_deps):
        """Test .restore when server doesn't come online."""
        server = Mock(name="TestServer")
        server.name = "TestServer"
        server.server_save_path = "/saved/TestServer"
        mock_deps["server_manager"].find_server.return_value = server
        mock_deps["server_manager"].is_specific_server_running.return_value = False  # Never comes online
        
        # Mock asyncio.sleep to raise exception after first call to break the loop
        sleep_count = 0
        async def mock_sleep(duration):
            nonlocal sleep_count
            sleep_count += 1
            if sleep_count > 1:  # Allow one iteration, then break
                raise asyncio.TimeoutError("Simulated timeout")
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TestServer_1.zip"]), \
             patch("os.path.getctime", return_value=1000), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.exists", return_value=True), \
             patch("shutil.copytree"), \
             patch("shutil.rmtree"), \
             patch("patchraptor.backup_restore_handler.BackupRestoreHandler.safe_extract"):
            
            mock_deps["server_manager"].wait_for_servers_online = AsyncMock(return_value=False)
            await handler.cmd_restore(mock_message, ".restore TestServer 1", ".restore testserver 1")
        
        # Should send timeout message
        calls = [str(call) for call in mock_deps["discord_manager"].send_temp_message.call_args_list]
        assert any("Timeout" in str(call) or "timeout" in str(call) for call in calls)

    @pytest.mark.asyncio
    async def test_cmd_restore_server_operation_error(self, handler, mock_message, mock_deps):
        """Test .restore with ServerOperationError during restart."""
        server = Mock(name="TestServer")
        server.name = "TestServer"
        server.server_save_path = "/saved/TestServer"
        mock_deps["server_manager"].find_server.return_value = server
        mock_deps["server_manager"].is_specific_server_running.return_value = False
        mock_deps["server_manager"].start_server.side_effect = ServerOperationError("start", "TestServer", "Failed to start")
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TestServer_1.zip"]), \
             patch("os.path.getctime", return_value=1000), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.exists", return_value=True), \
             patch("shutil.copytree"), \
             patch("shutil.rmtree"), \
             patch("patchraptor.backup_restore_handler.BackupRestoreHandler.safe_extract"):
            await handler.cmd_restore(mock_message, ".restore TestServer 1", ".restore testserver 1")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "Failed to restart" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_restore_unexpected_error(self, handler, mock_message, mock_deps):
        """Test .restore with unexpected exception."""
        server = Mock(name="TestServer")
        server.name = "TestServer"
        server.server_save_path = "/saved/TestServer"
        mock_deps["server_manager"].find_server.return_value = server
        mock_deps["server_manager"].is_specific_server_running.return_value = False
        
        with patch("os.path.isdir", return_value=True), \
             patch("os.listdir", return_value=["TestServer_1.zip"]), \
             patch("os.path.getctime", return_value=1000), \
             patch("os.path.getsize", return_value=1024), \
             patch("os.path.exists", side_effect=Exception("Unexpected error")):
            await handler.cmd_restore(mock_message, ".restore TestServer 1", ".restore testserver 1")
        
        args, _ = mock_deps["discord_manager"].send_temp_message.call_args
        assert "Unexpected error" in args[1]

    @pytest.mark.asyncio
    async def test_backup_all_maps_with_errors(self, handler, mock_deps, mock_message):
        """Test _backup_all_maps with various errors."""
        s1 = Mock(name="Server1")
        s2 = Mock(name="Server2")
        s3 = Mock(name="Server3")
        s1.name = "Server1"
        s2.name = "Server2"
        s3.name = "Server3"
        mock_deps["server_manager"].servers = [s1, s2, s3]
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        
        # Different errors for different servers
        mock_deps["backup_manager"].backup_server.side_effect = [
            None,  # Success
            BackupCreationError("Server2", "Disk full"),
            Exception("Unexpected")
        ]
        
        with patch("asyncio.sleep", new_callable=AsyncMock):
            await handler._backup_all_maps(mock_message.channel)
        
        # Should complete despite errors
        assert mock_deps["backup_manager"].backup_server.call_count == 3

    def test_safe_extract_absolute_path(self):
        """Test safe_extract prevents absolute path extraction."""
        with patch("zipfile.ZipFile") as mock_zip:
            mock_inst = MagicMock()
            mock_zip.return_value.__enter__.return_value = mock_inst
            
            bad_member = Mock()
            bad_member.filename = "/etc/passwd"
            mock_inst.infolist.return_value = [bad_member]
            
            with pytest.raises(BackupRestoreError):
                BackupRestoreHandler.safe_extract("test.zip", "/dest")

    def test_safe_extract_os_error(self):
        """Test safe_extract handles OSError."""
        with patch("zipfile.ZipFile") as mock_zip:
            mock_inst = MagicMock()
            mock_zip.return_value.__enter__.return_value = mock_inst
            
            member = Mock()
            member.filename = "valid.txt"
            mock_inst.infolist.return_value = [member]
            mock_inst.extract.side_effect = OSError("Permission denied")
            
            with pytest.raises(BackupRestoreError):
                BackupRestoreHandler.safe_extract("test.zip", "/dest")
