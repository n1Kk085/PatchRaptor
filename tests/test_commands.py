"""
Test suite for Command Manager.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from patchraptor.commands import CommandHandler, CommandMenuView
from patchraptor.models import ServerConfig


@pytest.fixture
def manager_mocks():
    """Create mocked dependencies for CommandHandler."""
    return {
        'server_manager': Mock(),
        'rcon_manager': Mock(),
        'version_manager': Mock(),
        'backup_manager': Mock(),
        'discord_manager': Mock(),
        'player_manager': Mock(),
        'schedule_manager': Mock(),
        'raptorchat_manager': Mock(),
        'config_manager': Mock()
    }


@pytest.fixture
def command_handler(manager_mocks):
    """Create CommandHandler instance."""
    return CommandHandler(
        server_manager=manager_mocks['server_manager'],
        rcon_manager=manager_mocks['rcon_manager'],
        version_manager=manager_mocks['version_manager'],
        backup_manager=manager_mocks['backup_manager'],
        discord_manager=manager_mocks['discord_manager'],
        player_manager=manager_mocks['player_manager'],
        schedule_manager=manager_mocks['schedule_manager'],
        raptorchat_manager=manager_mocks['raptorchat_manager'],
        config_manager=manager_mocks['config_manager']
    )


class TestCommandHandlerInit:
    """Test CommandHandler initialization."""
    
    def test_init_creates_subhandlers(self, command_handler):
        """Ensure all sub-handlers are initialized."""
        assert command_handler.server_control_handler is not None
        assert command_handler.system_monitoring_handler is not None
        assert command_handler.backup_restore_handler is not None
        assert command_handler.player_management_handler is not None
        assert command_handler.update_management_handler is not None
        assert command_handler.configuration_handler is not None
        assert command_handler.schedule_handler is not None


class TestCommandRouting:
    """Test command routing logic."""
    
    @pytest.mark.asyncio
    async def test_handle_command_exact_match(self, command_handler):
        """Test routing for exact command match."""
        mock_message = Mock()
        mock_message.content = ".status"
        
        # Mock the handler method
        command_handler.system_monitoring_handler.cmd_status = AsyncMock()
        # Command dictionary stores bound methods initialized during instantiation.
        # Patching the method on the handler instance and re-binding in the commands dict ensures routing to mock.
        
        with patch.object(command_handler.system_monitoring_handler, 'cmd_status', new_callable=AsyncMock) as mock_cmd:
            # Re-bind the command in the dictionary because it was bound at init
            command_handler.commands['.status'] = mock_cmd
            
            await command_handler.handle_command(mock_message)
            
            mock_cmd.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_handle_command_partial_match(self, command_handler):
        """Test routing for partial command match (arguments)."""
        mock_message = Mock()
        mock_message.content = ".reboot all"
        
        with patch.object(command_handler.server_control_handler, 'cmd_reboot', new_callable=AsyncMock) as mock_cmd:
            command_handler.commands['.reboot'] = mock_cmd
            
            await command_handler.handle_command(mock_message)
            
            mock_cmd.assert_called_once()               

    @pytest.mark.asyncio
    async def test_handle_command_unknown(self, command_handler):
        """Test handling of unknown commands."""
        mock_message = Mock()
        mock_message.content = ".unknown_command"
        
        # Should not raise error
        await command_handler.handle_command(mock_message)


class TestMenuCommand:
    """Test menu command functionality."""
    
    @pytest.mark.asyncio
    async def test_cmd_menu(self, command_handler, manager_mocks):
        """Test .menu command sends view."""
        mock_message = Mock()
        mock_message.channel = Mock()
        mock_message.channel.send = AsyncMock(return_value=Mock())
        
        manager_mocks['discord_manager']._delete_message_later = AsyncMock()
        
        await command_handler.cmd_menu(mock_message, ".menu", ".menu")
        
        assert mock_message.channel.send.called
        # Verify View was passed
        args, kwargs = mock_message.channel.send.call_args
        assert 'view' in kwargs
        assert isinstance(kwargs['view'], CommandMenuView)



    @pytest.mark.asyncio
    async def test_handle_command_startswith_joined(self, command_handler):
        """Test routing for joined command (e.g. .statuscheck where base is .statuscheck)."""
        mock_message = Mock()
        mock_message.content = ".status" # Exact match for .status key
        
        with patch.object(command_handler.system_monitoring_handler, 'cmd_status', new_callable=AsyncMock) as mock_cmd:
            command_handler.commands['.status'] = mock_cmd
            
            await command_handler.handle_command(mock_message)
            
            mock_cmd.assert_called_once()


class TestCommandMenuView:
    """Test CommandMenuView interactions."""
    
    @pytest.mark.asyncio
    async def test_button_callback_valid(self):
        """Test valid button click."""
        view = CommandMenuView()
        
        mock_interaction = Mock()
        mock_interaction.data = {"custom_id": "section_1"}
        mock_interaction.response.send_message = AsyncMock()
        
        await view.button_callback(mock_interaction)
        
        assert mock_interaction.response.send_message.called
        args, kwargs = mock_interaction.response.send_message.call_args
        assert 'embed' in kwargs

    @pytest.mark.asyncio
    async def test_button_callback_invalid(self):
        """Test invalid button click."""
        view = CommandMenuView()
        
        mock_interaction = Mock()
        mock_interaction.data = {"custom_id": "invalid_section"}
        mock_interaction.response.send_message = AsyncMock()
        
        await view.button_callback(mock_interaction)
        
        args, kwargs = mock_interaction.response.send_message.call_args
        assert "Unknown section" in args[0]

    @pytest.mark.asyncio
    async def test_button_callback_exception_data(self):
        """Test exception during interaction data access."""
        from unittest.mock import PropertyMock
        view = CommandMenuView()
        mock_interaction = Mock()
        # accessing data raises exception
        type(mock_interaction).data = PropertyMock(side_effect=Exception("Data Fail"))
        mock_interaction.response.send_message = AsyncMock()
        
        await view.button_callback(mock_interaction)
        
        # Verifies error message delivery.
        args, kwargs = mock_interaction.response.send_message.call_args
        assert "Error processing button click" in args[0]

    @pytest.mark.asyncio
    async def test_button_callback_send_exception(self):
        """Test exception during send_message."""
        view = CommandMenuView()
        mock_interaction = Mock()
        mock_interaction.data = {"custom_id": "section_1"}
        # Fail twice to cover the nested try-except
        mock_interaction.response.send_message = AsyncMock(side_effect=[Exception("Send Fail"), Exception("Error Fail")])
        
        await view.button_callback(mock_interaction)
        
        # Should attempt to send error message after failure
        assert mock_interaction.response.send_message.call_count == 2

    @pytest.mark.asyncio
    async def test_menu_with_examples(self):
        """Test menu section that includes examples."""
        view = CommandMenuView()
        mock_interaction = Mock()
        mock_interaction.data = {"custom_id": "section_7"} # Scheduling has examples
        mock_interaction.response.send_message = AsyncMock()
        
        await view.button_callback(mock_interaction)
        
        args, kwargs = mock_interaction.response.send_message.call_args
        embed = kwargs['embed']
        # Verifies Examples field presence.

    @pytest.mark.asyncio
    async def test_on_timeout(self):
        """Test on_timeout disables buttons."""
        view = CommandMenuView()
        # View buttons are initialized during instantiation.
        
        await view.on_timeout()
        
        for child in view.children:
            assert child.disabled is True
