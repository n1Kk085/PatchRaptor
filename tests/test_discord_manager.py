"""
Test suite for Discord Manager - validates Discord messaging and webhooks.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from patchraptor.discord_manager import DiscordManager
import discord


class TestDiscordManagerInit:
    """Test DiscordManager initialization."""
    
    def test_init_with_webhook(self):
        """Test initialization with webhook URL."""
        dm = DiscordManager(webhook_url="https://discord.com/api/webhooks/test", delete_seconds=3600)
        
        assert dm.webhook_url == "https://discord.com/api/webhooks/test"
        assert dm.delete_seconds == 3600
        assert dm.grey_color == 0x99AAB5
        assert dm.discord_client is None
    
    def test_init_without_webhook(self):
        """Test initialization without webhook URL."""
        dm = DiscordManager()
        
        assert dm.webhook_url == ""
        assert dm.delete_seconds == 86400  # Default 24 hours


class TestSetDiscordClient:
    """Test Discord client setup."""
    
    def test_set_discord_client(self):
        """Test setting Discord client."""
        dm = DiscordManager()
        mock_client = Mock()
        
        dm.set_discord_client(mock_client)
        
        assert dm.discord_client == mock_client


class TestSendTempMessage:
    """Test temporary message sending."""
    
    @pytest.mark.asyncio
    async def test_send_temp_message_short_content(self):
        """Test sending short message with embed."""
        dm = DiscordManager()
        mock_channel = AsyncMock()
        mock_message = Mock()
        mock_channel.send = AsyncMock(return_value=mock_message)
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl_get, \
             patch.object(dm, '_delete_message_later', new_callable=AsyncMock):
            mock_config = Mock()
            mock_config.get.return_value = None # No logo
            mock_sl_get.return_value = mock_config
            
            result = await dm.send_temp_message(mock_channel, "Test message", title="Test Title")
        
        assert result == mock_message
        mock_channel.send.assert_called_once()
        # Verify it sent an embed even for simple content
        _, kwargs = mock_channel.send.call_args
        assert "embed" in kwargs
        assert kwargs["embed"].title == "Test Title"
        # Check if thumbnail is not set
        assert not kwargs["embed"].thumbnail.url
    
    @pytest.mark.asyncio
    async def test_send_temp_message_long_content(self):
        """Test sending long message without embed."""
        dm = DiscordManager()
        mock_channel = AsyncMock()
        mock_message = Mock()
        mock_channel.send = AsyncMock(return_value=mock_message)
        
        long_content = "x" * 5000  # Longer than 4096 characters
        
        with patch.object(dm, '_delete_message_later', new_callable=AsyncMock):
            result = await dm.send_temp_message(mock_channel, long_content)
        
        assert result == mock_message
        mock_channel.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_temp_message_no_channel(self):
        """Test sending message with no channel returns None."""
        dm = DiscordManager()
        
        result = await dm.send_temp_message(None, "Test message")
        
        assert result is None


class TestSendWebhookMessage:
    """Test webhook message sending."""
    
    @pytest.mark.asyncio
    async def test_send_webhook_message_success(self):
        """Test successful webhook message."""
        dm = DiscordManager(webhook_url="https://discord.com/api/webhooks/test")
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None
            
            mock_post = MagicMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_response
            mock_context.__aexit__.return_value = None
            mock_post.return_value = mock_context
            
            mock_session.return_value.__aenter__.return_value.post = mock_post
            
            await dm.send_webhook_message("Test content", title="Test Title")
            
            mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_webhook_message_no_url(self):
        """Test webhook message with no URL does nothing."""
        dm = DiscordManager()  # No webhook URL
        
        # Should not raise exception
        await dm.send_webhook_message("Test content")
    
    @pytest.mark.asyncio
    async def test_send_webhook_message_failure(self):
        """Test webhook message handles failures gracefully."""
        dm = DiscordManager(webhook_url="https://discord.com/api/webhooks/test")
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 500  # Server error
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None
            
            mock_post = MagicMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_response
            mock_context.__aexit__.return_value = None
            mock_post.return_value = mock_context
            
            mock_session.return_value.__aenter__.return_value.post = mock_post
            
            # Should not raise exception
            await dm.send_webhook_message("Test content")


class TestGetDefaultChannel:
    """Test get_default_channel method."""
    
    @pytest.mark.asyncio
    async def test_get_default_channel_no_client(self):
        """Test get_default_channel with no Discord client."""
        dm = DiscordManager()
        
        result = await dm.get_default_channel()
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_default_channel_no_channel_id_configured(self):
        """Test get_default_channel with no channel_id in config."""
        dm = DiscordManager()
        dm.discord_client = Mock()
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl_get:
            mock_config = Mock()
            mock_config.get.return_value = None
            mock_sl_get.return_value = mock_config
            
            result = await dm.get_default_channel()
            
            assert result is None
            mock_sl_get.assert_called_with("ConfigManager")
    
    @pytest.mark.asyncio
    async def test_get_default_channel_channel_not_found(self):
        """Test get_default_channel when channel doesn't exist."""
        dm = DiscordManager()
        mock_client = Mock()
        mock_client.get_channel.return_value = None
        dm.discord_client = mock_client
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl_get:
            mock_config = Mock()
            mock_config.get.return_value = "123456789"
            mock_sl_get.return_value = mock_config
            
            result = await dm.get_default_channel()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_default_channel_no_send_permissions(self):
        """Test get_default_channel when bot lacks send permissions."""
        dm = DiscordManager()
        
        mock_guild = Mock()
        mock_me = Mock()
        mock_guild.me = mock_me
        
        mock_permissions = Mock()
        mock_permissions.send_messages = False
        
        mock_channel = Mock()
        mock_channel.guild = mock_guild
        mock_channel.permissions_for.return_value = mock_permissions
        mock_channel.name = "test-channel"
        mock_channel.id = 123456789
        
        mock_client = Mock()
        mock_client.get_channel.return_value = mock_channel
        dm.discord_client = mock_client
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl_get:
            mock_config = Mock()
            mock_config.get.return_value = "123456789"
            mock_sl_get.return_value = mock_config
            
            result = await dm.get_default_channel()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_default_channel_success(self):
        """Test get_default_channel successful retrieval."""
        dm = DiscordManager()
        
        mock_guild = Mock()
        mock_me = Mock()
        mock_guild.me = mock_me
        
        mock_permissions = Mock()
        mock_permissions.send_messages = True
        
        mock_channel = Mock()
        mock_channel.guild = mock_guild
        mock_channel.permissions_for.return_value = mock_permissions
        mock_channel.name = "test-channel"
        mock_channel.id = 123456789
        
        mock_client = Mock()
        mock_client.get_channel.return_value = mock_channel
        dm.discord_client = mock_client
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl_get:
            mock_config = Mock()
            mock_config.get.return_value = "123456789"
            mock_sl_get.return_value = mock_config
            
            result = await dm.get_default_channel()
            
            assert result == mock_channel
    
    @pytest.mark.asyncio
    async def test_get_default_channel_invalid_channel_id(self):
        """Test get_default_channel with invalid channel_id."""
        dm = DiscordManager()
        dm.discord_client = Mock()
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl_get:
            mock_config = Mock()
            mock_config.get.return_value = "not_a_number"
            mock_sl_get.return_value = mock_config
            
            result = await dm.get_default_channel()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_default_channel_exception(self):
        """Test get_default_channel handles exceptions."""
        dm = DiscordManager()
        dm.discord_client = Mock()
        
        with patch('patchraptor.service_locator.ServiceLocator.get') as mock_sl_get:
            mock_config = Mock()
            mock_config.get.side_effect = Exception("Config error")
            mock_sl_get.return_value = mock_config
            
            result = await dm.get_default_channel()
            
            assert result is None


