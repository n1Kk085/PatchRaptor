"""
Test suite for RaptorChat Utils - validates delayed restart functionality.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from patchraptor.raptorchat_utils import RaptorChatUtils


class TestDelayedRaptorChatRestart:
    """Test delayed_raptorchat_restart method."""
    
    @pytest.mark.asyncio
    async def test_delayed_restart_no_manager(self):
        """Test delayed restart with no manager provided."""
        # Should return early without error
        await RaptorChatUtils.delayed_raptorchat_restart(None, 5, Mock(), Mock())
    
    @pytest.mark.asyncio
    async def test_delayed_restart_with_delay(self):
        """Test delayed restart with delay > 0."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.start.return_value = True
        mock_channel = Mock()
        mock_discord = AsyncMock()
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await RaptorChatUtils.delayed_raptorchat_restart(
                mock_manager, 120, mock_channel, mock_discord
            )
            
            # Should sleep for the delay
            mock_sleep.assert_called_with(120)
            mock_manager.start.assert_called_once()
            mock_discord.send_temp_message.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_zero_delay(self):
        """Test delayed restart with zero delay."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.start.return_value = True
        mock_channel = Mock()
        mock_discord = AsyncMock()
        
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            await RaptorChatUtils.delayed_raptorchat_restart(
                mock_manager, 0, mock_channel, mock_discord
            )
            
            # Should not sleep
            mock_sleep.assert_not_called()
            mock_manager.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_already_running(self):
        """Test delayed restart when RaptorChat is already running."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = True
        mock_manager.stop.return_value = True
        mock_manager.start.return_value = True
        mock_channel = Mock()
        mock_discord = AsyncMock()
        
        with patch('asyncio.sleep', new_callable=AsyncMock):
            await RaptorChatUtils.delayed_raptorchat_restart(
                mock_manager, 0, mock_channel, mock_discord
            )
            
            # Should stop first, then start
            mock_manager.stop.assert_called_once()
            mock_manager.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_start_success(self):
        """Test delayed restart with successful start."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.start.return_value = True
        mock_channel = Mock()
        mock_discord = AsyncMock()
        
        await RaptorChatUtils.delayed_raptorchat_restart(
            mock_manager, 0, mock_channel, mock_discord
        )
        
        # Should send success message
        mock_discord.send_temp_message.assert_called_once()
        args = mock_discord.send_temp_message.call_args[0]
        assert "connected successfully" in args[1].lower()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_start_failure(self):
        """Test delayed restart with failed start."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.start.return_value = False
        mock_channel = Mock()
        mock_discord = AsyncMock()
        
        await RaptorChatUtils.delayed_raptorchat_restart(
            mock_manager, 0, mock_channel, mock_discord
        )
        
        # Should send failure message
        mock_discord.send_temp_message.assert_called_once()
        args = mock_discord.send_temp_message.call_args[0]
        assert "failed to reconnect" in args[1].lower()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_no_discord_manager(self):
        """Test delayed restart without discord manager."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.start.return_value = True
        
        # Should not raise exception
        await RaptorChatUtils.delayed_raptorchat_restart(
            mock_manager, 0, Mock(), None
        )
        
        mock_manager.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_no_channel(self):
        """Test delayed restart without channel."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.start.return_value = True
        
        # Should not raise exception
        await RaptorChatUtils.delayed_raptorchat_restart(
            mock_manager, 0, None, AsyncMock()
        )
        
        mock_manager.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_exception_handling(self):
        """Test delayed restart handles exceptions gracefully."""
        mock_manager = Mock()
        mock_manager.is_running.side_effect = Exception("Test error")
        mock_channel = Mock()
        mock_discord = AsyncMock()
        
        # Should not raise exception
        await RaptorChatUtils.delayed_raptorchat_restart(
            mock_manager, 0, mock_channel, mock_discord
        )
        
        # Should send error message
        mock_discord.send_temp_message.assert_called_once()
        args = mock_discord.send_temp_message.call_args[0]
        assert "error" in args[1].lower()
    
    @pytest.mark.asyncio
    async def test_delayed_restart_with_is_delayed_start_flag(self):
        """Test that start is called with is_delayed_start=True."""
        mock_manager = Mock()
        mock_manager.is_running.return_value = False
        mock_manager.start.return_value = True
        
        await RaptorChatUtils.delayed_raptorchat_restart(
            mock_manager, 0, Mock(), AsyncMock()
        )
        
        # Verify start was called with is_delayed_start=True
        mock_manager.start.assert_called_once_with(is_delayed_start=True)
