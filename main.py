# Copyright (c) 2026 n1Kk085/PatchRaptor
# Licensed under the PATCHRAPTOR LICENSE AGREEMENT.
# See LICENSE file for details. Distribution prohibited.

import os
import sys
import time
import asyncio
import discord

from patchraptor.config import ConfigManager
from patchraptor.log_manager import logger
from patchraptor.server_manager import ServerManager
from patchraptor.rcon_manager import RCONManager
from patchraptor.version_manager import VersionManager
from patchraptor.player_manager import PlayerManager
from patchraptor.backup_manager import BackupManager
from patchraptor.schedule_manager import ScheduleManager
from patchraptor.discord_manager import DiscordManager
from patchraptor.commands import CommandHandler
from patchraptor.raptorchat_manager import RaptorChatManager


class PatchRaptorClient(discord.Client):
    def __init__(self, config_manager: ConfigManager, command_handler: CommandHandler, schedule_manager: ScheduleManager, **kwargs):
        logger.debug_system("Starting PatchRaptorClient initialization")
        intents = discord.Intents.default()
        intents.message_content = True
        logger.debug_system("Discord intents configured")
        super().__init__(intents=intents, **kwargs)
        self.config_manager = config_manager
        self.command_handler = command_handler
        self.schedule_manager = schedule_manager
        logger.debug_system("PatchRaptorClient initialization completed")

    async def on_ready(self):
        logger.debug_system(f"on_ready event triggered for user: {self.user} (ID: {self.user.id})")
        logger.log(f"Logged in as {self.user} (ID: {self.user.id})")
        
        # Set the Discord client in the DiscordManager for channel access
        self.command_handler.discord_manager.set_discord_client(self)
        # Start the scheduler runner once on boot
        try:
            logger.debug_system("Creating schedule runner task")
            asyncio.create_task(self.schedule_manager.schedule_runner(self, self.command_handler.server_manager, self.command_handler.rcon_manager, self.command_handler.discord_manager, self.command_handler))
            logger.debug_system("Schedule runner task created successfully")
        except Exception as e:
            logger.debug_system(f"Failed to create schedule runner task: {e}")
            logger.error_system(f"Failed to start schedule runner: {e}")
        
        # Start the autoupdate checker if enabled
        try:
            if self.command_handler.update_management_handler.autoupdate_enabled:
                logger.debug_system("Autoupdate is enabled, starting autoupdate checker")
                asyncio.create_task(self.command_handler.update_management_handler.start_autoupdate_checker())
                logger.debug_system("Autoupdate checker task created successfully")
            else:
                logger.debug_system("Autoupdate is disabled, skipping autoupdate checker")
        except Exception as e:
            logger.debug_system(f"Failed to create autoupdate checker task: {e}")
            logger.error_system(f"Failed to start autoupdate checker: {e}")
        
        # Initialize PlayerManager
        try:
            logger.debug_system("Initializing PlayerManager")
            await self.command_handler.player_manager.initialize()
            logger.debug_system("PlayerManager initialized successfully")
            
            # Start periodic player update task (every 30 minutes) with delay to avoid duplicate checks
            logger.debug_system("Starting periodic player update task")
            asyncio.create_task(self._periodic_player_update())
            logger.debug_system("Periodic player update task created successfully")
        except Exception as e:
            logger.debug_system(f"Failed to initialize PlayerManager: {e}")
            logger.error_system(f"Failed to initialize PlayerManager: {e}")
        
        # Add a small delay to ensure autoupdate messages appear first
        await asyncio.sleep(0.1)
        
        # Initialize RaptorChat auto-monitor (auto-reconnect) without starting it
        try:
            logger.debug_system("Initializing RaptorChat auto-monitor feature")
            
            # Initialize auto-reconnect monitor without starting RaptorChat
            await self.command_handler.raptorchat_manager.start_auto_monitor()
            logger.debug_system("RaptorChat auto-monitor initialized successfully")
            
            # RaptorChat will be started after a short delay
            logger.info_system("RaptorChat will start in 15 seconds...")
            
        except Exception as e:
            logger.debug_system(f"Failed to initialize RaptorChat auto-monitor: {e}")
            logger.error_system(f"Failed to initialize RaptorChat auto-monitor: {e}")
        

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
            
        # Check if message is from the allowed channel
        allowed_channel_id = int(self.config_manager.get("channel_id"))
        if message.channel.id != allowed_channel_id:
            logger.debug_system(f"Message from channel {message.channel.id} ignored - not allowed channel {allowed_channel_id}")
            return
            
        logger.debug_system(f"Forwarding message to command handler: {message.content[:50]}{'...' if len(message.content) > 50 else ''}")
        await self.command_handler.handle_command(message)

    async def _delayed_raptorchat_start(self):
        """Start RaptorChat after a 15-second delay"""
        try:
            await asyncio.sleep(15)  # 15-second delay
            logger.info_system("Starting RaptorChat after initial delay...")
            if hasattr(self.command_handler, 'raptorchat_manager'):
                if not self.command_handler.raptorchat_manager.is_running():
                    if await self.command_handler.raptorchat_manager.async_reboot():
                        logger.info_system("RaptorChat started successfully")
                    else:
                        logger.error_system("Failed to start RaptorChat")
                else:
                    logger.debug_system("RaptorChat is already running, not starting again")
        except Exception as e:
            logger.error_system(f"Error in delayed RaptorChat start: {e}")
    
    async def _periodic_player_update(self):
        """
        Background task to monitor player activity (frequently) 
        and update log file paths (infrequently).
        """
        logger.debug_system("Starting player monitoring loop")
        
        # Start RaptorChat shortly after boot
        asyncio.create_task(self._delayed_raptorchat_start())
        

        
        while True:
            try:
                # 1. Update Active Players (High Frequency - every 5s)
                # This tails the logs for "Join/Leave" events
                await self.command_handler.player_manager.update_active_players()
                
                # 2. Update Log File Paths (Low Frequency - every 30m)
                # DEPRECATED: Smart detection in update_active_players() now handles this.
                # Keeping comment for clarity: We used to force a scan every 30m here.

                
                # Sleep for 30 seconds (resource optimized)
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                logger.debug_system("Player monitoring task cancelled")
                break
            except Exception as e:
                logger.error_system(f"Error in player monitoring loop: {e}")
                await asyncio.sleep(30) # Wait before retry


