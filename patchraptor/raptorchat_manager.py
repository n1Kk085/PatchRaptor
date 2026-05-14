import asyncio
import json
import os
import sys
import subprocess
import time
import psutil
from typing import Optional
from contextlib import asynccontextmanager
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
        self.delayed_start_task: asyncio.Task | None = None
        self.server_monitor_task: asyncio.Task | None = None
        self.maintenance_count: int = 0  # Reference-counted maintenance semaphore
        self.intentionally_stopped: bool = False  # Tracks intentional .chat stop vs crash
        
        logger.debug_system("RaptorChatManager initialization completed")

    def start_maintenance(self):
        """Increment maintenance counter to block auto-restart monitor"""
        self.maintenance_count += 1
        logger.debug_system(f"RaptorChat maintenance count incremented: {self.maintenance_count}")

    def end_maintenance(self):
        """Decrement maintenance counter, releasing monitor if it hits 0"""
        self.maintenance_count = max(0, self.maintenance_count - 1)
        logger.debug_system(f"RaptorChat maintenance count decremented: {self.maintenance_count}")

    def reset_maintenance(self):
        """Forcefully reset maintenance counter to 0"""
        self.maintenance_count = 0
        logger.warning_system("RaptorChat maintenance count reset to 0")

    def stop_maintenance(self):
        """Alias for end_maintenance"""
        self.end_maintenance()

    @asynccontextmanager
    async def maintenance_scope(self, handoff=False):
        """
        Context manager for safe maintenance handling.
        If handoff=True, the maintenance count is NOT decremented on exit,
        assuming a background task (like delayed start) will handle it.
        """
        self.start_maintenance()
        try:
            yield
        except Exception:
            # Always decrement on error to avoid stuck state
            self.end_maintenance()
            raise
        finally:
            if not handoff:
                self.end_maintenance()

    async def start_with_delay(self, delay_seconds: int) -> asyncio.Task:
        """Alias for start_delayed with task return matching SystemUtils expectations"""
        logger.debug_system(f"RaptorChat starting with delay: {delay_seconds}s")
        return await self.start_delayed(delay_seconds)

    def is_running(self) -> bool:
        logger.debug_system("Checking if RaptorChat process is running")
        
        # 1. Check direct handle if we have one
        if self.process is not None and self.process.poll() is None:
            logger.debug_system("RaptorChat direct handle is active")
            return True
            
        # 2. Fallback: Search for process by name (handles reconnects/external starts)
        try:
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] == "RaptorChat.exe":
                    # We found it running externally, try to re-attach handle if possible
                    # (Note: subprocess.Popen handles can't be easily re-attached, 
                    # but we can at least report truth)
                    logger.debug_system("RaptorChat found running via process scan")
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
            
        logger.debug_system("RaptorChat is not detected")
        return False

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
        
        # Prepare environment for the child process
        env = os.environ.copy()

        try:
            logger.debug_system(f"Starting RaptorChat with path: '{self.raptorchat_path}', dir: '{self.raptorchat_dir}'")
            if getattr(sys, 'frozen', False):
                # Running as compiled exe
                logger.debug_system("Running in frozen mode, looking for RaptorChat.exe")
                # When frozen, we expect RaptorChat.exe to be in the same folder as the main exe (Instinct.exe)
                exe_path = os.path.join(os.path.dirname(sys.executable), "RaptorChat.exe")
                logger.debug_system(f"Launching RaptorChat executable: {exe_path}")
                self.process = subprocess.Popen([exe_path], cwd=self.raptorchat_dir or None, env=env)
            elif self.raptorchat_path.endswith('.py'):
                logger.debug_system("Starting RaptorChat as Python script")
                self.process = subprocess.Popen(["python", self.raptorchat_path], cwd=self.raptorchat_dir or None, env=env)
            else:
                logger.debug_system("Starting RaptorChat as executable")
                self.process = subprocess.Popen([self.raptorchat_path], cwd=self.raptorchat_dir or None, env=env)
            
            # Track process start time
            self.process_start_time = time.time()
            logger.debug_system("RaptorChat process started successfully")
            return True
        except Exception as e:
            logger.debug_system(f"Failed to start RaptorChat: {e}")
            logger.error_system(f"Failed to start RaptorChat: {e}")
            return False

    def stop(self) -> bool:
        logger.debug_system("RaptorChat stop method called")
        
        # Cancel any pending delayed start
        if self.delayed_start_task and not self.delayed_start_task.done():
            try:
                loop = self.delayed_start_task.get_loop()
                if not loop.is_closed():
                    logger.debug_system("Cancelling pending delayed start task")
                    self.delayed_start_task.cancel()
                else:
                    logger.debug_system("Event loop closed, skipping task cancellation")
            except Exception as e:
                logger.debug_system(f"Error checking loop status: {e}")
            finally:
                 self.delayed_start_task = None
            
        if not self.is_running():
            logger.debug_system("RaptorChat is not running, cannot stop")
            return False
        try:
            # Use psutil for graceful terminate + child-aware kill (consistent with GUI)
            import psutil
            
            if self.process:
                parent = psutil.Process(self.process.pid)
                
                # Graceful terminate first
                parent.terminate()
                try:
                    parent.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    # Force kill if unresponsive
                    parent.kill()
                    
                # Terminate children (handles spawned server connections, etc.)
                for child in parent.children(recursive=True):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
            
            self.process = None
            # Mark that RaptorChat was intentionally stopped (not a crash)
            if not hasattr(self, 'intentionally_stopped'):
                self.intentionally_stopped = False
                logger.info_system("RaptorChat stop method called - marking as intentional stop")
            else:
                self.intentionally_stopped = True
                logger.debug_system("RaptorChat stopped via .chat command")
            
            # Process stopped
            logger.debug_system("RaptorChat process terminated successfully")
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
            time.sleep(1) # Give OS a moment to release file locks
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
            
    async def start_auto_monitor(self, initial_delay: int = 0):
        """Start the monitoring task (without auto-restart)"""
        if hasattr(self, 'monitor_task') and self.monitor_task and not self.monitor_task.done():
            logger.debug_system("Monitor is already running")
            return
            
        if initial_delay > 0:
            logger.debug_system(f"Waiting {initial_delay}s before starting RaptorChat monitor")
            await asyncio.sleep(initial_delay)

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
                try:
                    # Check if process is down and not in maintenance
                    is_crashed = self.process is None or self.process.poll() is not None
                    
                    if is_crashed and self.maintenance_count == 0:
                        # Only auto-restart if this wasn't an intentional stop by the user
                        if not self.intentionally_stopped:
                            logger.warning_system("RaptorChat process is down, attempting auto-restart...")
                            if self.start():
                                logger.info_system("RaptorChat auto-restart successful")
                                # Reset intentionally_stopped flag on successful restart
                                self.intentionally_stopped = False
                            else:
                                logger.error_system("RaptorChat auto-restart failed, will retry...")
                        else:
                            logger.debug_system(f"Skipping auto-restart - RaptorChat was intentionally stopped")
                    
                    await asyncio.sleep(10) # 10s Echo cycle
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.error_system(f"Error in RaptorChat monitor: {e}")
                    await asyncio.sleep(10)
                
        except asyncio.CancelledError:
            logger.debug_system("RaptorChat monitor task cancelled")
        finally:
            try:
                if self.process is not None and self.process.poll() is not None:
                    return_code = self.process.returncode
                    logger.warning_system(f"RaptorChat process terminated with code {return_code}")
            except Exception as e:
                logger.error_system(f"Error checking process status during cleanup: {e}")
            finally:
                self.process = None
                
                # Reset intentionally_stopped flag on monitor stop
                if hasattr(self, 'intentionally_stopped'):
                    self.intentionally_stopped = False
                
            logger.debug_system("RaptorChat monitor task ended")
        


    async def start_delayed(self, delay_seconds: int = 5):
        """Start RaptorChat after a specified delay (for backward compatibility)"""
        logger.debug_system(f"Scheduling RaptorChat to start in {delay_seconds} seconds")
        
        async def _delayed_start():
            try:
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)
                if not self.is_running():
                    if self.start():
                        logger.debug_system("RaptorChat started successfully after delay")
                    else:
                        logger.error_system("RaptorChat failed to start after delay")
                else:
                    logger.debug_system("RaptorChat is already running, skipping start")
            finally:
                # Release maintenance count after delayed start attempt or cancellation
                self.end_maintenance()
                self.delayed_start_task = None
        
        self.delayed_start_task = asyncio.create_task(_delayed_start())
        return self.delayed_start_task
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
