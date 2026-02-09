"""
Test suite for Version Manager - validates version tracking and build ID management.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, mock_open, AsyncMock
from patchraptor.version_manager import VersionManager
import os
import sys


@pytest.fixture
def version_manager(tmp_path):
    """Create VersionManager instance."""
    return VersionManager(
        steamcmd_path="C:\\steamcmd\\steamcmd.exe",
        app_id="2430930"
    )


class TestVersionManagerInit:
    """Test VersionManager initialization."""
    
    def test_init_with_paths(self):
        """Test initialization with steamcmd path and app ID."""
        vm = VersionManager(
            steamcmd_path="C:\\steamcmd\\steamcmd.exe",
            app_id="2430930"
        )
        
        assert vm.steamcmd_path == "C:\\steamcmd\\steamcmd.exe"
        assert vm.app_id == "2430930"


class TestSaveVersion:
    """Test saving version to file."""
    
    def test_save_version(self, version_manager, tmp_path):
        """Test saving build ID to version file."""
        with patch.object(version_manager, '_get_base_dir', return_value=str(tmp_path)):
            version_manager.save_version("12345678")
            
            version_file = tmp_path / "version.txt"
            assert version_file.exists()
            assert version_file.read_text() == "12345678"
    
    def test_save_version_error(self, version_manager):
        """Test save_version handles write errors."""
        with patch.object(version_manager, '_get_base_dir', return_value="/invalid/path"):
            # Should not raise exception
            version_manager.save_version("12345678")


class TestGetCurrentVersion:
    """Test retrieving current version."""
    
    def test_get_current_version_exists(self, version_manager, tmp_path):
        """Test getting version when file exists."""
        version_file = tmp_path / "version.txt"
        version_file.write_text("87654321")
        
        with patch.object(version_manager, '_get_base_dir', return_value=str(tmp_path)):
            version = version_manager.get_current_version()
            
            assert version == "87654321"
    
    def test_get_current_version_not_exists(self, version_manager, tmp_path):
        """Test getting version when file doesn't exist."""
        with patch.object(version_manager, '_get_base_dir', return_value=str(tmp_path)):
            version = version_manager.get_current_version()
            
            assert version == "Unknown"
    
    def test_get_current_version_read_error(self, version_manager, tmp_path):
        """Test get_current_version handles read errors."""
        version_file = tmp_path / "version.txt"
        version_file.write_text("12345678")
        
        with patch.object(version_manager, '_get_base_dir', return_value=str(tmp_path)), \
             patch('builtins.open', side_effect=PermissionError("Access denied")):
            version = version_manager.get_current_version()
            
            assert version == "Unknown"


class TestGetBaseDir:
    """Test base directory retrieval."""
    
    def test_get_base_dir(self, version_manager):
        """Test getting base directory."""
        base_dir = version_manager._get_base_dir()
        
        assert isinstance(base_dir, str)
        assert os.path.exists(base_dir)
    
    def test_get_base_dir_frozen(self, version_manager):
        """Test getting base directory when frozen."""
        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, 'executable', 'C:\\App\\patchraptor.exe'):
            base_dir = version_manager._get_base_dir()
            
            assert base_dir == "C:\\App"


class TestGetLatestBuildId:
    """Test getting latest build ID from SteamCMD."""
    
    @pytest.mark.asyncio
    async def test_get_latest_build_id_success(self, version_manager):
        """Test successful build ID retrieval."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''
        "2430930"
        {
            "appinfo"
            {
                "buildid"    "15678901"
            }
        }
        '''
        mock_result.stderr = ""
        
        with patch('asyncio.to_thread', new_callable=AsyncMock, return_value=mock_result):
            build_id = await version_manager.get_latest_build_id()
            
            assert build_id == "15678901"
    
    @pytest.mark.asyncio
    async def test_get_latest_build_id_timeout(self, version_manager):
        """Test timeout handling."""
        with patch('asyncio.wait_for', side_effect=asyncio.TimeoutError()):
            build_id = await version_manager.get_latest_build_id()
            
            assert build_id is None
    
    @pytest.mark.asyncio
    async def test_get_latest_build_id_command_failed(self, version_manager):
        """Test handling of failed SteamCMD command."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Error: Failed to connect"
        
        with patch('asyncio.to_thread', new_callable=AsyncMock, return_value=mock_result):
            build_id = await version_manager.get_latest_build_id()
            
            assert build_id is None
    
    @pytest.mark.asyncio
    async def test_get_latest_build_id_auth_failed(self, version_manager):
        """Test handling of authentication failure."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Not logged in"
        
        with patch('asyncio.to_thread', new_callable=AsyncMock, return_value=mock_result):
            build_id = await version_manager.get_latest_build_id()
            
            assert build_id is None
    
    @pytest.mark.asyncio
    async def test_get_latest_build_id_parse_error(self, version_manager):
        """Test handling of unparseable output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Invalid output with no build ID"
        mock_result.stderr = ""
        
        with patch('asyncio.to_thread', new_callable=AsyncMock, return_value=mock_result):
            build_id = await version_manager.get_latest_build_id()
            
            assert build_id is None
    
    @pytest.mark.asyncio
    async def test_get_latest_build_id_whitespace_parsing(self, version_manager):
        """Test parsing build ID from whitespace-separated output."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = '''
        buildid 15678901
        '''
        mock_result.stderr = ""
        
        with patch('asyncio.to_thread', new_callable=AsyncMock, return_value=mock_result):
            build_id = await version_manager.get_latest_build_id()
            
            assert build_id == "15678901"
    
    @pytest.mark.asyncio
    async def test_get_latest_build_id_exception(self, version_manager):
        """Test handling of unexpected exceptions."""
        with patch('asyncio.to_thread', side_effect=Exception("Unexpected error")):
            build_id = await version_manager.get_latest_build_id()
            
            assert build_id is None
