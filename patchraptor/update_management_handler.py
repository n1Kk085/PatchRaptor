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
from .system_utils import SystemUtils
from .base_handler import BaseHandler


class UpdateManagementHandler(BaseHandler):
    """Handles SteamCMD updates, versioning, and countdowns"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Internal state for long-running tasks
        self.update_lock = asyncio.Lock()
        self.timer_task: asyncio.Task | None = None
        self.update_task: asyncio.Task | None = None
        self.autoupdate_enabled: bool = True
        self.autoupdate_task: asyncio.Task | None = None

    async def _get_patch_settings(self):
        """Get patch settings from config with internal defaults for robustness"""
        settings = self.config_manager.get("patch_settings", {})
        return {
            "timer": settings.get("timer", 15),
            "broadcast": settings.get("broadcast", "Servers will be shutting down for maintenance in {minutes} minutes"),
            "intervals": settings.get("intervals", [15, 10, 5, 1])
        }

    async def _run_update_countdown(self, channel):
        """Runs the dynamic countdown with broadcasts based on configuration."""
        settings = await self._get_patch_settings()
        timer = settings["timer"]
        broadcast_template = settings["broadcast"]
        intervals = settings["intervals"]
        
        logger.debug_update(f"Starting patch countdown: {timer}m, Intervals: {intervals}")
        
        # Webhook notification
        webhook_url = self.config_manager.get("discord_webhook", "")
        # Look for patch-specific webhook, fallback to shutdown
        webhook_msg = self.config_manager.get("webhook_messages", {}).get("patch")
        if not webhook_msg:
            webhook_msg = self.config_manager.get("webhook_messages", {}).get("shutdown")
        
        if webhook_url:
            if webhook_msg:
                logger.debug_update("Sending patch/shutdown webhook notification")
                # Format with timer if placeholder exists
                try:
                    formatted_msg = webhook_msg.format(timer=f"{timer}")
                except (KeyError, ValueError):
                    formatted_msg = webhook_msg
                await self.discord_manager.send_webhook_message(formatted_msg)
            else:
                await self.discord_manager.send_temp_message(channel, "⚠️ No webhook message configured for `patch`. Skipping Discord announcement.")
        
        
        logger.info_system(f"Starting {timer}-minute patch countdown...")
        
        # Countdown loop
        for minutes_left in range(timer, 0, -1):
            logger.debug_update(f"Countdown: {minutes_left} minutes remaining")
            
            # Broadcast if minutes_left is in the configured intervals
            if minutes_left in intervals:
                logger.debug_update(f"Sending broadcast at {minutes_left} minutes")
                interval_msg = broadcast_template.format(minutes=f"{minutes_left}")
                if minutes_left == 1:
                    interval_msg = interval_msg.replace("1 minutes", "1 minute")
                await self._broadcast_all(interval_msg)
                await self.discord_manager.send_temp_message(channel, f"⏳ {interval_msg}")
            
            # Sleep for 1 minute
            await asyncio.sleep(60)

    async def _shutdown_and_update_servers(self, channel):
        """Wrapper for update process to ensure player manager is paused"""
        await self._internal_shutdown_and_update_servers(channel)

    async def _internal_shutdown_and_update_servers(self, channel, skip_countdown=False):
        """Internal method to perform the actual shutdown and update sequence (Unified Path)"""
        if channel:
            await self.discord_manager.send_temp_message(channel, "🖥️ Pausing Telemetry and Chat Relay...")
        
        # Use maintenance scope to ensure semaphore is released even on failure
        # We use handoff=True because SystemUtils.unified_system_recovery will eventually
        # call end_maintenance via raptorchat_manager.start_with_delay
        if self.raptorchat_manager:
            rc_scope = self.raptorchat_manager.maintenance_scope(handoff=True)
        else:
            from contextlib import asynccontextmanager
            @asynccontextmanager
            async def null_scope(): yield
            rc_scope = null_scope()

        async with rc_scope:
            if self.raptorchat_manager and self.raptorchat_manager.is_running():
                try:
                    self.raptorchat_manager.stop()
                    logger.info_system("RaptorChat stopped successfully")
                except Exception as e:
                    logger.error_system(f"Error stopping RaptorChat: {e}")
                    if channel:
                        await self.discord_manager.send_temp_message(channel, f"⚠️ Error stopping RaptorChat: {e}. Continuing...")
            elif self.raptorchat_manager:
                logger.debug_update("RaptorChat is not running, skipping stop")
            
            # Pause Player Manager after RaptorChat is stopped
            if self.player_manager:
                self.player_manager.pause()

            # Shutdown all servers using the shared helper
            logger.debug_update("Starting standardized shutdown of all servers")
            await self._shutdown_all_servers(channel)
        
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
        
        
        # Verify SteamCMD exists
        full_steamcmd_path = os.path.abspath(str(steamcmd_path))
        if not os.path.exists(full_steamcmd_path):
            logger.error_system(f"Update Aborted: SteamCMD not found at {full_steamcmd_path}")
            await self.discord_manager.send_temp_message(channel, f"❌ Update Error: SteamCMD not found at `{full_steamcmd_path}`! Please check your `config.json`.")
            raise UpdateError(f"SteamCMD executable not found: {full_steamcmd_path}")

        # Verify server_dir exists before proceeding
        full_server_path = os.path.abspath(str(server_dir))
        if not os.path.exists(full_server_path):
            logger.error_system(f"Update Aborted: Game directory not found at {full_server_path}")
            await self.discord_manager.send_temp_message(channel, f"❌ Update Error: Game directory not found! Check your configuration.")
            raise UpdateError(f"Install directory does not exist: {full_server_path}")

        # Build and execute SteamCMD command.
        cmd_args = [
            os.path.abspath(str(steamcmd_path)),
            "+login", "anonymous",
            "+app_update", str(app_id),
            "validate",
            "+quit"
        ]

        logger.debug_update(f"SteamCMD command: {cmd_args}")

        try:
            # Execute SteamCMD.
            result = await execute_steamcmd_simple(cmd_args)
        except OSError as e:
            logger.error_system(f"Windows rejected the SteamCMD launch (Errno {e.errno}): {e.strerror}")
            await self.discord_manager.send_temp_message(channel, f"❌ System Error: {e.strerror}. Check your config paths.")
            raise UpdateError(f"OS rejected the command: {e}")

        logger.debug_update(f"SteamCMD execution completed, return code: {result.returncode}")

        if result.returncode != 0:
            logger.debug_update(f"SteamCMD update failed (Code {result.returncode})")
            logger.error_system(f"SteamCMD update failed: {result.stderr or 'No error output'}")
            
            # Detailed error message for Discord
            error_details = (result.stderr or result.stdout or "No diagnostic output available").strip()
            if len(error_details) > 300:
                error_details = error_details[-300:] + "..." # Show last 300 chars of tail
            
            await self.discord_manager.send_temp_message(
                channel, 
                f"❌ SteamCMD Error (Code {result.returncode}):\n{error_details}"
            )
            raise UpdateError(f"SteamCMD update failed with code {result.returncode}")
        
        
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
        await self.discord_manager.send_temp_message(channel, f"🦖 Starting **{len(self.server_manager.servers)}** servers...")
        
        # Create a mock message object because _restart_all_servers expects one
        class UpdateMessage:
            def __init__(self, ch):
                self.channel = ch
                self.content = ".patch"
                self.author = type('MockAuthor', (), {'id': 'AutoUpdateSystem', 'name': 'PatchRaptor'})()
        
        await self._restart_all_servers(UpdateMessage(channel))
        
        # Wait for servers to come online and confirm success
        servers_online = False
        if self.server_manager:
            await self.discord_manager.send_temp_message(channel, f"⏳ Waiting for **{len(self.server_manager.servers)}** servers to come back online...")
            logger.debug_update("Waiting for servers to come online after global update...")
            servers_online = await self.server_manager.wait_for_servers_online(self.server_manager.servers)
            
            # Coordinated System Recovery
            if servers_online:
                await self.discord_manager.send_temp_message(channel, "🦕 All servers are back online")
                logger.info_system("All servers are back online")
                
                # Perform unified recovery (Wait 120s before starting chat)
                # This handles maintenance, player_manager resume, and raptorchat restart
                await SystemUtils.unified_system_recovery(
                    delay=5,
                    channel=channel,
                    raptorchat_manager=self.raptorchat_manager,
                    player_manager=self.player_manager,
                    discord_manager=self.discord_manager,
                    telemetry_manager=self.telemetry_manager,
                    msg_header="🖥️ Reconnecting Telemetry and Chat Relay after server update..."
                )

            else:
                await self.discord_manager.send_temp_message(channel, "⚠️ Not all servers came back online automatically. Please check status.")
        else:
            logger.warning_system("No server manager available for online check")

    async def cmd_patch(self, message, content: str, content_lower: str):
        """Handle .patch command"""
        author_id = getattr(getattr(message, "author", None), "id", None)
        if author_id == "ScheduleSystem":
            logger.info_command("Scheduled .patch initialising...")
        else:
            logger.info_command(".patch received")
        parts = content.split()
        
        # If no subcommands, start the patch process directly
        if len(parts) == 1:
            await self._internal_cmd_patch_start(message)
            return

        subcommand = parts[1].lower()
        
        if subcommand == "timer":
            await self._cmd_patch_set_timer(message, parts)
        elif subcommand == "broadcast":
            await self._cmd_patch_set_broadcast(message, parts, content)
        elif subcommand == "intervals":
            await self._cmd_patch_set_intervals(message, parts)
        elif subcommand == "webhook":
            await self._cmd_patch_set_webhook(message, parts, content)
        elif subcommand == "status":
            await self._cmd_patch_settings(message)
        else:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ Unknown patch subcommand: `{subcommand}`")

    async def _check_stale_lock_file(self, message):
        """Check for and remove stale update lock file"""
        if os.path.exists("update_in_progress.json"):
            try:
                creation_time = os.path.getctime("update_in_progress.json")
                if (time.time() - creation_time) > 7200: # 2 hours
                    logger.warning_system("Found stale update_in_progress.json (older than 2h), removing it.")
                    os.remove("update_in_progress.json")
                    return True
                else:
                    await self.discord_manager.send_temp_message(
                        message.channel, 
                        "⚠️ An update_in_progress.json file was found. This may indicate a previously failed update. Please resolve the issue and delete the file manually before starting a new update."
                    )
                    return False
            except OSError:
                return True # File deleted during check.
        return True

    async def _internal_cmd_patch_start(self, message):
        """Standard maintenance patch with countdown"""
        if self.update_lock.locked():
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Patch already in progress.")
            return

        if not await self._check_stale_lock_file(message):
            return

        async with self.update_lock:
            self.update_task = asyncio.current_task()
            try:
                with open("update_in_progress.json", "w") as f:
                    json.dump({"start_time": datetime.datetime.now().isoformat()}, f)

                settings = await self._get_patch_settings()
                timer = settings["timer"]
                
                await self.discord_manager.send_temp_message(message.channel, "🦖 Patch sequence initiated. Maintenance countdown started.")
                await self._run_update_countdown(message.channel)
                await self._internal_shutdown_and_update_servers(message.channel)
                
                # Completion Webhook for standard patches
                webhook_url = self.config_manager.get("discord_webhook", "")
                webhook_msg = self.config_manager.get("webhook_messages", {}).get("reboot")
                if webhook_url and webhook_msg:
                    logger.debug_update("Sending completion webhook notification")
                    await self.discord_manager.send_webhook_message(webhook_msg)
            except asyncio.CancelledError:
                logger.info_system("Patch process cancelled")
            except Exception as e:
                logger.error_system(f"Critical error during patch: {e}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ Patch Failed: {str(e)}")
            finally:
                if os.path.exists("update_in_progress.json"):
                    os.remove("update_in_progress.json")

    async def _cmd_patch_settings(self, message):
        """Display current patch configuration"""
        settings = await self._get_patch_settings()
        webhook_msgs = self.config_manager.get("webhook_messages", {})
        
        valid_intervals = [i for i in settings["intervals"] if i <= settings["timer"]]
        interval_str = ", ".join(map(str, sorted(valid_intervals, reverse=True)))
        
        embed = discord.Embed(title="🦖 Patch Settings", color=0x3498db)
        embed.add_field(name="⏱️ Countdown Timer", value=f"{settings['timer']} minutes", inline=True)
        embed.add_field(name="📡 Broadcast Schedule", value=f"At {interval_str} minutes", inline=True)
        embed.add_field(name="📡 Broadcast Template", value=f"{settings['broadcast']}", inline=False)
        
        shutdown_msg = webhook_msgs.get("shutdown", "🔲 OFF")
        reboot_msg = webhook_msgs.get("reboot", "🔲 OFF")
        
        embed.add_field(name="📢 Shutdown Webhook", value=f"{shutdown_msg}", inline=False)
        embed.add_field(name="📢 Reboot Webhook", value=f"{reboot_msg}", inline=False)
        await self.discord_manager.send_temp_message(message.channel, embed=embed)

    async def _cmd_patch_set_timer(self, message, parts):
        """Set the patch countdown timer"""
        if len(parts) < 3:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.patch timer <minutes>`")
            return
        try:
            timer = int(parts[2])
            if timer < 1: raise ValueError()
            settings = self.config_manager.get("patch_settings", {})
            settings["timer"] = timer
            self.config_manager.config["patch_settings"] = settings
            self.config_manager.save()
            await self.discord_manager.send_temp_message(message.channel, f"☑️ Patch timer set to {timer} minutes.")
        except ValueError:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Please provide a valid number of minutes.")

    async def _cmd_patch_set_broadcast(self, message, parts, content):
        """Set the RCON broadcast template"""
        if len(parts) < 3:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.patch broadcast <template>`\nUse {minutes} as a placeholder.")
            return
        template = " ".join(parts[2:])
        settings = self.config_manager.get("patch_settings", {})
        settings["broadcast"] = template
        self.config_manager.config["patch_settings"] = settings
        self.config_manager.save()
        await self.discord_manager.send_temp_message(message.channel, f"☑️ Patch broadcast template updated.")

    async def _cmd_patch_set_intervals(self, message, parts):
        """Set the broadcast intervals"""
        if len(parts) < 3:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.patch intervals 15,10,5,1`")
            return
        try:
            interval_str = parts[2].replace(" ", "")
            intervals = [int(i) for i in interval_str.split(",")]
            settings = self.config_manager.get("patch_settings", {})
            settings["intervals"] = intervals
            self.config_manager.config["patch_settings"] = settings
            self.config_manager.save()
            await self.discord_manager.send_temp_message(message.channel, f"☑️ Broadcast intervals updated.")
        except ValueError:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Please provide a comma-separated list of numbers.")

    async def _cmd_patch_set_webhook(self, message, parts, content):
        """Set webhook messages under .patch suite"""
        if len(parts) < 4:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.patch webhook shutdown|reboot <message>`")
            return
        msg_type = parts[2].lower()
        if msg_type not in ["shutdown", "reboot"]:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Type must be shutdown or reboot.")
            return
        webhook_msg = " ".join(parts[3:])
        webhook_messages = self.config_manager.get("webhook_messages", {})
        webhook_messages[msg_type] = webhook_msg
        self.config_manager.config["webhook_messages"] = webhook_messages
        self.config_manager.save()
        await self.discord_manager.send_temp_message(message.channel, f"☑️ {msg_type.capitalize()} webhook message updated.")

    async def cmd_forcepatch(self, message, content: str, content_lower: str):
        """Handle force update logic (.forcepatch)"""
        if self.update_lock.locked():
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Patch already in progress.")
            return
        async with self.update_lock:
            self.update_task = asyncio.current_task()
            try:
                with open("update_in_progress.json", "w") as f:
                    json.dump({"start_time": datetime.datetime.now().isoformat(), "force": True}, f)
                logger.info_system("Starting immediate force patch process...")
                await self.discord_manager.send_temp_message(message.channel, "🦖 Force update sequence initiated...")
                await self._internal_shutdown_and_update_servers(message.channel, skip_countdown=True)
            except asyncio.CancelledError:
                logger.info_system("Force patch cancelled")
            except Exception as e:
                logger.error_system(f"Critical error during force patch: {e}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ Force Patch Failed: {str(e)}")
            finally:
                if os.path.exists("update_in_progress.json"):
                    os.remove("update_in_progress.json")

    async def cmd_autopatch(self, message, content: str, content_lower: str):
        """Handle .autopatch command - toggle auto-patch"""
        from .log_manager import logger
        logger.debug_update(".autopatch command received")
        logger.info_command(".autopatch received")
        parts = content_lower.split()
        logger.debug_update(f"Command parts: {parts}")
        if len(parts) == 1:
            logger.debug_update("Checking autopatch status")
            status = "☑️ ON" if self.autoupdate_enabled else "🛑 OFF"
            task_status = "Running" if (self.autoupdate_task and not self.autoupdate_task.done()) else "Stopped"
            logger.debug_update(f"Autopatch status: {status}, task status: {task_status}")
            await self.discord_manager.send_temp_message(
                message.channel, 
                f"Autopatch status: {status}"
            )
            return
        
        if parts[1] == "on":
            logger.debug_update("Enabling autopatch")
            if not self.autoupdate_enabled:
                self.autoupdate_enabled = True
                logger.info_system("Autopatch enabled, starting background checker...")
                await self.start_autoupdate_checker(message.channel)
                await self.discord_manager.send_temp_message(message.channel, "☑️ Autopatch is now ON.")
            else:
                logger.debug_update("Autopatch already enabled")
                await self.discord_manager.send_temp_message(message.channel, "☑️ Autopatch is already ON")
        elif parts[1] == "off":
            logger.debug_update("Disabling autoupdate")
            if self.autoupdate_enabled:
                self.autoupdate_enabled = False
                logger.info_system("Autoupdate disabled, stopping background checker...")
                await self.stop_autoupdate_checker()
                await self.discord_manager.send_temp_message(message.channel, "🛑 Autopatch stopped.")
            else:
                logger.debug_update("Autoupdate already disabled")
                await self.discord_manager.send_temp_message(message.channel, "🛑 Autopatch already stopped")
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
        # Clear player data when restarting servers
        if self.player_manager:
            logger.debug_update("Clearing player data for all servers")
            try:
                logger.info_system("Clearing player data...")
                await self.player_manager.clear_server_players()
                logger.debug_update("Player data cleared successfully")
            except Exception as e:
                logger.debug_update(f"Failed to clear player logic: {e}")
                logger.warning_system(f"Failed to clear player logic: {e}")
        
        # Staggered server restart
        logger.debug_update(f"Restarting {len(self.server_manager.servers)} servers with 30-second stagger")
        for srv in self.server_manager.servers:
            logger.debug_update(f"Restarting server: {srv.name}")
            await self._restart_one_server(srv, message)
            logger.debug_update(f"Sleeping 30 seconds before next server restart")
            await asyncio.sleep(30)  # Staggered startup
        
        # RaptorChat will be restarted after the 5-minute delay in the .patch / .forcepatch command
        logger.debug_update("Server restarts completed, waiting for servers to come online...")

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

    async def _shutdown_all_servers(self, channel=None):
        """Shutdown all servers via RCON and wait for them to shut down"""
        from .log_manager import logger
        logger.debug_update("Starting _shutdown_all_servers method")
        logger.info_system("Sending RCON command: DoExit to all running servers")
        
        running_servers = [s for s in self.server_manager.servers if self.server_manager.is_specific_server_running(s)]
        if channel:
            await self.discord_manager.send_temp_message(channel, f"📡 Sending shutdown command to **{len(running_servers)}** servers...")
        
        tasks = []
        for server in running_servers:
            task = self.rcon_manager.execute_for_server(server, "DoExit")
            tasks.append((server, task))
        
        success_count = 0
        for server, task in tasks:
            try:
                await task
                success_count += 1
                logger.info_system(f"Successfully sent DoExit to {server.name}")
            except (RCONConnectionError, RCONCommandError) as e:
                display_name = self.server_manager.get_display_name(server)
                logger.debug_update(f"Failed to send shutdown to {server.name}: {e.reason}")
                logger.error_system(f"Failed to send shutdown to {server.name}: {e.reason}")
                if channel:
                    await self.discord_manager.send_temp_message(channel, f"⚠️ Failed to send shutdown to {display_name}: {e.reason}")
        
        # Wait for all servers to shut down
        logger.debug_update("Waiting for all servers to shut down")
        if tasks:
            if channel:
                await self.discord_manager.send_temp_message(channel, f"⏳ Waiting for **{len(running_servers)}** servers to shut down...")
        
        logger.info_system("Waiting for all servers to shut down...")
        for server in self.server_manager.servers:
            logger.debug_update(f"Waiting for server {server.name} to shut down (300 seconds timeout)")
            shutdown_success = await self.server_manager.wait_for_server_shutdown(server, timeout=300)
            if not shutdown_success:
                logger.warning_system(f"Timeout waiting for {server.name} to shut down. Initiating Ghost Recovery...")
                if channel:
                    await self.discord_manager.send_temp_message(channel, f"👻 {self.server_manager.get_display_name(server)} failed to shut down. Initiating Ghost Recovery...")
                self.server_manager.force_stop_server(server)
            else:
                logger.debug_update(f"Server {server.name} shut down successfully")
                
        if channel:
            await self.discord_manager.send_temp_message(channel, "🦕 All servers have shut down successfully")

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
        logger.info_system("Background autoupdate service initializing...")
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
            
            if not current or current == "Unknown":
                logger.debug_update("No current version found, setting initial version")
                logger.info_system("No current version found, performing initial update check")
            
            # Check if update is needed
            if current != latest:
                # Use provided discord_channel or fetch from config
                channel = discord_channel or await self.discord_manager.get_default_channel()
                
                if channel:
                    # Send notification that update was detected
                    await self.discord_manager.send_temp_message(channel, "⚠️ New version detected!")
                else:
                    logger.info_system("Update detected. No Discord channel found; relying on Unified Path Webhooks.")
                
                # Create mock message object so .patch works exactly like when user types it
                class MockMessage:
                    def __init__(self, channel):
                        self.channel = channel
                        self.author = type('MockAuthor', (), {'id': 'AutoUpdateSystem', 'name': 'PatchRaptor'})()
                
                # Trigger .patch command with proper message object
                await self.cmd_patch(MockMessage(channel), ".patch", ".patch")
                
            else:
                logger.debug_update("No new updates found, current version is up to date")
                logger.info_system("No new updates found")
                
        except Exception as e:
            logger.debug_update(f"Error during autoupdate check: {e}")
            logger.error_system(f"Error during autoupdate check: {e}")
