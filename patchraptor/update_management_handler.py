import asyncio
import subprocess
import os
import datetime
import time
import json
import tempfile
import discord
import traceback
from .log_manager import logger, execute_steamcmd_simple
from .server_manager import ServerManager
from .rcon_manager import RCONManager
from .version_manager import VersionManager
from .discord_manager import DiscordManager
from .config import ConfigManager
from .exceptions import (
    ServerError,
    ServerNotFoundError,
    ServerNotRunningError,
    ServerAlreadyRunningError,
    ServerOperationError,
    RCONError,
    RCONConnectionError,
    RCONCommandError,
    UpdateError,
    UpdateCheckError,
    UpdateDownloadError,
    ProcessError,
    ProcessOperationError,
    PlayerError,
    PlayerOperationError
)
from .raptorchat_utils import RaptorChatUtils


class UpdateManagementHandler:
    """Handles update management commands: update, forceupdate, autoupdate, cancel"""
    
    def __init__(
        self,
        server_manager: ServerManager,
        rcon_manager: RCONManager,
        version_manager: VersionManager,
        discord_manager: DiscordManager,
        config_manager: ConfigManager,
        player_manager,
        raptorchat_manager=None
    ):
        self.server_manager = server_manager
        self.rcon_manager = rcon_manager
        self.version_manager = version_manager
        self.discord_manager = discord_manager
        self.config_manager = config_manager
        self.player_manager = player_manager
        self.raptorchat_manager = raptorchat_manager

        # Internal state for long-running tasks
        self.update_lock = asyncio.Lock()
        self.timer_task: asyncio.Task | None = None
        self.update_task: asyncio.Task | None = None
        self.autoupdate_enabled: bool = True
        self.autoupdate_task: asyncio.Task | None = None
        self.last_check_version: str | None = None

    async def _run_update_countdown(self, channel):
        """Runs the 15-minute countdown with broadcasts."""
        broadcast_template = "Servers will be shutting down for maintenance in {minutes} minutes"
        logger.debug_update(f"Broadcast template configured: {broadcast_template}")
        
        # Webhook notification
        webhook_url = self.config_manager.get("discord_webhook", "")
        webhook_msg = self.config_manager.get("webhook_messages", {}).get("shutdown")
        logger.debug_update(f"Webhook configuration - URL: {'configured' if webhook_url else 'not configured'}, shutdown message: {'configured' if webhook_msg else 'not configured'}")
        if webhook_url and webhook_msg:
            logger.debug_update("Sending shutdown webhook notification")
            await self.discord_manager.send_webhook_message(webhook_msg)
        elif webhook_url and not webhook_msg:
            logger.debug_update("Webhook URL configured but no shutdown message, sending warning")
            await self.discord_manager.send_temp_message(channel, "⚠️ No webhook message configured for shutdown. Skipping Discord announcement.")
        
        logger.info_system("Starting 15-minute shutdown countdown...")
        
        # Countdown loop - logs every minute, but only broadcasts at 15, 10, 5, and 1 minutes
        logger.debug_update("Starting countdown loop for shutdown warnings")
        for minutes_left in range(15, 0, -1):
            # Log the countdown every minute
            logger.debug_update(f"Countdown: {minutes_left} minutes remaining")
            logger.info_system(f"Shutdown countdown: {minutes_left} minutes remaining.")
            
            # Only broadcast at 15, 10, 5, and 1 minute marks
            if minutes_left in [15, 10, 5, 1]:
                logger.debug_update(f"Sending broadcast at {minutes_left} minutes")
                await self._broadcast_all(broadcast_template.format(minutes=minutes_left))
            
            # Sleep for 1 minute between each iteration
            await asyncio.sleep(60)

    async def _shutdown_and_update_servers(self, channel):
        """Wrapper for update process to ensure player manager is paused"""
        # Player Manager will be explicitly resumed after the 2-minute delay
        # inside _internal_shutdown_and_update_servers (line 259)
        await self._internal_shutdown_and_update_servers(channel)

    async def _internal_shutdown_and_update_servers(self, channel):
        """Shuts down all servers, runs SteamCMD update, and saves the new version."""
        # Stop RaptorChat before server shutdown
        if hasattr(self, 'raptorchat_manager') and self.raptorchat_manager:
            logger.debug_update("Stopping RaptorChat before server shutdown")
            logger.info_system("Stopping RaptorChat before server shutdown...")
            try:
                if self.raptorchat_manager.is_running():
                    self.raptorchat_manager.stop()
                    logger.info_system("RaptorChat stopped successfully")
                else:
                    logger.debug_update("RaptorChat is not running, skipping stop")
            except Exception as e:
                logger.debug_update(f"Error stopping RaptorChat: {e}")
                logger.error_system(f"Error stopping RaptorChat: {e}")
        else:
            logger.debug_update("RaptorChat manager not available, skipping stop")
        
        # Pause Player Manager after RaptorChat is stopped
        if hasattr(self, 'player_manager') and self.player_manager:
            self.player_manager.pause()

        # Shutdown all servers
        logger.debug_update("Sending final shutdown broadcast to all servers")
        await self._broadcast_all("Servers are shutting down now.")
        logger.info_system("Sending final shutdown command to all servers.")
        await self.discord_manager.send_temp_message(
            channel, "🦕 Shutting down running servers..."
        )
        
        # Send DoExit to all servers
        logger.info_system("Sending RCON command: DoExit")
        shutdown_tasks = []
        for server in self.server_manager.servers:
            task = self.rcon_manager.execute_for_server(server, "DoExit")
            shutdown_tasks.append((server, task))
        
        for server, task in shutdown_tasks:
            try:
                await task
                logger.info_system(f"Successfully sent to {server.name} ({server.rcon_ip}:{server.rcon_port})")
            except (RCONConnectionError, RCONCommandError) as e:
                logger.debug_update(f"Failed to send shutdown to {server.name}: {e.reason}")
                logger.error_system(f"Failed to send shutdown to: {server.name} — {e.reason}")
                await self.discord_manager.send_temp_message(channel, f"❌ Failed to send shutdown to: {server.name}")
        
        logger.info_system("Waiting for all servers to shut down...")
        
        # Wait for each server to shut down with active monitoring
        for server in self.server_manager.servers:
            shutdown_success = await self.server_manager.wait_for_server_shutdown(server, timeout=300)
            if not shutdown_success:
                logger.warning_system(f"Timeout waiting for {server.name} to shut down completely")
        
        # Run SteamCMD update
        logger.debug_update("Starting SteamCMD update process")
        logger.info_system("Running SteamCMD update...")
        await self.discord_manager.send_temp_message(
            channel,
            "⬇️ Downloading server update..."
        )

        # Get SteamCMD path and app ID from config
        steamcmd_path = self.config_manager.get("steamcmd_path")
        server_dir = self.config_manager.get("server_dir")
        app_id = self.config_manager.get("app_id")
        
        logger.debug_update(f"Using direct SteamCMD execution - path: {steamcmd_path}, dir: {server_dir}, app_id: {app_id}")
        logger.info_system("Executing SteamCMD update directly...")
        
        # Build and execute SteamCMD command directly
        cmd_args = [
            steamcmd_path,
            "+force_install_dir", server_dir,
            "+login", "anonymous",
            "+app_update", app_id,
            "validate",
            "+quit"
        ]
        
        logger.debug_update(f"SteamCMD command: {cmd_args}")
        result = await execute_steamcmd_simple(cmd_args)
        
        logger.debug_update(f"SteamCMD execution completed, return code: {result.returncode}")
                 
        logger.debug_update(f"SteamCMD execution completed, return code: {result.returncode}")
        if result.returncode != 0:
            logger.debug_update("SteamCMD update failed, sending error notification to channel")
            logger.error_system("SteamCMD update failed")
            await self.discord_manager.send_temp_message(channel, "❌ SteamCMD update failed. Manual intervention required.")
            raise UpdateError("SteamCMD update failed.")
        
        logger.debug_update("SteamCMD update completed successfully")
        logger.info_system("SteamCMD update completed successfully")
        
        # Save new version
        logger.debug_update("Starting version information update process")
        logger.info_system("Updating version information...")
        try:
            logger.debug_update("Fetching latest build ID from version manager")
            latest = await self.version_manager.get_latest_build_id()
            if latest:
                logger.debug_update(f"Latest build ID found: {latest}, saving to version file")
                self.version_manager.save_version(latest)
                logger.info_system(f"Version updated to build {latest}")
            else:
                logger.debug_update("No latest build ID found, skipping version update")
        except UpdateCheckError as e:
            logger.debug_update(f"Failed to get latest build ID: {e.reason}")
            logger.warning_system(f"Failed to get latest build ID: {e.reason}")

        # Restart servers
        logger.debug_update("Starting server restart sequence")
        logger.info_system("Restarting servers...")
        await self.discord_manager.send_temp_message(channel, "🦖 Starting servers after update...")
        
        # Use shared restart method for consistency with forceupdate (clears cache, staggers 30s)
        # Create a mock message object because _restart_all_servers expects one
        class UpdateMessage:
            def __init__(self, ch):
                self.channel = ch
        
        await self._restart_all_servers(UpdateMessage(channel))
        
        # Wait for servers to come online and confirm success
        if hasattr(self, 'server_manager'):
            await self.discord_manager.send_temp_message(channel, "⏳ Waiting for servers to come back online...")
            all_online = await self._wait_for_servers_online(self.server_manager.servers)
            if all_online:
                await self.discord_manager.send_temp_message(channel, "✅ All servers are back online")
                
                # Webhook notification for completion (using reboot message as requested)
                webhook_url = self.config_manager.get("discord_webhook", "")
                webhook_msg = self.config_manager.get("webhook_messages", {}).get("reboot")
                if webhook_url and webhook_msg:
                    logger.debug_update("Sending completion webhook notification")
                    await self.discord_manager.send_webhook_message(webhook_msg)
            else:
                await self.discord_manager.send_temp_message(channel, "⚠️ Not all servers came back online automatically. Please check status.")

        # Restart RaptorChat
        # The start_server loop above might trigger RaptorChat if configured, 
        # but usually RaptorChat is a separate process.
        # We should check if we need to start it.
        if hasattr(self, 'raptorchat_manager') and self.raptorchat_manager:
            logger.info_system("Restarting RaptorChat...")
            # Use delayed start to let servers initialize (2 minute delay)
            
            # Wait 2 minutes (blocking)
            await asyncio.sleep(120)
            
            # Resume PlayerManager (explicitly here to control log order)
            if hasattr(self, 'player_manager') and self.player_manager:
                self.player_manager.resume()
                
            # Trigger PlayerManager Log Detection IMMEDIATELY
            if hasattr(self, 'player_manager') and self.player_manager:
                 await self.player_manager.trigger_log_file_detection_on_restart()
                 
            await RaptorChatUtils.delayed_raptorchat_restart(
                self.raptorchat_manager, 
                0, 
                channel, 
                self.discord_manager
            )

    async def cmd_update(self, message, content: str, content_lower: str):
        """Handle .update command - full maintenance update"""
        from .log_manager import logger
        logger.debug_update(".update command received")
        logger.info_command(".update received")
        
        # Check if update is already in progress (in-memory lock)
        if self.update_lock.locked():
            logger.debug_update("Update already in progress, sending notification")
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Update already in progress. Please wait for it to complete.")
            return

        # Check for a stale update file (disk lock)
        if os.path.exists("update_in_progress.json"):
            # Check if it's stale (older than 2 hours)
            try:
                creation_time = os.path.getctime("update_in_progress.json")
                if (time.time() - creation_time) > 7200: # 2 hours
                    logger.warning_system("Found stale update_in_progress.json (older than 2h), removing it.")
                    os.remove("update_in_progress.json")
                else:
                    await self.discord_manager.send_temp_message(message.channel, "⚠️ An `update_in_progress.json` file was found. This may indicate a previously failed update. Please resolve the issue and delete the file manually before starting a new update.")
                    return
            except OSError:
                pass # File might have been deleted in the meantime
        
        logger.debug_update("Acquiring update lock and starting update process")
        async with self.update_lock:
            self.update_task = asyncio.current_task()
            try:
                # Create state file
                with open("update_in_progress.json", "w") as f:
                    json.dump({"start_time": datetime.datetime.now().isoformat()}, f)

                logger.debug_update("Update lock acquired, starting full maintenance update process")
                logger.info_system("Starting full maintenance update process...")
                
                await self.discord_manager.send_temp_message(message.channel, "🦕 Update process started. Servers will shut down for maintenance in 15 minutes...")
                
                # Run the update sequence
                await self._run_update_countdown(message.channel)
                await self._shutdown_and_update_servers(message.channel)
                
                logger.debug_update("Full maintenance update process completed successfully")
                logger.info_system("Full maintenance update process completed")
                
            except asyncio.CancelledError:
                logger.info_system("Update process cancelled by user")
                # No separate message here, handled by cmd_cancel
                # The finally block will run automatically to clean up the lock file.
                
            except Exception as e:
                error_trace = traceback.format_exc()
                logger.error_system(f"Critical error during update process: {e}\n{error_trace}")
                
                # Notify Discord about the failure
                msg = f"❌ **Update Failed:** {str(e)}"
                if len(msg) > 1900:
                    msg = msg[:1900] + "..."
                await self.discord_manager.send_temp_message(message.channel, msg)
                
                # Attempt to send traceback as a file if it's long
                try:
                    with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as tf:
                        tf.write(error_trace)
                        temp_path = tf.name
                    await message.channel.send("Error Details:", file=discord.File(temp_path, filename="update_error.log"))
                    # We can't easily unlink here if send is async background, but temp files in OS temp usually get cleaned.
                    # Or we could schedule cleanup. For now let's leave it simple or try to clean immediately after await.
                    os.unlink(temp_path)
                except:
                    pass
            finally:
                # Always clean up the lock file when the operation finishes (success or failure)
                if os.path.exists("update_in_progress.json"):
                    try:
                        os.remove("update_in_progress.json")
                        logger.debug_update("Cleaned up update_in_progress.json lock file")
                    except Exception as ex:
                        logger.error_system(f"Failed to remove update_in_progress.json: {ex}")

    async def cmd_forceupdate(self, message, content: str, content_lower: str):
        """Handle .forceupdate command - wrapper for pause/resume"""
        # Player Manager will be paused after RaptorChat is stopped
        # inside _internal_cmd_forceupdate
        await self._internal_cmd_forceupdate(message, content, content_lower)

    async def _internal_cmd_forceupdate(self, message, content: str, content_lower: str):
        """Handle .forceupdate command - force update without countdown"""
        self.update_task = asyncio.current_task()
        from .log_manager import logger
        logger.debug_update(".forceupdate command received")
        logger.info_command(".forceupdate received")
        parts = content.split()
        steamcmd_path = self.config_manager.get("steamcmd_path")
        app_id = self.config_manager.get("app_id")
        
        logger.debug_update(f"Command parts: {parts}, steamcmd_path: {steamcmd_path}, app_id: {app_id}")
        
        if len(parts) == 1:
            logger.debug_update("Starting force update for all servers")
            # Update all servers
            logger.info_system("Starting force update for all servers...")
            server_dir = self.config_manager.get("server_dir")
            
            logger.debug_update(f"Server directory: {server_dir}")
            
            # Stop RaptorChat if it's running
            if hasattr(self, 'raptorchat_manager') and self.raptorchat_manager and self.raptorchat_manager.is_running():
                logger.debug_update("Stopping RaptorChat before force update")
                logger.info_system("Stopping RaptorChat before force update...")
                try:
                    self.raptorchat_manager.stop()
                    await asyncio.sleep(2)  # Give it a moment to stop
                    logger.debug_update("RaptorChat stopped successfully")
                except Exception as e:
                    logger.debug_update(f"Failed to stop RaptorChat: {e}")
                    logger.warning_system(f"Failed to stop RaptorChat: {e}")
            else:
                logger.debug_update("RaptorChat is not running or not available, skipping stop")
            
            # Pause Player Manager after RaptorChat is stopped
            if hasattr(self, 'player_manager') and self.player_manager:
                self.player_manager.pause()
            
            # Check if any servers are running
            logger.debug_update("Checking if any servers are currently running")
            running_servers = any(
                self.server_manager.is_specific_server_running(srv) 
                for srv in self.server_manager.servers
            )
            logger.debug_update(f"Running servers detected: {running_servers}")
            
            if running_servers:
                logger.debug_update("Servers are running, shutting them down before force update")
                await self.discord_manager.send_temp_message(
                    message.channel, "🦕 Shutting down running servers..."
                )
                logger.debug_update("Calling _shutdown_all_servers")
                await self._shutdown_all_servers()
            else:
                logger.debug_update("No servers running, proceeding directly with force update")
                await self.discord_manager.send_temp_message(
                    message.channel, "🦕 No ARK servers currently running. Starting force update..."
                )
            
            # Step 1: Build command as list to prevent command injection
            logger.debug_update("Building SteamCMD command for all servers")
            logger.info_system("Building SteamCMD command for all servers...")
            cmd_args = [
                steamcmd_path,
                "+force_install_dir", server_dir,
                "+login", "anonymous",
                "+app_update", app_id,
                "validate",
                "+quit"
            ]
            logger.debug_update(f"SteamCMD command for all servers: {cmd_args}")
            
            # Step 2: Execute SteamCMD update
            logger.debug_update("Executing SteamCMD update for all servers")
            logger.info_system("Executing SteamCMD update for all servers...")
            await self.discord_manager.send_temp_message(message.channel, "⬇️ Downloading server updates...")
            
            # Execute SteamCMD (SteamCMD buffers output internally)
            res = await execute_steamcmd_simple(cmd_args)
            
            logger.debug_update(f"SteamCMD execution completed, return code: {res.returncode}")
            if res.returncode != 0:
                logger.debug_update("SteamCMD force update failed for all servers")
                logger.error_system("SteamCMD force update failed for all servers")
                await self.discord_manager.send_temp_message(message.channel, "❌ SteamCMD update failed. Manual intervention required.")
                return
            
            logger.debug_update("SteamCMD force update completed successfully for all servers")
            logger.info_system("SteamCMD force update completed successfully for all servers")
            
            # Save new version
            logger.debug_update("Saving new version after force update")
            latest_version = await self.version_manager.get_latest_build_id()
            if latest_version:
                logger.debug_update(f"Latest version found: {latest_version}, saving to version file")
                self.version_manager.save_version(latest_version)
            else:
                logger.debug_update("No latest version found, skipping version save")
            
            # Step 3: Restart all servers
            logger.debug_update("Starting restart of all servers after force update")
            logger.info_system("Restarting all servers after force update...")
            await self.discord_manager.send_temp_message(message.channel, "🦖 Starting servers after update...")
            logger.debug_update("Calling _restart_all_servers")
            await self._restart_all_servers(message)
            
            # Step 4: Wait for servers to come back online
            running_servers = [s for s in self.server_manager.servers 
                             if self.server_manager.is_specific_server_running(s)]
            
            servers_online = False
            if running_servers:
                await self.discord_manager.send_temp_message(message.channel, "⏳ Waiting for servers to come back online...")
                
                # Wait for servers to come online (using the same timeout as in cmd_reboot)
                servers_online = await self._wait_for_servers_online(running_servers)
                
                if not servers_online:
                     await self.discord_manager.send_temp_message(
                        message.channel,
                        "⚠️ Not all servers came back online. RaptorChat will not be restarted automatically."
                    )
            else:
                await self.discord_manager.send_temp_message(message.channel, "✅ Force update complete. No servers were running to restart.")
            
            logger.debug_update("Force update process completed for all servers")
            logger.info_system("Force update process completed for all servers")
            
            # Handle delay and restarts AFTER logging completion
            if servers_online:
                # Get the current time as the last server online time
                last_online_time = asyncio.get_event_loop().time()
                # Calculate remaining delay (2 minutes from now)
                remaining_delay = max(0, 120 - (asyncio.get_event_loop().time() - last_online_time))
                
                if remaining_delay > 0:
                    minutes = round(remaining_delay / 60)
                    await self.discord_manager.send_temp_message(
                        message.channel, 
                        f"✅ All servers are back online"
                    )
                    
                    # Wait for delay FIRST
                    await asyncio.sleep(remaining_delay)
                    
                    # Resume PlayerManager (explicitly here to control log order)
                    if hasattr(self, 'player_manager') and self.player_manager:
                        self.player_manager.resume()
                    
                    # Trigger PlayerManager Log Detection IMMEDIATELY
                    if hasattr(self, 'player_manager') and self.player_manager:
                        await self.player_manager.trigger_log_file_detection_on_restart()
                        
                    # Start RaptorChat after the remaining delay
                    asyncio.create_task(
                        RaptorChatUtils.delayed_raptorchat_restart(
                            self.raptorchat_manager if hasattr(self, 'raptorchat_manager') else None,
                            0, # Delay handled above
                            message.channel,
                            self.discord_manager if hasattr(self, 'discord_manager') else None
                        )
                    )
                else:
                    # If we're already past the 2-minute mark, start immediately
                    
                     # Resume PlayerManager (explicitly here to control log order)
                    if hasattr(self, 'player_manager') and self.player_manager:
                        self.player_manager.resume()

                    # Trigger PlayerManager Log Detection IMMEDIATELY
                    if hasattr(self, 'player_manager') and self.player_manager:
                        await self.player_manager.trigger_log_file_detection_on_restart()

                    asyncio.create_task(
                        RaptorChatUtils.delayed_raptorchat_restart(
                            self.raptorchat_manager if hasattr(self, 'raptorchat_manager') else None,
                            0,
                            message.channel,
                            self.discord_manager if hasattr(self, 'discord_manager') else None
                        )
                    )

            return
        
        # Map-specific update
        map_name = parts[1]
        logger.debug_update(f"Starting force update for specific server: {map_name}")
        logger.info_system(f"Starting force update for server: {map_name}")
        try:
            logger.debug_update(f"Looking up server configuration for: {map_name}")
            server = self.server_manager.find_server(map_name)
            logger.debug_update(f"Server found: {server.name}")
        except ServerNotFoundError:
            logger.debug_update(f"Server not found for force update: {map_name}")
            logger.warning_system(f"Server not found for force update: {map_name}")
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with name or map '{map_name}'.")
            return
        
        display_name = self.server_manager.get_display_name(server)
        logger.debug_update(f"Server display name: {display_name}")
        await self.discord_manager.send_temp_message(
            message.channel, f"🦕 Force update: Shutting down {display_name} server..."
        )
        
        # Shutdown if running
        logger.debug_update(f"Checking if server {server.name} is currently running")
        if self.server_manager.is_specific_server_running(server):
            logger.debug_update(f"Server {server.name} is running, shutting it down")
            try:
                logger.info_system("Sending RCON command: DoExit")
                await self.rcon_manager.execute_for_server(server, "DoExit")
                logger.info_system(f"Successfully sent to {server.name} ({server.rcon_ip}:{server.rcon_port})")
                # Wait for shutdown
                logger.debug_update(f"Waiting for server {server.name} to shut down (180 seconds timeout)")
                await self.server_manager.wait_for_server_shutdown(server, 180)
                logger.debug_update(f"Server {server.name} shut down successfully")
            except (RCONConnectionError, RCONCommandError) as e:
                logger.debug_update(f"Failed to shut down server {server.name}: {e.reason}")
                await self.discord_manager.send_temp_message(
                    message.channel, f"❌ Failed to shut down {display_name} server."
                )
                return
        else:
            logger.debug_update(f"Server {server.name} is not running, proceeding with update")
        
        # Run SteamCMD update
        logger.debug_update(f"Running SteamCMD update for server {map_name}")
        logger.log(f"Running SteamCMD update for {map_name}...")
        await self.discord_manager.send_temp_message(message.channel, "⬇️ Downloading server update...")
        
        # Step 1: Build command as list to prevent command injection
        logger.debug_update(f"Building SteamCMD command for server {server.name}")
        logger.info_system(f"Building SteamCMD command for {server.name}...")
        cmd_args = [
            steamcmd_path,
            "+force_install_dir", server.install_dir,
            "+login", "anonymous",
            "+app_update", app_id,
            "validate",
            "+quit"
        ]
        logger.debug_update(f"SteamCMD command for {server.name}: {cmd_args}")
        
        # Step 2: Execute SteamCMD update
        logger.debug_update(f"Executing SteamCMD update for server {server.name}")
        logger.info_system(f"Executing SteamCMD update for {server.name}...")
        
        # Execute SteamCMD (SteamCMD buffers output internally)
        res = await execute_steamcmd_simple(cmd_args)
        
        logger.debug_update(f"SteamCMD execution completed for {server.name}, return code: {res.returncode}")
        if res.returncode != 0:
            logger.debug_update(f"SteamCMD force update failed for server {server.name}")
            logger.error_system(f"SteamCMD force update failed for {server.name}")
            await self.discord_manager.send_temp_message(
                message.channel, "❌ SteamCMD update failed. Manual intervention required."
            )
            return
        
        logger.debug_update(f"SteamCMD force update completed successfully for server {server.name}")
        logger.info_system(f"SteamCMD force update completed successfully for {server.name}")
        
        # Save new version
        logger.debug_update(f"Saving new version after force update for server {server.name}")
        latest_version = await self.version_manager.get_latest_build_id()
        if latest_version:
            logger.debug_update(f"Latest version found: {latest_version}, saving to version file")
            self.version_manager.save_version(latest_version)
        else:
            logger.debug_update("No latest version found, skipping version save")
        
        # Restart server
        logger.debug_update(f"Starting server {map_name} after force update")
        try:
            # Clear player data for this specific server
            if hasattr(self, 'player_manager'):
                logger.debug_update(f"Clearing player data for server {server.name}")
                await self.player_manager.clear_server_players(server.name)
                await self.player_manager.reset_file_positions(server.name)
            
            logger.debug_update(f"Starting server {server.name}")
            self.server_manager.start_server(server)
            logger.debug_update(f"Server {server.name} started successfully")
            await self.discord_manager.send_temp_message(
                message.channel, f"🦖 {display_name} is back online..."
            )
        except Exception as e:
            logger.debug_update(f"Failed to start server {server.name} after update: {e}")
            logger.error_system(f"Failed to start {server.name} after update: {e}")
            await self.discord_manager.send_temp_message(
                message.channel, f"❌ Failed to start {display_name}: {e}"
            )
        
        logger.debug_update(f"Force update process completed for server {server.name}")
        logger.info_system(f"Force update process completed for {server.name}")

    async def cmd_autoupdate(self, message, content: str, content_lower: str):
        """Handle .autoupdate command - toggle auto-update"""
        from .log_manager import logger
        logger.debug_update(".autoupdate command received")
        logger.info_command(".autoupdate received")
        parts = content_lower.split()
        logger.debug_update(f"Command parts: {parts}")
        if len(parts) == 1:
            logger.debug_update("Checking autoupdate status")
            status = "ON ✅" if self.autoupdate_enabled else "OFF ❌"
            task_status = "Running" if (self.autoupdate_task and not self.autoupdate_task.done()) else "Stopped"
            logger.debug_update(f"Autoupdate status: {status}, task status: {task_status}")
            await self.discord_manager.send_temp_message(
                message.channel, 
                f"Autoupdate status: {status}\nBackground task: {task_status}"
            )
            return
        
        if parts[1] == "on":
            logger.debug_update("Enabling autoupdate")
            if not self.autoupdate_enabled:
                self.autoupdate_enabled = True
                logger.info_system("Autoupdate enabled, starting background checker...")
                await self.start_autoupdate_checker(message.channel)
                await self.discord_manager.send_temp_message(message.channel, "Autoupdate is now **ON ✅**\nBackground checker started.")
            else:
                logger.debug_update("Autoupdate already enabled")
                await self.discord_manager.send_temp_message(message.channel, "Autoupdate is already **ON ✅**")
        elif parts[1] == "off":
            logger.debug_update("Disabling autoupdate")
            if self.autoupdate_enabled:
                self.autoupdate_enabled = False
                logger.info_system("Autoupdate disabled, stopping background checker...")
                await self.stop_autoupdate_checker()
                await self.discord_manager.send_temp_message(message.channel, "Autoupdate is now **OFF ❌**\nBackground checker stopped.")
            else:
                logger.debug_update("Autoupdate already disabled")
                await self.discord_manager.send_temp_message(message.channel, "Autoupdate is already **OFF ❌**")
        else:
            logger.debug_update(f"Invalid autoupdate option: {parts[1]}")
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Invalid option. Use `.autoupdate on` or `.autoupdate off`")

    async def cmd_cancel(self, message, content: str, content_lower: str):
        """Handle .cancel command - cancel ongoing operations"""
        from .log_manager import logger
        logger.debug_update(".cancel command received")
        logger.info_command(".cancel received")
        cancelled = False
        
        logger.debug_update("Checking for active timer task")
        if self.timer_task and not self.timer_task.done():
            logger.debug_update("Cancelling timer task")
            self.timer_task.cancel()
            cancelled = True
        
        logger.debug_update("Checking for active update task")
        if self.update_task and not self.update_task.done():
            logger.debug_update("Cancelling update task")
            self.update_task.cancel()
            cancelled = True
        
        logger.debug_update(f"Operations cancelled: {cancelled}")
        if cancelled:
            await self.discord_manager.send_temp_message(message.channel, "🛑 Process cancelled...")
        else:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ No active countdown or update to cancel.")

    async def _restart_all_servers(self, message):
        """Restart all servers with staggered startup"""
        from .log_manager import logger
        logger.debug_update("Starting _restart_all_servers method")
        # Clear player data and reset log positions when restarting servers
        if hasattr(self, 'player_manager'):
            logger.debug_update("Clearing player data for all servers")
            try:
                logger.info_system("Clearing player data and resetting log positions...")
                await self.player_manager.clear_server_players()
                await self.player_manager.reset_file_positions()
                logger.debug_update("Player data cleared successfully for all servers")
            except PlayerOperationError as e:
                logger.debug_update(f"Failed to clear player data: {e.reason}")
                logger.warning_system(f"Failed to clear player data: {e.reason}")
        
        # Staggered server restart
        logger.debug_update(f"Restarting {len(self.server_manager.servers)} servers with 30-second stagger")
        for srv in self.server_manager.servers:
            logger.debug_update(f"Restarting server: {srv.name}")
            await self._restart_one_server(srv, message)
            logger.debug_update(f"Sleeping 30 seconds before next server restart")
            await asyncio.sleep(30)  # Staggered startup
        
        # RaptorChat will be restarted after the 5-minute delay in the update/forceupdate command
        logger.debug_update("Server restarts completed, waiting for servers to come online...")

    async def _wait_for_servers_online(self, servers, timeout=300, check_interval=10):
        """Wait for all specified servers to come online"""
        from .log_manager import logger
        logger.info_system(f"Waiting for {len(servers)} servers to come online...")
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            all_online = True
            
            for server in servers:
                if not self.server_manager.is_specific_server_running(server):
                    all_online = False
                    logger.debug_system(f"Server {server.name} is not yet online")
                    break
                
                # Additional check to ensure RCON is responsive
                try:
                    await self.rcon_manager.execute_for_server(server, "SaveWorld")
                    logger.debug_system(f"Server {server.name} is online and responsive")
                except (RCONConnectionError, RCONCommandError):
                    all_online = False
                    logger.debug_system(f"Server {server.name} is running but RCON not yet responsive")
                    break
            
            if all_online:
                logger.info_system("All servers are now online and responsive")
                return True
                
            await asyncio.sleep(check_interval)
        
        logger.warning_system("Timeout waiting for all servers to come online")
        return False
        
        return True

    async def _restart_one_server(self, server, message):
        """Restart a single server"""
        from .log_manager import logger
        logger.debug_update(f"Starting _restart_one_server for: {server.name}")
        try:
            logger.debug_update(f"Starting server {server.name}")
            self.server_manager.start_server(server)
            await self.discord_manager.send_temp_message(message.channel, f"🦖 {self.server_manager.get_display_name(server)} is now starting...")
        except ServerAlreadyRunningError as e:
            logger.debug_update(f"Server {server.name} already running: {e.message}")
            logger.warning_system(f"Server {server.name} already running: {e.message}")
            await self.discord_manager.send_temp_message(message.channel, f"ℹ️ {self.server_manager.get_display_name(server)} was already running")
        except ServerOperationError as e:
            # Check if server actually started despite the error
            import asyncio
            logger.debug_update(f"Server start error for {server.name}: {e.reason}, checking actual status...")
            await asyncio.sleep(5)  # Wait a moment for server to potentially start
            
            if self.server_manager.is_specific_server_running(server):
                logger.debug_update(f"Server {server.name} is actually running despite start error")
                await self.discord_manager.send_temp_message(message.channel, f"🦖 {self.server_manager.get_display_name(server)} is now starting...")
            else:
                logger.debug_update(f"Failed to start server {server.name}: {e.reason}")
                logger.error_system(f"Failed to start {server.name}: {e.reason}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to start {server.name}: {e.reason}")

    async def _shutdown_all_servers(self):
        """Shutdown all servers via RCON and wait for them to shut down"""
        from .log_manager import logger
        logger.debug_update("Starting _shutdown_all_servers method")
        logger.info_system("Sending RCON command: DoExit")
        tasks = []
        for server in self.server_manager.servers:
            task = self.rcon_manager.execute_for_server(server, "DoExit")
            tasks.append((server, task))
        
        for server, task in tasks:
            try:
                await task
                logger.info_system(f"Successfully sent to {server.name} ({server.rcon_ip}:{server.rcon_port})")
            except (RCONConnectionError, RCONCommandError) as e:
                logger.debug_update(f"Failed to send shutdown to {server.name}: {e.reason}")
                logger.error_system(f"Failed to send shutdown to {server.name}: {e.reason}")
        
        # Wait for all servers to shut down
        logger.debug_update("Waiting for all servers to shut down")
        logger.info_system("Waiting for all servers to shut down...")
        for server in self.server_manager.servers:
            logger.debug_update(f"Waiting for server {server.name} to shut down (300 seconds timeout)")
            shutdown_success = await self.server_manager.wait_for_server_shutdown(server, timeout=300)
            if not shutdown_success:
                logger.debug_update(f"Timeout waiting for server {server.name} to shut down")
                logger.warning_system(f"Timeout waiting for {server.name} to shut down completely")
            else:
                logger.debug_update(f"Server {server.name} shut down successfully")

    async def _broadcast_all(self, msg: str):
        """Broadcast a message to all servers"""
        from .log_manager import logger
        logger.debug_update(f"Starting _broadcast_all with message: {msg}")
        logger.info_system(f"Sending RCON command: ServerChat {msg}")
        for server in self.server_manager.servers:
            logger.debug_update(f"Broadcasting to server: {server.name}")
            try:
                await self.rcon_manager.execute_for_server(server, f"ServerChat {msg}")
                logger.debug_update(f"Successfully sent broadcast to {server.name}")
                logger.info_system(f"Successfully sent to {server.name}")
            except (RCONConnectionError, RCONCommandError) as e:
                logger.debug_update(f"Failed to broadcast to {server.name}: {e.reason}")
                logger.warning_system(f"Failed to broadcast to {server.name}: {e.reason}")

    # ===== AUTOUPDATE MANAGEMENT METHODS =====
    
    async def start_autoupdate_checker(self, discord_channel=None, interval: int = 600):
        """Start the background autoupdate checking task"""
        from .log_manager import logger
        logger.debug_update("Starting start_autoupdate_checker method")
        if self.autoupdate_task and not self.autoupdate_task.done():
            logger.debug_update("Autoupdate checker already running, returning")
            logger.warning_system("Autoupdate checker already running")
            return
        self.autoupdate_enabled = True
        logger.debug_update(f"Creating autoupdate checker task with interval {interval}")
        logger.info_system("Starting autoupdate checker...")
        self.autoupdate_task = asyncio.create_task(self._autoupdate_checker_loop(discord_channel, interval=interval))
        logger.debug_update("Autoupdate checker task created successfully")
    async def stop_autoupdate_checker(self):
        """Stop the background autoupdate checking task"""
        from .log_manager import logger
        logger.debug_update("Starting stop_autoupdate_checker method")
        if self.autoupdate_task and not self.autoupdate_task.done():
            logger.debug_update("Cancelling autoupdate checker task")
            logger.info_system("Stopping autoupdate checker...")
            self.autoupdate_task.cancel()
            try:
                await self.autoupdate_task
                logger.debug_update("Autoupdate checker task cancelled successfully")
            except asyncio.CancelledError:
                logger.debug_update("Caught CancelledError during task cancellation")
                pass
            self.autoupdate_task = None
            logger.debug_update("Autoupdate checker task set to None")
            logger.info_system("Autoupdate checker stopped")
        else:
            logger.debug_update("No autoupdate checker task running or already completed")
    
    async def _autoupdate_checker_loop(self, discord_channel=None, interval: int = 600):
        """Main autoupdate checking loop"""
        from .log_manager import logger
        logger.debug_update("Starting _autoupdate_checker_loop method")
        logger.info_system("Autoupdate checker loop started")
        
        # Get the default channel for notifications
        if discord_channel is None:
            logger.debug_update("No discord_channel provided, checking webhook configuration")
            # Try to get a default channel from config
            webhook_url = self.config_manager.get("discord_webhook", "")
            if webhook_url:
                logger.debug_update("Webhook configured, will use webhook for notifications")
                # We'll use webhook for notifications instead of channel
                discord_channel = None
            else:
                logger.debug_update("No webhook configured for autoupdate notifications")
                logger.warning_system("No webhook configured for autoupdate notifications")
        else:
            logger.debug_update(f"Discord channel provided: {discord_channel}")
        
        # Wait before first check
        logger.debug_update(f"Waiting {interval} seconds before first autoupdate check")
        wait_minutes = interval // 60
        logger.info_system(f"Waiting {wait_minutes} minutes before first autoupdate check...")
        await asyncio.sleep(interval)
        logger.debug_update("Initial wait completed, starting main loop")
        
        while True:
            try:
                logger.debug_update("Loop iteration: checking autoupdate_enabled status")
                if self.autoupdate_enabled:
                    logger.debug_update("Autoupdate enabled, proceeding with check")
                    await self._check_and_perform_autoupdate(discord_channel)
                else:
                    logger.debug_update("Autoupdate disabled, skipping check")
                
                # Check every interval
                logger.debug_update(f"Waiting {interval} seconds before next check")
                await asyncio.sleep(interval)
                logger.debug_update(f"{interval}-second wait completed, continuing loop")
                
            except asyncio.CancelledError:
                logger.debug_update("Autoupdate checker loop cancelled via CancelledError")
                logger.info_system("Autoupdate checker loop cancelled")
                break
            except Exception as e:
                logger.debug_update(f"Error in autoupdate checker loop: {e}")
                logger.error_system(f"Error in autoupdate checker loop: {e}")
                # Wait 5 minutes before retrying after an error
                logger.debug_update("Waiting 5 minutes before retrying after error")
                await asyncio.sleep(300)
                logger.debug_update("Error retry wait completed, continuing loop")
    
    async def _check_and_perform_autoupdate(self, discord_channel=None):
        """Check for updates and perform automatic update if needed"""
        from .log_manager import logger
        logger.debug_update("Starting _check_and_perform_autoupdate method")
        try:
            logger.debug_update("Starting automatic update check")
            logger.info_system("Checking for automatic updates...")
            
            # Get current and latest versions
            logger.debug_update("Retrieving current and latest versions")
            current = self.version_manager.get_current_version()
            latest = await self.version_manager.get_latest_build_id()
            logger.debug_update(f"Version check - current: {current}, latest: {latest}")
            
            if not latest:
                logger.debug_update("Failed to get latest build ID")
                logger.warning_system("Failed to get latest build ID for autoupdate")
                return
            
            if not current:
                logger.debug_update("No current version found, setting initial version")
                logger.info_system("No current version found, performing initial update check")
                self.last_check_version = latest
                logger.debug_update(f"Set last_check_version to: {latest}")
                return
            
            # Check if update is needed
            if current != latest and self.last_check_version != latest:
                # Get the configured channel from config
                channel = await self.discord_manager.get_default_channel()
                if not channel:
                    logger.warning_system("No Discord channel available for autoupdate notification")
                    return
                
                # Send notification that update was detected
                await self.discord_manager.send_temp_message(channel, "⚠️ Update detected! Triggering update process...")
                
                # Create mock message object so .update works exactly like when user types it
                class MockMessage:
                    def __init__(self, channel):
                        self.channel = channel
                
                # Trigger .update command with proper message object
                await self.cmd_update(MockMessage(channel), ".update", ".update")
                
                # Update last check version to avoid repeated triggers
                self.last_check_version = latest
            else:
                logger.debug_update("No new updates found, current version is up to date")
                logger.info_system("No new updates found")
                
        except Exception as e:
            logger.debug_update(f"Error during autoupdate check: {e}")
            logger.error_system(f"Error during autoupdate check: {e}")
