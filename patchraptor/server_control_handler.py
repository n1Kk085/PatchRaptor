import asyncio
import datetime
import os
import psutil
from .log_manager import logger
from .server_manager import ServerManager
from .rcon_manager import RCONManager
from .discord_manager import DiscordManager
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
from .raptorchat_utils import RaptorChatUtils


class ServerControlHandler:
    """Handles server control commands: reboot, shutdown, servers, send"""
    
    def __init__(
        self,
        server_manager: ServerManager,
        rcon_manager: RCONManager,
        discord_manager: DiscordManager,
        player_manager,
        raptorchat_manager
    ):
        self.server_manager = server_manager
        self.rcon_manager = rcon_manager
        self.discord_manager = discord_manager
        self.player_manager = player_manager
        self.raptorchat_manager = raptorchat_manager

    async def _wait_for_servers_online(self, servers, timeout=300, check_interval=10):
        """Wait for all specified servers to come online"""
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

    async def cmd_reboot(self, message, content: str, content_lower: str):
        """Handle .reboot command - reboot servers"""
        logger.info_command(".reboot received")
        parts = content.split()
        
        # Stop RaptorChat before rebooting servers
        if hasattr(self, 'raptorchat_manager') and self.raptorchat_manager:
            logger.info_system("Stopping RaptorChat before server reboot...")
            try:
                if self.raptorchat_manager.is_running():
                    self.raptorchat_manager.stop()
                else:
                    logger.debug_system("RaptorChat is not running, skipping stop")
            except Exception as e:
                logger.error_system(f"Error stopping RaptorChat: {e}")
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Error stopping RaptorChat. Continuing with server reboot...")
        
        # Pause Player Manager after RaptorChat is stopped
        if hasattr(self, 'player_manager') and self.player_manager:
            self.player_manager.pause()
        
        if len(parts) == 1:
            # Reboot all: DoExit then start
            await self.discord_manager.send_temp_message(message.channel, "♻️ Rebooting all running servers...")
            
            # Get list of servers that are currently running
            running_servers = [s for s in self.server_manager.servers 
                             if self.server_manager.is_specific_server_running(s)]
            
            # Step 1: Send DoExit to each running server
            logger.info_system("Sending RCON command: DoExit")
            for server in running_servers:
                try:
                    await self.rcon_manager.execute_for_server(server, "DoExit")
                    logger.info_system(f"Successfully sent to {server.name} ({server.rcon_ip}:{server.rcon_port})")
                except (RCONConnectionError, RCONCommandError) as e:
                    logger.warning_system(f"Failed to send DoExit to {server.name}: {e.reason}")
            
            # Step 2: Wait for all servers to shutdown
            logger.info_system("Waiting for servers to shutdown...")
            for server in running_servers:
                await self.server_manager.wait_for_server_shutdown(server, 300)
            
            # Step 3: Restart all servers
            logger.info_system("Restarting servers with 30s delay...")
            await self._restart_all_servers(message)
            
            # Step 4: Wait for servers to come back online
            # We wait for ALL servers because _restart_all_servers attempts to start all of them
            if self.server_manager.servers:
                await self.discord_manager.send_temp_message(message.channel, "⏳ Waiting for servers to come back online...")
                servers_online = await self._wait_for_servers_online(self.server_manager.servers)
                
                if servers_online:
                    # Get the current time as the last server online time
                    last_online_time = asyncio.get_event_loop().time()
                    # Calculate remaining delay (2 minutes from now)
                    remaining_delay = max(0, 120 - (asyncio.get_event_loop().time() - last_online_time))
                    
                    if remaining_delay > 0:
                        await self.discord_manager.send_temp_message(
                            message.channel, 
                            f"✅ All servers are back online"
                        )
                        # Start RaptorChat after the remaining delay
                        await self._delayed_raptorchat_restart(remaining_delay, message.channel)
                        logger.info_system("Reboot process completed")
                    else:
                        # If we're already past the 5-minute mark, start immediately
                        await self._delayed_raptorchat_restart(0, message.channel)
                else:
                    await self.discord_manager.send_temp_message(
                        message.channel,
                        "⚠️ Not all servers came back online. RaptorChat will not be restarted automatically."
                    )
            return
            
        # Reboot specific server
        map_name = parts[1]
        try:
            server = self.server_manager.find_server(map_name)
        except ServerNotFoundError:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with name '{map_name}'.")
            return
            
        display_name = self.server_manager.get_display_name(server)
        was_running = self.server_manager.is_specific_server_running(server)
        
        if was_running:
            await self.discord_manager.send_temp_message(message.channel, f"♻️ Rebooting {display_name} server...")
            
            # Step 1: Send DoExit to specific server
            logger.info_system("Sending RCON command: DoExit")
            try:
                await self.rcon_manager.execute_for_server(server, "DoExit")
                logger.info_system(f"Successfully sent DoExit to {server.name} ({server.rcon_ip}:{server.rcon_port})")
            except (RCONConnectionError, RCONCommandError) as e:
                await self.discord_manager.send_temp_message(message.channel, f"⚠️ Failed to send shutdown command to {display_name}: {e.reason}")
                return
            
            # Step 2: Wait for server to shutdown
            logger.info_system(f"Waiting for {server.name} to shutdown...")
            await self.server_manager.wait_for_server_shutdown(server, 300)
        
        # Step 3: Restart the specific server
        logger.info_system(f"Restarting {server.name} with 30s delay...")
        await self._restart_one_server(server, message)
        
        # Step 4: Wait for server to come back online if it was running
        if was_running:
            await self.discord_manager.send_temp_message(message.channel, f"⏳ Waiting for {display_name} to come back online...")
            server_online = await self._wait_for_servers_online([server])
            
            if server_online:
                # Get the current time as the last server online time
                last_online_time = asyncio.get_event_loop().time()
                # Calculate remaining delay (2 minutes from now)
                remaining_delay = max(0, 120 - (asyncio.get_event_loop().time() - last_online_time))
                
                if remaining_delay > 0:
                    await self.discord_manager.send_temp_message(
                        message.channel,
                        f"✅ {display_name} is back online. RaptorChat will start in {int(remaining_delay/60)} minutes..."
                    )
                    # Start RaptorChat after the remaining delay
                    await self._delayed_raptorchat_restart(remaining_delay, message.channel)
                else:
                    # If we're already past the 5-minute mark, start immediately
                    await self._delayed_raptorchat_restart(0, message.channel)
            else:
                await self.discord_manager.send_temp_message(
                    message.channel,
                    f"⚠️ {display_name} did not come back online. RaptorChat will not be restarted automatically."
                )
    
    async def _delayed_raptorchat_restart(self, delay: int, channel):
        """Helper method to restart RaptorChat after a delay"""
        # Wait for the delay first
        if delay > 0:
            await asyncio.sleep(delay)

        # Resume PlayerManager (explicitly here to control log order)
        if hasattr(self, 'player_manager') and self.player_manager:
            self.player_manager.resume()

        # Trigger PlayerManager Log Detection IMMEDIATELY
        if self.player_manager:
            await self.player_manager.trigger_log_file_detection_on_restart()
        
        # Then start RaptorChat (pass 0 delay since we already waited)
        await RaptorChatUtils.delayed_raptorchat_restart(
            self.raptorchat_manager if hasattr(self, 'raptorchat_manager') else None,
            0, # 0 delay because we handled it above
            channel,
            self.discord_manager if hasattr(self, 'discord_manager') else None
        )

    async def cmd_shutdown(self, message, content: str, content_lower: str):
        """Handle .shutdown command - shutdown servers"""
        logger.info_command(".shutdown received")
        parts = content.split()
        if len(parts) == 1:
            await self.discord_manager.send_temp_message(message.channel, "⏹️ Shutting down all servers...")
            
            # Step 1: Stop RaptorChat gracefully before server shutdown
            if hasattr(self, 'raptorchat_manager') and self.raptorchat_manager:
                logger.info_system("Stopping RaptorChat before server shutdown...")
                try:
                    if self.raptorchat_manager.is_running():
                        self.raptorchat_manager.stop()
                        logger.info_system("RaptorChat stopped successfully")
                        await self.discord_manager.send_temp_message(message.channel, "💬 RaptorChat has been stopped.")
                    else:
                        logger.debug_system("RaptorChat is not running, skipping stop")
                except Exception as e:
                    error_msg = f"Error stopping RaptorChat: {e}"
                    logger.error_system(error_msg)
                    await self.discord_manager.send_temp_message(message.channel, f"⚠️ {error_msg}")
            
            # Step 2: Send DoExit to all servers
            logger.info_system("Sending RCON command: DoExit")
            for server in self.server_manager.servers:
                try:
                    await self.rcon_manager.execute_for_server(server, "DoExit")
                    logger.info_system(f"Successfully sent to {server.name} ({server.rcon_ip}:{server.rcon_port})")
                except (RCONConnectionError, RCONCommandError) as e:
                    error_msg = f"Failed to send DoExit to {server.name}: {e.reason}"
                    logger.warning_system(error_msg)
                    await self.discord_manager.send_temp_message(message.channel, f"⚠️ {error_msg}")
            
            # Step 3: Wait for all servers to shutdown
            logger.info_system("Waiting for all servers to shutdown...")
            all_shutdown = True
            for server in self.server_manager.servers:
                if not await self.server_manager.wait_for_server_shutdown(server, 300):
                    error_msg = f"Timeout waiting for {server.name} to shut down"
                    logger.warning_system(error_msg)
                    await self.discord_manager.send_temp_message(message.channel, f"⚠️ {error_msg}")
                    all_shutdown = False
            
            if all_shutdown:
                logger.info_system("All servers have shut down successfully")
                await self.discord_manager.send_temp_message(message.channel, "🦖 All servers have shut down successfully.")
            else:
                logger.warning_system("Some servers may not have shut down properly")
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Some servers may not have shut down properly. Please check logs.")
            return
        map_name = parts[1]
        try:
            server = self.server_manager.find_server(map_name)
        except ServerNotFoundError:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with name '{map_name}'.")
            return
        display_name = self.server_manager.get_display_name(server)
        await self.discord_manager.send_temp_message(message.channel, f"⏹️ Shutting down {display_name}...")
        
        # Step 1: Stop RaptorChat gracefully before server shutdown
        if hasattr(self, 'raptorchat_manager') and self.raptorchat_manager:
            logger.info_system("Stopping RaptorChat before server shutdown...")
            try:
                if self.raptorchat_manager.is_running():
                    self.raptorchat_manager.stop()
                    logger.info_system("RaptorChat stopped successfully")
                    await self.discord_manager.send_temp_message(message.channel, "💬 RaptorChat has been stopped.")
                else:
                    logger.debug_system("RaptorChat is not running, skipping stop")
            except Exception as e:
                error_msg = f"Error stopping RaptorChat: {e}"
                logger.error_system(error_msg)
                await self.discord_manager.send_temp_message(message.channel, f"⚠️ {error_msg}")
        
        # Step 2: Send DoExit to specific server
        logger.info_system("Sending RCON command: DoExit")
        try:
            await self.rcon_manager.execute_for_server(server, "DoExit")
            logger.info_system(f"Successfully sent to {server.name} ({server.rcon_ip}:{server.rcon_port})")
        except (RCONConnectionError, RCONCommandError) as e:
            error_msg = f"Failed to send shutdown command to {display_name}: {e.reason}"
            logger.error_system(error_msg)
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ {error_msg}")
            return
        
        # Step 3: Wait for server to shutdown
        logger.info_system(f"Waiting for {server.name} to shutdown...")
        if await self.server_manager.wait_for_server_shutdown(server, 300):
            logger.info_system(f"{server.name} has shut down successfully")
            await self.discord_manager.send_temp_message(
                message.channel, 
                f"🦖 {display_name} server has shut down successfully."
            )
        else:
            error_msg = f"Timeout waiting for {display_name} to shut down"
            logger.warning_system(error_msg)
            await self.discord_manager.send_temp_message(
                message.channel,
                f"⚠️ {error_msg}. The server may still be shutting down or may need manual intervention."
            )

    async def cmd_servers(self, message, content: str, content_lower: str):
        """Handle .servers command - show server details"""
        logger.info_command(".servers received")
        logger.debug_system("Gathering server details data...")
        
        now = datetime.datetime.now()
        lines = ["📊 Server Details:", ""]
        
        # Find all ARK server processes
        logger.debug_system("Scanning for ARK server processes...")
        ark_procs = []
        try:
            for proc in psutil.process_iter(attrs=['name', 'create_time', 'cmdline', 'memory_info']):
                if proc.info['name'] == "ArkAscendedServer.exe":
                    ark_procs.append(proc)
            logger.debug_system(f"Found {len(ark_procs)} ARK server processes")
        except psutil.NoSuchProcess:
            logger.debug_system("Process scan completed (some processes may have terminated during scan)")
            pass
        for server in self.server_manager.servers:
            logger.debug_system(f"Processing server: {server.name}")
            
            display_name = self.server_manager.get_display_name(server)
            lines.append(f"🗺️ Map Name      : {display_name}")
            
            # Match server to running process
            matched_proc = None
            identifiers = [server.map_name.lower() if server.map_name else "", server.name.lower(), str(server.rcon_port)]
            logger.debug_system(f"Looking for process with identifiers: {identifiers}")
            
            for proc in ark_procs:
                cmdline = " ".join(proc.info.get("cmdline", [])).lower()
                if any(ident and ident in cmdline for ident in identifiers):
                    matched_proc = proc
                    logger.debug_system(f"Matched server {server.name} to process PID {proc.pid}")
                    break
            
            if matched_proc:
                logger.debug_system(f"Gathering process data for {server.name}...")
                
                # Calculate process uptime
                uptime_seconds = (now - datetime.datetime.fromtimestamp(matched_proc.info["create_time"])).total_seconds()
                uptime_str = str(datetime.timedelta(seconds=int(uptime_seconds)))
                logger.debug_system(f"Process uptime: {uptime_str}")
                lines.append(f"🔌 Process Uptime  : {uptime_str}")
                
                # Get CPU usage (non-blocking)
                matched_proc.cpu_percent(interval=None) # Start measurement
                await asyncio.sleep(0.5) # Wait half a second
                cpu_usage = matched_proc.cpu_percent(interval=None) # End measurement
                logger.debug_system(f"Process CPU: {cpu_usage:.1f}%")
                lines.append(f"💻 Process CPU     : {cpu_usage:.1f}%")
                
                # Get RAM usage
                ram_usage_gb = matched_proc.info['memory_info'].rss / (1024 * 1024 * 1024)
                logger.debug_system(f"Process RAM: {ram_usage_gb:.2f} GB")
                lines.append(f"⚡ Process RAM     : {ram_usage_gb:.2f} GB")
                
                # Get disk usage for server save directory
                try:
                    if server.server_save_path and os.path.exists(server.server_save_path):
                        # Calculate actual directory size
                        total_size = 0
                        for dirpath, dirnames, filenames in os.walk(server.server_save_path):
                            for filename in filenames:
                                filepath = os.path.join(dirpath, filename)
                                try:
                                    total_size += os.path.getsize(filepath)
                                except (OSError, FileNotFoundError):
                                    # Skip files that can't be accessed
                                    continue
                        
                        # Get total disk space for the drive
                        drive_path = os.path.splitdrive(server.server_save_path)[0] + "\\"
                        if os.path.exists(drive_path):
                            disk_info = psutil.disk_usage(drive_path)
                            disk_total_gb = disk_info.total / (1024 * 1024 * 1024)
                            disk_used_gb = total_size / (1024 * 1024 * 1024)
                            disk_percent = (disk_used_gb / disk_total_gb) * 100
                            logger.debug_system(f"Server {server.name} save directory size: {disk_used_gb:.2f} GB")
                            lines.append(f"💾 Save Size       : {disk_used_gb:.2f} GB")
                        else:
                            # Just show directory size without drive percentage
                            disk_used_gb = total_size / (1024 * 1024 * 1024)
                            logger.debug_system(f"Server {server.name} save directory size: {disk_used_gb:.2f} GB")
                            lines.append(f"💾 Save Size       : {disk_used_gb:.2f} GB")
                    else:
                        logger.debug_system(f"Server {server.name} server_save_path not accessible: {server.server_save_path}")
                        lines.append(f"💾 Save Size       : N/A (save dir not accessible)")
                except Exception as e:
                    logger.debug_system(f"Error getting directory size for {server.name}: {e}")
                    lines.append(f"💾 Save Size       : Error")
            else:
                logger.debug_system(f"Server {server.name} is OFFLINE")
                lines.append("🔴 Status          : OFFLINE")
                
                # Still show disk usage even when server is offline
                try:
                    if server.server_save_path and os.path.exists(server.server_save_path):
                        # Calculate actual directory size
                        total_size = 0
                        for dirpath, dirnames, filenames in os.walk(server.server_save_path):
                            for filename in filenames:
                                filepath = os.path.join(dirpath, filename)
                                try:
                                    total_size += os.path.getsize(filepath)
                                except (OSError, FileNotFoundError):
                                    # Skip files that can't be accessed
                                    continue
                        
                        # Get total disk space for the drive
                        drive_path = os.path.splitdrive(server.server_save_path)[0] + "\\"
                        if os.path.exists(drive_path):
                            disk_info = psutil.disk_usage(drive_path)
                            disk_total_gb = disk_info.total / (1024 * 1024 * 1024)
                            disk_used_gb = total_size / (1024 * 1024 * 1024)
                            disk_percent = (disk_used_gb / disk_total_gb) * 100
                            logger.debug_system(f"Server {server.name} save directory size (offline): {disk_used_gb:.2f} GB")
                            lines.append(f"💾 Save Size       : {disk_used_gb:.2f} GB")
                        else:
                            # Just show directory size without drive percentage
                            disk_used_gb = total_size / (1024 * 1024 * 1024)
                            logger.debug_system(f"Server {server.name} save directory size (offline): {disk_used_gb:.2f} GB")
                            lines.append(f"💾 Save Size       : {disk_used_gb:.2f} GB")
                    else:
                        logger.debug_system(f"Server {server.name} server_save_path not accessible (offline): {server.server_save_path}")
                        lines.append(f"💾 Save Size       : N/A (save dir not accessible)")
                except Exception as e:
                    logger.debug_system(f"Error getting directory size for offline server {server.name}: {e}")
                    lines.append(f"💾 Save Size       : Error")
            lines.append("")
        await self.discord_manager.send_temp_message(message.channel, "\n".join(lines))

    async def cmd_send(self, message, content: str, content_lower: str):
        """Handle .send command - send messages to servers"""
        logger.info_command(".send received")
        # .send all <message> or .send <map> <message>
        if content_lower.startswith(".send all "):
            msg = content[10:].strip()
            for srv in self.server_manager.servers:
                try:
                    await self.rcon_manager.execute_for_server(srv, f"ServerChat {msg}")
                except (RCONConnectionError, RCONCommandError) as e:
                    logger.warning_system(f"Failed to send message to {srv.name}: {e.reason}")
            await self.discord_manager.send_temp_message(message.channel, f"Sent RCON message to all servers: {msg}")
            return
        parts = content.split(maxsplit=2)
        if len(parts) < 3:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: .send <map> <message>")
            return
        map_name = parts[1]
        msg = parts[2].strip()
        try:
            server = self.server_manager.find_server(map_name)
        except ServerNotFoundError:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ No server found with map name '{map_name}'.")
            return
        try:
            await self.rcon_manager.execute_for_server(server, f"ServerChat {msg}")
            await self.discord_manager.send_temp_message(message.channel, f"Sent RCON message to map '{map_name}': {msg}")
        except (RCONConnectionError, RCONCommandError) as e:
            await self.discord_manager.send_temp_message(message.channel, f"⚠️ Failed to send message to {self.server_manager.get_display_name(server)}: {e.reason}")

    async def _restart_all_servers(self, message):
        """Restart all servers with staggered startup"""
        # Clear player data and reset log positions when restarting servers
        if hasattr(self, 'player_manager'):
            try:
                logger.info_system("Clearing player data and resetting log positions...")
                await self.player_manager.clear_server_players()
                await self.player_manager.reset_file_positions()
                logger.debug_system("Player data cleared successfully for all servers")
            except Exception as e:
                logger.warning_system(f"Failed to clear player data: {e}")
        
        # Start servers with staggered startup
        for srv in self.server_manager.servers:
            await self._restart_one_server(srv, message)
            await asyncio.sleep(30)  # Staggered startup
            
        # RaptorChat will be restarted after the 5-minute delay in cmd_reboot
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
            # Check if server actually started despite the error
            import asyncio
            logger.warning_system(f"Server start error for {server.name}: {e.reason}, checking actual status...")
            await asyncio.sleep(5)  # Wait a moment for server to potentially start
            
            if self.server_manager.is_specific_server_running(server):
                logger.info_system(f"{server.name} is actually running despite start error")
                await self.discord_manager.send_temp_message(message.channel, f"🦖 {self.server_manager.get_display_name(server)} is now starting...")
            else:
                # Server is truly not running, send failure message
                logger.error_system(f"Failed to start {server.name}: {e.reason}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to start {server.name}: {e.reason}")
        except Exception as e:
            logger.error_system(f"Unexpected error restarting server {server.name}: {e}")
            await self.discord_manager.send_temp_message(message.channel, f"❌ Unexpected error starting {server.name}: {e}")

    async def _broadcast_all(self, msg: str):
        """Broadcast a message to all servers"""
        logger.info_system(f"Sending broadcast to all servers: {msg}")
        shutdown_tasks = []
        for server in self.server_manager.servers:
            task = self.rcon_manager.execute_for_server(server, f"ServerChat {msg}")
            shutdown_tasks.append((server, task))
        
        for server, task in shutdown_tasks:
            try:
                result = await task
                logger.info_system(f"Successfully sent broadcast to {server.name} ({server.rcon_ip}:{server.rcon_port})")
            except (RCONConnectionError, RCONCommandError) as e:
                logger.warning_system(f"Failed to send broadcast to {server.name} ({server.rcon_ip}:{server.rcon_port}): {e.reason}")
