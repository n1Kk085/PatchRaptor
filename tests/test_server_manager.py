"""
Test suite for Server Manager - validates server operations and process management.
"""
import pytest
import asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from patchraptor.server_manager import ServerManager
from patchraptor.models import ServerConfig
from patchraptor.exceptions import (
    ServerNotFoundError,
    ServerAlreadyRunningError,
    ServerOperationError,
    ProcessOperationError
)
import psutil


@pytest.fixture
def mock_server():
    """Create a mock server configuration."""
    return ServerConfig(
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


@pytest.fixture
def server_manager(mock_server):
    """Create a ServerManager instance with mock server."""
    with patch('patchraptor.server_manager.ServerManager._load_pids'):
        return ServerManager(servers=[mock_server], rcon_tool="rcon-cli")


class TestServerManagerInit:
    """Test ServerManager initialization."""
    
    def test_init_with_servers(self, mock_server):
        """Test initialization with server list."""
        sm = ServerManager(servers=[mock_server], rcon_tool="rcon-cli")
        
        assert len(sm.servers) == 1
        assert sm.servers[0].name == "TestServer"
        assert sm.rcon_tool == "rcon-cli"
    
    def test_init_with_empty_servers(self):
        """Test initialization with empty server list."""
        sm = ServerManager(servers=[], rcon_tool="rcon-cli")
        
        assert len(sm.servers) == 0


class TestFindServer:
    """Test server lookup functionality."""
    
    def test_find_server_by_name(self, server_manager):
        """Test finding server by name."""
        server = server_manager.find_server("TestServer")
        
        assert server is not None
        assert server.name == "TestServer"
    
    def test_find_server_by_display_name(self, server_manager):
        """Test finding server by display name."""
        server = server_manager.find_server("Test Server")
        
        assert server is not None
        assert server.display_name == "Test Server"
    
    def test_find_server_not_found(self, server_manager):
        """Test finding non-existent server raises error."""
        with pytest.raises(ServerNotFoundError):
            server_manager.find_server("NonExistent")


class TestGetDisplayName:
    """Test display name retrieval."""
    
    def test_get_display_name(self, server_manager, mock_server):
        """Test getting server display name."""
        display_name = server_manager.get_display_name(mock_server)
        
        assert display_name == "Test Server"


class TestServerRunningChecks:
    """Test server running status checks."""
    
    @patch('psutil.process_iter')
    def test_is_server_running_true(self, mock_process_iter, server_manager):
        """Test detecting running server."""
        # Mock a running ARK server process
        mock_process = Mock()
        mock_process.pid = 1234
        mock_process.info = {
            'name': 'ArkAscendedServer.exe',
            'exe': 'C:\\ARK\\ArkAscendedServer.exe',
            'cmdline': ['ArkAscendedServer.exe', 'TheIsland_WP', '?listen'],
            'cwd': 'C:\\ARK'
        }
        mock_process_iter.return_value = [mock_process]
        
        result = server_manager.is_server_running()
        
        assert result is not None  # Returns Process object
        assert result.pid == 1234
    
    @patch('psutil.process_iter')
    def test_is_server_running_false(self, mock_process_iter, server_manager):
        """Test detecting no running servers."""
        # Mock no ARK processes
        mock_process_iter.return_value = []
        
        result = server_manager.is_server_running()
        
        assert result is None  # Returns None when no server found
    
    @patch('psutil.process_iter')
    def test_is_server_running_psutil_error(self, mock_process_iter, server_manager):
        """Test handling psutil errors (now swallowed)."""
        mock_process_iter.side_effect = psutil.Error("Unexpected error")
        
        result = server_manager.is_server_running()
        assert result is None
    
    @patch('psutil.process_iter')
    def test_is_server_running_access_denied(self, mock_process_iter, server_manager):
        """Test handling access denied exceptions."""
        mock_process_iter.side_effect = psutil.AccessDenied()
        
        result = server_manager.is_server_running()
        assert result is None
    
    @patch('psutil.process_iter')
    def test_is_specific_server_running_true(self, mock_process_iter, server_manager, mock_server):
        """Test detecting specific running server."""
        # Mock a running server with matching map name
        mock_process = Mock()
        mock_process.info = {
            'name': 'ArkAscendedServer.exe',
            'exe': 'C:\\ARK\\ArkAscendedServer.exe',
            'cwd': 'C:\\test',
            'cmdline': ['ArkAscendedServer.exe', 'TheIsland_WP?listen']
        }
        mock_process_iter.return_value = [mock_process]
        
        result = server_manager.is_specific_server_running(mock_server)
        
        assert result is True
    
    @patch('psutil.process_iter')
    def test_is_specific_server_running_false(self, mock_process_iter, server_manager, mock_server):
        """Test detecting specific server not running."""
        # Mock no matching processes
        mock_process_iter.return_value = []
        
        result = server_manager.is_specific_server_running(mock_server)
        
        assert result is False
    
    @patch('psutil.process_iter')
    def test_is_specific_server_running_by_cwd(self, mock_process_iter, server_manager, mock_server):
        """Test detecting server by working directory."""
        mock_process = Mock()
        mock_process.info = {
            'name': 'ArkAscendedServer.exe',
            'exe': 'C:\\ARK\\ArkAscendedServer.exe',
            'cwd': 'C:\\test\\theisland_wp',
            'cmdline': ['ArkAscendedServer.exe']
        }
        mock_process_iter.return_value = [mock_process]
        
        result = server_manager.is_specific_server_running(mock_server)
        assert result is True
    
    @patch('psutil.process_iter')
    def test_is_specific_server_running_by_exe(self, mock_process_iter, server_manager, mock_server):
        """Test detecting server by executable path."""
        mock_process = Mock()
        mock_process.info = {
            'name': 'ArkAscendedServer.exe',
            'exe': 'C:\\test\\theisland_wp\\ArkAscendedServer.exe',
            'cwd': 'C:\\other',
            'cmdline': ['ArkAscendedServer.exe']
        }
        mock_process_iter.return_value = [mock_process]
        
        result = server_manager.is_specific_server_running(mock_server)
        assert result is True
    
    @patch('psutil.process_iter')
    def test_is_specific_server_running_psutil_error(self, mock_process_iter, server_manager, mock_server):
        """Test handling psutil errors in specific server check (now swallowed)."""
        mock_process_iter.side_effect = psutil.Error("Unexpected error")
        
        result = server_manager.is_specific_server_running(mock_server)
        assert result is False
    
    @patch('psutil.process_iter')
    def test_is_specific_server_running_general_error(self, mock_process_iter, server_manager, mock_server):
        """Test handling general errors in specific server check (now swallowed)."""
        mock_process_iter.side_effect = Exception("Unexpected error")
        
        result = server_manager.is_specific_server_running(mock_server)
        assert result is False



class TestStartServer:
    """Test server startup functionality."""
    
    @patch('subprocess.Popen')
    @patch.object(ServerManager, 'is_specific_server_running', return_value=False)
    def test_start_server_success(self, mock_running, mock_popen, server_manager, mock_server):
        """Test successful server start."""
        server_manager.start_server(mock_server)
        
        mock_popen.assert_called_once()
    
    @patch.object(ServerManager, 'is_specific_server_running', return_value=True)
    def test_start_server_already_running(self, mock_running, server_manager, mock_server):
        """Test starting already running server raises error."""
        with pytest.raises(ServerAlreadyRunningError):
            server_manager.start_server(mock_server)
    
    @patch('subprocess.Popen')
    @patch.object(ServerManager, 'is_specific_server_running', return_value=False)
    def test_start_server_quoted_command(self, mock_running, mock_popen, server_manager):
        """Test starting server with quoted command."""
        server = ServerConfig(
            name="TestServer",
            display_name="Test Server",
            map_name="TheIsland_WP",
            rcon_ip="127.0.0.1",
            rcon_port=27020,
            rcon_password="test123",
            start_command='"C:\\Program Files\\ARK\\start.bat" -arg1',
            install_dir="C:\\test",
            server_save_path="C:\\test\\saved",
            server_log_path="C:\\test\\logs\\game.log",
            log_dir="C:\\test\\logs"
        )
        
        sm = ServerManager(servers=[server], rcon_tool="rcon-cli")
        sm.start_server(server)
        
        mock_popen.assert_called_once()
    
    @patch('subprocess.Popen')
    @patch.object(ServerManager, 'is_specific_server_running', return_value=False)
    def test_start_server_single_command(self, mock_running, mock_popen, server_manager):
        """Test starting server with single command (no spaces)."""
        server = ServerConfig(
            name="TestServer",
            display_name="Test Server",
            map_name="TheIsland_WP",
            rcon_ip="127.0.0.1",
            rcon_port=27020,
            rcon_password="test123",
            start_command="C:\\start.bat",
            install_dir="C:\\test",
            server_save_path="C:\\test\\saved",
            server_log_path="C:\\test\\logs\\game.log",
            log_dir="C:\\test\\logs"
        )
        
        sm = ServerManager(servers=[server], rcon_tool="rcon-cli")
        sm.start_server(server)
        
        mock_popen.assert_called_once()
    
    @patch('subprocess.Popen', side_effect=OSError("File not found"))
    @patch.object(ServerManager, 'is_specific_server_running', return_value=False)
    def test_start_server_os_error(self, mock_running, mock_popen, server_manager, mock_server):
        """Test handling OS errors during server start."""
        with pytest.raises(ServerOperationError):
            server_manager.start_server(mock_server)
    
    @patch('subprocess.Popen', side_effect=ValueError("Invalid command"))
    @patch.object(ServerManager, 'is_specific_server_running', return_value=False)
    def test_start_server_value_error(self, mock_running, mock_popen, server_manager, mock_server):
        """Test handling value errors during server start."""
        with pytest.raises(ServerOperationError):
            server_manager.start_server(mock_server)
    
    @patch('subprocess.Popen', side_effect=Exception("Unexpected error"))
    @patch.object(ServerManager, 'is_specific_server_running', return_value=False)
    def test_start_server_unexpected_error(self, mock_running, mock_popen, server_manager, mock_server):
        """Test handling unexpected errors during server start."""
        with pytest.raises(ServerOperationError):
            server_manager.start_server(mock_server)


class TestWaitForServerShutdown:
    """Test server shutdown waiting functionality."""
    
    @pytest.mark.asyncio
    @patch.object(ServerManager, 'is_specific_server_running', return_value=False)
    async def test_wait_for_server_shutdown_already_stopped(self, mock_running, server_manager, mock_server):
        """Test waiting for already stopped server."""
        result = await server_manager.wait_for_server_shutdown(mock_server, timeout=5)
        
        assert result is True
    
    @pytest.mark.asyncio
    @patch.object(ServerManager, 'is_specific_server_running', side_effect=[True, True, False])
    async def test_wait_for_server_shutdown_success(self, mock_running, server_manager, mock_server):
        """Test successful shutdown wait."""
        result = await server_manager.wait_for_server_shutdown(mock_server, timeout=5)
        
        assert result is True
    
    @pytest.mark.asyncio
    @patch.object(ServerManager, 'is_specific_server_running', return_value=True)
    async def test_wait_for_server_shutdown_timeout(self, mock_running, server_manager, mock_server):
        """Test shutdown wait timeout."""
        result = await server_manager.wait_for_server_shutdown(mock_server, timeout=2)
        
        assert result is False
    
    @pytest.mark.asyncio
    @patch.object(ServerManager, 'is_specific_server_running', side_effect=[True, Exception("Unexpected error")])
    async def test_wait_for_server_shutdown_error(self, mock_running, server_manager, mock_server):
        """Test handling errors during shutdown wait."""
        with pytest.raises(ServerOperationError):
            await server_manager.wait_for_server_shutdown(mock_server, timeout=5)
