"""
Test suite for RCON Manager - validates command safety and execution.
"""
import pytest
import asyncio
import subprocess
from unittest.mock import Mock, patch, AsyncMock
from patchraptor.rcon_manager import RCONManager
from patchraptor.models import ServerConfig
from patchraptor.exceptions import (
    RCONValidationError,
    RCONCommandError,
    RCONConnectionError
)


class TestRCONCommandValidation:
    """Test RCON command validation and security."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rcon = RCONManager(rcon_tool="rcon-cli")
    
    def test_safe_commands_allowed(self):
        """Test that safe commands pass validation."""
        safe_commands = [
            "SaveWorld",
            "DoExit",
            "ServerChat Hello World",
            "ListPlayers",
            "KickPlayer PlayerName",
        ]
        
        for cmd in safe_commands:
            # Should not raise exception
            try:
                self.rcon._validate_rcon_command(cmd)
            except RCONValidationError:
                pytest.fail(f"Safe command '{cmd}' was rejected")
    
    def test_dangerous_characters_blocked(self):
        """Test that dangerous characters are blocked."""
        dangerous_commands = [
            "SaveWorld; DoExit",  # Semicolon
            "SaveWorld && DoExit",  # Double ampersand
            "SaveWorld | DoExit",  # Pipe
            "SaveWorld `whoami`",  # Backticks
            "SaveWorld $(whoami)",  # Command substitution
        ]
        
        for cmd in dangerous_commands:
            with pytest.raises(RCONValidationError):
                self.rcon._validate_rcon_command(cmd)
    
    def test_empty_command_rejected(self):
        """Test that empty commands are rejected."""
        with pytest.raises(RCONValidationError):
            self.rcon._validate_rcon_command("")
    
    def test_whitespace_only_rejected(self):
        """Test that whitespace-only commands are rejected."""
        with pytest.raises(RCONValidationError):
            self.rcon._validate_rcon_command("   ")


class TestRCONCommandArgs:
    """Test RCON command argument creation."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rcon = RCONManager(rcon_tool="rcon-cli")
    
    def test_create_command_args(self):
        """Test creating command arguments."""
        args = self.rcon.create_command_args(
            ip="127.0.0.1",
            port=27020,
            password="test123",
            cmd="SaveWorld"
        )
        
        assert args[0] == "rcon-cli"
        assert "ip=127.0.0.1" in args
        assert "port=27020" in args
        assert "pwd=test123" in args
        assert "cmd=SaveWorld" in args


class TestExecuteCommand:
    """Test RCON command execution."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rcon = RCONManager(rcon_tool="rcon-cli")
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_success(self, mock_to_thread):
        """Test successful command execution."""
        mock_result = Mock()
        mock_result.stdout = "Command executed successfully"
        mock_result.stderr = ""
        mock_to_thread.return_value = mock_result
        
        result = await self.rcon.execute_command("127.0.0.1", 27020, "test123", "SaveWorld")
        
        assert result == "Command executed successfully"
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_doexit_success(self, mock_to_thread):
        """Test successful DoExit command execution."""
        mock_result = Mock()
        mock_result.stdout = "Server shutting down"
        mock_result.stderr = ""
        mock_to_thread.return_value = mock_result
        
        result = await self.rcon.execute_command("127.0.0.1", 27020, "test123", "DoExit")
        
        assert result == "Server shutting down"
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_doexit_stderr(self, mock_to_thread):
        """Test DoExit command with stderr."""
        mock_result = Mock()
        mock_result.stdout = ""
        mock_result.stderr = "Connection error"
        mock_to_thread.return_value = mock_result
        
        with pytest.raises(RCONConnectionError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "DoExit")
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_doexit_rcon_exception(self, mock_to_thread):
        """Test DoExit command with RCON exception in output."""
        mock_result = Mock()
        mock_result.stdout = "RCON Exception: Connection failed"
        mock_result.stderr = ""
        mock_to_thread.return_value = mock_result
        
        with pytest.raises(RCONConnectionError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "DoExit")
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_doexit_one_or_more_errors(self, mock_to_thread):
        """Test DoExit command with 'One or more errors occurred' in output."""
        mock_result = Mock()
        mock_result.stdout = "One or more errors occurred"
        mock_result.stderr = ""
        mock_to_thread.return_value = mock_result
        
        with pytest.raises(RCONConnectionError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "DoExit")
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_regular_stderr(self, mock_to_thread):
        """Test regular command with stderr."""
        mock_result = Mock()
        mock_result.stdout = "Output"
        mock_result.stderr = "Error message"
        mock_to_thread.return_value = mock_result
        
        with pytest.raises(RCONConnectionError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "SaveWorld")
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_called_process_error(self, mock_to_thread):
        """Test handling CalledProcessError."""
        error = subprocess.CalledProcessError(1, "cmd")
        error.stderr = "Process failed"
        mock_to_thread.side_effect = error
        
        with pytest.raises(RCONCommandError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "SaveWorld")
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_called_process_error_no_stderr(self, mock_to_thread):
        """Test handling CalledProcessError without stderr."""
        error = subprocess.CalledProcessError(1, "cmd")
        error.stderr = None
        mock_to_thread.side_effect = error
        
        with pytest.raises(RCONCommandError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "SaveWorld")
    
    @pytest.mark.asyncio
    async def test_execute_command_validation_error(self):
        """Test handling validation errors."""
        with pytest.raises(RCONValidationError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "Invalid; Command")
    
    @pytest.mark.asyncio
    @patch('asyncio.to_thread', new_callable=AsyncMock)
    async def test_execute_command_connection_error(self, mock_to_thread):
        """Test handling connection errors."""
        mock_to_thread.side_effect = Exception("Connection refused")
        
        with pytest.raises(RCONConnectionError):
            await self.rcon.execute_command("127.0.0.1", 27020, "test123", "SaveWorld")


class TestExecuteForServer:
    """Test RCON command execution for specific servers."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.rcon = RCONManager(rcon_tool="rcon-cli")
        self.mock_server = ServerConfig(
            name="TestServer",
            display_name="Test Server",
            map_name="TheIsland_WP",
            rcon_ip="127.0.0.1",
            rcon_port=27020,
            rcon_password="test123",
            start_command="C:\\test\\start.bat",
            install_dir="C:\\test",
            server_save_path="C:\\test\\saved",
            server_log_path="C:\\test\\logs\\game.log",
            log_dir="C:\\test\\logs"
        )
    
    @pytest.mark.asyncio
    @patch.object(RCONManager, 'execute_command', new_callable=AsyncMock)
    async def test_execute_for_server_success(self, mock_execute):
        """Test successful command execution for server."""
        mock_execute.return_value = "Command executed"
        
        result = await self.rcon.execute_for_server(self.mock_server, "SaveWorld")
        
        assert result == "Command executed"
        mock_execute.assert_called_once_with("127.0.0.1", 27020, "test123", "SaveWorld")
