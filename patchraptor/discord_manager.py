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
    @property
    def config_manager(self):
        from .service_locator import ServiceLocator
        return ServiceLocator.get("ConfigManager")

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

        config_manager = self.config_manager
        
        try:
            raw_id = config_manager.get("channel_id")
            if not raw_id:
                logger.error_system("No channel_id configured in settings")
                return None
                
            channel_id = int(raw_id)
                
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

    async def send_temp_message(self, channel, content: str = "", title: Optional[str] = None, embed: Optional[discord.Embed] = None, file: Optional[discord.File] = None, view: Optional[discord.ui.View] = None):
        """Send a temporary message with optional embed, file, and view support"""
        if not channel:
            logger.error_system("Channel not found for send_temp_message")
            return None
        
        try:
            msg = None
            if file:
                # If we have a file, we send it along with content/embed
                if embed:
                    msg = await channel.send(content=content, embed=embed, file=file, view=view)
                else:
                    msg = await channel.send(content=content, file=file, view=view)
            elif embed:
                # If we have an embed but no file
                logo_url = self.config_manager.get("logo_url")
                if logo_url and not embed.thumbnail:
                    embed.set_thumbnail(url=logo_url)
                msg = await channel.send(content=content, embed=embed, view=view)
            else:
                # Behavior for simple content
                if len(content) > 4096:
                    msg = await channel.send(f"\n```\n{content}\n```", view=view)
                else:
                    embed = discord.Embed(description=content, color=self.grey_color)
                    if title:
                        embed.title = title
                    
                    # Add branding thumbnail if configured
                    logo_url = self.config_manager.get("logo_url")
                    if logo_url:
                        embed.set_thumbnail(url=logo_url)
                        
                    msg = await channel.send("", embed=embed, view=view)
            
            if msg:
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
            return None

    async def send_system_alert(self, content: str, title: str = "🚨 System Alert"):
        """Send a critical system alert (Now following Zero-Clutter policy)"""
        channel = await self.get_default_channel()
        if not channel:
            return None
            
        try:
            embed = discord.Embed(
                title=title,
                description=content,
                color=0xFF0000, # Bright Red for alerts
                timestamp=discord.utils.utcnow()
            )
            msg = await channel.send(embed=embed)
            # Apply Zero-Clutter policy to system alerts
            asyncio.create_task(self._delete_message_later(msg))
            return msg
        except Exception as e:
            logger.error_system(f"Failed to send system alert: {e}")
            return None
