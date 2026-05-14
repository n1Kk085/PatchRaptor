# Copyright (c) 2026 n1Kk085/PatchRaptor
# Licensed under the PATCHRAPTOR LICENSE AGREEMENT.
# See LICENSE file for details. Distribution prohibited.

from patchraptor.log_manager import logger
import os
import sys
import time
import asyncio
import discord
import traceback

from patchraptor.config import ConfigManager
from patchraptor.server_manager import ServerManager
from patchraptor.rcon_manager import RCONManager
from patchraptor.version_manager import VersionManager
from patchraptor.player_manager import PlayerManager
from patchraptor.backup_manager import BackupManager
from patchraptor.schedule_manager import ScheduleManager
from patchraptor.discord_manager import DiscordManager
from patchraptor.commands import CommandHandler
from patchraptor.raptorchat_manager import RaptorChatManager
from patchraptor.service_locator import ServiceLocator


class PatchRaptorClient(discord.Client):
    def __init__(self, config_manager: ConfigManager, command_handler: CommandHandler, schedule_manager: ScheduleManager, **kwargs):
        logger.debug_system("Starting PatchRaptorClient initialization")
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents, **kwargs)
        self.config_manager = config_manager
        self.command_handler = command_handler
        self.schedule_manager = schedule_manager
        self.background_tasks = []
        self.on_ready_executed = False
        logger.debug_system("PatchRaptorClient initialization completed")

    async def _run_supervisored(self, coro, task_name: str):
        """Run a background task and track its handle for supervision"""
        try:
            logger.debug_system(f"Launching supervised task: {task_name}")
            task = asyncio.create_task(coro)
            task.set_name(task_name)
            self.background_tasks.append(task)
            
            # Chain a callback to detect silent failures
            def _handle_done(t):
                if not t.cancelled() and t.exception():
                    logger.error_system(f"Critical background task '{task_name}' failed: {t.exception()}")

                elif not t.cancelled():
                    logger.debug_system(f"Background task '{task_name}' finished normally.")
            
            task.add_done_callback(_handle_done)
            return task
        except Exception as e:
            logger.error_system(f"Failed to launch task {task_name}: {e}")

    async def on_ready(self):
        if self.on_ready_executed:
            return
        self.on_ready_executed = True
        
        logger.info_command(f"Authenticated as {self.user} (Sync Success)")
        
        # 🟢 PHASE 1: SEQUENTIAL MANAGER INITIALIZATION
        logger.info_system("Initializing server and cluster management core...")
        try:
            # Player Manager (Loads bans, registers for Echo events)
            player_manager = ServiceLocator.get("PlayerManager")
            await player_manager.initialize()
            
            # Schedule Manager (Loads schedule from disk)
            await self.schedule_manager.initialize()
            
            # Discord Manager (Connects client and channels)
            ServiceLocator.get("DiscordManager").set_discord_client(self)
        except Exception as e:
            logger.error_system(f"FATAL: Sequenced bootstrap failed: {e}")
            await self.close()
            return

        # 🔵 PHASE 2: LAUNCH BACKGROUND TASKS (SUPERVISED)
        logger.info_system("Launching background services...")
        
        # 1. Telemetry Echo Loop
        await self._run_supervisored(
            ServiceLocator.get("TelemetryManager").telemetry_loop(interval=10),
            "Telemetry-Echo"
        )

        # 2. Schedule Runner
        await self._run_supervisored(
            self.schedule_manager.schedule_runner(),
            "Schedule-Runner"
        )

        # 3. Autoupdate Checker
        if self.command_handler.update_management_handler.autoupdate_enabled:
             await self._run_supervisored(
                self.command_handler.update_management_handler.start_autoupdate_checker(),
                "Autoupdate-Checker"
            )

        # 4. RaptorChat (Delayed Startup)
        async def startup_raptorchat_wrapper():
            rc_manager = ServiceLocator.get("RaptorChatManager")
            if rc_manager:
                rc_manager.start_maintenance()
                await self._run_supervisored(rc_manager.start_auto_monitor(initial_delay=0), "RaptorChat-Monitor")
                logger.info_system("RaptorChat will start in 15 seconds...")
                await asyncio.sleep(15)
                rc_manager.start()
                rc_manager.end_maintenance()


        await self._run_supervisored(startup_raptorchat_wrapper(), "RaptorChat-Bootstrapper")

        logger.info_system("PatchRaptor is now online and ready to use.")

    async def close(self):
        """Override close() for graceful shutdown of background tasks"""
        logger.info_system("Shutting down... Cancelling supervised background tasks.")
        for task in self.background_tasks:
            if not task.done():
                logger.debug_system(f"Stopping task: {task.get_name()}")
                task.cancel()
        
        if self.background_tasks:
            # Wait for tasks to acknowledge cancellation
            await asyncio.gather(*self.background_tasks, return_exceptions=True)
            logger.debug_system("All background tasks terminated.")
        
        # Final cleanup for RaptorChat
        try:
            rc_manager = ServiceLocator.get("RaptorChatManager")
            if rc_manager and rc_manager.is_running():
                logger.debug_system("Stopping RaptorChat process...")
                rc_manager.stop()
        except Exception:
            pass
            
        # Final cleanup for Command Handlers (WebPanel, etc)
        try:
            if self.command_handler:
                await self.command_handler.cleanup()
        except Exception:
            pass

        await super().close()
        

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


