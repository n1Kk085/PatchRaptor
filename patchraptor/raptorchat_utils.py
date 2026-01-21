import asyncio
from .log_manager import logger

class RaptorChatUtils:
    """Utility functions for RaptorChat operations"""
    
    @staticmethod
    async def delayed_raptorchat_restart(raptorchat_manager, delay, channel, discord_manager):
        """
        Restarts RaptorChat after a specified delay.
        
        Args:
            raptorchat_manager: The RaptorChatManager instance
            delay (int): Delay in seconds before restart
            channel: Discord channel context for notifications
            discord_manager: DiscordManager instance for sending messages
        """
        if not raptorchat_manager:
            logger.debug_system("RaptorChat manager not provided for delayed restart, skipping")
            return
            
        logger.debug_system(f"Scheduling RaptorChat restart in {delay} seconds")
        
        # Wait for the delay
        if delay > 0:
            await asyncio.sleep(delay)
            
        # Double check manager exists
        if not raptorchat_manager:
            return

        # Prepare the message header
        msg_header = "Reconnecting chat relay after server restart..."
        
        # Start RaptorChat
        logger.debug_system("Starting RaptorChat after delay")
        try:
            # Check if it's already running first
            if raptorchat_manager.is_running():
                logger.debug_system("RaptorChat is already running, stopping first")
                raptorchat_manager.stop()
                await asyncio.sleep(2)
                
            success = raptorchat_manager.start(is_delayed_start=True)
            
            final_text = ""
            if success:
                logger.info_system("RaptorChat started successfully after delay")
                final_text = f"🔄 {msg_header}\n\n💬 RaptorChat connected successfully"
            else:
                logger.error_system("Failed to start RaptorChat after delay")
                final_text = f"🔄 {msg_header}\n\n⚠️ Failed to reconnect"

            # Send single atomic result message
            if discord_manager and channel:
                 await discord_manager.send_temp_message(channel, final_text)

        except Exception as e:
            logger.error_system(f"Error in delayed RaptorChat restart: {e}")
            if discord_manager and channel:
                await discord_manager.send_temp_message(channel, f"❌ Error restarting RaptorChat: {e}")
