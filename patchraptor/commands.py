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

class CommandHandler:
    """Handles Discord bot commands using focused handler classes."""
    def __init__(
        self,
        server_manager: ServerManager,
        rcon_manager: RCONManager,
        version_manager: VersionManager,
        backup_manager: BackupManager,
        discord_manager: DiscordManager,
        player_manager: PlayerManager,
        schedule_manager: ScheduleManager,
        raptorchat_manager,
        config_manager: ConfigManager,
    ):
        self.server_manager = server_manager
        self.rcon_manager = rcon_manager
        self.version_manager = version_manager
        self.backup_manager = backup_manager
        self.discord_manager = discord_manager
        self.player_manager = player_manager
        self.raptorchat_manager = raptorchat_manager
        self.schedule_manager = schedule_manager
        self.config_manager = config_manager

        # Initialize focused handlers
        self.server_control_handler = ServerControlHandler(
            server_manager,
            rcon_manager,
            discord_manager,
            player_manager,
            raptorchat_manager
        )
        
        self.system_monitoring_handler = SystemMonitoringHandler(
            server_manager, rcon_manager, discord_manager, version_manager, 
            config_manager, backup_manager, player_manager, schedule_manager, raptorchat_manager
        )
        
        self.backup_restore_handler = BackupRestoreHandler(
            server_manager, rcon_manager, backup_manager, discord_manager, config_manager, raptorchat_manager
        )
        
        self.player_management_handler = PlayerManagementHandler(
            server_manager, rcon_manager, discord_manager, player_manager
        )
        
        self.update_management_handler = UpdateManagementHandler(
            server_manager, rcon_manager, version_manager, discord_manager, 
            config_manager, player_manager, raptorchat_manager
        )
        
        self.configuration_handler = ConfigurationHandler(
            discord_manager, config_manager, raptorchat_manager
        )
        
        self.schedule_handler = ScheduleHandler(
            server_manager, discord_manager, schedule_manager
        )
        
        # Update ScheduleManager with focused handler references
        self.schedule_manager.server_control_handler = self.server_control_handler
        self.schedule_manager.backup_restore_handler = self.backup_restore_handler
        self.schedule_manager.update_management_handler = self.update_management_handler
        self.schedule_manager.raptorchat_manager = raptorchat_manager

        # Command routing to focused handlers
        self.commands = {
            ".status": self.system_monitoring_handler.cmd_status,
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
            ".autoupdate": self.update_management_handler.cmd_autoupdate,
            ".update": self.update_management_handler.cmd_update,
            ".forceupdate": self.update_management_handler.cmd_forceupdate,
            ".cancel": self.update_management_handler.cmd_cancel,
            ".send": self.server_control_handler.cmd_send,
            ".schedule": self.schedule_handler.cmd_schedule,
            ".webhook": self.configuration_handler.cmd_webhook,
            ".chat": self.configuration_handler.cmd_chat,
            ".discord": self.configuration_handler.cmd_discord,
            ".menu": self.cmd_menu,
        }

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
            logger.debug_system(f"No exact match found, checking for partial matches")
            for cmd_key in self.commands:
                if content_lower.startswith(cmd_key):
                    logger.debug_system(f"Found partial match: '{cmd_key}' for command: '{content_lower}'")
                    await self.commands[cmd_key](message, content, content_lower)
                    break
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
            ("🔧 Server Controls", "section_2"),
            ("🔄 Server Updates", "section_3"),
            ("💬 Server Broadcasts", "section_5"),
            ("🎮 Player Management", "section_9")
        ]
        
        right_buttons = [
            ("📡 Webhook Settings", "section_4"),
            ("💾 Backup System", "section_6"),
            ("📅 Scheduling", "section_7"),
            ("⚙️ Advanced Settings", "section_8"),
            ("🦖 RaptorChat", "section_10"),
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
                "commands": "`.status`  - check server status\n`.servers`  - get server details\n`.check`  - check for updates manually\n`.autoupdate`  - shows autoupdate status\n`.autoupdate on|off`  - toggles autoupdate"
            },
            "section_2": {
                "title": "🔧 Server Control",
                "commands": "`.reboot`  - restart all servers\n`.reboot [map]`  - restart specific map\n`.shutdown`  - stop all servers\n`.shutdown [map]`  - stop specific map\n`.cancel`  - cancel ongoing operations"
            },
            "section_3": {
                "title": "🔄 Server Updates",
                "commands": "`.update`  - schedule a maintenance update\n`.forceupdate`  - immediate server update\n`.check`  - check for available updates"
            },
            "section_4": {
                "title": "📡 Webhook Settings",
                "commands": "`.webhook get shutdown|reboot`  - view webhook messages\n`.webhook set shutdown|reboot`  - set webhook messages"
            },
            "section_5": {
                "title": "💬 Server Broadcasts",
                "commands": "`.send all [message]`  - send message to all servers\n`.send [map] [message]`  - send message to specific server"
            },
            "section_6": {
                "title": "💾 Backup System",
                "commands": "`.backup all`  - full server backup\n`.backup [map]`  - backup specific map\n`.restore [map]`  - show backup list for map\n`.restore [map] [number]`  - restore specific backup"
            },
            "section_7": {
                "title": "📅 Scheduling System",
                "commands": "`.schedule`  - view scheduled tasks\n`.schedule add`  - add new task\n`.schedule clear`  - clear all tasks\n`.schedule clear [type]`  - clear specific task type",
                "examples": "Daily Shutdown: `.schedule add shutdown 03:00` \nWeekly Backup: `.schedule add backup rag tue thu 02:00` \nDaily Reboot: `.schedule add reboot 04:00` \nWeekly Update: `.schedule add update sun 01:00` "
            },
            "section_8": {
                "title": "⚙️ Advanced Settings",
                "commands": "`.discord delete 24:00`  - auto-delete messages after 24h\n`.backup amount 10`  - keep 10 backups of each map\n`.webpanel`  - view web panel status\n`.webpanel on|off`  - toggle web panel\n`.report`  - generate log report\n`.diagnose`  - perform a system health check"
            },
            "section_9": {
                "title": "🎮 Player Management",
                "commands": "`.players`  - shows total number of players\n`.players list`  - shows detailed player info\n`.kick <playerID>`  - kick a player from the server\n`.ban <playerID>`  - ban a player from the server\n`.unban <playerID>`  - unban a player from the servers"
            },
            "section_10": {
                "title": "🦖 RaptorChat",
                "commands": "`.chat status`  - shows status of chat relay\n`.chat reboot`  - restarts chat relay\n`.chat stop`  - stop chat relay"
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