async def main():
    logger.debug_system("Starting main function")
    logger.debug_system("Building application")
    
    # Build all managers upfront before Discord client initialization
    config = ConfigManager()
    token = config.get("bot_token")
    if not token:
        logger.debug_system("No bot_token found in config")
        raise RuntimeError("bot_token missing in config.json")
    
    # Build core managers before Discord init (preserves async bootstrapping)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    servers = config.get_server_configs()
    server_manager = ServerManager(servers, config.get("rcon_tool"))
    rcon_manager = RCONManager(config.get("rcon_tool"))
    version_manager = VersionManager(config.get("steamcmd_path"), config.get("app_id"))
    
    # Backup Manager (path resolution needed)
    backup_config = config.get("backup_config", {})
    backup_path = backup_config.get("backup_path", "backups")
    if not os.path.isabs(backup_path):
        backup_path = os.path.join(base_dir, backup_path)
    backup_retention = backup_config.get("backup_retention_count", 10)
    backup_manager = BackupManager(backup_path, base_dir, backup_retention)
    
    # Discord Manager (connects after client init)
    discord_manager = DiscordManager(config.get("discord_webhook", ""))
    
    # Player Manager
    player_manager = PlayerManager(servers)
    
    # Schedule Manager
    schedule_file = os.path.join(base_dir, "schedule.json")
    schedule_manager = ScheduleManager(schedule_file=schedule_file)
    
    # RaptorChat Manager
    raptorchat_dir = config.get("raptorchat_dir", base_dir)
    raptorchat_path = config.get("raptorchat_path", os.path.join(base_dir, "RaptorChat.py"))
    raptorchat_manager = RaptorChatManager(
        raptorchat_dir=raptorchat_dir,
        raptorchat_path=raptorchat_path
    )
    
    # Telemetry Manager (needs base_dir)
    from patchraptor.telemetry_manager import TelemetryManager
    telemetry_manager = TelemetryManager(base_dir)
    
    # Command Handler
    cmd = CommandHandler()
    
    # Create Client with dependencies
    client = PatchRaptorClient(config, cmd, schedule_manager)
    
    logger.debug_system("PatchRaptor client created successfully")
    
    # Register all managers into ServiceLocator for on_ready() access
    ServiceLocator.clear()
    ServiceLocator.register("ConfigManager", config)
    ServiceLocator.register("ServerManager", server_manager)
    ServiceLocator.register("RCONManager", rcon_manager)
    ServiceLocator.register("VersionManager", version_manager)
    ServiceLocator.register("BackupManager", backup_manager)
    ServiceLocator.register("DiscordManager", discord_manager)
    ServiceLocator.register("PlayerManager", player_manager)
    ServiceLocator.register("ScheduleManager", schedule_manager)
    ServiceLocator.register("RaptorChatManager", raptorchat_manager)
    ServiceLocator.register("TelemetryManager", telemetry_manager)
    
    logger.debug_system("All Managers registered with ServiceLocator")
    
    # Start Discord client
    try:
        await client.start(token)
    finally:
        logger.info_system("Bot shutting down, performing final cleanup...")
        try:
            rc_manager = ServiceLocator.get("RaptorChatManager")
            if rc_manager and rc_manager.is_running():
                logger.info_system("Stopping RaptorChat process...")
                rc_manager.stop()
        except:
            pass
            
        try:
            if client and client.command_handler:
                await client.command_handler.cleanup()
        except:
            pass


if __name__ == "__main__":
    # Ensure standard output is flushed regularly for the launcher
    try:
        # Use info_system for initial startup message to ensure visibility 
        # Ensures visibility if debug_system is suppressed by default level
        logger.info_system("Application starting...")
        
        try:
            logger.debug_system("Running main async function")
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info_system("KeyboardInterrupt received, shutting down gracefully")
            pass
        except Exception as e:
            # Use direct print and sys.stderr for critical startup failures 
            # to ensure they bypass the logger level checks and flush immediately
            print(f"\nCRITICAL ERROR: {e}", file=sys.stderr, flush=True)
            logger.error_system(f"Unexpected error in main: {e}")
            import traceback
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()
            # Give the launcher a moment to read the buffer before exiting
            time.sleep(1)
            sys.exit(1)
    except Exception as e:
        print(f"FATAL BOOTSTRAP ERROR: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
