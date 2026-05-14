import os
import sys
import subprocess
import asyncio
from .log_manager import logger
from .discord_manager import DiscordManager
from .config import ConfigManager
from .exceptions import (
    ProcessError,
    ProcessOperationError,
    ConfigurationError,
    ConfigSaveError,
    ConfigLoadError
)
from .base_handler import BaseHandler
from .service_locator import ServiceLocator



class ConfigurationHandler(BaseHandler):
    """Handles system configuration commands: webpanel, chat, discord"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Web panel process management
        self.webpanel_process = None
        self.tunnel_process = None
        self.tunnel_monitor_task = None

    async def cmd_discord(self, message, content: str, content_lower: str):
        """Handle .discord command - manage Discord settings"""
        logger.info_command(".discord received")
        args = content.split()
        if len(args) < 2:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Usage: .discord delete [H:MM]"
            )
            return
        
        subcmd = args[1].lower()
        
        if subcmd == "delete":
            if len(args) < 3:
                # Display current setting
                hours = self.discord_manager.delete_seconds // 3600
                minutes = (self.discord_manager.delete_seconds % 3600) // 60
                current_time_str = f"{hours}:{minutes:02d}"
                await self.discord_manager.send_temp_message(
                    message.channel, 
                    f"ℹ️ Current message deletion time: {current_time_str} (H:MM). Usage: .discord delete [H:MM]"
                )
                return
            
            time_str = args[2]
            try:
                if ":" in time_str:
                    parts = time_str.split(":")
                    if len(parts) != 2:
                        raise ValueError("Invalid format")
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    if hours < 0 or minutes < 0 or minutes >= 60:
                        raise ValueError("Invalid time values")
                    total_seconds = (hours * 3600) + (minutes * 60)
                else:
                    # Backwards compatibility - treat as hours
                    hours = float(time_str)
                    if hours < 0:
                        raise ValueError("Negative time")
                    total_seconds = int(hours * 3600)
                
                if total_seconds <= 0:
                    await self.discord_manager.send_temp_message(
                        message.channel, "⚠️ Time must be greater than 0."
                    )
                    return
                
                self.discord_manager.delete_seconds = total_seconds
                
                # Update config
                try:
                    backup_config = self.config_manager.get("backup_config", {})
                    backup_config["message_delete_seconds"] = total_seconds
                    self.config_manager.config["backup_config"] = backup_config
                    self.config_manager.save()
                except ConfigSaveError as e:
                    await self.discord_manager.send_temp_message(
                        message.channel, f"❌ Failed to save config: {e.reason}"
                    )
                    return
                
                # Display confirmation
                display_hours = total_seconds // 3600
                display_minutes = (total_seconds % 3600) // 60
                display_time = f"{display_hours}:{display_minutes:02d}"
                await self.discord_manager.send_temp_message(
                    message.channel, f"🦖 Message deletion time updated to {display_time} (H:MM)."
                )
                
            except ValueError:
                await self.discord_manager.send_temp_message(
                    message.channel, 
                    "⚠️ Invalid time format. Use H:MM (e.g., 0:05 for 5 minutes, 24:00 for 24 hours)"
                )
        else:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Unknown .discord subcommand. Use: delete"
            )

    async def cmd_webpanel(self, message, content, content_lower):
        """Handle .webpanel command - control web panel"""
        logger.info_command(".webpanel received")
        parts = content.strip().split()

        if len(parts) == 1:
            is_running = self.webpanel_process and self.webpanel_process.poll() is None
            if is_running:
                await self.discord_manager.send_temp_message(message.channel, "☑️ Web Panel is Online")
            else:
                await self.discord_manager.send_temp_message(message.channel, "🛑 Web Panel is Offline")
            return

        toggle = parts[1].lower()
        if toggle == "on":
            if self.webpanel_process and self.webpanel_process.poll() is None:
                await self.discord_manager.send_temp_message(message.channel, "☑️ Web panel is already running")
                return
            
            try:
                # Start tunnel if script exists
                if getattr(sys, 'frozen', False):
                     # Running as compiled exe
                    root_dir = os.path.dirname(sys.executable)
                else:
                    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    
                tunnel_script = os.path.join(root_dir, "start_tunnel.bat")
                cloudflared_exe = os.path.join(root_dir, "cloudflared.exe")
                
                # Check for cloudflared.exe, script, and config before launching
                config_yml = os.path.join(root_dir, "config.yml")
                if os.path.exists(tunnel_script) and os.path.exists(cloudflared_exe) and os.path.exists(config_yml):
                    try:
                        self.tunnel_process = subprocess.Popen(
                            [tunnel_script],
                            cwd=root_dir,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                            shell=False
                        )
                        # Give it a moment to initialize
                        await asyncio.sleep(2)
                        
                        if self.tunnel_process.poll() is None:
                            await self.discord_manager.send_temp_message(message.channel, "🚇 Tunnel started")
                        else:
                            # It crashed immediately despite existing
                            logger.error_system("Tunnel process exited immediately.")
                            self.tunnel_process = None
                            await self.discord_manager.send_temp_message(message.channel, "⚠️ Tunnel failed to start. Launching local WebPanel.")
                            
                    except Exception as e:
                        logger.error_system(f"Failed to start tunnel: {e}")
                        await self.discord_manager.send_temp_message(message.channel, "⚠️ Tunnel start error. Launching local WebPanel.")
                else:
                    # Cloudflared, script, or config missing
                    missing = []
                    if not os.path.exists(tunnel_script): missing.append("start_tunnel.bat")
                    if not os.path.exists(cloudflared_exe): missing.append("cloudflared.exe")
                    if not os.path.exists(config_yml): missing.append("config.yml")
                    
                    reason = f"Missing: {', '.join(missing)}"
                    await self.discord_manager.send_temp_message(message.channel, f"⚠️ Tunnel not configured ({reason}). Launching local WebPanel.")

                # Start Web Panel
                cwd = root_dir
                if getattr(sys, 'frozen', False):
                     # Running as compiled exe
                    exe_path = os.path.join(os.path.dirname(sys.executable), "WebPanel.exe")
                    logger.debug_system(f"Launching WebPanel executable: {exe_path}")
                    self.webpanel_process = subprocess.Popen(
                        [exe_path],
                        cwd=cwd,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                else:
                    # Running as script
                    self.webpanel_process = subprocess.Popen(
                        [sys.executable, "pr_live.py"],
                        cwd=cwd,
                        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                    )
                await self.discord_manager.send_temp_message(message.channel, "🌐 Web Panel is now ON")
            except ProcessOperationError as e:
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to start web panel: {e.reason}")
            except Exception as e:
                logger.error_system(f"WebPanel error: {e}")
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to start web panel: {e}")
                
        elif toggle == "off":
            if not self.webpanel_process or self.webpanel_process.poll() is not None:
                await self.discord_manager.send_temp_message(message.channel, "Web panel already stopped 🛑")
                return
            
            try:
                # Use psutil for consistent child-aware process termination
                import psutil
                
                # Stop tunnel (cloudflared.exe and its children) if running
                if self.tunnel_process:
                    try:
                        parent = psutil.Process(self.tunnel_process.pid)
                        
                        # Terminate children first
                        for child in parent.children(recursive=True):
                            try:
                                child.terminate()
                            except psutil.NoSuchProcess:
                                pass
                        
                        gone, alive = psutil.wait_procs(parent.children(), timeout=1)
                        for p in alive:
                            p.kill()
                        
                        parent.terminate()
                        try:
                            parent.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            parent.kill()
                        
                        self.tunnel_process = None
                        await self.discord_manager.send_temp_message(message.channel, "🛑 Tunnel stopped")
                    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                        pass  # Already gone or access denied
                    except Exception as e:
                        logger.error(f"Error stopping tunnel: {e}")

                # Stop WebPanel process and its children
                if self.webpanel_process:
                    try:
                        parent = psutil.Process(self.webpanel_process.pid)

                        # Terminate children first
                        for child in parent.children(recursive=True):
                            try:
                                child.terminate()
                            except psutil.NoSuchProcess:
                                pass

                        gone, alive = psutil.wait_procs(parent.children(), timeout=1)
                        for p in alive:
                            p.kill()

                        parent.terminate()
                        try:
                            parent.wait(timeout=1)
                        except subprocess.TimeoutExpired:
                            parent.kill()

                    except psutil.NoSuchProcess:
                        pass  # Already terminated

                    self.webpanel_process = None
                
                await self.discord_manager.send_temp_message(message.channel, "🛑 Web Panel stopped")
                    
            except ProcessOperationError as e:
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to stop web panel: {e.reason}")
            except Exception as e:
                logger.error_system(f"Error stopping web panel: {e}")
        else:
            await self.discord_manager.send_temp_message(message.channel, "Usage: `.webpanel on` or `.webpanel off`")

    async def cmd_chat(self, message, content: str, content_lower: str):
        """Handle .chat command - control RaptorChat"""
        logger.info_command(".chat received")
        parts = content.split()
        if len(parts) < 2:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Usage: `.chat status|stop|reboot`"
            )
            return
        
        subcommand = parts[1].lower()
        
        if subcommand == "status":
            if self.raptorchat_manager.is_running():
                await self.discord_manager.send_temp_message(
                    message.channel, "☑️ RaptorChat is Online"
                )
            else:
                await self.discord_manager.send_temp_message(
                    message.channel, "🛑 RaptorChat is Offline"
                )
        
        elif subcommand == "stop":
            if not self.raptorchat_manager.is_running():
                await self.discord_manager.send_temp_message(
                    message.channel, "⚠️ RaptorChat is not running."
                )
            else:
                success = self.raptorchat_manager.stop()
                if success:
                    await self.discord_manager.send_temp_message(
                        message.channel, "🛑 RaptorChat stopped"
                    )
                else:
                    await self.discord_manager.send_temp_message(
                        message.channel, "❌ Failed to stop RaptorChat."
                    )
        
        elif subcommand == "reboot":
            await self.discord_manager.send_temp_message(
                message.channel, "🔄 Restarting RaptorChat..."
            )
            success = self.raptorchat_manager.reboot()
            if success:
                await self.discord_manager.send_temp_message(
                    message.channel, "🦖 RaptorChat restarted"
                )
            else:
                await self.discord_manager.send_temp_message(
                    message.channel, "❌ Failed to restart RaptorChat."
                )
        
        else:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Unknown subcommand. Use: `status`, `stop`, or `reboot`."
            )

    def _process_tunnel_line(self, line: str):
        """Processes and translates Cloudflare tunnel output to friendly logs."""
        if not line:
            return

        line = line.strip()
        
        # Friendly translations for common Cloudflare messages
        if "stream canceled by remote" in line.lower():
            logger.info_web("Tunnel stream adjusted by remote endpoint.")
            return

        # Standard Cloudflare log format: [TIMESTAMP] [LEVEL] [MESSAGE]
        # Example: 2024-04-17T03:19:33Z INF Testing
        parts = line.split()
        if len(parts) >= 3:
            level = parts[1]
            message = " ".join(parts[2:])
            
            if level == "INF":
                logger.info_web(f"Tunnel: {message}")
            elif level == "ERR":
                logger.error_web(f"Tunnel Error: {message}")
            elif level == "WRN":
                logger.warning_web(f"Tunnel Warning: {message}")
        else:
            logger.debug_web(f"Tunnel Data: {line}")

    async def cleanup(self):
        """Final cleanup using psutil for all process termination - ensures child awareness"""
        logger.info_system("ConfigurationHandler: Cleaning up external processes with psutil...")
        
        # 1. Stop WebPanel using psutil tree kill
        if self.webpanel_process:
            logger.debug_system("ConfigurationHandler: Terminating WebPanel process tree...")
            try:
                import psutil
                parent = psutil.Process(self.webpanel_process.pid)
                
                # Terminate children first (handles any spawned sub-processes)
                for child in parent.children(recursive=True):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                
                gone, alive = psutil.wait_procs(parent.children(), timeout=1)
                for p in alive:
                    p.kill()
                
                parent.terminate()
                try:
                    parent.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    parent.kill()
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # Already terminated or access denied
                pass
            except Exception as e:
                logger.error_system(f"Error during WebPanel cleanup: {e}")
            
            self.webpanel_process = None

        # 2. Stop Tunnel using psutil tree kill
        if self.tunnel_process:
            logger.debug_system("ConfigurationHandler: Terminating Tunnel process tree...")
            try:
                import psutil
                parent = psutil.Process(self.tunnel_process.pid)
                
                # Terminate children first (handles cloudflared and any sub-processes)
                for child in parent.children(recursive=True):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                
                gone, alive = psutil.wait_procs(parent.children(), timeout=1)
                for p in alive:
                    p.kill()
                
                parent.terminate()
                try:
                    parent.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    parent.kill()
            
            except psutil.NoSuchProcess:
                pass  # Already terminated
            except Exception as e:
                logger.error_system(f"Error during Tunnel cleanup: {e}")
            
            self.tunnel_process = None
