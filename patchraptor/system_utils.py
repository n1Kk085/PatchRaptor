import asyncio
from .log_manager import logger

class SystemUtils:
    """Unified utility for cross-module system operations"""
    
    @staticmethod
    async def unified_system_recovery(
        delay: int, 
        channel, 
        raptorchat_manager, 
        player_manager, 
        discord_manager,
        telemetry_manager = None,
        msg_header: str = "Reconnecting system components after restart..."
    ):
        """
        Coordinates recovery of all system components in the correct order.
        1. Resumes and triggers log detection for PlayerManager.
        2. Releases maintenance for RaptorChat.
        3. Restarts RaptorChat after the specified delay.
        4. Sends unified status updates to Discord once RaptorChat has actually started.
        """
        # Check if already connected to avoid misleading logs
        is_already_running = raptorchat_manager and raptorchat_manager.is_running()
        
        if is_already_running:
            delay = 0 # Skip the reconnection wait if already online
        else:
            duration_str = SystemUtils.format_duration(delay)
            logger.info_system(f"RaptorChat will reconnect in {duration_str}...")
        
        # 0. Telemetry/Log Reset (Ensures we start fresh after any system operation)
        if telemetry_manager:
            try:
                logger.debug_system("Triggering telemetry log reset during recovery")
                await telemetry_manager.trigger_log_file_detection_on_restart()
            except Exception as e:
                logger.error_system(f"Error during telemetry reset: {e}")

        # 1. PlayerManager Recovery (should happen immediately to catch early log lines)
        if player_manager:
            try:
                logger.debug_system("Resuming PlayerManager monitoring")
                player_manager.resume()
            except Exception as e:
                logger.error_system(f"Error resuming PlayerManager: {e}")

        # 2. RaptorChat Recovery (Scheduled to start after delay)
        if raptorchat_manager:
            try:
                await raptorchat_manager.start_with_delay(delay)

                # Wait for the delayed start task to actually execute before checking status
                if delay > 0:
                    await asyncio.sleep(delay + 5)  # Give it time to complete its sleep and check/start cycle
                else:
                    # Even with 0 delay, wait briefly for async operation to complete
                    await asyncio.sleep(1)

                # Check actual running status after delay completes
                is_running = raptorchat_manager.is_running()
                if is_running:
                    logger.debug_system("RaptorChat started successfully during recovery")
                    final_text = f"{msg_header}\n\n☑️ All systems online and operational"
                else:
                    logger.error_system("Failed to start RaptorChat during recovery")
                    final_text = f"{msg_header}\n\n⚠️ Failed to reconnect chat relay"

                # 3. Discord Notification
                if discord_manager and channel:
                    await discord_manager.send_temp_message(channel, final_text)

            except Exception as e:
                logger.error_system(f"Error during RaptorChat recovery: {e}")
                if discord_manager and channel:
                    await discord_manager.send_temp_message(channel, f"❌ Error recovering RaptorChat: {e}")
        else:
            logger.debug_system("No RaptorChat manager provided for recovery")

    @staticmethod
    def get_directory_size(path: str) -> int:
        """
        Calculate total size of a directory in bytes.
        Optimized to handle missing files or permission errors during scan.
        """
        import os
        total_size = 0
        try:
            if not os.path.exists(path):
                return 0
            for dirpath, dirnames, filenames in os.walk(path):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        # Skip if it is a symbolic link
                        if not os.path.islink(fp):
                            total_size += os.path.getsize(fp)
                    except (OSError, FileNotFoundError):
                        continue
        except Exception:
            pass
        return total_size

    @staticmethod
    def generate_progress_bar(percent, width=10):
        """
        Generates a text-based progress bar using block characters.
        Example: [■■■■□□□□□□] 40%
        """
        filled = int((percent / 100) * width)
        bar = "■" * filled + "□" * (width - filled)
        return f"[{bar}] {percent:.1f}%"

    @staticmethod
    def format_duration(seconds: int) -> str:
        """Format seconds into a compact string like '1d 2h 3m' or '45m 12s'"""
        if seconds < 0: return "0s"
        
        d = seconds // (24 * 3600)
        seconds %= (24 * 3600)
        h = seconds // 3600
        seconds %= 3600
        m = seconds // 60
        s = seconds % 60
        
        parts = []
        if d > 0: parts.append(f"{d}d")
        if h > 0: parts.append(f"{h}h")
        if m > 0: parts.append(f"{m}m")
        if s > 0 or not parts: parts.append(f"{s}s")
        
        return " ".join(parts[:3]) # Return top 3 units for compactness
