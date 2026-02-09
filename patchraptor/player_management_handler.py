import asyncio
import discord
from .log_manager import logger
from .server_manager import ServerManager
from .rcon_manager import RCONManager
from .discord_manager import DiscordManager
from .player_manager import PlayerManager
from .exceptions import (
    ServerError,
    ServerNotFoundError,
    ServerNotRunningError,
    ServerAlreadyRunningError,
    ServerOperationError,
    RCONError,
    RCONConnectionError,
    RCONCommandError,
    PlayerError,
    PlayerNotFoundError,
    PlayerOperationError
)


class PlayerManagementHandler:
    """Handles player management commands: players, kick, ban, unban"""
    
    def __init__(
        self,
        server_manager: ServerManager,
        rcon_manager: RCONManager,
        discord_manager: DiscordManager,
        player_manager: PlayerManager
    ):
        self.server_manager = server_manager
        self.rcon_manager = rcon_manager
        self.discord_manager = discord_manager
        self.player_manager = player_manager

    async def cmd_players(self, message, content: str, content_lower: str):
        """Handle .players command - show player information"""
        logger.info_command(".players received")
        parts = content.split()
        
        try:
            # Ensure player data is fully updated before getting the count
            await self.player_manager.update_active_players()
            
            # Get fresh data after update
            total_players, server_details = await self.player_manager.get_total_players()
            
            # Debug log the raw data
            logger.debug_player(f"Player data: {server_details}")
            
        except Exception as e:
            logger.error_player(f"Error in .players command: {str(e)}")
            await self.discord_manager.send_temp_message(
                message.channel, f"❌ Failed to fetch player data: {str(e)}"
            )
            return
        servers_checked = len(self.server_manager.servers)
        
        import discord as _discord
        embed = _discord.Embed(title="Player Information", color=0x99AAB5)
        summary_text = f"Total Players Online: {total_players}\nServers Checked: {servers_checked}"
        embed.add_field(name="Summary", value=summary_text, inline=False)
        
        if len(parts) > 1 and parts[1].lower() == "list":
            lines = []
            for display_name, players in server_details.items():
                if players:
                    player_list = "\n".join([f"{p['name']} | {p['unique_id']} | {p['session_time']}" for p in players])
                else:
                    player_list = "No players online"
                lines.append(f"**{display_name}**\n{player_list}")
            
            if lines:
                embed.add_field(name="Server Details", value="\n\n".join(lines), inline=False)
        
        await message.channel.send(embed=embed)

    async def cmd_kick(self, message, content: str, content_lower: str):
        """Handle .kick command - kick players from all servers"""
        logger.info_command(".kick received")
        parts = content.split()
        if len(parts) < 2:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Usage: .kick <player_name>"
            )
            return
        
        player_name = " ".join(parts[1:])
        kick_command = f"KickPlayer {player_name}"
        
        logger.debug_player(f"Attempting to kick player '{player_name}' across {len(self.server_manager.servers)} servers")
        
        successful_kicks = []
        failed_kicks = []
        
        # Iterate through all servers in the cluster
        for server in self.server_manager.servers:
            logger.debug_player(f"Processing kick for server: {server.name} ({self.server_manager.get_display_name(server)})")
            try:
                logger.debug_player(f"Executing RCON command on {server.name}: {kick_command}")
                await self.rcon_manager.execute_for_server(server, kick_command)
                successful_kicks.append(self.server_manager.get_display_name(server))
                logger.info_system(f"Kicked player '{player_name}' from {server.name}")
                logger.debug_player(f"Kick successful for {server.name}")
            except (RCONConnectionError, RCONCommandError) as e:
                failed_kicks.append(f"{self.server_manager.get_display_name(server)}: {e.reason}")
                logger.warning_system(f"Failed to kick player '{player_name}' from {server.name}: {e.reason}")
                logger.debug_player(f"Kick failed for {server.name}: {e.reason}")
        
        logger.debug_player(f"Kick operation summary: {len(successful_kicks)} successful, {len(failed_kicks)} failed")
        
        # Send summary message
        if successful_kicks:
            await self.discord_manager.send_temp_message(
                message.channel, f"✅ Kicked player '{player_name}'"
            )
        
        if failed_kicks:
            await self.discord_manager.send_temp_message(
                message.channel, f"⚠️ Failed to kick '{player_name}'"
            )
        
        if not successful_kicks and not failed_kicks:
            await self.discord_manager.send_temp_message(
                message.channel, f"⚠️ No servers found to kick player '{player_name}' from"
            )

    async def cmd_ban(self, message, content: str, content_lower: str):
        """Handle .ban command - ban players from all servers"""
        logger.info_command(".ban received")
        parts = content.split()
        if len(parts) < 2:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Usage: .ban <player_name>"
            )
            return
        
        player_input = " ".join(parts[1:])
        successful_bans = []
        failed_bans = []
        player_unique_id = None
        player_name = player_input
        
        # Check if input looks like a unique ID (hexadecimal format)
        import re
        logger.debug_player(f"BAN: Checking if input '{player_input}' matches unique ID pattern")
        if re.match(r'^[0-9a-fA-F]{32}$', player_input):
            # Input is already a unique ID
            player_unique_id = player_input
            logger.debug_player(f"BAN: Input '{player_input}' recognized as unique ID")
        else:
            # Input is a player name, need to look up unique ID
            player_name = player_input
            logger.debug_player(f"BAN: Input '{player_input}' treated as player name, looking up unique ID")
            logger.info_system(f"BAN: Input '{player_input}' treated as player name, looking up unique ID")
            
            logger.debug_player(f"Attempting to ban player '{player_name}' across {len(self.server_manager.servers)} servers")
            
            # Try to get player's unique ID from the first available server
            logger.debug_player(f"Searching for player unique ID for '{player_name}'")
            for server in self.server_manager.servers:
                if self.server_manager.is_specific_server_running(server):
                    logger.debug_player(f"Checking server {server.name} for player info")
                    try:
                        success, player_info = await self._get_player_info(server, player_name)
                        if success and player_info.get('unique_id'):
                            player_unique_id = player_info['unique_id']
                            logger.debug_player(f"Found unique ID for '{player_name}': {player_unique_id} on server {server.name}")
                            break
                        else:
                            logger.debug_player(f"Player info not found on server {server.name}")
                    except Exception as e:
                        logger.debug_player(f"Error getting player info from server {server.name}: {e}")
                        continue
        
        # Determine ban command based on whether we have the unique ID
        if player_unique_id:
            ban_command = f"BanPlayer {player_unique_id}"
            logger.info_system(f"Banning player '{player_name}' by unique ID: {player_unique_id}")
            logger.debug_player(f"Using unique ID for ban command: {ban_command}")
        else:
            ban_command = f"BanPlayer {player_name}"
            logger.info_system(f"Banning player '{player_name}' by name (unique ID not found)")
            logger.debug_player(f"Using player name for ban command: {ban_command}")
        
        # Iterate through all servers in the cluster
        for server in self.server_manager.servers:
            logger.debug_player(f"Processing ban for server: {server.name} ({self.server_manager.get_display_name(server)})")
            try:
                logger.debug_player(f"Executing RCON command on {server.name}: {ban_command}")
                await self.rcon_manager.execute_for_server(server, ban_command)
                successful_bans.append(self.server_manager.get_display_name(server))
                logger.info_system(f"Banned player '{player_name}' from {server.name}")
                logger.debug_player(f"Ban successful for {server.name}")
            except (RCONConnectionError, RCONCommandError) as e:
                failed_bans.append(f"{self.server_manager.get_display_name(server)}: {e.reason}")
                logger.warning_system(f"Failed to ban player '{player_name}' from {server.name}: {e.reason}")
                logger.debug_player(f"Ban failed for {server.name}: {e.reason}")
        
        logger.debug_player(f"Ban operation summary: {len(successful_bans)} successful, {len(failed_bans)} failed")
        
        # Add to player manager's ban list for tracking
        try:
            await self.player_manager.ban_player(player_unique_id or player_name)
            logger.debug_player(f"Added player '{player_name}' to ban list with ID: {player_unique_id or 'unknown'}")
        except PlayerOperationError as e:
            logger.warning_system(f"Failed to add player '{player_name}' to ban list: {e.reason}")
            logger.debug_player(f"Ban list addition failed for '{player_name}': {e.reason}")
        
        # Send summary message
        if successful_bans:
            await self.discord_manager.send_temp_message(
                message.channel, f"🚫 Banned player '{player_name}'"
            )
        
        if failed_bans:
            await self.discord_manager.send_temp_message(
                message.channel, f"⚠️ Failed to ban '{player_name}'"
            )
        
        if not successful_bans and not failed_bans:
            await self.discord_manager.send_temp_message(
                message.channel, f"⚠️ No servers found to ban player '{player_name}' from"
            )

    async def cmd_unban(self, message, content: str, content_lower: str):
        """Handle .unban command - unban players"""
        logger.info_command(".unban received")
        parts = content.split()
        if len(parts) < 2:
            await self.discord_manager.send_temp_message(
                message.channel, "⚠️ Usage: .unban <player_name>"
            )
            return
        
        player_input = " ".join(parts[1:])
        player_unique_id = None
        player_name = player_input
        
        # Check if input looks like a unique ID (hexadecimal format)
        import re
        if re.match(r'^[0-9a-fA-F]{32}$', player_input):
            # Input is already a unique ID
            player_unique_id = player_input
        else:
            # Input is a player name, need to look up unique ID
            player_name = player_input
            
            # Try to get player's unique ID from the first available server
            for server in self.server_manager.servers:
                if self.server_manager.is_specific_server_running(server):
                    try:
                        success, player_info = await self._get_player_info(server, player_name)
                        if success and player_info.get('unique_id'):
                            player_unique_id = player_info['unique_id']
                            break
                    except Exception as e:
                        continue
        
        # Use ARK RCON to unban the player
        try:
            if player_unique_id:
                # Use the unique ID (Steam ID) for unban command
                unban_command = f"UnbanPlayer {player_unique_id}"
                logger.info_system(f"Unbanning player '{player_name}' by Steam ID: {player_unique_id}")
                
                # Execute unban command on all running servers
                success = False
                for server in self.server_manager.servers:
                    if self.server_manager.is_specific_server_running(server):
                        try:
                            await self.rcon_manager.execute_command(server.rcon_ip, server.rcon_port, server.rcon_password, unban_command)
                            logger.info_system(f"Successfully executed unban command on server {server.name}")
                            success = True
                        except Exception as e:
                            logger.warning_system(f"Failed to execute unban command on server {server.name}: {e}")
                
                if success:
                    # Also unban from PlayerManager/bans.json cache
                    try:
                        await self.player_manager.unban_player(player_name)
                        if player_unique_id:
                            await self.player_manager.unban_player(player_unique_id)
                        logger.info_system(f"Removed player '{player_name}' from local ban list")
                    except Exception as e:
                         logger.warning_system(f"Failed to remove '{player_name}' from local ban list: {e}")

                    logger.info_system(f"Unbanned player '{player_name}'")
                    await self.discord_manager.send_temp_message(
                        message.channel, f"✅ Unbanned player '{player_name}' from all servers"
                    )
                else:
                    await self.discord_manager.send_temp_message(
                        message.channel, f"⚠️ Failed to unban player '{player_name}' - no servers running"
                    )
            else:
                # No unique ID found, can't unban without Steam ID
                await self.discord_manager.send_temp_message(
                    message.channel, f"⚠️ Cannot unban '{player_name}' - Steam ID not found. Player must be online to get Steam ID."
                )
        except PlayerOperationError as e:
            logger.warning_system(f"Failed to unban player '{player_name}': {e.reason}")
            logger.debug_player(f"Unban operation failed for '{player_name}': {e.reason}")
            await self.discord_manager.send_temp_message(
                message.channel, f"❌ Failed to unban player '{player_name}': {e.reason}"
            )
        except Exception as e:
            logger.warning_system(f"Unexpected error during unban of '{player_name}': {e}")
            logger.debug_player(f"Unexpected error during unban of '{player_name}': {e}")
            await self.discord_manager.send_temp_message(
                message.channel, f"❌ Unexpected error during unban: {e}"
            )

    async def _get_player_info(self, server, player_name):
        """Get detailed player information including unique ID"""
        logger.debug_player(f"Getting player info for '{player_name}' from server {server.name}")
        try:
            # Try to get player list and find the specific player
            logger.debug_player(f"Executing ListPlayers command on server {server.name}")
            output = await self.rcon_manager.execute_for_server(server, "ListPlayers")
            logger.debug_player(f"ListPlayers output from {server.name}: {output[:200]}...")
            
            # Parse the player list output to find the player and their ID
            # This is a simplified approach - actual parsing depends on ARK's output format
            lines = output.split('\n')
            logger.debug_player(f"Parsing {len(lines)} lines from player list")
            
            for i, line in enumerate(lines):
                logger.debug_player(f"Checking line {i+1}: {line[:100]}...")
                if player_name.lower() in line.lower():
                    logger.debug_player(f"Found potential match for '{player_name}' in line {i+1}")
                    # Extract player ID from the line (format may vary)
                    # This is a basic implementation - you may need to adjust based on actual ARK output
                    parts = line.split()
                    if len(parts) >= 2:
                        player_id = parts[-1]  # Usually the last part is the Steam ID
                        logger.debug_player(f"Extracted player ID: {player_id} for '{player_name}'")
                        return True, {'name': player_name, 'unique_id': player_id}
                    else:
                        logger.debug_player(f"Could not extract player ID from line: {line}")
            
            logger.debug_player(f"Player '{player_name}' not found in player list from server {server.name}")
            return False, {}
            
        except (RCONConnectionError, RCONCommandError) as e:
            logger.error_system(f"RCON error getting player info for {player_name}: {e.reason}")
            logger.debug_player(f"RCON error details for '{player_name}' on {server.name}: {e.reason}")
            return False, {}
        except Exception as e:
            logger.error_system(f"Unexpected error getting player info for {player_name}: {e}")
            logger.debug_player(f"Unexpected error details for '{player_name}' on {server.name}: {e}")
            return False, {}
