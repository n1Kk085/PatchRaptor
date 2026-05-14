"""
Test suite for RaptorChat Manager - validates RaptorChat process management.
"""
import pytest
import asyncio
import sys
import os
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from patchraptor.raptorchat_manager import RaptorChatManager


@pytest.fixture
def raptorchat_manager():
    """Create RaptorChatManager instance."""
    rcm = RaptorChatManager(
        raptorchat_dir="C:\\raptorchat",
        raptorchat_path="C:\\raptorchat\\RaptorChat.exe"
    )
    yield rcm
    # Teardown: ensure process and tasks are stopped
    rcm.stop()
    # If there are any stray async tasks (monitor), we should try to cancel them too
    # but since this is a sync fixture, we can't await stop_auto_monitor easily without a loop.
    # However, stop() now handles the delayed_start_task cancellation which was the source of the warning.
    if rcm.monitor_task and not rcm.monitor_task.done():
         rcm.monitor_task.cancel()


class TestRaptorChatManagerInit:
    """Test RaptorChatManager initialization."""
    
    def test_init_with_paths(self):
        """Test initialization with paths."""
        rcm = RaptorChatManager(
            raptorchat_dir="C:\\raptorchat",
            raptorchat_path="C:\\raptorchat\\RaptorChat.exe"
        )
        
        assert rcm.raptorchat_dir == "C:\\raptorchat"
        assert rcm.raptorchat_path == "C:\\raptorchat\\RaptorChat.exe"


class TestStart:
    """Test start command logic."""

    @patch('subprocess.Popen')
    def test_start_success(self, mock_popen, raptorchat_manager):
        """Test successful start."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_popen.return_value = mock_process
        
        assert raptorchat_manager.start() is True
        assert raptorchat_manager.is_running() is True
        assert raptorchat_manager.process_start_time > 0
        mock_popen.assert_called_once()

    @patch('subprocess.Popen')
    def test_start_already_running(self, mock_popen, raptorchat_manager):
        """Test start when already running."""
        # Setup running state
        mock_process = Mock()
        mock_process.poll.return_value = None
        raptorchat_manager.process = mock_process
        
        assert raptorchat_manager.start() is False
        mock_popen.assert_not_called()

    def test_start_no_path(self):
        """Test start with no path configured."""
        rcm = RaptorChatManager()
        assert rcm.start() is False

    @patch('subprocess.Popen')
    def test_start_failure(self, mock_popen, raptorchat_manager):
        """Test start failure (exception)."""
        mock_popen.side_effect = Exception("Launch failed")
        
        assert raptorchat_manager.start() is False
        assert raptorchat_manager.process is None

    @patch('subprocess.Popen')
    @patch('sys.frozen', True, create=True)
    @patch('sys.executable', 'C:\\app\\Instinct.exe')
    @patch('os.path.dirname')
    def test_start_frozen(self, mock_dirname, mock_popen, raptorchat_manager):
        """Test start in frozen mode (compiled exe)."""
        mock_dirname.return_value = "C:\\app"
        
        raptorchat_manager.start()
        
        # Should look for RaptorChat.exe in same dir
        args, kwargs = mock_popen.call_args
        assert args[0] == [os.path.join("C:\\app", "RaptorChat.exe")]

    @patch('subprocess.Popen')
    def test_start_python_script(self, mock_popen, raptorchat_manager):
        """Test start as python script."""
        raptorchat_manager.raptorchat_path = "script.py"
        
        raptorchat_manager.start()
        
        args, kwargs = mock_popen.call_args
        assert args[0] == ["python", "script.py"]


class TestStop:
    """Test stop command logic."""

    def test_stop_not_running(self, raptorchat_manager):
        """Test stop when not running."""
        assert raptorchat_manager.stop() is False

    def test_stop_success(self, raptorchat_manager):
        """Test successful stop."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        raptorchat_manager.process = mock_process
        
        with patch("psutil.Process") as mock_psutil_process:
            mock_parent = Mock()
            mock_parent.terminate.return_value = None
            mock_parent.wait.return_value = None
            mock_parent.children.return_value = []
            mock_psutil_process.return_value = mock_parent
            
            assert raptorchat_manager.stop() is True
        
        # Verify psutil.Process.terminate called
        mock_parent.terminate.assert_called()
        assert raptorchat_manager.process is None

    def test_stop_exception(self, raptorchat_manager):
        """Test stop with exception."""
        mock_process = Mock()
        mock_process.poll.return_value = None
        mock_process.kill.side_effect = Exception("Kill failed")
        raptorchat_manager.process = mock_process
        
        # Even with kill failing, it handles it gracefully?
        # The code returns False on exception
        assert raptorchat_manager.stop() is False


class TestReboot:
    """Test reboot logic."""

    @patch('time.sleep') 
    def test_reboot_success(self, mock_sleep, raptorchat_manager):
        """Test successful reboot."""
        # Mock start and stop methods to avoid mocking subprocess internals again
        with patch.object(RaptorChatManager, 'stop', return_value=True) as mock_stop, \
             patch.object(RaptorChatManager, 'start', return_value=True) as mock_start, \
             patch.object(RaptorChatManager, 'is_running', side_effect=[True, False]): # Running then not running
            
            assert raptorchat_manager.reboot() is True
            
            mock_stop.assert_called_once()
            mock_sleep.assert_called_once()
            mock_start.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_reboot(self, raptorchat_manager):
        """Test async wrapper for reboot."""
        with patch.object(RaptorChatManager, 'reboot', return_value=True) as mock_reboot:
            result = await raptorchat_manager.async_reboot()
            
            assert result is True
            mock_reboot.assert_called_once()


