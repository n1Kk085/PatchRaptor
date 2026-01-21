import asyncio
from typing import Optional
import discord
from .log_manager import logger
import aiohttp

class DiscordManager:
    """Manages Discord interactions and messaging"""
    def __init__(self, webhook_url: str = "", delete_seconds: int = 86400):
        self.webhook_url = webhook_url
        self.delete_seconds = delete_seconds
        self.grey_color = 0x99AAB5
        self.discord_client = None
    def set_discord_client(self, client):
        """Set the Discord client for channel access"""
        self.discord_client = client
    
    async def get_default_channel(self):
        """Get the configured text channel for sending messages
        
        Returns:
            Optional[discord.TextChannel]: The configured channel if found and accessible, None otherwise
        """
        if not self.discord_client:
            logger.error_system("Discord client not initialized")
            return None

        # Import config manager to get configured channel ID
        from .config import ConfigManager
        config_manager = ConfigManager()
        
        try:
            channel_id = int(config_manager.get("channel_id"))
            if not channel_id:
                logger.error_system("No channel_id configured in settings")
                return None
                
            # Get the specific configured channel
            channel = self.discord_client.get_channel(channel_id)
            if not channel:
                logger.error_system(f"Configured channel {channel_id} not found")
                return None
                
            # Verify send permissions
            if not channel.permissions_for(channel.guild.me).send_messages:
                logger.error_system(f"Missing send permissions in channel {channel.name} ({channel.id})")
                return None
                
            return channel
            
        except ValueError:
            logger.error_system(f"Invalid channel_id in config: {config_manager.get('channel_id')}")
        except Exception as e:
            logger.error_system(f"Error getting default channel: {e}")
            
        return None

    async def send_temp_message(self, channel, content: str, title: Optional[str] = None):
        if not channel:
            logger.error_system("Channel not found for send_temp_message")
            return None
        
        try:
            if len(content) > 4096:
                msg = await channel.send(f"\n```\n{content}\n```")
            else:
                embed = discord.Embed(description=content, color=self.grey_color)
                if title:
                    embed.title = title
                msg = await channel.send("", embed=embed)
            
            asyncio.create_task(self._delete_message_later(msg))
            return msg
        except Exception as e:
            logger.error_system(f"Failed to send temp message: {e}")
            return None

    async def _delete_message_later(self, msg):
        await asyncio.sleep(self.delete_seconds)
        try:
            await msg.delete()
        except Exception as e:
            pass

    async def send_webhook_message(self, content: str, title: Optional[str] = None):
        if not self.webhook_url:
            return
        embed_data = {"description": content, "color": self.grey_color}
        if title:
            embed_data["title"] = title
        payload = {"content": "", "embeds": [embed_data]}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=payload) as resp:
                    if resp.status >= 300:
                        logger.error_system(f"Webhook post failed with status {resp.status}")
        except Exception as e:
            logger.error_system(f"Failed to send webhook message: {e}")
