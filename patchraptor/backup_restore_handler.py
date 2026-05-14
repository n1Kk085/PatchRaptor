import asyncio
import os
import datetime as _dt
import shutil
import zipfile
from .log_manager import logger
from .server_manager import ServerManager
from .rcon_manager import RCONManager
from .backup_manager import BackupManager
from .discord_manager import DiscordManager
from .config import ConfigManager
from .service_locator import ServiceLocator
from .exceptions import (
    ServerError,
    ServerNotFoundError,
    ServerNotRunningError,
    ServerAlreadyRunningError,
    ServerOperationError,
    BackupError,
    BackupCreationError,
    BackupRestoreError,
    BackupNotFoundError,
    FileSystemError,
    DiskSpaceError,
    FileNotFoundError,
    PermissionError,
    RCONError,
    RCONConnectionError,
    RCONCommandError
)
from .system_utils import SystemUtils
from .base_handler import BaseHandler


class BackupRestoreHandler(BaseHandler):
    """Handles backup and restore commands: backup, restore"""

    def _get_highest_ark_mtime(self, save_path):
        """Get the highest modification time of any .ark file in the save path"""
        highest = 0
        try:
            if not isinstance(save_path, str) or not os.path.isdir(save_path):
                return highest
            for f in os.listdir(save_path):
                if f.lower().endswith('.ark'):
                    fpath = os.path.join(save_path, f)
                    if os.path.exists(fpath):
                        highest = max(highest, os.path.getmtime(fpath))
        except Exception as e:
            logger.debug_system(f"Error checking ark mtimes: {e}")
        return highest

    async def _trigger_save_and_wait(self, server, channel):
        """Send SaveWorld and wait for file modification time to increase"""
        if self.server_manager.is_specific_server_running(server):
            display_name = self.server_manager.get_display_name(server)
            try:
                save_path = getattr(server, 'server_save_path', None)
                initial_mtime = self._get_highest_ark_mtime(save_path)
                
                # Notify save trigger
                await self.discord_manager.send_temp_message(channel, f"💾 Triggering world save for {display_name}...")
                logger.info_system(f"Sending SaveWorld RCON command to {server.name}")
                
                # We expect "World Saved" or similar in response, but we'll rely on mtime for truth
                await self.rcon_manager.execute_for_server(server, "SaveWorld")
                
                # Wait for file modification and flush (max 15s)
                await self.discord_manager.send_temp_message(channel, f"⏳ Validating save flush for {display_name}...")
                
                save_confirmed = False
                for attempt in range(3): # 3 * 5s = 15s max
                    await asyncio.sleep(5)
                    
                    current_mtime = self._get_highest_ark_mtime(save_path)
                    if current_mtime > initial_mtime:
                        # Save detected, now wait for size to stabilize (flush completion)
                        updated_file = None
                        if save_path and os.path.isdir(save_path):
                            for f in os.listdir(save_path):
                                if f.lower().endswith('.ark'):
                                    fpath = os.path.join(save_path, f)
                                    if os.path.exists(fpath) and os.path.getmtime(fpath) > initial_mtime:
                                        updated_file = fpath
                                        break
                        
                        if updated_file:
                            last_size = os.path.getsize(updated_file)
                            await asyncio.sleep(2)
                            if os.path.getsize(updated_file) == last_size:
                                logger.info_system(f"Save confirmed for {server.name} (mtime: {current_mtime})")
                                save_confirmed = True
                                break
                        else:
                            await asyncio.sleep(2)
                            save_confirmed = True
                            break
                
                if not save_confirmed:
                    await asyncio.sleep(2) # Short fallback wait
                else:
                    await self.discord_manager.send_temp_message(channel, f"✅ Save confirmed for {display_name}.")
                
            except (RCONConnectionError, RCONCommandError) as e:
                logger.warning_system(f"Failed to send SaveWorld to {server.name}: {e}. Proceeding with backup anyway.")
                await self.discord_manager.send_temp_message(channel, f"⚠️ RCON failed ({e}), proceeding with backup...")
            except Exception as e:
                logger.error_system(f"Error during save validation for {server.name}: {e}")
                await asyncio.sleep(10) # Fallback wait
        else:
            logger.info_system(f"{server.name} is offline, skipping SaveWorld")

    async def cmd_backup(self, message, content: str, content_lower: str):
        """Handle .backup command"""
        author_id = getattr(getattr(message, "author", None), "id", None)
        if author_id == "ScheduleSystem":
            logger.info_command("Scheduled .backup initialising...")
        else:
            logger.info_command(".backup received")
        parts = content.strip().split()
        
        if len(parts) < 2:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Usage: .backup <all | map_name | amount <number>>"
            )
            return
        
        sub_command = parts[1].lower()
        
        if sub_command == "amount":
            if len(parts) < 3:
                current_count = self.backup_manager.retention_count
                await self.discord_manager.send_temp_message(
                    message.channel, f"ℹ️ Current backup retention count: {current_count}. Usage: .backup amount <number>"
                )
                return
            
            try:
                new_amount = int(parts[2])
                if new_amount <= 0:
                    await self.discord_manager.send_temp_message(
                        message.channel, "⚠️ Amount must be a positive number."
                    )
                    return
                
                self.backup_manager.retention_count = new_amount
                
                # Update nested backup_config structure
                backup_config = self.config_manager.config.get("backup_config", {})
                backup_config["backup_retention_count"] = new_amount
                self.config_manager.config["backup_config"] = backup_config
                self.config_manager.save()
                await self.discord_manager.send_temp_message(
                    message.channel, f"🦖 Backup retention count updated to {new_amount} per map."
                )
            except ValueError:
                await self.discord_manager.send_temp_message(
                    message.channel, "⚠️ Invalid amount. Usage: .backup amount <number>"
                )
        
        elif sub_command == "all":
            logger.info_system("Starting backup process for all servers...")
            await self._backup_all_maps(message.channel)
        
        else:
            # Backup specific map
            map_name_arg = content.split(maxsplit=1)[1]
            try:
                server = self.server_manager.find_server(map_name_arg)
            except ServerNotFoundError:
                await self.discord_manager.send_temp_message(
                    message.channel, f"⚠️ No server found with name or map '{map_name_arg}'."
                )
                return
            
            logger.info_system(f"Starting backup process for {server.name}...")
            try:
                await self._trigger_save_and_wait(server, message.channel)
                logger.info_system(f"Creating backup for {server.name}...")
                await self.backup_manager.backup_server(server, message.channel, self.discord_manager, self.server_manager)
                logger.info_system(f"Backup completed successfully for {server.name}")
            except BackupCreationError as e:
                logger.error_system(f"Failed to create backup for {server.name}: {e.reason}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to create backup for {self.server_manager.get_display_name(server)}: {e.reason}")
                return
            except (FileSystemError, DiskSpaceError) as e:
                logger.error_system(f"File system error during backup for {server.name}: {e.message}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ File system error during backup: {e.message}")
                return

    async def cmd_restore(self, message, content: str, content_lower: str):
        """Handle .restore command"""
        logger.info_command(".restore received")
        # .restore <map_name> [index]
        parts = content.split()
        if len(parts) < 2:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: .restore <map_name> [number]")
            return
        map_name = parts[1]
        try:
            server = self.server_manager.find_server(map_name)
        except ServerNotFoundError:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with name '{map_name}'.")
            return
        
        backup_dir = self.backup_manager.backup_path
        if not os.path.isdir(backup_dir):
            await self.discord_manager.send_temp_message(message.channel, "⚠️ No backups directory found.")
            return
        
        # List backups for map
        backups = []
        for item in os.listdir(backup_dir):
            if item.startswith(f"{server.name}_") and item.endswith('.zip'):
                fpath = os.path.join(backup_dir, item)
                try:
                    ts = os.path.getctime(fpath)
                    size_mb = os.path.getsize(fpath) / (1024*1024)
                    backups.append((ts, fpath, item, size_mb))
                except OSError:
                    continue
        backups.sort(reverse=True)
        
        if len(parts) == 2:
            if not backups:
                await self.discord_manager.send_temp_message(message.channel, f"ℹ️ No backups found for map '{server.name}'.")
                return
            lines = [f"Backups for {server.name}:"]
            for i, (ts, _, filename, size) in enumerate(backups, 1):
                dt = _dt.datetime.fromtimestamp(ts).strftime('%d-%m-%y %H:%M:%S')
                lines.append(f"{i}. {filename} ({size:.2f} MB) - {dt}")
            lines.append("\nUse: .restore <map_name> <number> to restore a backup")
            await self.discord_manager.send_temp_message(message.channel, "\n".join(lines))
            return
        
        # Perform restore
        logger.info_system(f"Starting restore process for {server.name}...")
        try:
            idx = int(parts[2])
            if idx <= 0 or idx > len(backups):
                raise ValueError
        except ValueError:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Invalid backup number.")
            return
        
        _, backup_file, _, _ = backups[idx-1]
        logger.info_system(f"Selected backup: {os.path.basename(backup_file)}")
        
        # Extract backup to server save path
        if not server.server_save_path or not os.path.isdir(server.server_save_path):
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ Save path not found for '{server.name}'.")
            return
        
        try:
            display_name = self.server_manager.get_display_name(server)
            
            # Step 1: Check if server is running and shut it down
            server_was_running = self.server_manager.is_specific_server_running(server)
            
            if server_was_running:
                logger.info_system(f"Found running {server.name} server, initiating shutdown for restore...")
                await self.discord_manager.send_temp_message(
                    message.channel, f"⏹️ Shutting down {display_name} server for restore..."
                )
                
                try:
                    await self.rcon_manager.execute_for_server(server, "DoExit")
                    logger.info_system(f"Successfully sent to {server.name}")
                except (RCONConnectionError, RCONCommandError) as e:
                    logger.warning_system(f"Failed to send shutdown to {server.name}: {e.reason}")
                
                # Wait for server to shut down
                logger.info_system(f"Waiting for {server.name} to shut down...")
                await self.discord_manager.send_temp_message(
                    message.channel, f"🦕 Waiting for {display_name} server to shut down..."
                )
                
                shutdown_success = await self.server_manager.wait_for_server_shutdown(server, 300)
                if shutdown_success:
                    logger.info_system(f"{server.name} server has shut down successfully")
                    await self.discord_manager.send_temp_message(
                        message.channel, f"🦖 {display_name} server has shut down successfully..."
                    )
                else:
                    logger.warning_system(f"Timeout waiting for {server.name} to shut down")
            else:
                logger.info_system(f"{server.name} server was not running, proceeding with restore")
                await self.discord_manager.send_temp_message(
                    message.channel, f"ℹ️ {display_name} server was not running"
                )
            
            # Step 2: Create backup of current save before restoring
            if os.path.exists(server.server_save_path):
                timestamp = _dt.datetime.now().strftime("%d%m%y_%H%M%S")
                backup_name = f"{server.server_save_path}_before_restore_{timestamp}"
                logger.info_system(f"Creating backup of current save: {backup_name}")
                await self.discord_manager.send_temp_message(
                    message.channel, f"💾 Creating backup of current save..."
                )
                await asyncio.to_thread(shutil.copytree, server.server_save_path, backup_name)
                logger.info_system(f"Backup of current save completed")
            
            # Step 3: Remove current save folder
            if os.path.exists(server.server_save_path):
                logger.info_system(f"Removing current save folder: {server.server_save_path}")
                await asyncio.to_thread(shutil.rmtree, server.server_save_path)
            
            # Step 4: Extract backup to save folder
            logger.info_system(f"Extracting backup {os.path.basename(backup_file)} to {server.server_save_path}")
            await self.discord_manager.send_temp_message(
                message.channel, f"📂 Extracting backup..."
            )
            
            await asyncio.to_thread(self.safe_extract, backup_file, server.server_save_path)
            logger.info_system(f"Backup extraction completed successfully")
            
            # Step 5: Restart server after restore
            logger.info_system(f"Restarting {server.name} server after restore...")
            await self.discord_manager.send_temp_message(
                message.channel, f"🦖 Restarting {display_name} server..."
            )
            
            try:
                self.server_manager.start_server(server)
                logger.info_system(f"{server.name} started successfully")
                
                # Wait for server to come back online
                await self.discord_manager.send_temp_message(
                    message.channel, f"⏳ Waiting for {display_name} to come back online..."
                )
                
                server_online = await self.server_manager.wait_for_servers_online([server])
                
                if server_online:
                    logger.info_system(f"Successfully restored backup {os.path.basename(backup_file)} for {server.name}")
                    await self.discord_manager.send_temp_message(message.channel, f"🦕 {display_name} is back online")
                    await self.discord_manager.send_temp_message(message.channel, "🦖 Restore process completed")
                else:
                    await self.discord_manager.send_temp_message(
                        message.channel, f"⚠️ Timeout waiting for {display_name} to come online. Chat relay may not reconnect automatically."
                    )
                
            except ServerAlreadyRunningError as e:
                logger.warning_system(f"Server {server.name} already running after restore: {e.message}")
            except ServerOperationError as e:
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to restart {server.name} after restore: {e.reason}")
                return
            
            
        except (BackupRestoreError, FileSystemError, PermissionError) as e:
            logger.error_system(f"Failed to restore backup {os.path.basename(backup_file)} for {server.name}: {e.message}")
            await self.discord_manager.send_temp_message(
                message.channel, f"❌ Failed to restore backup: {e.message}"
            )
        except Exception as e:
            logger.error_system(f"Unexpected error restoring backup {os.path.basename(backup_file)} for {server.name}: {e}")
            await self.discord_manager.send_temp_message(
                message.channel, f"❌ Unexpected error restoring backup: {e}"
            )

    async def _backup_all_maps(self, channel):
        """Backup all maps"""
        await self.discord_manager.send_temp_message(channel, "🦖 Starting backup of all servers...")
        
        for server in self.server_manager.servers:
            logger.info_system(f"Processing backup for {server.name}...")
            try:
                await self._trigger_save_and_wait(server, channel)
                logger.info_system(f"Creating backup for {server.name}...")
                await self.backup_manager.backup_server(server, channel, self.discord_manager, self.server_manager)
                logger.info_system(f"Backup completed successfully for {server.name}")
                await asyncio.sleep(5)  # Small delay between backups
            except BackupCreationError as e:
                logger.error_system(f"Failed to backup {server.name}: {e.reason}")
                await self.discord_manager.send_temp_message(channel, f"❌ Failed to backup {server.name}: {e.reason}")
            except (FileSystemError, DiskSpaceError) as e:
                logger.error_system(f"File system error backing up {server.name}: {e.message}")
                await self.discord_manager.send_temp_message(channel, f"❌ File system error backing up {server.name}: {e.message}")
            except Exception as e:
                logger.error_system(f"Unexpected error backing up {server.name}: {e}")
                await self.discord_manager.send_temp_message(channel, f"❌ Unexpected error backing up {server.name}: {e}")
        
        logger.info_system("Backup process completed for all servers")
        await self.discord_manager.send_temp_message(channel, "🦖 Backup process completed for all servers.")

    @staticmethod
    def safe_extract(zip_file, extract_path):
        """Safe zip extraction to prevent path traversal attacks"""
        try:
            with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                for member in zip_ref.infolist():
                    # Check for path traversal attempts
                    if '..' in member.filename or member.filename.startswith('/') or member.filename.startswith('\\'):
                        raise ValueError(f"Potential path traversal attack detected in zip file: {member.filename}")
                    
                    # Construct the full path for extraction
                    full_path = os.path.join(extract_path, member.filename)
                    
                    # Ensure the extracted path is within the target directory
                    if not os.path.abspath(full_path).startswith(os.path.abspath(extract_path)):
                        raise ValueError(f"Path traversal attempt detected: {member.filename}")
                    
                    # Extract the file safely
                    zip_ref.extract(member, extract_path)
        except (zipfile.BadZipFile, ValueError) as e:
            raise BackupRestoreError("unknown", zip_file, f"Invalid or corrupted backup file: {e}")
        except OSError as e:
            raise BackupRestoreError("unknown", zip_file, f"File system error during extraction: {e}")
