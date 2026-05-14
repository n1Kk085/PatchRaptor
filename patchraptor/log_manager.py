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
        # We apply this specifically to the discord logger and all children
        class NoisyFilter(logging.Filter):
            def filter(self, record):
                msg = record.getMessage()
                # Suppress both the log version and the warning version
                if "PyNaCl is not installed" in msg:
                    return False
                if "pkg_resources is deprecated" in msg:
                    return False
                if "voice will NOT be supported" in msg:
                    return False
                return True
        
        # Capture all python warnings into the logging system so we can filter them
        logging.captureWarnings(True)
        
        # Apply to root, discord, and py.warnings loggers
        logging.getLogger().addFilter(NoisyFilter())
        logging.getLogger('discord').addFilter(NoisyFilter())
        logging.getLogger('py.warnings').addFilter(NoisyFilter())
        
        # FORCE discord logger to ERROR level to prevent the WARNING from even being generated
        logging.getLogger('discord.client').setLevel(logging.ERROR)
        logging.getLogger('discord.gateway').setLevel(logging.ERROR)
        
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
        file_handler.addFilter(NoisyFilter())
        self.root_logger.addHandler(file_handler)
        
        # Simple console handler - just use print with flush
        class SimpleConsoleHandler(logging.Handler):
            def emit(self, record):
                try:
                    msg = self.format(record)
                    if msg.strip():
                        print(msg, flush=True)
                except Exception:
                    pass
        
        console_handler = SimpleConsoleHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(asctime)s|%(levelname)s|%(message)s',
            datefmt='%d-%m-%y %H:%M:%S'
        ))
        console_handler.addFilter(NoisyFilter())
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
        
        # Log to console and file using standard logging
        try:
            self.root_logger.log(log_level, enhanced_msg)
        except Exception:
            # Fallback for when standard logging fails
            try:
                print(f"{datetime.datetime.now().strftime('%d-%m-%y %H:%M:%S')}|{level_upper:<7}|FAILED_TO_LOG|{enhanced_msg}", flush=True)
            except:
                pass

    def debug(self, msg: str, **context):
        """Standard logging debug level method"""
        self.log(msg, level="DEBUG", context=context)

    def info(self, msg: str, **context):
        """Standard logging info level method"""
        self.log(msg, level="INFO", context=context)

    def warning(self, msg: str, **context):
        """Standard logging warning level method"""
        self.log(msg, level="WARNING", context=context)

    def error(self, msg: str, **context):
        """Standard logging error level method"""
        self.log(msg, level="ERROR", context=context)

    def critical(self, msg: str, **context):
        """Standard logging critical level method"""
        self.log(msg, level="CRITICAL", context=context)
    
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
    
    # --- Convenience Category Methods ---
    def debug_player(self, msg, **ctx): self.log(msg, level="DEBUG", category="PLAYER", context=ctx)
    def info_player(self, msg, **ctx): self.log(msg, level="INFO", category="PLAYER", context=ctx)
    def warning_player(self, msg, **ctx): self.log(msg, level="WARNING", category="PLAYER", context=ctx)
    def error_player(self, msg, **ctx): self.log(msg, level="ERROR", category="PLAYER", context=ctx)
    
    def debug_server(self, msg, **ctx): self.log(msg, level="DEBUG", category="SERVER", context=ctx)
    def info_server(self, msg, **ctx): self.log(msg, level="INFO", category="SERVER", context=ctx)
    def warning_server(self, msg, **ctx): self.log(msg, level="WARNING", category="SERVER", context=ctx)
    def error_server(self, msg, **ctx): self.log(msg, level="ERROR", category="SERVER", context=ctx)
    
    def debug_system(self, msg, **ctx): self.log(msg, level="DEBUG", category="SYSTEM", context=ctx)
    def info_system(self, msg, **ctx): self.log(msg, level="INFO", category="SYSTEM", context=ctx)
    def warning_system(self, msg, **ctx): self.log(msg, level="WARNING", category="SYSTEM", context=ctx)
    def error_system(self, msg, **ctx): self.log(msg, level="ERROR", category="SYSTEM", context=ctx)
    
    def debug_web(self, msg, **ctx): self.log(msg, level="DEBUG", category="WEB", context=ctx)
    def info_web(self, msg, **ctx): self.log(msg, level="INFO", category="WEB", context=ctx)
    def warning_web(self, msg, **ctx): self.log(msg, level="WARNING", category="WEB", context=ctx)
    def error_web(self, msg, **ctx): self.log(msg, level="ERROR", category="WEB", context=ctx)
    
    def debug_discord(self, msg, **ctx): self.log(msg, level="DEBUG", category="DISCORD", context=ctx)
    def info_discord(self, msg, **ctx): self.log(msg, level="INFO", category="DISCORD", context=ctx)
    def info_command(self, msg, **ctx): self.log(msg, level="INFO", category="DISCORD", context=ctx)
    
    def debug_performance(self, msg, **ctx): self.log(msg, level="DEBUG", category="PERFORMANCE", context=ctx)
    def info_performance(self, msg, **ctx): self.log(msg, level="INFO", category="PERFORMANCE", context=ctx)
    
    def debug_rcon(self, msg, **ctx): self.log(msg, level="DEBUG", category="RCON", context=ctx)
    def debug_backup(self, msg, **ctx): self.log(msg, level="DEBUG", category="BACKUP", context=ctx)
    def debug_schedule(self, msg, **ctx): self.log(msg, level="DEBUG", category="SCHEDULE", context=ctx)
    def debug_update(self, msg, **ctx): self.log(msg, level="DEBUG", category="UPDATE", context=ctx)
    def debug_config(self, msg, **ctx): self.log(msg, level="DEBUG", category="CONFIG", context=ctx)
    
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
    
    # Try to determine CWD from the steamcmd path
    cwd = None
    if cmd_args and os.path.exists(str(cmd_args[0])):
        cwd = os.path.dirname(os.path.abspath(str(cmd_args[0])))
        logger.debug_update(f"Setting SteamCMD working directory to: {cwd}")

    # Run subprocess in a thread to avoid blocking event loop
    def run_subprocess():
        import subprocess
        creationflags = 0
        target_cmd = [str(x) for x in cmd_args]
        
        if os.name == 'nt':
            # Create a dedicated console session to physically simulate a .bat file
            creationflags = subprocess.CREATE_NEW_CONSOLE
        # Create the exact command string to mirror a manual batch file - this prevents 
        # Windows 11 from mangling arguments with extra quotes.
        # Format: start /wait "Title" "PathToExe" Args
        exe_path = str(target_cmd[0])
        
        # Intelligently quote arguments that contain spaces to ensure shell compatibility
        processed_args = []
        for arg in target_cmd[1:]:
            s_arg = str(arg)
            if " " in s_arg and not (s_arg.startswith('"') and s_arg.endswith('"')):
                processed_args.append(f'"{s_arg}"')
            else:
                processed_args.append(s_arg)
        
        args_str = " ".join(processed_args)
        
        # Build the final command string
        full_cmd = f'start /wait "PatchRaptor SteamCMD" "{exe_path}" {args_str}'
        logger.debug_update(f"Executing mirrored shell command: {full_cmd}")
        
        # Execute using shell=True to allow 'start' to function as a native command
        result = subprocess.run(
            full_cmd,
            cwd=cwd,
            shell=True,
            creationflags=creationflags,
            timeout=7200
        )
            
        # Read SteamCMD's *native* generated log file instead of trying to trap it in Python
        output_txt = ""
        try:
            # SteamCMD inherently writes failures to its own root logs folder
            native_log = os.path.join(cwd if cwd else os.getcwd(), "logs", "stderr.txt")
            if os.path.exists(native_log):
                with open(native_log, "r", encoding="utf-8", errors="replace") as read_file:
                    output_txt = read_file.read()[-3000:] # Last 3000 chars
        except Exception as e:
            output_txt = f"Could not extract SteamCMD log tail: {str(e)}"
            
        result.stdout = output_txt
        result.stderr = None
        return result
    
    # Execute in thread to prevent Discord heartbeat timeouts
    result = await asyncio.to_thread(run_subprocess)
    
    # Dump the tail logs cleanly so Patchraptor system logs still see success/failure 
    try:
        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    print(line, flush=True)
    except Exception:
        pass
    
    return result