def build_app():
    logger.debug_system("Starting build_app function")
    # Config
    logger.debug_system("Creating ConfigManager")
    config = ConfigManager()
    logger.debug_system("ConfigManager created successfully")

    # Determine base directory and paths based on execution mode (Frozen vs Source)
    # logic moved up to ensure managers get absolute paths
    if getattr(sys, 'frozen', False):
        # Running as compiled exe in 'dist' folder
        base_dir = os.path.dirname(sys.executable)
        default_raptorchat_dir = base_dir
        default_raptorchat_path = os.path.join(base_dir, "RaptorChat.exe")
        logger.debug_system(f"Running in FROZEN mode. Base dir: {base_dir}")
    else:
        # Running from source
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_raptorchat_dir = os.path.join(base_dir, "RaptorChat")
        default_raptorchat_path = os.path.join(default_raptorchat_dir, "RaptorChat.py")
        logger.debug_system(f"Running in SOURCE mode. Base dir: {base_dir}")

    # Managers
    logger.debug_system("Getting server configurations")
    servers = config.get_server_configs()
    logger.debug_system(f"Found {len(servers)} server configurations")
    logger.debug_system("Creating ServerManager")
    server_manager = ServerManager(servers, config.get("rcon_tool"))
    logger.debug_system("Creating RCONManager")
    rcon_manager = RCONManager(config.get("rcon_tool"))
    logger.debug_system("Creating VersionManager")
    version_manager = VersionManager(config.get("steamcmd_path"), config.get("app_id"))
    # Get backup config from nested structure
    logger.debug_system("Getting backup configuration")
    backup_config = config.get("backup_config", {})
    backup_path = backup_config.get("backup_path", "backups")
    # Ensure backup path is absolute
    if not os.path.isabs(backup_path):
        backup_path = os.path.join(base_dir, backup_path)
    
    backup_retention = backup_config.get("backup_retention_count", 10)
    logger.debug_system(f"Backup config: path={backup_path}, retention={backup_retention}")
    logger.debug_system("Creating BackupManager")
    backup_manager = BackupManager(backup_path, base_dir, backup_retention)
    logger.debug_system("Creating DiscordManager")
    discord_manager = DiscordManager(config.get("discord_webhook", ""))
    logger.debug_system("Creating PlayerManager")
    player_manager = PlayerManager(servers)
    logger.debug_system("PlayerManager created successfully")
    logger.debug_system("Creating ScheduleManager")
    schedule_file = os.path.join(base_dir, "schedule.json")
    schedule_manager = ScheduleManager(schedule_file=schedule_file)
    # Initialize RaptorChat manager with config defaults
    logger.debug_system("Initializing RaptorChat manager")
    
    # Base dir logic was here, moved to top

    logger.debug_system(f"RaptorChat defaults: dir={default_raptorchat_dir}, path={default_raptorchat_path}")
    raptorchat_manager = RaptorChatManager(
        raptorchat_dir=config.get("raptorchat_dir", default_raptorchat_dir),
        raptorchat_path=config.get("raptorchat_path", default_raptorchat_path)
    )
    logger.debug_system("RaptorChat manager created successfully")

    # Command handler
    logger.debug_system("Creating CommandHandler")
    cmd = CommandHandler(
        server_manager=server_manager,
        rcon_manager=rcon_manager,
        version_manager=version_manager,
        backup_manager=backup_manager,
        discord_manager=discord_manager,
        player_manager=player_manager,
        schedule_manager=schedule_manager,
        raptorchat_manager=raptorchat_manager,
        config_manager=config,
    )
    logger.debug_system("CommandHandler created successfully")

    logger.debug_system("Creating PatchRaptorClient")
    client = PatchRaptorClient(config, cmd, schedule_manager)
    logger.debug_system("PatchRaptorClient created successfully")
    logger.debug_system("build_app function completed successfully")
    return client, config


async def main():
    logger.debug_system("Starting main function")
    logger.debug_system("Building application")
    client, config = build_app()
    logger.debug_system("Getting bot token from config")
    token = config.get("bot_token")
    if not token:
        logger.debug_system("No bot_token found in config")
        raise RuntimeError("bot_token missing in config.json")
    logger.debug_system("Bot token retrieved, starting Discord client")
    
    # Start Discord client
    await client.start(token)


if __name__ == "__main__":
    logger.debug_system("Application starting...")
    try:
        logger.debug_system("Running main async function")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.debug_system("KeyboardInterrupt received, shutting down gracefully")
        pass
    except Exception as e:
        logger.debug_system(f"Unexpected error in main: {e}")
        raise
