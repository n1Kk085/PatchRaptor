import os
import shutil
import datetime
from .log_manager import logger
from .models import ServerConfig
from .exceptions import (
    BackupError,
    BackupCreationError,
    BackupRestoreError,
    BackupNotFoundError,
    FileSystemError,
    FileNotFoundError,
    PermissionError,
    DiskSpaceError
)

class BackupManager:
    """Manages server backups and retention"""
    def __init__(self, backup_path: str, retention_count: int = 10):
        self.backup_path = backup_path
        self.retention_count = retention_count

    def cleanup_old_backups(self, map_name: str) -> None:
        """Clean up old backups beyond retention count"""
        logger.debug_backup(f"Starting cleanup of old backups for: {map_name}")
        
        try:
            if not os.path.exists(self.backup_path):
                logger.debug_backup(f"Backup path does not exist: {self.backup_path}")
                return
            
            logger.debug_backup(f"Scanning for backups in: {self.backup_path}")
            backups = []
            for item in os.listdir(self.backup_path):
                if item.startswith(f"{map_name}_") and item.endswith(".zip"):
                    backup_file = os.path.join(self.backup_path, item)
                    logger.debug_backup(f"Found backup file: {item}")
                    try:
                        creation_time = os.path.getctime(backup_file)
                        backups.append((creation_time, backup_file, item))
                        logger.debug_backup(f"Backup {item} creation time: {creation_time}")
                    except OSError as e:
                        logger.debug_backup(f"Failed to get creation time for {backup_file}: {e}")
                        logger.warning_system(f"Failed to get creation time for {backup_file}: {e}")
                        continue
            
            logger.debug_backup(f"Found {len(backups)} total backups for {map_name}")
            backups.sort(reverse=True)
            
            if len(backups) > self.retention_count:
                backups_to_remove = backups[self.retention_count:]
                logger.debug_backup(f"Removing {len(backups_to_remove)} old backups (retention: {self.retention_count})")
                
                for _, backup_file, backup_name in backups_to_remove:
                    try:
                        logger.debug_backup(f"Removing old backup: {backup_name}")
                        os.remove(backup_file)
                        logger.info_system(f"Removed old backup: {backup_name}")
                        logger.debug_backup(f"Successfully removed: {backup_name}")
                    except OSError as e:
                        logger.debug_backup(f"Failed to remove old backup {backup_name}: {e}")
                        logger.warning_system(f"Failed to remove old backup {backup_name}: {e}")
            else:
                logger.debug_backup(f"No backups to remove (current: {len(backups)}, retention: {self.retention_count})")
                    
        except Exception as e:
            logger.debug_backup(f"Backup cleanup failed for {map_name}: {e}")
            logger.error_system(f"Failed to cleanup backups for {map_name}: {e}")
            raise BackupError(f"Backup cleanup failed for {map_name}: {e}")

    def _log_backup_entry(self, map_name: str, zip_path: str) -> None:
        """Log backup entry to backup.txt file"""
        logger.debug_backup(f"Logging backup entry for {map_name}: {zip_path}")
        
        try:
            backup_entry = f"{datetime.datetime.now().isoformat()} | {map_name} | {zip_path}\n"
            logger.debug_backup(f"Backup entry: {backup_entry.strip()}")
            
            existing_lines = []
            backup_log_file = "backup.txt"
            logger.debug_backup(f"Backup log file: {backup_log_file}")
            
            if os.path.exists(backup_log_file):
                logger.debug_backup(f"Reading existing backup log entries")
                with open(backup_log_file, "r") as f:
                    existing_lines = f.readlines()
                logger.debug_backup(f"Found {len(existing_lines)} existing log entries")
            else:
                logger.debug_backup(f"Backup log file does not exist, will create new one")
            
            existing_lines.append(backup_entry)
            logger.debug_backup(f"Added new entry to log (total: {len(existing_lines)})")
            
            if len(existing_lines) > self.retention_count:
                logger.debug_backup(f"Trimming log to {self.retention_count} entries (current: {len(existing_lines)})")
                existing_lines = existing_lines[-self.retention_count:]
            
            logger.debug_backup(f"Writing {len(existing_lines)} entries to backup log")
            with open(backup_log_file, "w") as f:
                f.writelines(existing_lines)
                
            logger.debug_backup(f"Backup entry logged successfully")
                
        except OSError as e:
            logger.debug_backup(f"Failed to log backup entry: {e}")
            logger.warning_system(f"Failed to log backup entry: {e}")
            # Don't raise here as logging failure shouldn't stop the backup process

    async def backup_server(self, server: ServerConfig, channel, discord_manager, server_manager) -> str:
        """Create a backup of the specified server"""
        import time
        start_time = time.time()
        
        logger.debug_backup(f"Starting backup for server: {server.name}")
        
        # Validate server save path
        if not server.server_save_path:
            logger.debug_backup(f"Backup failed for {server.name}: save path not configured")
            raise BackupCreationError(server.name, "Server save path is not configured")
        
        logger.debug_backup(f"Server save path: {server.server_save_path}")
        
        if not os.path.exists(server.server_save_path):
            logger.debug_backup(f"Backup failed for {server.name}: save folder not found at {server.server_save_path}")
            raise BackupCreationError(server.name, f"Save folder not found: {server.server_save_path}")
        
        # Check disk space
        logger.debug_backup(f"Checking disk space for backup")
        try:
            disk_usage = shutil.disk_usage(self.backup_path)
            logger.debug_backup(f"Available disk space: {disk_usage.free} bytes")
            
            save_path_size = sum(os.path.getsize(os.path.join(dirpath, filename)) 
                               for dirpath, dirnames, filenames in os.walk(server.server_save_path) 
                               for filename in filenames)
            
            logger.debug_backup(f"Save path size: {save_path_size} bytes")
            
            if save_path_size > disk_usage.free:
                logger.debug_backup(f"Backup failed for {server.name}: insufficient disk space (needed: {save_path_size}, available: {disk_usage.free})")
                raise DiskSpaceError(save_path_size, disk_usage.free)
        except OSError as e:
            logger.debug_backup(f"Disk space check failed for {server.name}: {e}")
            raise FileSystemError(f"Failed to check disk space: {e}")
        
        timestamp = datetime.datetime.now().strftime("%d%m%y_%H%M%S")
        backup_name = os.path.join(self.backup_path, f"{server.name}_{timestamp}")
        logger.debug_backup(f"Backup name: {backup_name}")
        
        try:
            # Create backup directory if it doesn't exist
            logger.debug_backup(f"Creating backup directory: {self.backup_path}")
            os.makedirs(self.backup_path, exist_ok=True)
            
            display_name = server_manager.get_display_name(server)
            logger.debug_backup(f"Sending backup start message to Discord for {display_name}")
            await discord_manager.send_temp_message(channel, f"🦕 {display_name} is backing up now...")
            
            # Create the backup
            logger.debug_backup(f"Creating backup archive from {server.server_save_path}")
            zip_path = await __import__('asyncio').to_thread(
                shutil.make_archive,
                base_name=backup_name,
                format='zip',
                root_dir=server.server_save_path
            )
            
            backup_time = time.time() - start_time
            logger.debug_backup(f"Backup archive created in {backup_time:.2f}s: {zip_path}")
            
            # Clean up old backups
            logger.debug_backup(f"Cleaning up old backups for server: {server.name}")
            self.cleanup_old_backups(server.name)
            
            # Log the backup
            backup_filename = os.path.basename(zip_path)
            logger.debug_backup(f"Sending backup completion message to Discord")
            await discord_manager.send_temp_message(channel, f"🦖 Backup completed for '{display_name}' ({backup_filename})")
            logger.info_system(f"Backup for '{server.name}' created at '{zip_path}'")
            logger.debug_backup(f"Logging backup entry to backup.txt")
            self._log_backup_entry(server.name, zip_path)
            
            return zip_path
            
        except (OSError, shutil.Error) as e:
            error_msg = f"File system error during backup: {e}"
            logger.error_system(f"Backup failed for '{server.name}': {error_msg}")
            logger.debug_backup(f"Backup failed for {server.name}: file system error - {e}")
            raise BackupCreationError(server.name, error_msg)
        except Exception as e:
            error_msg = str(e)
            logger.error_system(f"Backup failed for '{server.name}': {error_msg}")
            logger.debug_backup(f"Backup failed for {server.name}: unexpected error - {e}")
            raise BackupCreationError(server.name, error_msg)
