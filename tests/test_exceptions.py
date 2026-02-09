"""
Test suite for custom exception classes.
"""
import pytest
from patchraptor.exceptions import (
    PatchraptorException,
    ServerError, ServerNotFoundError, ServerNotRunningError,
    ServerAlreadyRunningError, ServerOperationError,
    RCONError, RCONConnectionError, RCONCommandError, RCONValidationError,
    BackupError, BackupCreationError, BackupRestoreError, BackupNotFoundError,
    ConfigurationError, ConfigurationNotFoundError, ConfigurationValidationError,
    ConfigSaveError, ConfigLoadError,
    PlayerError, PlayerNotFoundError, PlayerOperationError,
    FileSystemError, FileNotFoundError, PermissionError, DiskSpaceError,
    ProcessError, ProcessNotFoundError, ProcessOperationError,
    UpdateError, UpdateCheckError, UpdateDownloadError,
    ScheduleError, ScheduleParseError, ScheduleOperationError
)


class TestBaseException:
    """Test base PatchraptorException class."""
    
    def test_base_exception_with_message(self):
        """Test creating base exception with message."""
        exc = PatchraptorException("Test error")
        assert str(exc) == "Test error"
        assert exc.message == "Test error"
        assert exc.details is None
    
    def test_base_exception_with_details(self):
        """Test creating base exception with details."""
        details = {"key": "value"}
        exc = PatchraptorException("Test error", details=details)
        assert exc.message == "Test error"
        assert exc.details == details


