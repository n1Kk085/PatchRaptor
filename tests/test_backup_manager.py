"""
Test suite for Backup Manager - validates backup creation and retention.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import os
import tempfile
import shutil
from pathlib import Path
from patchraptor.backup_manager import BackupManager
from patchraptor.models import ServerConfig
from patchraptor.exceptions import BackupCreationError, BackupError, DiskSpaceError, FileSystemError


@pytest.fixture
def temp_backup_dir(tmp_path):
    """Create a temporary backup directory."""
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()
    return str(backup_dir)


@pytest.fixture
def temp_root_dir(tmp_path):
    """Create a temporary root directory."""
    root_dir = tmp_path / "root"
    root_dir.mkdir()
    return str(root_dir)


@pytest.fixture
def mock_server(tmp_path):
    """Create a mock server configuration."""
    save_path = tmp_path / "saved"
    save_path.mkdir()
    (save_path / "test.ark").write_text("test data")
    
    return ServerConfig(
        name="TestServer",
        display_name="Test Server",
        map_name="TheIsland_WP",
        rcon_ip="127.0.0.1",
        rcon_port=27020,
        rcon_password="test123",
        start_command="C:\\test\\start.bat",
        install_dir="C:\\test",
        server_save_path=str(save_path),
        server_log_path="C:\\test\\logs\\game.log",
        log_dir="C:\\test\\logs"
    )


@pytest.fixture
def backup_manager(temp_backup_dir, temp_root_dir):
    """Create a BackupManager instance."""
    return BackupManager(
        backup_path=temp_backup_dir,
        root_dir=temp_root_dir,
        retention_count=5
    )


@pytest.fixture
def mock_discord_manager():
    """Create a mock Discord manager."""
    dm = Mock()
    dm.send_temp_message = AsyncMock()
    return dm


@pytest.fixture
def mock_server_manager():
    """Create a mock server manager."""
    sm = Mock()
    sm.get_display_name = Mock(return_value="Test Server")
    return sm


class TestBackupManagerInit:
    """Test BackupManager initialization."""
    
    def test_init_with_paths(self, temp_backup_dir, temp_root_dir):
        """Test initialization with paths."""
        bm = BackupManager(
            backup_path=temp_backup_dir,
            root_dir=temp_root_dir,
            retention_count=10
        )
        
        assert bm.backup_path == temp_backup_dir
        assert bm.root_dir == temp_root_dir
        assert bm.retention_count == 10
    
    def test_init_default_retention(self, temp_backup_dir, temp_root_dir):
        """Test initialization with default retention count."""
        bm = BackupManager(
            backup_path=temp_backup_dir,
            root_dir=temp_root_dir
        )
        
        assert bm.retention_count == 10  # Default


class TestCleanupOldBackups:
    """Test backup cleanup functionality."""
    
    def test_cleanup_old_backups(self, backup_manager, temp_backup_dir):
        """Test cleaning up old backups beyond retention count."""
        map_name = "TheIsland_WP"
        
        # Create 10 mock backup files with correct naming pattern
        for i in range(10):
            backup_file = Path(temp_backup_dir) / f"{map_name}_{i:02d}.zip"
            backup_file.touch()
        
        # Should keep only 5 (retention_count)
        backup_manager.cleanup_old_backups(map_name)
        
        # Count remaining backups with correct pattern
        remaining_backups = list(Path(temp_backup_dir).glob(f"{map_name}_*.zip"))
        assert len(remaining_backups) == 5
    
    def test_cleanup_no_backups(self, backup_manager):
        """Test cleanup with no existing backups."""
        # Should not raise exception
        backup_manager.cleanup_old_backups("NonExistentMap")
    
    def test_cleanup_backup_path_not_exists(self, temp_root_dir):
        """Test cleanup when backup path doesn't exist."""
        bm = BackupManager(
            backup_path="/nonexistent/path",
            root_dir=temp_root_dir,
            retention_count=5
        )
        
        # Should not raise exception
        bm.cleanup_old_backups("TestMap")
    
    def test_cleanup_getctime_error(self, backup_manager, temp_backup_dir):
        """Test cleanup handles getctime errors."""
        map_name = "TestMap"
        
        # Create backup files
        for i in range(3):
            backup_file = Path(temp_backup_dir) / f"{map_name}_{i}.zip"
            backup_file.touch()
        
        with patch('os.path.getctime', side_effect=[123456, OSError("Access denied"), 123458]):
            # Should handle error and continue
            backup_manager.cleanup_old_backups(map_name)
    
    def test_cleanup_remove_error(self, backup_manager, temp_backup_dir):
        """Test cleanup handles remove errors."""
        map_name = "TestMap"
        
        # Create 10 backup files
        for i in range(10):
            backup_file = Path(temp_backup_dir) / f"{map_name}_{i:02d}.zip"
            backup_file.touch()
        
        with patch('os.remove', side_effect=OSError("Permission denied")):
            # Should handle error and continue
            backup_manager.cleanup_old_backups(map_name)
    
    def test_cleanup_general_error(self, backup_manager):
        """Test cleanup handles general errors."""
        with patch('os.path.exists', side_effect=Exception("Unexpected error")):
            with pytest.raises(BackupError):
                backup_manager.cleanup_old_backups("TestMap")


