import logging
import logging.handlers
import os
import datetime
import time
from typing import Dict, Optional, Set
from collections import defaultdict

LOG_PATH = "logs"

class LogManager:
    """Enhanced centralized logging management with rate limiting and contextual logging"""
    def __init__(self):
        self.last_cleanup_date = None
        self.debug_enabled = False
        self._setup_logging()
        
        # Rate limiting configuration
        self.rate_limits = {
            'DEBUG': {'interval': 5, 'max_count': 10},     # 10 debug messages per 5 seconds
            'INFO': {'interval': 10, 'max_count': 20},     # 20 info messages per 10 seconds
            'WARNING': {'interval': 30, 'max_count': 10},  # 10 warnings per 30 seconds
            'ERROR': {'interval': 60, 'max_count': 5},     # 5 errors per 60 seconds
        }
        
        # Rate limiting state
        self.message_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.last_reset: Dict[str, float] = {}
        self.suppressed_counts: Dict[str, int] = defaultdict(int)
        
        # Context tracking
        self.context_stack: list = []
        self.global_context: Dict[str, str] = {}
        
        # Message categorization
        self.categories = {
            'PLAYER': 'Player tracking and management',
            'SERVER': 'Server operations and status',
            'RCON': 'RCON commands and connections',
            'BACKUP': 'Backup and restore operations',
            'UPDATE': 'Update and version management',
            'DISCORD': 'Discord bot operations',
            'SYSTEM': 'System monitoring and performance',
            'CONFIG': 'Configuration management',
            'SCHEDULE': 'Scheduled operations',
            'PERFORMANCE': 'Performance metrics and optimization',
        }
    
    def _setup_logging(self):
        os.makedirs(LOG_PATH, exist_ok=True)
        
        # Suppress Discord.py debug output
        discord_logger = logging.getLogger('discord')
        discord_logger.setLevel(logging.WARNING)
        
        # Suppress PyNaCl warning message
        pynacl_logger = logging.getLogger('discord.gateway')
        pynacl_logger.addFilter(lambda record: 'PyNaCl is not installed' not in record.getMessage())
        
        # Create rotating file handler with 10MB size limit and 10 backup files
        log_file = os.path.join(LOG_PATH, datetime.datetime.now().strftime("patchraptor_%d-%m-%y.log"))
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=10,
            encoding='utf-8'
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%d-%m-%y %H:%M:%S'
        ))
        
        # Configure root logger
        self.root_logger = logging.getLogger()
        self.root_logger.setLevel(logging.INFO)
        self.root_logger.addHandler(file_handler)
        
        # Simple console handler - just use print with flush
        class SimpleConsoleHandler(logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    print(msg, flush=True)
                except Exception:
                    pass
        
        console_handler = SimpleConsoleHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%d-%m-%y %H:%M:%S'
        ))
        self.root_logger.addHandler(console_handler)
    
    def get_current_log_file(self) -> str:
        return os.path.join(
            LOG_PATH,
            datetime.datetime.now().strftime("patchraptor_%d-%m-%y.log")
        )
    
    def log(self, msg: str, level: str = "INFO", category: Optional[str] = None, context: Optional[Dict[str, str]] = None):
        """Enhanced logging with rate limiting, categorization, and context"""
        level_upper = level.upper()
        
        # Skip debug messages if debug is disabled
        if level_upper == "DEBUG" and not self.debug_enabled:
            return
            
        log_level = getattr(logging, level_upper, logging.INFO)
        
        # Apply rate limiting
        if self._is_rate_limited(msg, level_upper):
            return
        
        # Add context and category information
        enhanced_msg = self._enhance_message(msg, category, context)
        
        # Log to console using unbuffered handler
        self.root_logger.log(log_level, enhanced_msg)
        
        # Log to file with enhanced formatting
        try:
            current_log_file = self.get_current_log_file()
            with open(current_log_file, "a", encoding="utf-8") as f:
                ts = datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S")
                category_str = f"[{category}]" if category else ""
                context_str = self._format_context(context) if context else ""
                f.write(f"{ts}|{level:<7}|{category_str:<12}|{enhanced_msg}{context_str}\n")
            self._manage_log_files()
        except Exception:
            pass
    
    def _is_rate_limited(self, msg: str, level: str) -> bool:
        """Check if message should be rate limited"""
        if level not in self.rate_limits:
            return False
            
        config = self.rate_limits[level]
        current_time = time.time()
        
        # Reset counters if interval has passed
        if level not in self.last_reset or current_time - self.last_reset[level] > config['interval']:
            # Report suppressed messages
            if self.suppressed_counts[level] > 0:
                suppressed_msg = f"[RATE_LIMIT] Suppressed {self.suppressed_counts[level]} duplicate {level} messages"
                self.root_logger.log(getattr(logging, level), suppressed_msg)
                self.suppressed_counts[level] = 0
            
            self.message_counts[level].clear()
            self.last_reset[level] = current_time
        
        # Check if we've exceeded the limit
        if self.message_counts[level][msg] >= config['max_count']:
            self.suppressed_counts[level] += 1
            return True
        
        self.message_counts[level][msg] += 1
        return False
    
    def _enhance_message(self, msg: str, category: Optional[str], context: Optional[Dict[str, str]]) -> str:
        """Enhance message with category and context information"""
        enhanced = msg
        
        # Add category prefix if specified
        if category and category in self.categories:
            enhanced = f"[{category}] {enhanced}"
        elif category:
            enhanced = f"[{category}] {enhanced}"
        
        # Add global context
        if self.global_context:
            context_parts = [f"{k}={v}" for k, v in self.global_context.items()]
            if context_parts:
                enhanced += f" | {', '.join(context_parts)}"
        
        return enhanced
    
    def _format_context(self, context: Dict[str, str]) -> str:
        """Format context information for logging"""
        if not context:
            return ""
        context_parts = [f"{k}={v}" for k, v in context.items()]
        return f" | Context: {', '.join(context_parts)}"
    
    def set_global_context(self, **kwargs):
        """Set global context that will be included in all log messages"""
        self.global_context.update(kwargs)
    
    def clear_global_context(self):
        """Clear all global context"""
        self.global_context.clear()
    
    def push_context(self, **kwargs):
        """Push context onto the stack for nested operations"""
        self.context_stack.append(kwargs)
    
    def pop_context(self):
        """Pop context from the stack"""
        if self.context_stack:
            self.context_stack.pop()
    
    def get_current_context(self) -> Dict[str, str]:
        """Get merged context from stack and global context"""
        context = self.global_context.copy()
        for stack_context in self.context_stack:
            context.update(stack_context)
        return context
    
    def debug_player(self, msg: str, **context):
        """Convenience method for player-related debug messages"""
        self.log(msg, level="DEBUG", category="PLAYER", context=context)
    
    def info_player(self, msg: str, **context):
        """Convenience method for player-related info messages"""
        self.log(msg, level="INFO", category="PLAYER", context=context)
    
    def warning_player(self, msg: str, **context):
        """Convenience method for player-related warning messages"""
        self.log(msg, level="WARNING", category="PLAYER", context=context)
    
    def error_player(self, msg: str, **context):
        """Convenience method for player-related error messages"""
        self.log(msg, level="ERROR", category="PLAYER", context=context)
    
    def debug_server(self, msg: str, **context):
        """Convenience method for server-related debug messages"""
        self.log(msg, level="DEBUG", category="SERVER", context=context)
    
    def info_server(self, msg: str, **context):
        """Convenience method for server-related info messages"""
        self.log(msg, level="INFO", category="SERVER", context=context)
    
    def warning_server(self, msg: str, **context):
        """Convenience method for server-related warning messages"""
        self.log(msg, level="WARNING", category="SERVER", context=context)
    
    def error_server(self, msg: str, **context):
        """Convenience method for server-related error messages"""
        self.log(msg, level="ERROR", category="SERVER", context=context)
    
    def debug_performance(self, msg: str, **context):
        """Convenience method for performance-related debug messages"""
        self.log(msg, level="DEBUG", category="PERFORMANCE", context=context)
    
    def debug_rcon(self, msg: str, **context):
        """Convenience method for RCON-related debug messages"""
        self.log(msg, level="DEBUG", category="RCON", context=context)
    
    def debug_backup(self, msg: str, **context):
        """Convenience method for backup-related debug messages"""
        self.log(msg, level="DEBUG", category="BACKUP", context=context)
    
    def debug_discord(self, msg: str, **context):
        """Convenience method for Discord-related debug messages"""
        self.log(msg, level="DEBUG", category="DISCORD", context=context)
    
    def debug_schedule(self, msg: str, **context):
        """Convenience method for schedule-related debug messages"""
        self.log(msg, level="DEBUG", category="SCHEDULE", context=context)
    
    def debug_update(self, msg: str, **context):
        """Convenience method for update-related debug messages"""
        self.log(msg, level="DEBUG", category="UPDATE", context=context)
    
    def debug_config(self, msg: str, **context):
        """Convenience method for configuration-related debug messages"""
        self.log(msg, level="DEBUG", category="CONFIG", context=context)
    
    def debug_system(self, msg: str, **context):
        """Convenience method for system-related debug messages"""
        self.log(msg, level="DEBUG", category="SYSTEM", context=context)
    
    def info_performance(self, msg: str, **context):
        """Convenience method for performance-related info messages"""
        self.log(msg, level="INFO", category="PERFORMANCE", context=context)
    
    def info_system(self, msg: str, **context):
        """Convenience method for system-related info messages"""
        self.log(msg, level="INFO", category="SYSTEM", context=context)
    
    def info_discord(self, msg: str, **context):
        """Convenience method for Discord command info messages"""
        self.log(msg, level="INFO", category="DISCORD", context=context)
    
    def info_command(self, msg: str, **context):
        """Convenience method for command info messages with DISCORD prefix"""
        self.log(msg, level="INFO", category="DISCORD", context=context)
    
    def warning_system(self, msg: str, **context):
        """Convenience method for system-related warning messages"""
        self.log(msg, level="WARNING", category="SYSTEM", context=context)
    
    def error_system(self, msg: str, **context):
        """Convenience method for system-related error messages"""
        self.log(msg, level="ERROR", category="SYSTEM", context=context)
    
    def toggle_debug(self) -> bool:
        """Toggle debug logging on/off and return new state"""
        self.debug_enabled = not self.debug_enabled
        
        # Also update the console logging level to show/hide debug messages
        if self.debug_enabled:
            self.root_logger.setLevel(logging.DEBUG)
        else:
            self.root_logger.setLevel(logging.INFO)
            
        return self.debug_enabled
    
    def is_debug_enabled(self) -> bool:
        """Check if debug logging is currently enabled"""
        return self.debug_enabled
    
    def _manage_log_files(self):
        current_date = datetime.datetime.now().date()
        if self.last_cleanup_date == current_date:
            return
        try:
            # Clean up old log files, keeping only the last 10
            import re
            log_pattern = re.compile(r'^patchraptor_.*\.log(\.\d+)?$')
            log_files = sorted(
                (f for f in os.listdir(LOG_PATH)
                 if log_pattern.match(f)),
                reverse=True
            )
            for old_log in log_files[10:]:
                try:
                    os.remove(os.path.join(LOG_PATH, old_log))
                except Exception:
                    pass
            self.last_cleanup_date = current_date
        except Exception:
            pass


# Singleton logger for convenience
logger = LogManager()

# Simple SteamCMD execution - SteamCMD buffers output internally so real-time isn't possible
import asyncio
import subprocess
import threading

async def execute_steamcmd_simple(cmd_args):
    """
    Execute SteamCMD with basic subprocess execution.
    SteamCMD internally buffers output, so real-time display isn't possible.
    Runs in a thread to avoid blocking the asyncio event loop.
    """
    
    logger.info_system("Starting SteamCMD process...")
    
    # Run subprocess in a thread to avoid blocking event loop
    def run_subprocess():
        return subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
    
    # Execute in thread to prevent Discord heartbeat timeouts
    result = await asyncio.to_thread(run_subprocess)
    
    # Log output after completion (SteamCMD only releases output at the end)
    if result.stdout:
        for line in result.stdout.strip().split('\n'):
            if line.strip():
                print(line, flush=True)
    
    if result.stderr:
        for line in result.stderr.strip().split('\n'):
            if line.strip():
                print(f"ERROR: {line}", flush=True)
    
    return result

