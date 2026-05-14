import asyncio
import subprocess
import datetime
import os
import sys
import tempfile
import psutil
import discord
import shlex
from .log_manager import logger, LOG_PATH
from .server_manager import ServerManager
from .rcon_manager import RCONManager
from .version_manager import VersionManager
from .backup_manager import BackupManager
from .discord_manager import DiscordManager
from .schedule_manager import ScheduleManager
from .config import ConfigManager
from .server_control_handler import ServerControlHandler
from .system_monitoring_handler import SystemMonitoringHandler
from .backup_restore_handler import BackupRestoreHandler
from .player_management_handler import PlayerManagementHandler
from .update_management_handler import UpdateManagementHandler
from .configuration_handler import ConfigurationHandler
from .schedule_handler import ScheduleHandler
from .player_manager import PlayerManager
from .system_utils import SystemUtils
from .service_locator import ServiceLocator
from .base_handler import BaseHandler

class CommandHandler(BaseHandler):
    """Handles Discord bot commands using focused handler classes."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize focused handlers with injected managers
        self.server_control_handler = ServerControlHandler(**kwargs)
        self.system_monitoring_handler = SystemMonitoringHandler(**kwargs)
        self.backup_restore_handler = BackupRestoreHandler(**kwargs)
        self.player_management_handler = PlayerManagementHandler(**kwargs)
        self.update_management_handler = UpdateManagementHandler(**kwargs)
        self.configuration_handler = ConfigurationHandler(**kwargs)
        self.schedule_handler = ScheduleHandler(**kwargs)
        
        # Register handlers with ServiceLocator for cross-module access (e.g. ScheduleManager)
        ServiceLocator.register("ServerControlHandler", self.server_control_handler)
        ServiceLocator.register("BackupRestoreHandler", self.backup_restore_handler)
        ServiceLocator.register("UpdateManagementHandler", self.update_management_handler)
        ServiceLocator.register("ScheduleManager", self.schedule_manager)

        # Command routing to focused handlers
        self.commands = {
            ".status": self.system_monitoring_handler.cmd_status,
            ".analytics": self.system_monitoring_handler.cmd_analytics,
            ".diagnose": self.system_monitoring_handler.cmd_diagnose,
            ".check": self.system_monitoring_handler.cmd_check,
            ".debug": self.system_monitoring_handler.cmd_debug,
            ".webpanel": self.configuration_handler.cmd_webpanel,
            ".servers": self.server_control_handler.cmd_servers,
            ".reboot": self.server_control_handler.cmd_reboot,
            ".shutdown": self.server_control_handler.cmd_shutdown,
            ".players": self.player_management_handler.cmd_players,
            ".kick": self.player_management_handler.cmd_kick,
            ".ban": self.player_management_handler.cmd_ban,
            ".unban": self.player_management_handler.cmd_unban,
            ".report": self.system_monitoring_handler.cmd_report,
            ".backup": self.backup_restore_handler.cmd_backup,
            ".restore": self.backup_restore_handler.cmd_restore,
            ".autopatch": self.update_management_handler.cmd_autopatch,
            ".patch": self.update_management_handler.cmd_patch,
            ".forcepatch": self.update_management_handler.cmd_forcepatch,
            ".cancel": self.update_management_handler.cmd_cancel,
            ".send": self.server_control_handler.cmd_send,
            ".schedule": self.schedule_handler.cmd_schedule,
            ".chat": self.configuration_handler.cmd_chat,
            ".discord": self.configuration_handler.cmd_discord,
            ".menu": self.cmd_menu,
        }

    async def cleanup(self):
        """Perform final cleanup of all sub-handlers"""
        logger.info_system("CommandHandler: Cleaning up sub-handlers...")
        if self.configuration_handler:
            await self.configuration_handler.cleanup()


    async def handle_command(self, message):
        logger.debug_system(f"handle_command called for message: {message.content[:100]}{'...' if len(message.content) > 100 else ''}")
        content = message.content.strip()
        content_lower = content.lower()
        base = content_lower.split()[0] if content_lower else ""
        logger.debug_system(f"Parsed command base: '{base}'")
        
        if base in self.commands:
            logger.debug_system(f"Found exact match for command: '{base}', routing to handler")
            await self.commands[base](message, content, content_lower)
        else:
            logger.debug_system(f"No command handler found for: '{content_lower}'")

    async def cmd_menu(self, message, content: str, content_lower: str):
        """Handle .menu command"""
        logger.debug_system("cmd_menu called")
        logger.info_command(".menu received")
        logger.debug_system("Creating CommandMenuView")
        view = CommandMenuView()
        logger.debug_system("Sending menu message to channel")
        msg = await message.channel.send(view=view)
        logger.debug_system("Scheduling menu message for auto-deletion")
        # Schedule the menu message for auto-deletion
        asyncio.create_task(self.discord_manager._delete_message_later(msg))
        logger.debug_system("cmd_menu completed successfully")



class CommandMenuView(discord.ui.View):
    """Interactive command menu with Discord UI buttons"""
    
    def __init__(self):
        super().__init__(timeout=900)  # 15 minute timeout
        logger.debug_system("CommandMenuView initialized")
        
        # Create button layout: 5x2 grid
        left_buttons = [
            ("📊 Server Monitoring", "section_1"),
            ("🔧 Server Management", "section_2"),
            ("💬 Server Broadcasts", "section_5"),
            ("🎮 Player Management", "section_9"),
            ("🌐 Web Panel Controls", "section_11")
        ]
        
        right_buttons = [
            ("🦖 Patch Management", "section_3"),
            ("📅 Server Automation", "section_7"),
            ("💾 Backup & Restore", "section_6"),
            ("⚙️ Advanced Settings", "section_8"),
            ("🦖 Chat Relay Controls", "section_10"),
        ]
        
        # Add left column buttons
        for row, (label, custom_id) in enumerate(left_buttons):
            button = discord.ui.Button(
                label=label, custom_id=custom_id, 
                style=discord.ButtonStyle.secondary, row=row
            )
            button.callback = self.button_callback
            self.add_item(button)
            logger.debug_system(f"Added left button: {label} (row={row})")
        
        # Add right column buttons
        for row, (label, custom_id) in enumerate(right_buttons):
            button = discord.ui.Button(
                label=label, custom_id=custom_id, 
                style=discord.ButtonStyle.secondary, row=row
            )
            button.callback = self.button_callback
            self.add_item(button)
            logger.debug_system(f"Added right button: {label} (row={row})")
    
    async def button_callback(self, interaction):
        """Handle button interactions"""
        try:
            logger.debug_system(f"Button callback triggered for: {interaction.data['custom_id']}")
            section_id = interaction.data["custom_id"]
        except Exception as e:
            logger.error_system(f"Error accessing interaction data: {e}")
            await interaction.response.send_message("❌ Error processing button click.", ephemeral=True)
            return
        grey_color = 0x99AAB5  # Discord's secondary button grey
        
        embed_data = {
            "section_1": {
                "title": "📊 Server Monitoring",
                "description": "Monitor cluster health, resource usage, and player trends.",
                "commands": "`.status` — View host hardware load and health\n`.servers` — Get live usage and save sizes per map\n`.check` — Query SteamCMD for pending updates\n`.analytics` — View 7-day performance and player trends"
            },
            "section_2": {
                "title": "🔧 Server Control",
                "description": "Control server processes for all maps or specific instances.",
                "commands": "`.reboot` — Gracefully restart all servers\n`.reboot <map>` — Gracefully restart a specific server\n`.shutdown` — Gracefully stop all servers\n`.shutdown <map>` — Gracefully stop a specific server"
            },
            "section_3": {
                "title": "🦖 Patch Management",
                "description": "Manage SteamCMD updates and automated patching.",
                "commands": "`.patch` — Start graceful patch with countdowns\n`.forcepatch` — Instantly force patch without countdown\n`.patch status` — View current patch configuration\n`.autopatch on|off` — Toggle automatic background updates\n`.cancel` — Abort any active patch sequence",
                "examples": "Set Countdown: `.patch timer 15` (minutes)\nSet Warning Timing: `.patch intervals 15,10,5,1` (minutes)\nSet In-Game Alert: `.patch broadcast Server shutdown in {minutes} minutes...`\nSet Discord Webhook Announcement: `.patch webhook reboot Patch complete!`"
            },
            "section_5": {
                "title": "💬 Server Broadcasts",
                "description": "Send global announcements to in-game players.",
                "commands": "`.send all <message>` — Broadcast alert to all running servers\n`.send <map> <message>` — Broadcast alert to a specific server"
            },
            "section_6": {
                "title": "💾 Backup & Restore",
                "description": "Protect and rollback save game archives.",
                "commands": "`.backup all` — Instantly archive all server data\n`.backup <map>` — Archive data for a specific server\n`.backup amount <num>` — Set number of retained backups\n`.restore <map>` — List archives for a specific server\n`.restore <map> <num>` — Stop, restore archive, and restart"
            },
            "section_7": {
                "title": "📅 Automation",
                "description": "Configure recurring maintenance and cluster tasks.",
                "commands": "`.schedule` — View active scheduled tasks\n`.schedule add` — Create a new task (reboot, patch, backup)\n`.schedule clear` — Remove all scheduled tasks\n`.schedule clear <type>` — Remove tasks of a specific type",
                "examples": "Daily Shutdown: `.schedule add shutdown 03:00`\nWeekly Backup: `.schedule add backup all 02:00`\nMap Reboot: `.schedule add reboot scorched 04:00`\nWeekly Patch: `.schedule add patch sun 01:00`"
            },
            "section_8": {
                "title": "⚙️ Advanced Settings",
                "description": "System-level configuration and diagnostic tools.",
                "commands": "`.discord delete <time>` — Set auto-deletion for bot messages\n`.report` — Generate a downloadable system log report\n`.diagnose` — Run internal system health check\n`.debug` — Toggle diagnostic logging mode"
            },
            "section_9": {
                "title": "🎮 Player Management",
                "description": "Moderate and track players across the cluster.",
                "commands": "`.players` — Show total active players\n`.players list` — Show detailed player info\n`.kick <player>` — Disconnect player from all servers\n`.ban <player>` — Ban player across cluster (Name or ID)\n`.unban <player>` — Lift ban across cluster (Name or ID)"
            },
            "section_10": {
                "title": "🦖 Chat Relay",
                "description": "Manage the chat relay and telemetry system.",
                "commands": "`.chat status` — View health of the chat relay\n`.chat reboot` — Forcefully restart the relay service\n`.chat stop` — Disconnect the chat relay"
            },
            "section_11": {
                "title": "🌐 Web Panel",
                "description": "Control the management interface and secure tunnel.",
                "commands": "`.webpanel` — View tunnel URL and connection status\n`.webpanel on` — Launch web server and open tunnel\n`.webpanel off` — Shut down web server and close tunnel"
            }
        }
        
        try:
            if section_id in embed_data:
                data = embed_data[section_id]
                embed = discord.Embed(title=data["title"], color=grey_color)
                embed.add_field(name="Available Commands", value=data["commands"], inline=False)
                
                if "examples" in data:
                    embed.add_field(name="Examples", value=data["examples"], inline=False)
                
                logger.debug_system(f"Sending embed response for section: {section_id}")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                logger.debug_system(f"Unknown section selected: {section_id}")
                await interaction.response.send_message("❌ Unknown section selected.", ephemeral=True)
        except Exception as e:
            logger.error_system(f"Error creating or sending embed response: {e}")
            try:
                await interaction.response.send_message("❌ Error displaying command menu.", ephemeral=True)
            except:
                logger.error_system("Failed to send error response to user")
    
    async def on_timeout(self):
        """Disable all buttons when the view times out"""
        try:
            logger.debug_system("CommandMenuView on_timeout called")
            logger.debug_system(f"Disabling {len(self.children)} buttons")
            for item in self.children:
                item.disabled = True
            logger.debug_system("All buttons disabled due to timeout")
        except Exception as e:
            logger.error_system(f"Error in on_timeout: {e}")