class TestLogBackupEntry:
    """Test backup logging functionality."""
    
    def test_log_backup_entry_creates_file(self, backup_manager, temp_root_dir):
        """Test that logging creates backup.txt file."""
        map_name = "TheIsland_WP"
        zip_path = "C:\\backups\\test_backup.zip"
        
        backup_manager._log_backup_entry(map_name, zip_path)
        
        backup_log = Path(temp_root_dir) / "backup.txt"  # Uses root_dir not backup_path
        assert backup_log.exists()
    
    def test_log_backup_entry_appends(self, backup_manager, temp_root_dir):
        """Test that logging appends to existing file."""
        map_name = "TheIsland_WP"
        zip_path1 = "C:\\backups\\backup1.zip"
        zip_path2 = "C:\\backups\\backup2.zip"
        
        backup_manager._log_backup_entry(map_name, zip_path1)
        backup_manager._log_backup_entry(map_name, zip_path2)
        
        backup_log = Path(temp_root_dir) / "backup.txt"  # Uses root_dir not backup_path
        content = backup_log.read_text()
        
        assert "backup1.zip" in content
        assert "backup2.zip" in content
    
    def test_log_backup_entry_trimming(self, backup_manager, temp_root_dir):
        """Test that logging trims old entries."""
        map_name = "TestMap"
        
        # Add more entries than retention count
        for i in range(10):
            backup_manager._log_backup_entry(map_name, f"C:\\backups\\backup{i}.zip")
        
        backup_log = Path(temp_root_dir) / "backup.txt"
        lines = backup_log.read_text().strip().split('\n')
        
        # Should only keep retention_count entries
        assert len(lines) == 5
    
    def test_log_backup_entry_error(self, backup_manager):
        """Test that logging handles write errors gracefully."""
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            # Should not raise exception
            backup_manager._log_backup_entry("TestMap", "C:\\backups\\test.zip")


class TestBackupServer:
    """Test server backup functionality."""
    
    @pytest.mark.asyncio
    async def test_backup_server_success(self, backup_manager, mock_server, mock_discord_manager, mock_server_manager):
        """Test successful server backup."""
        mock_channel = Mock()
        
        with patch('shutil.make_archive', return_value=f"{backup_manager.backup_path}/TestServer_test.zip") as mock_archive, \
             patch('asyncio.to_thread', new_callable=AsyncMock, side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)):
            
            zip_path = await backup_manager.backup_server(mock_server, mock_channel, mock_discord_manager, mock_server_manager)
            
            assert zip_path.endswith(".zip")
            mock_discord_manager.send_temp_message.assert_called()
    
    @pytest.mark.asyncio
    async def test_backup_server_no_save_path(self, backup_manager, mock_discord_manager, mock_server_manager):
        """Test backup fails when save path not configured."""
        server = Mock()
        server.name = "TestServer"
        server.server_save_path = None
        
        with pytest.raises(BackupCreationError) as exc_info:
            await backup_manager.backup_server(server, Mock(), mock_discord_manager, mock_server_manager)
        
        assert "not configured" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_backup_server_save_path_not_exists(self, backup_manager, mock_discord_manager, mock_server_manager):
        """Test backup fails when save path doesn't exist."""
        server = Mock()
        server.name = "TestServer"
        server.server_save_path = "/nonexistent/path"
        
        with pytest.raises(BackupCreationError) as exc_info:
            await backup_manager.backup_server(server, Mock(), mock_discord_manager, mock_server_manager)
        
        assert "not found" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_backup_server_insufficient_disk_space(self, backup_manager, mock_server, mock_discord_manager, mock_server_manager):
        """Test backup fails with insufficient disk space."""
        mock_disk_usage = Mock()
        mock_disk_usage.free = 100  # Very small
        
        # Mock os.walk to return a large size
        def mock_walk(path):
            yield (path, [], ["large_file.ark"])
        
        with patch('shutil.disk_usage', return_value=mock_disk_usage), \
             patch('os.walk', side_effect=mock_walk), \
             patch('os.path.getsize', return_value=1000000):  # 1MB file
            with pytest.raises(DiskSpaceError):
                await backup_manager.backup_server(mock_server, Mock(), mock_discord_manager, mock_server_manager)
    
    @pytest.mark.asyncio
    async def test_backup_server_disk_check_error(self, backup_manager, mock_server, mock_discord_manager, mock_server_manager):
        """Test backup handles disk check errors."""
        with patch('shutil.disk_usage', side_effect=OSError("Disk error")):
            with pytest.raises(FileSystemError):
                await backup_manager.backup_server(mock_server, Mock(), mock_discord_manager, mock_server_manager)
    
    @pytest.mark.asyncio
    async def test_backup_server_archive_error(self, backup_manager, mock_server, mock_discord_manager, mock_server_manager):
        """Test backup handles archive creation errors."""
        with patch('asyncio.to_thread', side_effect=shutil.Error("Archive failed")):
            with pytest.raises(BackupCreationError):
                await backup_manager.backup_server(mock_server, Mock(), mock_discord_manager, mock_server_manager)
    
    @pytest.mark.asyncio
    async def test_backup_server_unexpected_error(self, backup_manager, mock_server, mock_discord_manager, mock_server_manager):
        """Test backup handles unexpected errors."""
        with patch('os.makedirs', side_effect=Exception("Unexpected error")):
            with pytest.raises(BackupCreationError):
                await backup_manager.backup_server(mock_server, Mock(), mock_discord_manager, mock_server_manager)
