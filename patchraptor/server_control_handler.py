# =============================================================================
# Async Consistency Pattern Implementation
# =============================================================================
# This file implements consistent async/await patterns for server control operations.
# Pattern Guide:
#   - All public methods are async (await-based, no blocking calls)
#   - RCON execute_for_server() returns async Task with timeout handling
#   - asyncio.to_thread() used for blocking subprocess operations (RCON communication)
#   - Server lifecycle operations (start/stop/wait) use explicit timeouts
import asyncio
import datetime
import os
import psutil
import discord
from .log_manager import logger
from .exceptions import (
    ServerError,
    ServerNotFoundError,
    ServerNotRunningError,
    ServerAlreadyRunningError,
    ServerOperationError,
    RCONError,
    RCONConnectionError,
    RCONCommandError,
    ProcessError
)
from .system_utils import SystemUtils
from .base_handler import BaseHandler

RAPTORCHAT_RESTART_DELAY = 5  # Seconds to wait after servers online before restarting RaptorChat
SERVER_SHUTDOWN_TIMEOUT = 300   # Seconds to wait for a server to shut down before Ghost Recovery


class ServerControlHandler(BaseHandler):
    """Handles server control commands: reboot, shutdown, servers, send"""


    async def cmd_reboot(self, message, content: str, content_lower: str):
        """Handle .reboot command - reboot servers"""
        author_id = getattr(getattr(message, "author", None), "id", None)
        if author_id == "ScheduleSystem":
            logger.info_command("Scheduled .reboot initialising...")
        else:
            logger.info_command(".reboot received")
        parts = content.split()
        
        is_all = len(parts) == 1
        server = None
        display_name = None
        
        if not is_all:
            map_name = parts[1]
            try:
                server = self.server_manager.find_server(map_name)
                display_name = self.server_manager.get_display_name(server)
            except ServerNotFoundError:
                await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with name '{map_name}'.")
                return
                
        if is_all:
            await self.discord_manager.send_temp_message(message.channel, "🦖 Reboot sequence initiated...")
            await self.discord_manager.send_temp_message(message.channel, "🖥️ Pausing Telemetry and Chat Relay...")
            
            # Use maintenance scope to ensure semaphore is released even on failure
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
                        logger.info_system("Stopping RaptorChat for reboot...")
                        self.raptorchat_manager.stop()
                        logger.info_system("RaptorChat stopped successfully")
                    except Exception as e:
                        logger.error_system(f"Error stopping RaptorChat: {e}")
                        await self.discord_manager.send_temp_message(message.channel, "⚠️ Error stopping RaptorChat. Continuing with reboot sequence...")
                elif self.raptorchat_manager:
                    logger.debug_system("RaptorChat is not running, skipping stop")
                
                # Pause Player Manager after RaptorChat is stopped
                if self.player_manager:
                    self.player_manager.pause()
                
                # Get list of servers that are currently running
                running_servers = [s for s in self.server_manager.servers 
                                 if self.server_manager.is_specific_server_running(s)]
                
                # Step 1: Send DoExit to each running server
                if running_servers:
                    await self.discord_manager.send_temp_message(message.channel, f"📡Sending shutdown command to **{len(running_servers)}** servers...")
                    logger.info_system("Sending RCON command: DoExit to all running servers")
                    
                    for server in running_servers:
                        try:
                            await self.rcon_manager.execute_for_server(server, "DoExit")
                            logger.info_system(f"Successfully sent DoExit to {server.name}")
                        except (RCONConnectionError, RCONCommandError) as e:
                            display_name_srv = self.server_manager.get_display_name(server)
                            await self.discord_manager.send_temp_message(message.channel, f"⚠️ Failed to send shutdown to {display_name_srv}: {e.reason}")
                            logger.warning_system(f"Failed to send DoExit to {server.name}: {e.reason}")
                
                # Step 2: Wait for all servers to shutdown
                logger.info_system("Waiting for servers to shutdown...")
                if running_servers:
                    await self.discord_manager.send_temp_message(message.channel, f"⏳ Waiting for **{len(running_servers)}** servers to shut down completely...")
                    for server in running_servers:
                        success = await self.server_manager.wait_for_server_shutdown(server, SERVER_SHUTDOWN_TIMEOUT)
                        if not success:
                            logger.warning_system(f"Timeout waiting for {server.name} to shut down. Initiating Ghost Recovery...")
                            await self.discord_manager.send_temp_message(message.channel, f"👻 {self.server_manager.get_display_name(server)} failed to shut down. Initiating Ghost Recovery...")
                            self.server_manager.force_stop_server(server)
                    await self.discord_manager.send_temp_message(message.channel, "🦕 All servers have shut down successfully")
                
                # Step 3: Restart all servers
                logger.info_system("Restarting servers with 30s staggered delay...")
                await self.discord_manager.send_temp_message(message.channel, f"🦖 Starting **{len(self.server_manager.servers)}** servers...")
                await self._restart_all_servers(message)
                
                # Step 4: Wait for servers to come back online
                if self.server_manager.servers:
                    await self.discord_manager.send_temp_message(message.channel, f"⏳ Waiting for **{len(self.server_manager.servers)}** servers to come back online...")
                    servers_online = await self.server_manager.wait_for_servers_online(self.server_manager.servers)
                    
                    if servers_online:
                        logger.info_system("All servers are back online")
                        await self.discord_manager.send_temp_message(message.channel, "🦕 All servers are back online")
                        await self._delayed_raptorchat_restart(RAPTORCHAT_RESTART_DELAY, message.channel)
                        logger.info_system("Reboot process completed")
                    else:
                        await self.discord_manager.send_temp_message(
                            message.channel,
                            "⚠️ Not all servers came back online. RaptorChat will not be restarted automatically."
                        )
                        if self.raptorchat_manager:
                            self.raptorchat_manager.end_maintenance()
            return

        # Single-server reboot logic
        await self.discord_manager.send_temp_message(message.channel, f"🦖 Reboot sequence initiated for {display_name}...")
        was_running = self.server_manager.is_specific_server_running(server)
        
        if was_running:
            # Step 1: Send DoExit to specific server
            logger.info_system(f"Sending RCON command: DoExit to {server.name}")
            try:
                await self.rcon_manager.execute_for_server(server, "DoExit")
                await self.discord_manager.send_temp_message(message.channel, f"📡Sending shutdown command to {display_name}...")
                logger.info_system(f"Successfully sent DoExit to {server.name}")
            except (RCONConnectionError, RCONCommandError) as e:
                await self.discord_manager.send_temp_message(message.channel, f"⚠️ Failed to send shutdown command to {display_name}: {e.reason}")
                return
            
            # Step 2: Wait for server to shutdown
            logger.info_system(f"Waiting for {server.name} to shutdown...")
            await self.discord_manager.send_temp_message(message.channel, f"⏳ Waiting for {display_name} to shut down...")
            success = await self.server_manager.wait_for_server_shutdown(server, SERVER_SHUTDOWN_TIMEOUT)
            if not success:
                logger.warning_system(f"Timeout waiting for {server.name} to shut down. Initiating Ghost Recovery...")
                await self.discord_manager.send_temp_message(message.channel, f"👻 {display_name} failed to shut down. Initiating Ghost Recovery...")
                self.server_manager.force_stop_server(server)
            await self.discord_manager.send_temp_message(message.channel, f"🦕 {display_name} has shut down successfully")
        
        # Step 3: Restart the specific server
        logger.debug_system(f"Restarting {server.name}...")
        await self._restart_one_server(server, message)
        
        # Step 4: Wait for server to come back online
        await self.discord_manager.send_temp_message(message.channel, f"⏳ Waiting for {display_name} to come back online...")
        server_online = await self.server_manager.wait_for_servers_online([server])
        
        if server_online:
            logger.info_system(f"{server.name} is back online")
            await self.discord_manager.send_temp_message(message.channel, f"🦕 {display_name} is back online")
            logger.info_system("Reboot process completed")
        else:
            await self.discord_manager.send_temp_message(
                message.channel,
                f"⚠️ {display_name} did not come back online."
            )
    
    async def _delayed_raptorchat_restart(self, delay: int, channel):
        """Helper method to coordinate system recovery after a delay"""
        await SystemUtils.unified_system_recovery(
            delay=delay,
            channel=channel,
            raptorchat_manager=self.raptorchat_manager,
            player_manager=self.player_manager,
            discord_manager=self.discord_manager,
            telemetry_manager=self.telemetry_manager,
            msg_header="🖥️ Reconnecting Telemetry and Chat Relay after server reboot..."
        )

    async def cmd_shutdown(self, message, content: str, content_lower: str):
        """Handle .shutdown command - shutdown servers"""
        author_id = getattr(getattr(message, "author", None), "id", None)
        if author_id == "ScheduleSystem":
            logger.info_command("Scheduled .shutdown initialising...")
        else:
            logger.info_command(".shutdown received")
        parts = content.split()
        if len(parts) == 1:
            await self.discord_manager.send_temp_message(message.channel, "🦖 Shutdown sequence initiated...")
            
            # Step 1: Stop RaptorChat gracefully before server shutdown
            if self.raptorchat_manager:
                rc_scope = self.raptorchat_manager.maintenance_scope(handoff=False)
            else:
                from contextlib import asynccontextmanager
                @asynccontextmanager
                async def null_scope(): yield
                rc_scope = null_scope()

            async with rc_scope:
                if self.raptorchat_manager and self.raptorchat_manager.is_running():
                    try:
                        logger.info_system("Stopping RaptorChat for shutdown...")
                        self.raptorchat_manager.stop()
                        logger.info_system("RaptorChat stopped successfully")
                        await self.discord_manager.send_temp_message(message.channel, "🖥️ Pausing Telemetry and Chat Relay...")
                    except Exception as e:
                        logger.error_system(f"Error stopping RaptorChat: {e}")
                        await self.discord_manager.send_temp_message(message.channel, f"⚠️ Error stopping RaptorChat: {e}")
                elif self.raptorchat_manager:
                    logger.debug_system("RaptorChat is not running, skipping stop")
            
            # Step 2: Send DoExit to all running servers
            running_servers = [s for s in self.server_manager.servers if self.server_manager.is_specific_server_running(s)]
            if running_servers:
                await self.discord_manager.send_temp_message(message.channel, f"📡Sending shutdown command to **{len(running_servers)}** servers...")
                logger.info_system("Sending RCON command: DoExit to all running servers")
                
                for server in running_servers:
                    try:
                        await self.rcon_manager.execute_for_server(server, "DoExit")
                        logger.info_system(f"Successfully sent DoExit to {server.name}")
                    except (RCONConnectionError, RCONCommandError) as e:
                        display_name = self.server_manager.get_display_name(server)
                        await self.discord_manager.send_temp_message(message.channel, f"⚠️ Failed to send shutdown to {display_name}: {e.reason}")
                        logger.warning_system(f"Failed to send DoExit to {server.name}: {e.reason}")
            
            # Step 3: Wait for all servers to shutdown
            logger.info_system("Waiting for all servers to shutdown...")
            await self.discord_manager.send_temp_message(message.channel, f"⏳ Waiting for **{len(running_servers)}** servers to shut down...")
            for server in self.server_manager.servers:
                if not await self.server_manager.wait_for_server_shutdown(server, SERVER_SHUTDOWN_TIMEOUT):
                    logger.warning_system(f"Timeout waiting for {server.name} to shut down. Initiating Ghost Recovery...")
                    await self.discord_manager.send_temp_message(message.channel, f"👻 {self.server_manager.get_display_name(server)} failed to shut down. Initiating Ghost Recovery...")
                    self.server_manager.force_stop_server(server)
            
            logger.info_system("All servers have shut down successfully")
            await self.discord_manager.send_temp_message(message.channel, "🦕 All servers have shut down successfully")
            return

        map_name = parts[1]
        try:
            server = self.server_manager.find_server(map_name)
        except ServerNotFoundError:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with name '{map_name}'.")
            return
        display_name = self.server_manager.get_display_name(server)
        
        await self.discord_manager.send_temp_message(message.channel, f"🦖 Shutdown sequence initiated for {display_name}...")
        
        # Step 1: Send DoExit to specific server
        logger.info_system(f"Sending RCON command: DoExit to {server.name}")
        try:
            await self.rcon_manager.execute_for_server(server, "DoExit")
            await self.discord_manager.send_temp_message(message.channel, f"📡Sending shutdown command to {display_name}...")
            logger.info_system(f"Successfully sent DoExit to {server.name}")
        except (RCONConnectionError, RCONCommandError) as e:
            error_msg = f"Failed to send shutdown command to {display_name}: {e.reason}"
            logger.error_system(error_msg)
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ {error_msg}")
            return
        
        # Step 2: Wait for server to shutdown
        logger.info_system(f"Waiting for {display_name} to shut down...")
        await self.discord_manager.send_temp_message(message.channel, f"⏳ Waiting for {display_name} to shut down...")
        success = await self.server_manager.wait_for_server_shutdown(server, SERVER_SHUTDOWN_TIMEOUT)
        
        if not success:
            logger.warning_system(f"Timeout waiting for {server.name} to shut down. Initiating Ghost Recovery...")
            await self.discord_manager.send_temp_message(message.channel, f"👻 {display_name} failed to shut down. Initiating Ghost Recovery...")
            self.server_manager.force_stop_server(server)
            
        logger.info_system(f"{server.name} has shut down successfully")
        await self.discord_manager.send_temp_message(
            message.channel, 
            f"🦕 {display_name} has shut down successfully"
        )

    async def cmd_servers(self, message, content: str, content_lower: str):
        """Handle .servers command - show server details"""
        logger.info_command(".servers received")
        logger.debug_system("Gathering server details from Telemetry Echo...")
        
        # Pull the latest live state from TelemetryManager
        telemetry = self.telemetry_manager
        state = telemetry.current_state
        
        embed = discord.Embed(title="📊 **Server Details**", color=0x3498DB)
        lines = []
        
        for server in self.server_manager.servers:
            display_name = self.server_manager.get_display_name(server)
            lines.append(f"🗺️ Map Name      : {display_name}")
            
            server_data = next((s for s in state.servers if s['name'] == server.name), None)
            
            if server_data and server_data['status'] == 'online':
                lines.append(f"☑️ Status          : Online")
                lines.append(f"🔌 Uptime          : {SystemUtils.format_duration(server_data.get('uptime_seconds', 0))}")
                lines.append(f"🎮 Players         : {server_data['playerCount']}")
                lines.append(f"💻 Process CPU     : {server_data['cpu']:.1f}%")
                lines.append(f"⚡ Process RAM     : {server_data['ram']:.2f} GB")
            else:
                lines.append("🔲 Status          : Offline")

            try:
                if server.server_save_path and os.path.exists(server.server_save_path):
                    total_bytes = SystemUtils.get_directory_size(server.server_save_path)
                    disk_used_gb = total_bytes / (1024 ** 3)
                    
                    drive_path = os.path.splitdrive(server.server_save_path)[0] + "\\"
                    if os.path.exists(drive_path):
                        disk_info = psutil.disk_usage(drive_path)
                        disk_total_gb = disk_info.total / (1024 ** 3)
                        disk_percent = (disk_used_gb / disk_total_gb) * 100
                        lines.append(f"💾 Save Size       : {disk_used_gb:.2f} GB")
                    else:
                        lines.append(f"💾 Save Size       : {disk_used_gb:.2f} GB")
                else:
                    lines.append(f"💾 Save Size       : N/A (path inaccessible)")
            except Exception as e:
                logger.debug_system(f"Error getting disk size for {server.name}: {e}")
                lines.append(f"💾 Save Size       : Error")
                
            lines.append("")
        
        embed.description = "\n".join(lines)
        await self.discord_manager.send_temp_message(message.channel, embed=embed)

    async def cmd_send(self, message, content: str, content_lower: str):
        """Handle .send command - send messages to servers"""
        logger.info_command(".send received")
        
        if content_lower.startswith(".send all "):
            msg = content[10:].strip()
            await self.discord_manager.send_temp_message(message.channel, "📡Sending broadcast to all servers...")
            
            for srv in self.server_manager.servers:
                try:
                    await self.rcon_manager.execute_for_server(srv, f"ServerChat {msg}")
                except (RCONConnectionError, RCONCommandError) as e:
                    display_name = self.server_manager.get_display_name(srv)
                    logger.warning_system(f"Failed to send message to {srv.name}: {e.reason}")
                    await self.discord_manager.send_temp_message(message.channel, f"⚠️ Failed to send to {display_name}: {e.reason}")
            return

        parts = content.split(maxsplit=2)
        if len(parts) < 3:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.send <map> <message>`")
            return
            
        map_name = parts[1]
        msg = parts[2].strip()
        
        try:
            server = self.server_manager.find_server(map_name)
        except ServerNotFoundError:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with map name '{map_name}'.")
            return
            
        display_name = self.server_manager.get_display_name(server)
        
        try:
            await self.rcon_manager.execute_for_server(server, f"ServerChat {msg}")
            await self.discord_manager.send_temp_message(message.channel, f"📡Sending broadcast to {display_name}...")
        except (RCONConnectionError, RCONCommandError) as e:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ Failed to send to {display_name}: {e.reason}")

    async def _restart_all_servers(self, message):
        """Restart all servers with staggered startup"""
        if hasattr(self, 'player_manager') and self.player_manager:
            try:
                logger.info_system("Clearing player data...")
                await self.player_manager.clear_server_players()
                
                if self.telemetry_manager:
                    logger.info_system("Resetting log detection positions...")
                    await self.telemetry_manager.trigger_log_file_detection_on_restart()

                logger.debug_system("Player data and log positions reset successfully")
            except Exception as e:
                logger.warning_system(f"Failed to clear player logic: {e}")
        
        for srv in self.server_manager.servers:
            await self._restart_one_server(srv, message)
            await asyncio.sleep(30)  # Staggered startup
            
        logger.debug_system("Server restarts completed, waiting for servers to come online...")

    async def _restart_one_server(self, server, message):
        """Restart a single server"""
        try:
            self.server_manager.start_server(server)
            await self.discord_manager.send_temp_message(message.channel, f"🦖 {self.server_manager.get_display_name(server)} is now starting...")
        except ServerAlreadyRunningError as e:
            logger.warning_system(f"{server.name} already running: {e.message}")
            await self.discord_manager.send_temp_message(message.channel, f"ℹ️ {self.server_manager.get_display_name(server)} was already running")
        except ServerOperationError as e:
            import asyncio
            logger.warning_system(f"Server start error for {server.name}: {e.reason}, checking actual status...")
            await asyncio.sleep(5)
            
            if self.server_manager.is_specific_server_running(server):
                logger.info_system(f"{server.name} is actually running despite start error")
                await self.discord_manager.send_temp_message(message.channel, f"🦖 {self.server_manager.get_display_name(server)} is now starting...")
            else:
                logger.error_system(f"Failed to start {server.name}: {e.reason}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to start {server.name}: {e.reason}")
        except Exception as e:
            logger.error_system(f"Unexpected error restarting server {server.name}: {e}")
            await self.discord_manager.send_temp_message(message.channel, f"❌ Unexpected error starting {server.name}: {e}")
