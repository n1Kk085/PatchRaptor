import asyncio
import json
import os
import subprocess
import time
from typing import Optional
from .log_manager import logger

class RaptorChatManager:
    """Manages RaptorChat relay process with auto-reconnect and auto-start capabilities"""
    def __init__(self, raptorchat_dir: str = "", raptorchat_path: str = ""):
        logger.debug_system(f"RaptorChatManager initialization started with dir: '{raptorchat_dir}', path: '{raptorchat_path}'")
        self.raptorchat_dir = raptorchat_dir
        self.raptorchat_path = raptorchat_path
        self.process: subprocess.Popen | None = None
        self.process_start_time: float = 0  # Track process start time manually
        
        # Process tracking
        self.monitor_task: asyncio.Task | None = None
        
        logger.debug_system("RaptorChatManager initialization completed")

    def is_running(self) -> bool:
        logger.debug_system("Checking if RaptorChat process is running")
        running = self.process is not None and self.process.poll() is None
        logger.debug_system(f"RaptorChat running status: {running}")
        return running

    def start(self, is_delayed_start: bool = False) -> bool:
        if is_delayed_start:
            logger.debug_system("RaptorChat delayed start - beginning actual startup")
        else:
            logger.debug_system("RaptorChat immediate start method called")
            
        if self.is_running():
            logger.debug_system("RaptorChat is already running, cannot start")
            return False
        if not self.raptorchat_path:
            logger.debug_system("RaptorChat path not configured")
            logger.error_system("RaptorChat path not configured")
            return False
        try:
            logger.debug_system(f"Starting RaptorChat with path: '{self.raptorchat_path}', dir: '{self.raptorchat_dir}'")
            if self.raptorchat_path.endswith('.py'):
                logger.debug_system("Starting RaptorChat as Python script")
                self.process = subprocess.Popen(["python", self.raptorchat_path], cwd=self.raptorchat_dir or None)
            else:
                logger.debug_system("Starting RaptorChat as executable")
                self.process = subprocess.Popen([self.raptorchat_path], cwd=self.raptorchat_dir or None)
            
            # Track process start time
            self.process_start_time = time.time()
            
            # Track process start time
            self.process_start_time = time.time()
            logger.debug_system("RaptorChat process started successfully")
            logger.info_system("RaptorChat started")
            return True
        except Exception as e:
            logger.debug_system(f"Failed to start RaptorChat: {e}")
            logger.error_system(f"Failed to start RaptorChat: {e}")
            return False

    def stop(self) -> bool:
        logger.debug_system("RaptorChat stop method called")
        if not self.is_running():
            logger.debug_system("RaptorChat is not running, cannot stop")
            return False
        try:
            logger.debug_system("Terminating RaptorChat process")
            self.process.terminate()
            self.process = None
            # Process stopped
            logger.debug_system("RaptorChat process terminated successfully")
            logger.info_system("RaptorChat stopped")
            return True
        except Exception as e:
            logger.debug_system(f"Failed to stop RaptorChat: {e}")
            logger.error_system(f"Failed to stop RaptorChat: {e}")
            return False

    def reboot(self) -> bool:
        logger.debug_system("RaptorChat reboot method called")
        if self.is_running():
            logger.debug_system("RaptorChat is running, stopping before reboot")
            self.stop()
        else:
            logger.debug_system("RaptorChat is not running, proceeding with start")
        logger.debug_system("Starting RaptorChat after reboot sequence")
        result = self.start()
        logger.debug_system(f"RaptorChat reboot completed with result: {result}")
        return result
    
    async def async_reboot(self) -> bool:
        """Async version of reboot method to prevent blocking in async contexts"""
        logger.debug_system("RaptorChat async_reboot method called")
        # Run the synchronous reboot in a thread executor to avoid blocking
        import concurrent.futures
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, self.reboot)
            logger.debug_system(f"RaptorChat async_reboot completed with result: {result}")
            return result
        except Exception as e:
            logger.error_system(f"Error in async_reboot: {e}")
            return False
            
    async def start_auto_monitor(self):
        """Start the monitoring task (without auto-restart)"""
        if hasattr(self, 'monitor_task') and self.monitor_task and not self.monitor_task.done():
            logger.debug_system("Monitor is already running")
            return
            
        logger.debug_system("Starting RaptorChat monitor")
        self.monitor_task = asyncio.create_task(self._monitor_raptorchat())
    
    async def stop_auto_monitor(self):
        """Stop the monitoring task"""
        if hasattr(self, 'monitor_task') and self.monitor_task and not self.monitor_task.done():
            logger.debug_system("Stopping RaptorChat monitor")
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                logger.debug_system("RaptorChat monitor cancelled successfully")
            self.monitor_task = None
        
        # Clean up server monitor task if it exists
        if hasattr(self, 'server_monitor_task') and self.server_monitor_task:
            logger.debug_system("Stopping server monitor task")
            if not self.server_monitor_task.done():
                self.server_monitor_task.cancel()
                try:
                    await self.server_monitor_task
                except asyncio.CancelledError:
                    logger.debug_system("Server monitor task cancelled successfully")
            self.server_monitor_task = None
            logger.debug_system("Server monitor stopped")

    async def _monitor_raptorchat(self):
        """Monitor RaptorChat process (without auto-reconnect)"""
        logger.debug_system("RaptorChat monitor task started")
        
        try:
            while True:
                # Just monitor without auto-restarting
                if self.process is None or self.process.poll() is not None:
                    logger.debug_system("RaptorChat process is not running")
                await asyncio.sleep(5)
                
        except asyncio.CancelledError:
            logger.debug_system("RaptorChat monitor task cancelled")
        except Exception as e:
            logger.error_system(f"Error in RaptorChat monitor: {e}")
        finally:
            if self.process is not None and self.process.poll() is not None:
                return_code = self.process.returncode
                logger.warning_system(f"RaptorChat process terminated with code {return_code}")
                self.process = None
                
        logger.debug_system("RaptorChat monitor task ended")
        
    async def _check_server_connections(self) -> bool:
        """Check if RaptorChat is actually connected to all configured servers"""
        try:
            if not self.is_running():
                logger.debug_system("RaptorChat process is not running")
                return False
                
            # Get list of configured servers from RaptorChat's config
            config_path = os.path.join(self.raptorchat_dir, 'config.json')
            if not os.path.exists(config_path):
                logger.warning_system("RaptorChat config not found, cannot verify server connections")
                return False
                
            with open(config_path, 'r') as f:
                config = json.load(f)
                
            # Get list of expected servers from config
            expected_servers = set(server['name'] for server in config.get('servers', []))
            
            if not expected_servers:
                logger.warning_system("No servers configured in RaptorChat config")
                return True  # If no servers configured, consider it a success
                
            # Check if process is running
            if not self.process or self.process.poll() is not None:
                logger.debug_system("RaptorChat process is not running")
                return False
                
            # Get process uptime using our tracked start time
            process_uptime = time.time() - self.process_start_time
            
            # If the process is very new, give it time to establish connections
            if process_uptime < 30:  # 30 seconds grace period
                logger.debug_system(f"RaptorChat process is new ({int(process_uptime)}s old), giving it time to connect")
                return True
                
            # For a more thorough check, we could look at the log file
            # But for now, we'll assume that if the process is running and not brand new,
            # it's probably connected to the servers
            logger.debug_system(f"RaptorChat process is running (uptime: {int(process_uptime)}s), assuming connections are good")
            return True
            
        except Exception as e:
            logger.error_system(f"Error checking server connections: {e}")
            # On error, assume the connection is okay to avoid unnecessary restarts
            return True

    async def _monitor_server_connection(self):
        """
        Monitor server connections (without auto-restart).
        This is kept for backward compatibility but doesn't perform any actions.
        """
        logger.debug_system("Server connection monitor started (monitoring only, no auto-restart)")
        
        try:
            while True:  # Run until cancelled
                await asyncio.sleep(30)  # Just sleep until cancelled
                
        except asyncio.CancelledError:
            logger.debug_system("Server monitor task cancelled")
        except Exception as e:
            logger.error_system(f"Error in server monitor: {e}")
        finally:
            logger.debug_system("Server monitor stopped")
    def set_server_monitor_interval(self, interval_seconds: int):
        """Set the interval between server connection checks"""
        self.server_monitor_interval = max(5, interval_seconds)  # Minimum 5 seconds
        logger.debug_system(f"Server monitor interval set to {self.server_monitor_interval} seconds")
        
    def set_max_monitor_duration(self, duration_seconds: int):
        """Set the maximum duration to monitor for server reconnection"""
        self.max_monitor_duration = max(0, duration_seconds)
        logger.debug_system(f"Server monitor will run for {self.max_monitor_duration} seconds")

    async def start_delayed(self, delay_seconds: int = 5):
        """Start RaptorChat after a specified delay (for backward compatibility)"""
        logger.debug_system(f"Scheduling RaptorChat to start in {delay_seconds} seconds")
        
        async def _delayed_start():
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)
            if not self.is_running():
                if self.start():
                    logger.info_system("RaptorChat started successfully after delay")
                else:
                    logger.error_system("RaptorChat failed to start after delay")
            else:
                logger.debug_system("RaptorChat is already running, skipping start")
        
        asyncio.create_task(_delayed_start())

    async def restart_chat_threads(self):
        """Restart chat monitoring threads by rebooting RaptorChat process"""
        logger.info_system("Restarting RaptorChat chat threads after server restart")
        
        # Stop the current process if running
        if self.is_running():
            logger.debug_system("Stopping current RaptorChat process for thread restart")
            self.stop()
        
        # Start the process again
        logger.debug_system("Starting RaptorChat process to restart chat threads")
        if self.start():
            logger.info_system("RaptorChat chat threads restarted successfully")
            return True
        else:
            logger.error_system("Failed to restart RaptorChat chat threads")
            return False
