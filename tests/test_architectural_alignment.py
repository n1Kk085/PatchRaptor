import pytest
import asyncio
from unittest.mock import MagicMock, Mock, patch
from patchraptor.configuration_handler import ConfigurationHandler
from patchraptor.raptorchat_manager import RaptorChatManager

@pytest.mark.asyncio
async def test_configuration_handler_cleanup():
    """Verify that cleanup() terminates external processes."""
    handler = ConfigurationHandler()
    mock_webpanel = MagicMock()
    mock_tunnel = MagicMock()
    
    handler.webpanel_process = mock_webpanel
    handler.tunnel_process = mock_tunnel
    
    with patch("psutil.Process") as mock_psutil:
        mock_parent = Mock()
        mock_parent.children.return_value = []
        mock_parent.terminate.return_value = None
        mock_parent.wait.return_value = None
        mock_psutil.return_value = mock_parent
        
        await handler.cleanup()
        
        assert handler.webpanel_process is None
        assert handler.tunnel_process is None

@pytest.mark.asyncio
async def test_raptorchat_maintenance_count():
    """Verify reference-counted maintenance semaphore."""
    manager = RaptorChatManager()
    assert manager.maintenance_count == 0
    
    manager.start_maintenance()
    assert manager.maintenance_count == 1
    
    manager.start_maintenance()
    assert manager.maintenance_count == 2
    
    manager.end_maintenance()
    assert manager.maintenance_count == 1
    
    manager.end_maintenance()
    assert manager.maintenance_count == 0
    
    # Ensure no negative count
    manager.end_maintenance()
    assert manager.maintenance_count == 0

@pytest.mark.asyncio
async def test_raptorchat_auto_restart_blocked_by_maintenance():
    """Verify auto-restart is blocked when maintenance count > 0."""
    manager = RaptorChatManager()
    manager.start_maintenance()
    
    with patch.object(manager, "start", return_value=True) as mock_start:
        # Mocking the loop internals for a single iteration
        # In a real test we'd use a shorter sleep or mock asyncio.sleep
        with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]):
            try:
                await manager._monitor_raptorchat()
            except asyncio.CancelledError:
                pass
        
        mock_start.assert_not_called()

@pytest.mark.asyncio
async def test_raptorchat_auto_restart_trigger():
    """Verify auto-restart triggers when process is down and maintenance is 0."""
    manager = RaptorChatManager()
    assert manager.maintenance_count == 0
    
    def start_side_effect():
        manager.process = MagicMock()
        manager.process.poll.return_value = None
        return True
        
    with patch.object(manager, "start", side_effect=start_side_effect) as mock_start:
        with patch("asyncio.sleep", side_effect=[None, asyncio.CancelledError]):
            try:
                await manager._monitor_raptorchat()
            except asyncio.CancelledError:
                pass
        
        # Should be called once then blocked because self.process is now set
        assert mock_start.call_count == 1
