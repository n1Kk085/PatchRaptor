import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from patchraptor.player_management_handler import PlayerManagementHandler
from patchraptor.exceptions import RCONConnectionError, RCONCommandError, PlayerOperationError

class TestPlayerManagementHandler:
    @pytest.fixture
    def mock_server_manager(self):
        sm = Mock()
        sm.servers = []
        sm.get_display_name = Mock(return_value="The Island")
        return sm

    @pytest.fixture
    def mock_rcon_manager(self):
        rm = Mock()
        rm.execute_for_server = AsyncMock()
        rm.execute_command = AsyncMock()
        return rm

    @pytest.fixture
    def mock_discord_manager(self):
        dm = Mock()
        dm.send_temp_message = AsyncMock()
        return dm

    @pytest.fixture
    def mock_player_manager(self):
        pm = Mock()
        pm.update_active_players = AsyncMock()
        pm.get_total_players = AsyncMock(return_value=(10, {"The Island": []}))
        pm.ban_player = AsyncMock()
        pm.unban_player = AsyncMock()
        return pm

    @pytest.fixture
    def handler(self, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_player_manager):
        return PlayerManagementHandler(
            mock_server_manager,
            mock_rcon_manager,
            mock_discord_manager,
            mock_player_manager
        )

    @pytest.fixture
    def mock_server(self):
        server = Mock()
        server.name = "TestServer"
        server.rcon_ip = "127.0.0.1"
        server.rcon_port = 27020
        return server

    @pytest.fixture
    def mock_message(self):
        message = AsyncMock()
        message.channel = Mock()
        message.channel.send = AsyncMock()
        return message

    @pytest.mark.asyncio
    async def test_cmd_players(self, handler, mock_message, mock_player_manager):
        """Test .players command"""
        mock_player_manager.get_total_players.return_value = (5, {"The Island": [{"name": "Player1", "unique_id": "123", "session_time": "1h"}]})
        
        await handler.cmd_players(mock_message, ".players", ".players")
        
        mock_player_manager.update_active_players.assert_called_once()
        mock_message.channel.send.assert_called_once()
        # Verify embed content
        args, kwargs = mock_message.channel.send.call_args
        embed = kwargs['embed']
        assert "Total Players Online: 5" in embed.fields[0].value

    @pytest.mark.asyncio
    async def test_cmd_kick_success(self, handler, mock_server_manager, mock_rcon_manager, mock_server, mock_message):
        """Test .kick command success"""
        mock_server_manager.servers = [mock_server]
        
        await handler.cmd_kick(mock_message, ".kick BadPlayer", ".kick badplayer")
        
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, "KickPlayer BadPlayer")

    @pytest.mark.asyncio
    async def test_cmd_ban_with_id(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_server, mock_message):
        """Test .ban command with exact unique (hex) ID"""
        mock_server_manager.servers = [mock_server]
        hex_id = "1234567890abcdef1234567890abcdef" # 32 chars
        
        await handler.cmd_ban(mock_message, f".ban {hex_id}", f".ban {hex_id}")
        
        # Should call BanPlayer with ID directly, skipping lookup
        mock_rcon_manager.execute_for_server.assert_called_with(mock_server, f"BanPlayer {hex_id}")
        mock_player_manager.ban_player.assert_called_with(hex_id)

    @pytest.mark.asyncio
    async def test_cmd_ban_with_name_lookup_success(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_server, mock_message):
        """Test .ban command with name, requiring successful lookup via ListPlayers"""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = True
        
        # Mock ListPlayers output
        player_id = "1234567890abcdef1234567890abcdef"
        mock_rcon_manager.execute_for_server.return_value = f"0. BadPlayer, {player_id}"
        
        # We need to mock _get_player_info logic or just rely on the fact that execute_for_server return value is parsed
        # The implementation of _get_player_info calls execute_for_server("ListPlayers")
        # However, the Handler iterates all servers to execute the BAN command later.
        
        # First call is ListPlayers (lookup), Second call is BanPlayer (action)
        await handler.cmd_ban(mock_message, ".ban BadPlayer", ".ban badplayer")
        
        # Check calls
        # 1. Lookup
        # 2. Ban execution
        assert mock_rcon_manager.execute_for_server.call_count >= 2
        
        # Verify persistence called with the ID found
        mock_player_manager.ban_player.assert_called_with(player_id)

    @pytest.mark.asyncio
    async def test_cmd_unban_with_id(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_server, mock_message):
        """Test .unban command with Hex ID"""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = True
        hex_id = "1234567890abcdef1234567890abcdef"
        
        await handler.cmd_unban(mock_message, f".unban {hex_id}", f".unban {hex_id}")
        
        mock_rcon_manager.execute_command.assert_called() # Uses direct execute_command in unban logic
        mock_player_manager.unban_player.assert_any_call(hex_id)

    @pytest.mark.asyncio
    async def test_cmd_unban_fail_no_id(self, handler, mock_server_manager, mock_server, mock_discord_manager, mock_message):
        """Test .unban command failing when name provided but player not found online"""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = True
        
        # Mock ListPlayers returning empty
        handler.rcon_manager.execute_for_server.return_value = "No Players Connected"
        
        await handler.cmd_unban(mock_message, ".unban UnknownPlayer", ".unban unknownplayer")
        
        # Verify failure message
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Steam ID not found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_players_with_exception(self, handler, mock_player_manager, mock_discord_manager, mock_message):
        """Test .players command when update_active_players raises exception."""
        mock_player_manager.update_active_players.side_effect = Exception("Database error")
        
        await handler.cmd_players(mock_message, ".players", ".players")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Failed to fetch player data" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_players_list(self, handler, mock_player_manager, mock_message):
        """Test .players list command showing detailed player info."""
        mock_player_manager.get_total_players.return_value = (2, {
            "The Island": [
                {"name": "Player1", "unique_id": "123", "session_time": "1h"},
                {"name": "Player2", "unique_id": "456", "session_time": "2h"}
            ]
        })
        
        await handler.cmd_players(mock_message, ".players list", ".players list")
        
        args, kwargs = mock_message.channel.send.call_args
        embed = kwargs['embed']
        # Should have server details field
        assert len(embed.fields) > 1

    @pytest.mark.asyncio
    async def test_cmd_kick_insufficient_args(self, handler, mock_discord_manager, mock_message):
        """Test .kick command with insufficient arguments."""
        await handler.cmd_kick(mock_message, ".kick", ".kick")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_kick_rcon_error(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .kick command with RCON connection error."""
        mock_server_manager.servers = [mock_server]
        mock_rcon_manager.execute_for_server.side_effect = RCONConnectionError("connect", "Connection refused")
        
        await handler.cmd_kick(mock_message, ".kick BadPlayer", ".kick badplayer")
        
        # Should send failure message
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Failed to kick" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_kick_no_servers(self, handler, mock_server_manager, mock_discord_manager, mock_message):
        """Test .kick command when no servers are configured."""
        mock_server_manager.servers = []
        
        await handler.cmd_kick(mock_message, ".kick BadPlayer", ".kick badplayer")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "No servers found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_ban_insufficient_args(self, handler, mock_discord_manager, mock_message):
        """Test .ban command with insufficient arguments."""
        await handler.cmd_ban(mock_message, ".ban", ".ban")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_ban_lookup_failure_fallback_to_name(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_server, mock_message):
        """Test .ban command when player lookup fails, falls back to name."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = True
        
        # First call is ListPlayers (lookup) - returns no match
        # Second call is BanPlayer (action)
        mock_rcon_manager.execute_for_server.side_effect = [
            "No Players Connected",  # ListPlayers returns empty
            None  # BanPlayer succeeds
        ]
        
        await handler.cmd_ban(mock_message, ".ban UnknownPlayer", ".ban unknownplayer")
        
        # Should use player name for ban command
        assert mock_rcon_manager.execute_for_server.call_count >= 2
        mock_player_manager.ban_player.assert_called_with("UnknownPlayer")

    @pytest.mark.asyncio
    async def test_cmd_ban_rcon_error(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .ban command with RCON command error."""
        mock_server_manager.servers = [mock_server]
        mock_rcon_manager.execute_for_server.side_effect = RCONCommandError("BanPlayer", "TestServer", "Command failed")
        
        await handler.cmd_ban(mock_message, ".ban BadPlayer", ".ban badplayer")
        
        # Should send failure message
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Failed to ban" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_ban_player_operation_error(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_server, mock_message):
        """Test .ban command when player_manager.ban_player raises error."""
        mock_server_manager.servers = [mock_server]
        mock_player_manager.ban_player.side_effect = PlayerOperationError("ban", "BadPlayer", "Database error")
        
        await handler.cmd_ban(mock_message, ".ban BadPlayer", ".ban badplayer")
        
        # Should still complete ban on servers, just log warning about ban list
        mock_rcon_manager.execute_for_server.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_ban_no_servers(self, handler, mock_server_manager, mock_discord_manager, mock_message):
        """Test .ban command when no servers are configured."""
        mock_server_manager.servers = []
        
        await handler.cmd_ban(mock_message, ".ban BadPlayer", ".ban badplayer")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "No servers found" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_unban_insufficient_args(self, handler, mock_discord_manager, mock_message):
        """Test .unban command with insufficient arguments."""
        await handler.cmd_unban(mock_message, ".unban", ".unban")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "Usage" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_unban_no_running_servers(self, handler, mock_server_manager, mock_discord_manager, mock_server, mock_message):
        """Test .unban command when no servers are running."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = False
        hex_id = "1234567890abcdef1234567890abcdef"
        
        await handler.cmd_unban(mock_message, f".unban {hex_id}", f".unban {hex_id}")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        assert "no servers running" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_unban_player_operation_error(self, handler, mock_server_manager, mock_rcon_manager, mock_player_manager, mock_discord_manager, mock_server, mock_message):
        """Test .unban command when player_manager.unban_player raises error."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = True
        hex_id = "1234567890abcdef1234567890abcdef"
        mock_player_manager.unban_player.side_effect = PlayerOperationError("unban", hex_id, "Not in ban list")
        
        await handler.cmd_unban(mock_message, f".unban {hex_id}", f".unban {hex_id}")
        
        # Should still attempt RCON unban
        mock_rcon_manager.execute_command.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_unban_unexpected_error(self, handler, mock_server_manager, mock_rcon_manager, mock_discord_manager, mock_server, mock_message):
        """Test .unban command with unexpected exception."""
        mock_server_manager.servers = [mock_server]
        mock_server_manager.is_specific_server_running.return_value = True
        hex_id = "1234567890abcdef1234567890abcdef"
        mock_rcon_manager.execute_command.side_effect = Exception("Unexpected error")
        
        await handler.cmd_unban(mock_message, f".unban {hex_id}", f".unban {hex_id}")
        
        mock_discord_manager.send_temp_message.assert_called()
        args, _ = mock_discord_manager.send_temp_message.call_args
        # When execute_command fails, it falls through to "no servers running" message
        assert "no servers running" in args[1] or "Unexpected error" in args[1]

    @pytest.mark.asyncio
    async def test_get_player_info_success(self, handler, mock_rcon_manager, mock_server):
        """Test _get_player_info successfully finding player."""
        mock_rcon_manager.execute_for_server.return_value = "0. TestPlayer, 1234567890abcdef1234567890abcdef"
        
        success, info = await handler._get_player_info(mock_server, "TestPlayer")
        
        assert success is True
        assert "unique_id" in info

    @pytest.mark.asyncio
    async def test_get_player_info_not_found(self, handler, mock_rcon_manager, mock_server):
        """Test _get_player_info when player not in list."""
        mock_rcon_manager.execute_for_server.return_value = "No Players Connected"
        
        success, info = await handler._get_player_info(mock_server, "UnknownPlayer")
        
        assert success is False
        assert info == {}

    @pytest.mark.asyncio
    async def test_get_player_info_rcon_error(self, handler, mock_rcon_manager, mock_server):
        """Test _get_player_info with RCON connection error."""
        mock_rcon_manager.execute_for_server.side_effect = RCONConnectionError("connect", "Connection refused")
        
        success, info = await handler._get_player_info(mock_server, "TestPlayer")
        
        assert success is False
        assert info == {}

    @pytest.mark.asyncio
    async def test_get_player_info_unexpected_error(self, handler, mock_rcon_manager, mock_server):
        """Test _get_player_info with unexpected exception."""
        mock_rcon_manager.execute_for_server.side_effect = Exception("Unexpected error")
        
        success, info = await handler._get_player_info(mock_server, "TestPlayer")
        
        assert success is False
        assert info == {}

    @pytest.mark.asyncio
    async def test_get_player_info_malformed_output(self, handler, mock_rcon_manager, mock_server):
        """Test _get_player_info with malformed ListPlayers output."""
        mock_rcon_manager.execute_for_server.return_value = "TestPlayer"  # Missing ID
        
        success, info = await handler._get_player_info(mock_server, "TestPlayer")
        
        # Should not find player due to malformed output
        assert success is False