class TestSendTempMessageErrorHandling:
    """Test send_temp_message error handling."""
    
    @pytest.mark.asyncio
    async def test_send_temp_message_send_exception(self):
        """Test send_temp_message handles send exceptions."""
        dm = DiscordManager()
        mock_channel = AsyncMock()
        mock_channel.send.side_effect = Exception("Send failed")
        
        result = await dm.send_temp_message(mock_channel, "Test message")
        
        assert result is None


class TestDeleteMessageLater:
    """Test _delete_message_later method."""
    
    @pytest.mark.asyncio
    async def test_delete_message_later_success(self):
        """Test _delete_message_later deletes message."""
        dm = DiscordManager(delete_seconds=0)  # Immediate deletion for testing
        mock_message = AsyncMock()
        
        await dm._delete_message_later(mock_message)
        
        mock_message.delete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_delete_message_later_exception(self):
        """Test _delete_message_later handles delete exceptions."""
        dm = DiscordManager(delete_seconds=0)
        mock_message = AsyncMock()
        mock_message.delete.side_effect = Exception("Delete failed")
        
        # Should not raise exception
        await dm._delete_message_later(mock_message)


class TestSendWebhookMessageEdgeCases:
    """Test send_webhook_message edge cases."""
    
    @pytest.mark.asyncio
    async def test_send_webhook_message_exception(self):
        """Test send_webhook_message handles exceptions."""
        dm = DiscordManager(webhook_url="https://discord.com/api/webhooks/test")
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.side_effect = Exception("Network error")
            
            # Should not raise exception
            await dm.send_webhook_message("Test content")
    
    @pytest.mark.asyncio
    async def test_send_webhook_message_without_title(self):
        """Test send_webhook_message without title."""
        dm = DiscordManager(webhook_url="https://discord.com/api/webhooks/test")
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.__aenter__.return_value = mock_response
            mock_response.__aexit__.return_value = None
            
            mock_post = MagicMock()
            mock_context = AsyncMock()
            mock_context.__aenter__.return_value = mock_response
            mock_context.__aexit__.return_value = None
            mock_post.return_value = mock_context
            
            mock_session.return_value.__aenter__.return_value.post = mock_post
            
            await dm.send_webhook_message("Test content")
            
            # Verify payload doesn't have title
            call_args = mock_post.call_args
            payload = call_args.kwargs['json']
            assert 'title' not in payload['embeds'][0]