class TestServerExceptions:
    """Test server-related exceptions."""
    
    def test_server_error(self):
        """Test base ServerError."""
        exc = ServerError("Server error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "Server error"
    
    def test_server_not_found_error(self):
        """Test ServerNotFoundError."""
        exc = ServerNotFoundError("TheIsland")
        assert isinstance(exc, ServerError)
        assert "TheIsland" in str(exc)
        assert exc.server_identifier == "TheIsland"
    
    def test_server_not_running_error(self):
        """Test ServerNotRunningError."""
        exc = ServerNotRunningError("TheCenter")
        assert isinstance(exc, ServerError)
        assert "TheCenter" in str(exc)
        assert exc.server_name == "TheCenter"
    
    def test_server_already_running_error(self):
        """Test ServerAlreadyRunningError."""
        exc = ServerAlreadyRunningError("Ragnarok")
        assert isinstance(exc, ServerError)
        assert "Ragnarok" in str(exc)
        assert exc.server_name == "Ragnarok"
    
    def test_server_operation_error(self):
        """Test ServerOperationError."""
        exc = ServerOperationError("start", "TheIsland", "Port in use")
        assert isinstance(exc, ServerError)
        assert "start" in str(exc)
        assert "TheIsland" in str(exc)
        assert "Port in use" in str(exc)
        assert exc.operation == "start"
        assert exc.server_name == "TheIsland"
        assert exc.reason == "Port in use"


class TestRCONExceptions:
    """Test RCON-related exceptions."""
    
    def test_rcon_error(self):
        """Test base RCONError."""
        exc = RCONError("RCON error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "RCON error"
    
    def test_rcon_connection_error(self):
        """Test RCONConnectionError."""
        exc = RCONConnectionError("TheIsland", "Connection refused")
        assert isinstance(exc, RCONError)
        assert "TheIsland" in str(exc)
        assert "Connection refused" in str(exc)
        assert exc.server_name == "TheIsland"
        assert exc.reason == "Connection refused"
    
    def test_rcon_command_error(self):
        """Test RCONCommandError."""
        exc = RCONCommandError("SaveWorld", "TheCenter", "Timeout")
        assert isinstance(exc, RCONError)
        assert "SaveWorld" in str(exc)
        assert "TheCenter" in str(exc)
        assert "Timeout" in str(exc)
        assert exc.command == "SaveWorld"
        assert exc.server_name == "TheCenter"
        assert exc.reason == "Timeout"
    
    def test_rcon_validation_error(self):
        """Test RCONValidationError."""
        exc = RCONValidationError("InvalidCmd", "Unknown command")
        assert isinstance(exc, RCONError)
        assert "InvalidCmd" in str(exc)
        assert "Unknown command" in str(exc)
        assert exc.command == "InvalidCmd"
        assert exc.reason == "Unknown command"


class TestBackupExceptions:
    """Test backup-related exceptions."""
    
    def test_backup_error(self):
        """Test base BackupError."""
        exc = BackupError("Backup error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "Backup error"
    
    def test_backup_creation_error(self):
        """Test BackupCreationError."""
        exc = BackupCreationError("TheIsland", "Disk full")
        assert isinstance(exc, BackupError)
        assert "TheIsland" in str(exc)
        assert "Disk full" in str(exc)
        assert exc.server_name == "TheIsland"
        assert exc.reason == "Disk full"
    
    def test_backup_restore_error(self):
        """Test BackupRestoreError."""
        exc = BackupRestoreError("TheCenter", "backup_20240101.tar", "Corrupted")
        assert isinstance(exc, BackupError)
        assert "TheCenter" in str(exc)
        assert "backup_20240101.tar" in str(exc)
        assert "Corrupted" in str(exc)
        assert exc.server_name == "TheCenter"
        assert exc.backup_file == "backup_20240101.tar"
        assert exc.reason == "Corrupted"
    
    def test_backup_not_found_error(self):
        """Test BackupNotFoundError."""
        exc = BackupNotFoundError("missing_backup.tar")
        assert isinstance(exc, BackupError)
        assert "missing_backup.tar" in str(exc)
        assert exc.backup_file == "missing_backup.tar"


class TestConfigurationExceptions:
    """Test configuration-related exceptions."""
    
    def test_configuration_error(self):
        """Test base ConfigurationError."""
        exc = ConfigurationError("Config error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "Config error"
    
    def test_configuration_not_found_error(self):
        """Test ConfigurationNotFoundError."""
        exc = ConfigurationNotFoundError("server_port")
        assert isinstance(exc, ConfigurationError)
        assert "server_port" in str(exc)
        assert exc.config_key == "server_port"
    
    def test_configuration_validation_error(self):
        """Test ConfigurationValidationError."""
        exc = ConfigurationValidationError("port", 99999, "Out of range")
        assert isinstance(exc, ConfigurationError)
        assert "port" in str(exc)
        assert "Out of range" in str(exc)
        assert exc.config_key == "port"
        assert exc.value == 99999
        assert exc.reason == "Out of range"
    
    def test_config_save_error(self):
        """Test ConfigSaveError."""
        exc = ConfigSaveError("Permission denied")
        assert isinstance(exc, ConfigurationError)
        assert "Permission denied" in str(exc)
        assert exc.reason == "Permission denied"
    
    def test_config_load_error(self):
        """Test ConfigLoadError."""
        exc = ConfigLoadError("File not found")
        assert isinstance(exc, ConfigurationError)
        assert "File not found" in str(exc)
        assert exc.reason == "File not found"


class TestPlayerExceptions:
    """Test player-related exceptions."""
    
    def test_player_error(self):
        """Test base PlayerError."""
        exc = PlayerError("Player error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "Player error"
    
    def test_player_not_found_error(self):
        """Test PlayerNotFoundError."""
        exc = PlayerNotFoundError("PlayerName123")
        assert isinstance(exc, PlayerError)
        assert "PlayerName123" in str(exc)
        assert exc.player_identifier == "PlayerName123"
    
    def test_player_operation_error(self):
        """Test PlayerOperationError."""
        exc = PlayerOperationError("ban", "PlayerName123", "Invalid reason")
        assert isinstance(exc, PlayerError)
        assert "ban" in str(exc)
        assert "PlayerName123" in str(exc)
        assert "Invalid reason" in str(exc)
        assert exc.operation == "ban"
        assert exc.player_identifier == "PlayerName123"
        assert exc.reason == "Invalid reason"


class TestFileSystemExceptions:
    """Test file system-related exceptions."""
    
    def test_filesystem_error(self):
        """Test base FileSystemError."""
        exc = FileSystemError("FS error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "FS error"
    
    def test_file_not_found_error(self):
        """Test FileNotFoundError."""
        exc = FileNotFoundError("/path/to/file.txt")
        assert isinstance(exc, FileSystemError)
        assert "/path/to/file.txt" in str(exc)
        assert exc.path == "/path/to/file.txt"
    
    def test_permission_error(self):
        """Test PermissionError."""
        exc = PermissionError("/protected/file", "write")
        assert isinstance(exc, FileSystemError)
        assert "/protected/file" in str(exc)
        assert "write" in str(exc)
        assert exc.path == "/protected/file"
        assert exc.operation == "write"
    
    def test_disk_space_error(self):
        """Test DiskSpaceError."""
        exc = DiskSpaceError(1000000, 500000)
        assert isinstance(exc, FileSystemError)
        assert "1000000" in str(exc)
        assert "500000" in str(exc)
        assert exc.required_space == 1000000
        assert exc.available_space == 500000


class TestProcessExceptions:
    """Test process-related exceptions."""
    
    def test_process_error(self):
        """Test base ProcessError."""
        exc = ProcessError("Process error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "Process error"
    
    def test_process_not_found_error(self):
        """Test ProcessNotFoundError."""
        exc = ProcessNotFoundError("steamcmd.exe")
        assert isinstance(exc, ProcessError)
        assert "steamcmd.exe" in str(exc)
        assert exc.process_name == "steamcmd.exe"
    
    def test_process_operation_error(self):
        """Test ProcessOperationError."""
        exc = ProcessOperationError("kill", "server.exe", "Access denied")
        assert isinstance(exc, ProcessError)
        assert "kill" in str(exc)
        assert "server.exe" in str(exc)
        assert "Access denied" in str(exc)
        assert exc.operation == "kill"
        assert exc.process_name == "server.exe"
        assert exc.reason == "Access denied"


class TestUpdateExceptions:
    """Test update-related exceptions."""
    
    def test_update_error(self):
        """Test base UpdateError."""
        exc = UpdateError("Update error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "Update error"
    
    def test_update_check_error(self):
        """Test UpdateCheckError."""
        exc = UpdateCheckError("Network timeout")
        assert isinstance(exc, UpdateError)
        assert "Network timeout" in str(exc)
        assert exc.reason == "Network timeout"
    
    def test_update_download_error(self):
        """Test UpdateDownloadError."""
        exc = UpdateDownloadError("Checksum mismatch")
        assert isinstance(exc, UpdateError)
        assert "Checksum mismatch" in str(exc)
        assert exc.reason == "Checksum mismatch"


class TestScheduleExceptions:
    """Test schedule-related exceptions."""
    
    def test_schedule_error(self):
        """Test base ScheduleError."""
        exc = ScheduleError("Schedule error")
        assert isinstance(exc, PatchraptorException)
        assert str(exc) == "Schedule error"
    
    def test_schedule_parse_error(self):
        """Test ScheduleParseError."""
        exc = ScheduleParseError("0 0 * * *", "Invalid format")
        assert isinstance(exc, ScheduleError)
        assert "0 0 * * *" in str(exc)
        assert "Invalid format" in str(exc)
        assert exc.schedule_data == "0 0 * * *"
        assert exc.reason == "Invalid format"
    
    def test_schedule_operation_error(self):
        """Test ScheduleOperationError."""
        exc = ScheduleOperationError("add", "Time conflict")
        assert isinstance(exc, ScheduleError)
        assert "add" in str(exc)
        assert "Time conflict" in str(exc)
        assert exc.operation == "add"
        assert exc.reason == "Time conflict"