class TestMonitoring:
    """Test monitoring logic."""


    @pytest.mark.asyncio
    async def test_monitor_raptorchat_loop(self, raptorchat_manager):
        """Test monitor loop functionality."""
        # Use a side effect to break the infinite loop
        with patch('asyncio.sleep', side_effect=[None, asyncio.CancelledError]) as mock_sleep:
             try:
                 await raptorchat_manager._monitor_raptorchat()
             except asyncio.CancelledError:
                 pass
             
             assert mock_sleep.call_count == 2


class TestDelayedStart:
    @pytest.mark.asyncio
    async def test_start_delayed(self, raptorchat_manager):
        """Test delayed start."""
        with patch.object(RaptorChatManager, 'start', return_value=True) as mock_start, \
             patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            
            task = await raptorchat_manager.start_delayed(delay_seconds=1)
            # Cancel the task as we've verified it was created
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            
            assert raptorchat_manager.delayed_start_task is not None

class TestDelayedStartInternal:
    """Test delayed start internal function."""
    
    @pytest.mark.asyncio
    async def test_delayed_start_creates_task(self, raptorchat_manager):
        """Test that delayed start creates a task."""
        with patch('asyncio.create_task') as mock_create_task:
            mock_task = MagicMock()
            mock_task.done.return_value = False
            mock_create_task.return_value = mock_task
            
            await raptorchat_manager.start_delayed(delay_seconds=1)
            
            # Verify task was created and clean up coroutine to avoid warning
            mock_create_task.assert_called_once()
            coro = mock_create_task.call_args[0][0]
            await coro # Actually run it (it will sleep but we mocked sleep)
    
    @pytest.mark.asyncio
    async def test_delayed_start_with_zero_delay(self, raptorchat_manager):
        """Test delayed start with zero delay."""
        with patch('asyncio.create_task') as mock_create_task:
            mock_task = MagicMock()
            mock_task.done.return_value = False
            mock_create_task.return_value = mock_task
            
            await raptorchat_manager.start_delayed(delay_seconds=0)
            
            # Verify task was created and clean up coroutine
            mock_create_task.assert_called_once()
            coro = mock_create_task.call_args[0][0]
            await coro


class TestRestartChatThreads:
    """Test chat thread restart functionality."""
    
    @pytest.mark.asyncio
    async def test_restart_chat_threads_success(self, raptorchat_manager):
        """Test successful chat thread restart."""
        with patch.object(RaptorChatManager, 'stop', return_value=True) as mock_stop, \
             patch.object(RaptorChatManager, 'start', return_value=True) as mock_start, \
             patch.object(RaptorChatManager, 'is_running', side_effect=[True, False]), \
             patch.object(RaptorChatManager, 'start_delayed', new_callable=AsyncMock) as mock_start_delayed:
            
            # Allow start_delayed to return a value if needed, or just be an AsyncMock
            # The warning happens because start() calls start_delayed() which returns a coroutine.
            # If start_delayed is an AsyncMock, calling it returns a coroutine.
            # That coroutine must be awaited. But start() is synchronous and just fires it via create_task.
            # So start() basically does `asyncio.create_task(self.start_delayed())`.
            # We need start_delayed to NOT return a coroutine that needs awaiting, OR we need the loop to process it.
            # Returning None from side_effect handles coroutine expectations.
            # Better: Make start_delayed a MagicMock that returns a dummy object, avoiding the "coroutine never awaited" check?
            # Uses AsyncMock for async methods defined in class.
            # The issue is typically that the test ends before the loop processes the task.
            # We will try setting return_value to None explicitly.
            mock_start_delayed.return_value = None
            
            result = await raptorchat_manager.restart_chat_threads()
            
            assert result is True
            mock_stop.assert_called_once()
            mock_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restart_chat_threads_not_running(self, raptorchat_manager):
        """Test restart when not running."""
        with patch.object(RaptorChatManager, 'stop') as mock_stop, \
             patch.object(RaptorChatManager, 'start', return_value=True) as mock_start, \
             patch.object(RaptorChatManager, 'is_running', return_value=False), \
             patch.object(RaptorChatManager, 'start_delayed', new_callable=AsyncMock) as mock_start_delayed:
            
            mock_start_delayed.return_value = None
            
            result = await raptorchat_manager.restart_chat_threads()
            
            assert result is True
            mock_stop.assert_not_called()
            mock_start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_restart_chat_threads_failure(self, raptorchat_manager):
        """Test restart failure."""
        with patch.object(RaptorChatManager, 'stop', return_value=True), \
             patch.object(RaptorChatManager, 'start', return_value=False), \
             patch.object(RaptorChatManager, 'is_running', side_effect=[True, False]):
            
            result = await raptorchat_manager.restart_chat_threads()
            
            assert result is False


class TestAsyncRebootException:
    """Test async reboot exception handling."""
    
    @pytest.mark.asyncio
    async def test_async_reboot_exception(self, raptorchat_manager):
        """Test exception in async reboot."""
        # reboot is run in an executor, so side_effect exception propagates correctly
        with patch.object(RaptorChatManager, 'reboot', side_effect=Exception("Reboot failed")):
            result = await raptorchat_manager.async_reboot()
            assert result is False


class TestStartEdgeCases:
    """Test edge cases in start method."""
    
    @patch('subprocess.Popen')
    def test_start_subprocess_exception(self, mock_popen, raptorchat_manager):
        """Test subprocess exception during start."""
        mock_popen.side_effect = OSError("Failed to start process")
        
        result = raptorchat_manager.start()
        
        assert result is False
        assert raptorchat_manager.process is None
