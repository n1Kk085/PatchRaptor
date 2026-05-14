import asyncio
import datetime
from typing import List, Dict, Any, Optional
from types import SimpleNamespace
from .log_manager import logger

SCHEDULE_FILE = "schedule.json"

class ScheduleManager:
    """Manages scheduled events and background execution with persistence."""
    def __init__(self, schedule_file: str = SCHEDULE_FILE):
        self.schedule_file = schedule_file
        self.scheduled_events: List[Dict[str, Any]] = []
        self._runner_started = False

    @property
    def config_manager(self):
        from .service_locator import ServiceLocator
        return ServiceLocator.get("ConfigManager")

    @property
    def discord_manager(self):
        from .service_locator import ServiceLocator
        return ServiceLocator.get("DiscordManager")

    @property
    def server_manager(self):
        from .service_locator import ServiceLocator
        return ServiceLocator.get("ServerManager")

    @property
    def server_control_handler(self):
        from .service_locator import ServiceLocator
        return ServiceLocator.get("ServerControlHandler")

    @property
    def backup_restore_handler(self):
        from .service_locator import ServiceLocator
        return ServiceLocator.get("BackupRestoreHandler")

    @property
    def update_management_handler(self):
        from .service_locator import ServiceLocator
        return ServiceLocator.get("UpdateManagementHandler")

    async def initialize(self):
        """Async initialization for the schedule manager"""
        logger.debug_schedule(f"Initializing ScheduleManager...")
        await asyncio.to_thread(self.load_schedule)
        logger.debug_schedule(f"ScheduleManager initialized with {len(self.scheduled_events)} events")

    def load_schedule(self):
        logger.debug_schedule(f"Loading schedule from file: {self.schedule_file}")
        try:
            import json, os
            if os.path.isfile(self.schedule_file):
                logger.debug_schedule(f"Schedule file exists, reading contents")
                with open(self.schedule_file, 'r', encoding='utf-8') as f:
                    self.scheduled_events = json.load(f)
                logger.debug_schedule(f"Loaded {len(self.scheduled_events)} scheduled events")
            else:
                logger.debug_schedule(f"Schedule file does not exist, initializing empty schedule")
                self.scheduled_events = []
        except Exception as e:
            logger.error_system(f"Failed to load schedule: {e}")
            logger.debug_schedule(f"Failed to load schedule: {e}, initializing empty schedule")
            self.scheduled_events = []

    def save_schedule(self):
        logger.debug_schedule(f"Saving {len(self.scheduled_events)} scheduled events to file: {self.schedule_file}")
        try:
            import json
            with open(self.schedule_file, 'w', encoding='utf-8') as f:
                json.dump(self.scheduled_events, f, indent=2)
            logger.debug_schedule(f"Schedule saved successfully")
        except Exception as e:
            logger.error_system(f"Failed to save schedule: {e}")
            logger.debug_schedule(f"Failed to save schedule: {e}")

    def add_event(self, event_type: str, time_str: str, days: Optional[List[str]] = None, map_name: Optional[str] = None, subtype: Optional[str] = None) -> bool:
        logger.debug_schedule(f"Adding scheduled event: type={event_type}, time={time_str}, days={days}, map={map_name}, subtype={subtype}")
        try:
            datetime.datetime.strptime(time_str, "%H:%M")
            evt = {"type": event_type, "time": time_str}
            if days: evt["days"] = days
            if map_name: evt["map_name"] = map_name
            if subtype: evt["subtype"] = subtype
            
            logger.debug_schedule(f"Event validation successful, adding to schedule")
            self.scheduled_events.append(evt)
            self.save_schedule()
            logger.debug_schedule(f"Event added successfully, total events: {len(self.scheduled_events)}")
            return True
        except Exception as e:
            logger.error_system(f"Failed to add scheduled event: {e}")
            logger.debug_schedule(f"Failed to add scheduled event: {e}")
            return False

    def clear_events(self, event_type: Optional[str] = None) -> int:
        logger.debug_schedule(f"Clearing scheduled events, event_type filter: {event_type}")
        initial = len(self.scheduled_events)
        logger.debug_schedule(f"Initial event count: {initial}")
        
        if event_type:
            logger.debug_schedule(f"Filtering events by type: {event_type}")
            self.scheduled_events = [e for e in self.scheduled_events if e.get('type') != event_type]
        else:
            logger.debug_schedule(f"Clearing all events (no filter)")
            self.scheduled_events = []
        
        removed = initial - len(self.scheduled_events)
        logger.debug_schedule(f"Removed {removed} events, remaining: {len(self.scheduled_events)}")
        
        if removed:
            logger.debug_schedule(f"Saving schedule after clearing events")
            self.save_schedule()
        else:
            logger.debug_schedule(f"No events to remove, schedule unchanged")
        
        return removed

    def get_events(self) -> List[Dict[str, Any]]:
        logger.debug_schedule(f"Retrieving all scheduled events, count: {len(self.scheduled_events)}")
        events = list(self.scheduled_events)
        logger.debug_schedule(f"Returning {len(events)} scheduled events")
        return events

    async def schedule_runner(self):
        logger.debug_schedule(f"Starting schedule runner, already started: {self._runner_started}")
        if self._runner_started:
            logger.debug_schedule(f"Schedule runner already started, skipping")
            return
        
        logger.debug_schedule(f"Marking runner as started and waiting for client ready")
        self._runner_started = True
        
        client = self.discord_manager.discord_client
        if not client:
            logger.error_system("Discord client not available in schedule_runner, skipping.")
            return

        await client.wait_until_ready()
        logger.info_system("Automated Schedule Runner initialized...")
        logger.debug_schedule(f"Schedule runner is ready, entering main loop")
        
        while not client.is_closed():
            try:
                now = datetime.datetime.now()
                current_time = now.strftime("%H:%M")
                current_day = now.strftime("%a").lower()
                
                channel = await self.discord_manager.get_default_channel()
                if not channel:
                    logger.error_system("Target channel not found in schedule_runner.")
                    continue
                
                for event in self.scheduled_events:
                    days = event.get("days", None)
                    if days and current_day not in days:
                        continue
                    
                    if event["time"] == current_time:
                        await self._execute_scheduled_event(event, channel)
                        
                        # Sleep to avoid executing the same event multiple times
                        await asyncio.sleep(60)
            except Exception as e:
                logger.error_system(f"Error in schedule runner: {e}")
            await asyncio.sleep(30)
    
    async def _execute_scheduled_event(self, event, channel=None):
        """Execute a specific scheduled event using the appropriate command handler"""
        # Resolve channel via discord_manager if not provided
        if not channel:
            channel = await self.discord_manager.get_default_channel()
        
        if not channel:
            logger.error_system("No default channel found for scheduled event execution")
            return
            
        # Get discord client (via ServiceLocator if needed, but here we can grab from managers)
        # Assuming discord_manager has a client or can send messages directly.
        # Actually, DiscordManager usually has a 'client' attribute or 'bot'.
        
        event_type = event.get("type")
        subtype = event.get("subtype")
        map_name = event.get("map_name")
        
        logger.debug_schedule(f"Executing scheduled event: type={event_type}, subtype={subtype}, map={map_name}")
        
        # Create a mock message object for command handlers
        class MockMessage:
            def __init__(self, channel):
                self.channel = channel
                self.content = ""
                self.author = SimpleNamespace(id="ScheduleSystem")
        
        mock_msg = MockMessage(channel)
        
        try:
            # Send initial notification
            display_name = f"'{map_name}'" if map_name else "all servers"
            event_display = f"{event_type} ({display_name})" if map_name else f"{event_type}"
            
            await self.discord_manager.send_temp_message(
                channel, f"⏰ Executing scheduled {event_display}..."
            )
            
            # Route to appropriate command handler
            if event_type == "shutdown":
                if subtype == "map" and map_name:
                    # Map-specific shutdown
                    mock_msg.content = f".shutdown {map_name}"
                    await self.server_control_handler.cmd_shutdown(
                        mock_msg, mock_msg.content, mock_msg.content.lower()
                    )
                else:
                    # Global shutdown
                    mock_msg.content = ".shutdown"
                    await self.server_control_handler.cmd_shutdown(
                        mock_msg, mock_msg.content, mock_msg.content.lower()
                    )
            
            elif event_type == "reboot":
                if subtype == "map" and map_name:
                    # Map-specific reboot
                    mock_msg.content = f".reboot {map_name}"
                    await self.server_control_handler.cmd_reboot(
                        mock_msg, mock_msg.content, mock_msg.content.lower()
                    )
                else:
                    # Global reboot
                    mock_msg.content = ".reboot"
                    await self.server_control_handler.cmd_reboot(
                        mock_msg, mock_msg.content, mock_msg.content.lower()
                    )
            
            elif event_type == "patch":
                # Updates are always global due to shared installation
                mock_msg.content = ".patch"
                await self.update_management_handler.cmd_patch(
                    mock_msg, mock_msg.content, mock_msg.content.lower()
                )
            
            elif event_type == "backup":
                if subtype == "map" and map_name:
                    # Map-specific backup
                    server = self.server_manager.find_server(map_name)
                    if server:
                        mock_msg.content = f".backup {server.name}"
                        await self.backup_restore_handler.cmd_backup(
                            mock_msg, mock_msg.content, mock_msg.content.lower()
                        )
                    else:
                        await self.discord_manager.send_temp_message(
                            channel, f"⚠️ Server '{map_name}' not found for backup"
                        )
                        logger.warning_system(f"Server '{map_name}' not found for scheduled backup")
                else:
                    # Global backup (handles "all")
                    mock_msg.content = ".backup all"
                    await self.backup_restore_handler.cmd_backup(
                        mock_msg, mock_msg.content, mock_msg.content.lower()
                    )
            
            else:
                logger.warning_system(f"Unknown scheduled event type: {event_type}")
                await self.discord_manager.send_temp_message(
                    channel, f"⚠️ Unknown scheduled event type: {event_type}"
                )
        
        except Exception as e:
            logger.error_system(f"Failed to execute scheduled {event_type} event: {e}")
            logger.debug_schedule(f"Exception in scheduled {event_type} execution: {e}")
            await self.discord_manager.send_temp_message(
                channel, f"⚠️ Failed to execute scheduled {event_type}: {str(e)[:100]}"
            )
