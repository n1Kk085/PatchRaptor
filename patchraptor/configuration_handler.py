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


class ConfigurationHandler:
    """Handles configuration commands: webhook, discord, webpanel, chat"""
    
    def __init__(
        self,
        discord_manager: DiscordManager,
        config_manager: ConfigManager,
        raptorchat_manager
    ):
        self.discord_manager = discord_manager
        self.config_manager = config_manager
        self.raptorchat_manager = raptorchat_manager

        # Web panel process management
        self.webpanel_process: subprocess.Popen | None = None
        self.tunnel_process: subprocess.Popen | None = None

    async def cmd_webhook(self, message, content: str, content_lower: str):
        """Handle .webhook command - manage webhook settings"""
        logger.info_command(".webhook received")
        parts = content.split()
        
        if len(parts) == 1:
            # Show current webhook URL
            url = self.config_manager.get("webhook", "")
            if url:
                await self.discord_manager.send_temp_message(message.channel, f"Webhook configured: {url}")
            else:
                await self.discord_manager.send_temp_message(message.channel, "No webhook configured. Use `.webhook <url>` to set.")
            return
        
        if len(parts) < 2:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.webhook get shutdown|reboot` or `.webhook set shutdown|reboot <message>`")
            return
        
        action = parts[1].lower()
        
        if action == "get":
            if len(parts) < 3:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.webhook get shutdown|reboot`")
                return
            
            msg_type = parts[2].lower()
            if msg_type not in ["shutdown", "reboot"]:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Message type must be 'shutdown' or 'reboot'")
                return
            
            # Check existing webhook_messages structure
            webhook_messages = self.config_manager.get("webhook_messages", {})
            current_msg = webhook_messages.get(msg_type, "")
            
            if current_msg:
                await self.discord_manager.send_temp_message(message.channel, f"📡 {msg_type.capitalize()} webhook message: `{current_msg}`")
            else:
                await self.discord_manager.send_temp_message(message.channel, f"⚠️ No {msg_type} webhook message configured")
        
        elif action == "set":
            if len(parts) < 4:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Usage: `.webhook set shutdown|reboot <message>`")
                return
            
            msg_type = parts[2].lower()
            if msg_type not in ["shutdown", "reboot"]:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Message type must be 'shutdown' or 'reboot'")
                return
            
            # Join remaining parts as the message
            webhook_message = " ".join(parts[3:])
            
            try:
                # Use existing webhook_messages structure
                if "webhook_messages" not in self.config_manager.config:
                    self.config_manager.config["webhook_messages"] = {}
                
                self.config_manager.config["webhook_messages"][msg_type] = webhook_message
                self.config_manager.save()
                await self.discord_manager.send_temp_message(message.channel, f"✅ {msg_type.capitalize()} webhook message updated.")
            except ConfigSaveError as e:
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to save webhook message: {e.reason}")
            except Exception as e:
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to update webhook message: {e}")
        
        else:
            # Treat as webhook URL setting (backward compatibility)
            url = " ".join(parts[1:]).strip()
            self.discord_manager.webhook_url = url
            try:
                self.config_manager.config["webhook"] = url
                self.config_manager.save()
                await self.discord_manager.send_temp_message(message.channel, "✅ Webhook URL updated.")
            except ConfigSaveError as e:
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to save webhook URL: {e.reason}")
            except Exception as e:
                await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to update webhook URL: {e}")

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
            status = "running ✅" if self.webpanel_process and self.webpanel_process.poll() is None else "stopped ❌"
            await message.channel.send(f"Web panel is currently **{status}**")
            return

        toggle = parts[1].lower()
        if toggle == "on":
            if self.webpanel_process and self.webpanel_process.poll() is None:
                await message.channel.send("Web panel is already **running ✅**")
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
                
                # Check for cloudflared.exe and script explicitly before launching
                if os.path.exists(tunnel_script) and os.path.exists(cloudflared_exe):
                    try:
                        self.tunnel_process = subprocess.Popen(
                            [tunnel_script],
                            cwd=root_dir,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                            shell=True
                        )
                        # Give it a moment to initialize
                        await asyncio.sleep(2)
                        
                        if self.tunnel_process.poll() is None:
                            await message.channel.send("Tunnel started 🚇")
                        else:
                            # It crashed immediately despite existing
                            logger.error_system("Tunnel process exited immediately.")
                            self.tunnel_process = None
                            await message.channel.send("⚠️ Tunnel failed to start. Launching local WebPanel.")
                            
                    except Exception as e:
                        logger.error_system(f"Failed to start tunnel: {e}")
                        await message.channel.send("⚠️ Tunnel start error. Launching local WebPanel.")
                else:
                    # Cloudflared or script missing
                    await message.channel.send("⚠️ Tunnel not configured. Launching local WebPanel.")

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
                await message.channel.send("Web panel is now **starting ✅**")
            except ProcessOperationError as e:
                await message.channel.send(f"❌ Failed to start web panel: {e.reason}")
            except Exception as e:
                await message.channel.send(f"❌ Failed to start web panel: {e}")
                
        elif toggle == "off":
            if not self.webpanel_process or self.webpanel_process.poll() is not None:
                await message.channel.send("Web panel is already **stopped ❌**")
                return
            
            try:
                # Stop tunnel if running
                if self.tunnel_process:
                    try:
                        self.tunnel_process.terminate()
                        # Force kill cloudflared to ensure no zombie processes
                        if sys.platform == "win32":
                            subprocess.run("taskkill /F /IM cloudflared.exe", shell=True, stderr=subprocess.DEVNULL)
                        
                        try:
                            self.tunnel_process.wait(timeout=2)
                        except subprocess.TimeoutExpired:
                            self.tunnel_process.kill()
                            
                        self.tunnel_process = None
                        await message.channel.send("Tunnel stopped 🛑")
                    except Exception as e:
                        logger.error(f"Error stopping tunnel: {e}")

                # Stop WebPanel
                # Force kill immediately on Windows to handle PyInstaller one-file process trees (Bootloader + App)
                if sys.platform == "win32":
                    subprocess.run("taskkill /F /IM WebPanel.exe", shell=True, stderr=subprocess.DEVNULL)
                    
                # Graceful cleanup attempt for non-Windows or if process object still exists
                if self.webpanel_process:
                    self.webpanel_process.terminate()
                    try:
                        self.webpanel_process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        self.webpanel_process.kill()
                
                await message.channel.send("Web panel is now **stopped ❌**")
                    
                self.webpanel_process = None
                
            except ProcessOperationError as e:
                await message.channel.send(f"❌ Failed to stop web panel: {e.reason}")
            except Exception as e:
                await message.channel.send(f"❌ Failed to stop web panel: {e}")
        else:
            await message.channel.send("Usage: `.webpanel on` or `.webpanel off`")

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
                    message.channel, "🟢 RaptorChat is **running**."
                )
            else:
                await self.discord_manager.send_temp_message(
                    message.channel, "🔴 RaptorChat is **not running**."
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
                        message.channel, "🛑 RaptorChat stopped."
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
                    message.channel, "🦖 RaptorChat restarted."
                )
            else:
                await self.discord_manager.send_temp_message(
                    message.channel, "❌ Failed to restart RaptorChat."
                )
        
        else:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Unknown subcommand. Use: `status`, `stop`, or `reboot`."
            )
