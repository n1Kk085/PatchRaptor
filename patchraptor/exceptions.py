"""
Custom exception classes for consistent error handling across the patchraptor codebase.
"""

from typing import Optional, Any


class PatchraptorException(Exception):
    """Base exception class for all patchraptor errors."""
    
    def __init__(self, message: str, details: Optional[Any] = None):
        self.message = message
        self.details = details
        super().__init__(self.message)


class ServerError(PatchraptorException):
    """Exception raised for server-related errors."""
    pass


class ServerNotFoundError(ServerError):
    """Exception raised when a server cannot be found."""
    
    def __init__(self, server_identifier: str):
        super().__init__(f"Server not found: {server_identifier}")
        self.server_identifier = server_identifier


class ServerNotRunningError(ServerError):
    """Exception raised when trying to operate on a server that is not running."""
    
    def __init__(self, server_name: str):
        super().__init__(f"Server is not running: {server_name}")
        self.server_name = server_name


class ServerAlreadyRunningError(ServerError):
    """Exception raised when trying to start a server that is already running."""
    
    def __init__(self, server_name: str):
        super().__init__(f"Server is already running: {server_name}")
        self.server_name = server_name


class ServerOperationError(ServerError):
    """Exception raised for general server operation failures."""
    
    def __init__(self, operation: str, server_name: str, reason: str):
        super().__init__(f"Failed to {operation} server '{server_name}': {reason}")
        self.operation = operation
        self.server_name = server_name
        self.reason = reason


class RCONError(PatchraptorException):
    """Exception raised for RCON-related errors."""
    pass


class RCONConnectionError(RCONError):
    """Exception raised when RCON connection fails."""
    
    def __init__(self, server_name: str, reason: str):
        super().__init__(f"RCON connection failed for server '{server_name}': {reason}")
        self.server_name = server_name
        self.reason = reason


class RCONCommandError(RCONError):
    """Exception raised when RCON command execution fails."""
    
    def __init__(self, command: str, server_name: str, reason: str):
        super().__init__(f"RCON command '{command}' failed on server '{server_name}': {reason}")
        self.command = command
        self.server_name = server_name
        self.reason = reason


class RCONValidationError(RCONError):
    """Exception raised when RCON command validation fails."""
    
    def __init__(self, command: str, reason: str):
        super().__init__(f"RCON command validation failed for '{command}': {reason}")
        self.command = command
        self.reason = reason


class BackupError(PatchraptorException):
    """Exception raised for backup-related errors."""
    pass


class BackupCreationError(BackupError):
    """Exception raised when backup creation fails."""
    
    def __init__(self, server_name: str, reason: str):
        super().__init__(f"Failed to create backup for server '{server_name}': {reason}")
        self.server_name = server_name
        self.reason = reason


class BackupRestoreError(BackupError):
    """Exception raised when backup restoration fails."""
    
    def __init__(self, server_name: str, backup_file: str, reason: str):
        super().__init__(f"Failed to restore backup '{backup_file}' for server '{server_name}': {reason}")
        self.server_name = server_name
        self.backup_file = backup_file
        self.reason = reason


class BackupNotFoundError(BackupError):
    """Exception raised when backup file cannot be found."""
    
    def __init__(self, backup_file: str):
        super().__init__(f"Backup file not found: {backup_file}")
        self.backup_file = backup_file


class ConfigurationError(PatchraptorException):
    """Exception raised for configuration-related errors."""
    pass


class ConfigurationNotFoundError(ConfigurationError):
    """Exception raised when configuration cannot be found."""
    
    def __init__(self, config_key: str):
        super().__init__(f"Configuration not found: {config_key}")
        self.config_key = config_key


class ConfigurationValidationError(ConfigurationError):
    """Exception raised when configuration validation fails."""
    
    def __init__(self, config_key: str, value: Any, reason: str):
        super().__init__(f"Configuration validation failed for '{config_key}': {reason}")
        self.config_key = config_key
        self.value = value
        self.reason = reason


class PlayerError(PatchraptorException):
    """Exception raised for player-related errors."""
    pass


class PlayerNotFoundError(PlayerError):
    """Exception raised when player cannot be found."""
    
    def __init__(self, player_identifier: str):
        super().__init__(f"Player not found: {player_identifier}")
        self.player_identifier = player_identifier


class PlayerOperationError(PlayerError):
    """Exception raised for player operation failures."""
    
    def __init__(self, operation: str, player_identifier: str, reason: str):
        super().__init__(f"Failed to {operation} player '{player_identifier}': {reason}")
        self.operation = operation
        self.player_identifier = player_identifier
        self.reason = reason


class FileSystemError(PatchraptorException):
    """Exception raised for file system-related errors."""
    pass


class FileNotFoundError(FileSystemError):
    """Exception raised when file or directory cannot be found."""
    
    def __init__(self, path: str):
        super().__init__(f"File or directory not found: {path}")
        self.path = path


class PermissionError(FileSystemError):
    """Exception raised when file system permission is denied."""
    
    def __init__(self, path: str, operation: str):
        super().__init__(f"Permission denied for {operation} on: {path}")
        self.path = path
        self.operation = operation


class DiskSpaceError(FileSystemError):
    """Exception raised when there is insufficient disk space."""
    
    def __init__(self, required_space: int, available_space: int):
        super().__init__(f"Insufficient disk space. Required: {required_space} bytes, Available: {available_space} bytes")
        self.required_space = required_space
        self.available_space = available_space


class ProcessError(PatchraptorException):
    """Exception raised for process-related errors."""
    pass


class ProcessNotFoundError(ProcessError):
    """Exception raised when process cannot be found."""
    
    def __init__(self, process_name: str):
        super().__init__(f"Process not found: {process_name}")
        self.process_name = process_name


class ProcessOperationError(ProcessError):
    """Exception raised for process operation failures."""
    
    def __init__(self, operation: str, process_name: str, reason: str):
        super().__init__(f"Failed to {operation} process '{process_name}': {reason}")
        self.operation = operation
        self.process_name = process_name
        self.reason = reason


class UpdateError(PatchraptorException):
    """Exception raised for update-related errors."""
    pass


class UpdateCheckError(UpdateError):
    """Exception raised when update check fails."""
    
    def __init__(self, reason: str):
        super().__init__(f"Failed to check for updates: {reason}")
        self.reason = reason


class UpdateDownloadError(UpdateError):
    """Exception raised when update download fails."""
    
    def __init__(self, reason: str):
        super().__init__(f"Failed to download update: {reason}")
        self.reason = reason


class ConfigSaveError(ConfigurationError):
    """Exception raised when configuration save fails."""
    
    def __init__(self, reason: str):
        super().__init__(f"Failed to save configuration: {reason}")
        self.reason = reason


class ConfigLoadError(ConfigurationError):
    """Exception raised when configuration load fails."""
    
    def __init__(self, reason: str):
        super().__init__(f"Failed to load configuration: {reason}")
        self.reason = reason


class ScheduleError(PatchraptorException):
    """Exception raised for schedule-related errors."""
    pass


class ScheduleParseError(ScheduleError):
    """Exception raised when schedule parsing fails."""
    
    def __init__(self, schedule_data: str, reason: str):
        super().__init__(f"Failed to parse schedule '{schedule_data}': {reason}")
        self.schedule_data = schedule_data
        self.reason = reason


class ScheduleOperationError(ScheduleError):
    """Exception raised for schedule operation failures."""
    
    def __init__(self, operation: str, reason: str):
        super().__init__(f"Failed to {operation} schedule: {reason}")
        self.operation = operation
        self.reason = reason
