from .log_manager import logger
from .server_manager import ServerManager
from .discord_manager import DiscordManager
from .schedule_manager import ScheduleManager
from .exceptions import (
    ServerError,
    ServerNotFoundError,
    ScheduleError,
    ScheduleParseError,
    ScheduleOperationError
)


class ScheduleHandler:
    """Handles scheduling commands: schedule"""
    
    def __init__(
        self,
        server_manager: ServerManager,
        discord_manager: DiscordManager,
        schedule_manager: ScheduleManager
    ):
        self.server_manager = server_manager
        self.discord_manager = discord_manager
        self.schedule_manager = schedule_manager

    async def cmd_schedule(self, message, content: str, content_lower: str):
        """Handle .schedule command"""
        logger.info_command(".schedule received")
        args = content.split()[1:]
        
        if len(args) == 0:
            # Step 1: Show current schedule
            logger.info_system("Retrieving current scheduled events...")
            events = self.schedule_manager.get_events()
            if not events:
                logger.info_system("No scheduled events found")
                await self.discord_manager.send_temp_message(
                    message.channel, "ℹ️ No scheduled events."
                )
                return
            
            logger.info_system(f"Found {len(events)} scheduled events")
            lines = ["Scheduled Events:"]
            for evt in events:
                if evt.get("subtype") == "all":
                    desc = f"- {evt['type'].capitalize()} all at {evt['time']}"
                elif evt.get("subtype") == "map":
                    map_name = evt.get('map_name', 'unknown')
                    try:
                        server = self.server_manager.find_server(map_name)
                        display_name = self.server_manager.get_display_name(server) if server else map_name
                    except ServerNotFoundError:
                        display_name = map_name
                    desc = f"- {evt['type'].capitalize()} {display_name} at {evt['time']}"
                else:
                    desc = f"- {evt['type'].capitalize()} at {evt['time']}"
                
                if "days" in evt:
                    desc += f" on {', '.join(evt['days'])}"
                else:
                    desc += " daily"
                lines.append(desc)
            
            logger.info_system("Displaying scheduled events list")
            await self.discord_manager.send_temp_message(message.channel, "\n".join(lines))
            return
        
        cmd = args[0].lower()
        
        if cmd == "add":
            logger.info_system("Starting schedule add process...")
            if len(args) < 3:
                logger.warning_system("Insufficient arguments for schedule add")
                await self.discord_manager.send_temp_message(
                    message.channel, 
                    "⚠️ Usage: .schedule add <type> <time> OR .schedule add <type> <days> <time>\n"
                    "Examples:\n  .schedule add shutdown 03:00\n  .schedule add backup all 02:00\n  .schedule add backup ragnarok mon fri 18:00"
                )
                return
            
            # Step 1: Validate event type
            logger.info_system("Validating event type...")
            evt_type = args[1].lower()
            if evt_type not in ("shutdown", "reboot", "update", "backup"):
                logger.warning_system(f"Invalid event type: {evt_type}")
                await self.discord_manager.send_temp_message(
                    message.channel, "⚠️ Invalid event type. Use: shutdown, reboot, update, or backup"
                )
                return
            
            # Step 2: Parse and validate time
            logger.info_system("Parsing and validating time format...")
            time_str = args[-1]
            try:
                import datetime
                datetime.datetime.strptime(time_str, "%H:%M")
                logger.info_system(f"Time format validated: {time_str}")
            except Exception:
                logger.warning_system(f"Invalid time format: {time_str}")
                await self.discord_manager.send_temp_message(
                    message.channel, "⚠️ Invalid time format. Use HH:MM (24-hour format)"
                )
                return
            
            # Step 3: Parse additional arguments
            logger.info_system("Parsing additional arguments...")
            middle_args = args[2:-1]
            valid_days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
            days = []
            backup_target = None
            
            for arg in middle_args:
                arg_lower = arg.lower()[:3]
                if arg_lower in valid_days:
                    days.append(arg_lower)
                elif evt_type == "backup" and not backup_target:
                    backup_target = arg.lower()
            
            logger.info_system(f"Parsed arguments - days: {days}, backup_target: {backup_target}")
            
            # Step 4: Handle scheduling based on event type
            logger.info_system(f"Processing {evt_type} event scheduling...")
            if evt_type == "backup":
                if not backup_target:
                    backup_target = "all"
                
                if backup_target == "all":
                    subtype = "all"
                    map_name = None
                    schedule_desc = f"backup all at {time_str}"
                    logger.info_system("Scheduling backup for all servers")
                else:
                    try:
                        logger.info_system(f"Finding server for backup: {backup_target}")
                        server = self.server_manager.find_server(backup_target)
                    except ServerNotFoundError:
                        logger.warning_system(f"Server not found for backup: {backup_target}")
                        await self.discord_manager.send_temp_message(
                            message.channel, f"⚠️ No server found with name '{backup_target}'."
                        )
                        return
                    subtype = "map"
                    map_name = backup_target
                    display_name = self.server_manager.get_display_name(server)
                    schedule_desc = f"backup {display_name} at {time_str}"
                    logger.info_system(f"Scheduling backup for specific server: {display_name}")
            else:
                # Other event types
                subtype = "all"
                map_name = None
                schedule_desc = f"{evt_type} all at {time_str}"
                logger.info_system(f"Scheduling {evt_type} for all servers")
            
            if days:
                schedule_desc += f" on {' '.join(days)}"
                logger.info_system(f"Scheduling for specific days: {days}")
            else:
                schedule_desc += " daily"
                logger.info_system("Scheduling for daily execution")
            
            # Step 5: Add the scheduled event
            logger.info_system(f"Adding scheduled event: {schedule_desc}")
            try:
                success = self.schedule_manager.add_event(evt_type, time_str, days, map_name, subtype)
                if success:
                    logger.info_system(f"Successfully scheduled event: {schedule_desc}")
                    await self.discord_manager.send_temp_message(
                        message.channel, f"🦖 Scheduled {schedule_desc}"
                    )
                else:
                    logger.error_system("Failed to add scheduled event")
                    await self.discord_manager.send_temp_message(
                        message.channel, "❌ Failed to add scheduled event."
                    )
            except ScheduleOperationError as e:
                logger.error_system(f"Schedule operation error: {e.reason}")
                await self.discord_manager.send_temp_message(
                    message.channel, f"❌ Failed to add scheduled event: {e.reason}"
                )
        
        elif cmd == "clear":
            logger.info_system("Starting schedule clear process...")
            if len(args) > 2:
                logger.warning_system("Invalid arguments for schedule clear")
                await self.discord_manager.send_temp_message(
                    message.channel, "⚠️ Usage: .schedule clear [all|shutdown|reboot|update|backup]"
                )
                return
            
            if len(args) == 2:
                # Step 1: Clear specific event type
                type_to_clear = args[1].lower()
                logger.info_system(f"Clearing scheduled events of type: {type_to_clear}")
                
                if type_to_clear == "all":
                    removed_count = self.schedule_manager.clear_events()
                    logger.info_system(f"Cleared all scheduled events ({removed_count} removed)")
                    await self.discord_manager.send_temp_message(
                        message.channel, "🦖 Cleared all scheduled events."
                    )
                elif type_to_clear in ("shutdown", "reboot", "update", "backup"):
                    logger.info_system(f"Clearing {type_to_clear} events...")
                    removed_count = self.schedule_manager.clear_events(type_to_clear)
                    if removed_count > 0:
                        logger.info_system(f"Removed {removed_count} scheduled '{type_to_clear}' event(s)")
                        await self.discord_manager.send_temp_message(
                            message.channel, f"🦖 Removed {removed_count} scheduled '{type_to_clear}' event(s)."
                        )
                    else:
                        logger.info_system(f"No scheduled '{type_to_clear}' events found to remove")
                        await self.discord_manager.send_temp_message(
                            message.channel, f"ℹ️ No scheduled '{type_to_clear}' events found to remove."
                        )
                else:
                    logger.warning_system(f"Invalid event type for clear: {type_to_clear}")
                    await self.discord_manager.send_temp_message(
                        message.channel, f"⚠️ Invalid event type '{type_to_clear}'. Use: all, shutdown, reboot, update, or backup"
                    )
            else:
                # Step 1: Clear all events
                logger.info_system("Clearing all scheduled events...")
                removed_count = self.schedule_manager.clear_events()
                logger.info_system(f"Cleared all scheduled events ({removed_count} removed)")
                await self.discord_manager.send_temp_message(
                    message.channel, "🦖 Cleared all scheduled events."
                )
        else:
            logger.warning_system(f"Unknown schedule command: {cmd}")
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Unknown .schedule command. Use: add, clear"
            )
