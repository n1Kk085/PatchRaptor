import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from threading import Event

# Allow importing patchraptor modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from patchraptor import log_utils


# -----------------------
# Config
# -----------------------
# -----------------------
# Config
# -----------------------
parser = argparse.ArgumentParser(description='RaptorChat Chat Relay')
parser.add_argument('--config', type=str, help='Path to config.json', default=None)
args, _ = parser.parse_known_args()

config_path = args.config
if not config_path:
    # Fallback checks
    if os.path.exists("config.json"):
        config_path = "config.json"
    elif os.path.exists("../config.json"):
        config_path = "../config.json"
    else:
        # Last ditch: try to find it in the current working directory if it's not the script dir
        cwd_config = os.path.join(os.getcwd(), "config.json")
        if os.path.exists(cwd_config):
            config_path = cwd_config
        else:
            print("ERROR: Could not find config.json")
            sys.exit(1)

with open(config_path, "r", encoding="utf-8") as f:
    config = json.load(f)

RCON_CLI_PATH = config.get("rcon_tool", "")

# Support both "cluster_servers" (main app) and "servers" (legacy chat2)
if "cluster_servers" in config:
    SERVERS = config["cluster_servers"]
else:
    SERVERS = config.get("servers", [])

# -----------------------
# Logging (identical pattern to pr1.py)
# -----------------------
LOG_PATH = "logs"


class LogManager:
    """Centralized logging management (copied from pr1.py)"""

    def __init__(self):
        self.last_cleanup_date = None
        self._setup_logging()

    def _setup_logging(self):
        os.makedirs(LOG_PATH, exist_ok=True)
        
        # Clear any existing handlers
        logging.basicConfig(handlers=[])
        
        # Set up console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(asctime)s|%(levelname)s|%(message)s', datefmt='%d-%m-%y %H:%M:%S')
        console_handler.setFormatter(console_formatter)
        
        # Get root logger and configure it
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        
        # Prevent propagation to avoid duplicate logs
        root_logger.propagate = False

    def log(self, msg: str, level: str = "INFO"):
        # Add [CHAT] prefix to all messages
        prefixed_msg = f"[CHAT] {msg}"
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        # Log to console via root logger
        logging.log(log_level, prefixed_msg)
        
        # Write to daily log file (same format and rotation policy)
        try:
            current_log_file = self.get_current_log_file()
            with open(current_log_file, "a", encoding="utf-8") as f:
                timestamp = datetime.datetime.now().strftime("%d-%m-%y %H:%M:%S")
                f.write(f"{timestamp}|{level:<7}|{prefixed_msg}\n")
            self._manage_log_files()
        except Exception as e:
            logging.error(f"Failed to write to log file: {e}")
            # Also print to stderr as a fallback
            print(f"{datetime.datetime.now().strftime('%d-%m-%y %H:%M:%S')}|ERROR|Failed to write to log: {e}", file=sys.stderr)

    # Generic Logger compatibility methods
    def info(self, msg, *args, **kwargs): self.log(msg, "INFO")
    def error(self, msg, *args, **kwargs): self.log(msg, "ERROR")
    def warning(self, msg, *args, **kwargs): self.log(msg, "WARNING")
    def debug(self, msg, *args, **kwargs): 
        # Only log debug if we want verbose output (optional)
        pass

    def _manage_log_files(self):
        current_date = datetime.datetime.now().strftime("%d-%m-%y")
        if hasattr(self, '_last_cleanup_date') and self._last_cleanup_date == current_date:
            return
            
        try:
            log_files = sorted(
                (
                    f
                    for f in os.listdir(LOG_PATH)
                    if f.startswith("patchraptor_") and f.endswith(".log")
                ),
                reverse=True,
            )
            
            # Only keep the 7 most recent log files
            old_logs = log_files[7:]
            if old_logs:
                removed_count = 0
                for old_log in old_logs:
                    try:
                        os.remove(os.path.join(LOG_PATH, old_log))
                        removed_count += 1
                    except Exception:
                        pass
                if removed_count > 0:
                    # Use print instead of self.log to avoid recursion
                    print(f"Cleaned up {removed_count} old log files")
            
            self._last_cleanup_date = current_date
        except Exception as e:
            print(f"Error during log cleanup: {e}")

    def get_current_log_file(self) -> str:
        return os.path.join(
            LOG_PATH,
            datetime.datetime.now().strftime("patchraptor_%d-%m-%y.log")
        )


logger = LogManager()


# -----------------------
# Globals
# -----------------------
shutdown_event = Event()
log_threads = []



# -----------------------
# Multi-server RCON wrapper with retry logic
# -----------------------
class MultiRCON:
    def __init__(self, servers):
        self.servers = servers

    def send(self, server_name, message, retries=3):
        server = next((s for s in self.servers if s["name"] == server_name), None)
        if not server:
            logger.log(f"Server {server_name} not found", "ERROR")
            return False

        # Support both 'rcon_ip' (main app) and 'rcon_host' (legacy)
        rcon_ip = server.get("rcon_ip", server.get("rcon_host"))
        if not rcon_ip:
             logger.log(f"No RCON IP/Host found for server {server_name}", "ERROR")
             return False

        cmd = (
            f'"{RCON_CLI_PATH}" ip={rcon_ip} port={server["rcon_port"]} '
            f'pwd={server["rcon_password"]} cmd="ServerChat {message}"'
        )

        for attempt in range(retries):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    return True
                else:
                    if attempt < retries - 1:
                        logger.log(
                            f"RCON attempt {attempt + 1} failed for {server_name}, retrying...",
                            "WARNING",
                        )
                        time.sleep(2 ** attempt)
                    else:
                        logger.log(
                            f"RCON failed for {server_name} after {retries} attempts: {result.stderr.strip()}",
                            "ERROR",
                        )
                        return False
            except Exception as e:
                if attempt < retries - 1:
                    logger.log(
                        f"RCON error for {server_name} (attempt {attempt + 1}), retrying: {e}",
                        "WARNING",
                    )
                    time.sleep(2 ** attempt)
                else:
                    logger.log(
                        f"RCON error for {server_name} after {retries} attempts: {e}",
                        "ERROR",
                    )
                    return False
        return False


# -----------------------
# Parse player name from log line
# -----------------------
def extract_player_and_message(line):
    """
    Extract player name and message from ARK chat log format.
    Based on actual ARK log format: [timestamp][frame]date_time: PlayerName (CharacterName): message
    Returns (player_name, message) or (None, None) if not found or not a "/" message.
    """

    match = re.search(
        r"\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}:\s*([^(]+)\s*\([^)]+\):\s*(/.*)",
        line,
    )
    if match:
        player_name = match.group(1).strip()
        message = match.group(2).strip()
        return player_name, message

    return None, None


# -----------------------
# Log file following with graceful shutdown
# -----------------------
def follow_log(server):
    """Follow a server's log file and process chat messages."""
    server_name = server["name"]
    current_log_file = None
    file_handle = None
    file_pos = 0  # Track position manually
    
    while not shutdown_event.is_set():
        try:
            # 1. Resolve log file path if not set or if we need to find it
            current_config = next((s for s in SERVERS if s["name"] == server_name), None)
            if not current_config:
                logger.log(f"Server {server_name} no longer in config", "WARNING")
                time.sleep(5)
                continue
                
            config_log_file = current_config.get("server_log_path")
            
            # If we don't have a valid handle, try to open the file
            if file_handle is None:
                # If path changed or not set, find it
                if current_log_file != config_log_file or not config_log_file or not os.path.exists(config_log_file):
                     # Run dynamic detection just for this server/log if needed
                     # But first check if config has it
                     if config_log_file and os.path.exists(config_log_file):
                         current_log_file = config_log_file
                     else:
                         # Try to find it using log_utils
                         found_log = log_utils.find_matching_log_file(current_config, log_utils.get_logs_directory(SERVERS), logger=logger)
                         if found_log and found_log != current_log_file:
                             logger.log(f"Found new log file for {server_name}: {os.path.basename(found_log)}", "INFO")
                             current_log_file = found_log
                             # Update config reference in memory so we don't re-search constantly
                             current_config["server_log_path"] = current_log_file
                
                # Try open
                if current_log_file and os.path.exists(current_log_file):
                    try:
                        file_handle = open(current_log_file, "r", encoding="utf-8", errors="replace")
                        # Always seek to end on first open to avoid processing old chat
                        file_handle.seek(0, 2)
                        file_pos = file_handle.tell()
                        logger.log(f"Opened log file for {server_name}: {os.path.basename(current_log_file)}", "DEBUG")
                    except Exception as e:
                        logger.log(f"Error opening log file {current_log_file}: {e}", "ERROR")
                        time.sleep(5)
                        continue
                else:
                    # No log file found, wait and retry
                    time.sleep(5)
                    continue

            # 2. Check for rotation / restart (The "Smart" Check)
            try:
                current_size = os.path.getsize(current_log_file)
                if current_size < file_pos:
                    logger.log(f"Log rotation detected for {server_name} (Size: {current_size} < Pos: {file_pos})", "INFO")
                    # Close handle to force re-open
                    file_handle.close()
                    file_handle = None
                    file_pos = 0
                    
                    # Re-scan immediately to find new file (server might have renamed old one and created new one)
                    found_log = log_utils.find_matching_log_file(current_config, log_utils.get_logs_directory(SERVERS), logger=logger)
                    if found_log:
                        current_log_file = found_log
                        current_config["server_log_path"] = current_log_file
                    continue
            except (OSError, FileNotFoundError):
                logger.log(f"Log file disappeared for {server_name}", "WARNING")
                if file_handle:
                    file_handle.close()
                    file_handle = None
                time.sleep(2)
                continue

            # 3. Read Lines
            try:
                line = file_handle.readline()
                if line:
                    file_pos = file_handle.tell() # Update pos only after successful read
                    handle_line(server, line)
                else:
                    time.sleep(0.1)
            except Exception as e:
                logger.log(f"Error reading log file {current_log_file}: {e}", "ERROR")
                file_handle.close()
                file_handle = None
                time.sleep(1)

        except Exception as e:
            logger.log(f"Unexpected error in log follower for {server_name}: {e}", "ERROR")
            if file_handle:
                # noinspection PyBroadException
                try:
                    file_handle.close()
                except Exception:
                    pass
                file_handle = None
            time.sleep(5)
    
    # Cleanup on exit
    if file_handle:
        file_handle.close()


# -----------------------
# Handle a line from log
# -----------------------
def handle_line(server, line):
    player_name, message = extract_player_and_message(line)
    if not message or not message.startswith('/'):
        return

    clean_message = message[1:] if message.startswith('/') else message
    # Use map_abbrev if available, then display_name, otherwise name
    server_display = server.get('map_abbrev', server.get('display_name', server['name']))
    if player_name:
        relay_message = f"[{server_display}] {player_name}: {clean_message}"
    else:
        relay_message = f"[{server_display}] {clean_message}"

    logger.log(f"{relay_message}", "INFO")

    all_success = True
    failed_servers = []

    for s in SERVERS:
        if s["name"] != server["name"]:
            ok = rcon.send(s["name"], relay_message)
            if not ok:
                all_success = False
                failed_servers.append(s["name"])
            time.sleep(0.5)

    if not all_success:
        logger.log(f"Failed to relay to: {', '.join(failed_servers)}", "WARNING")


# -----------------------
# Status monitoring
# -----------------------
def status_loop():
    """Status monitoring loop that checks for issues"""
    # Initial delay to let threads start up
    for _ in range(5):  # Wait up to 5 seconds for threads to start
        if shutdown_event.is_set():
            return
        time.sleep(1)
    
    # Only log if there are issues
    last_status = (len(SERVERS), len(SERVERS))
    
    while not shutdown_event.is_set():
        try:
            alive_count = sum(1 for t in log_threads if t.is_alive())
            
            # Only log if there's an issue or status has changed
            current_status = (alive_count, len(SERVERS))
            if current_status != last_status:
                if alive_count == 0:
                    logger.log("Warning: No log threads are currently active", "WARNING")
                elif alive_count < len(SERVERS):
                    logger.log(f"Warning: Only {alive_count} of {len(SERVERS)} log threads are active", "WARNING")
                else:
                    logger.log(f"All {alive_count} log threads are active and running", "INFO")
                last_status = current_status
            
            # Check if RCON tool exists
            if not os.path.exists(RCON_CLI_PATH):
                logger.log(f"RCON tool missing: {RCON_CLI_PATH}", "ERROR")
                
        except Exception as e:
            logger.log(f"Error in status loop: {e}", "ERROR")
        
        # Wait for 1 minute or until shutdown is requested
        shutdown_event.wait(60)


# -----------------------
# Dynamic Log File Detection (Delegated to log_utils)
# -----------------------
def get_logs_directory():
    """Extract the logs directory path from configuration"""
    return log_utils.get_logs_directory(SERVERS, logger)

def extract_server_info_from_log(log_file_path):
    """Extract server identification information from log file content"""
    return log_utils.extract_server_info_from_log(log_file_path, logger)

def find_matching_log_file(server_config, exclude_files=None):
    """Find the correct log file for a server based on its RCON port"""
    logs_dir = get_logs_directory()
    return log_utils.find_matching_log_file(server_config, logs_dir, exclude_files, logger)


def update_server_log_files():
    """Update all server log file paths based on dynamic detection"""
    logger.log("Starting dynamic log file detection", "INFO")
    start_time = time.time()
    updates_made = False
    assigned_log_files = set()  # Track which log files are already assigned
    logs_dir = get_logs_directory()
    
    if not logs_dir or not os.path.isdir(logs_dir):
        logger.log(f"Logs directory not found: {logs_dir}", "ERROR")
        return False
    
    try:
        # First, find all potential log files in the logs directory
        log_files = []
        try:
            for filename in os.listdir(logs_dir):
                if filename.startswith("ShooterGame") and filename.endswith(".log"):
                    log_path = os.path.join(logs_dir, filename)
                    log_files.append(log_path)
        except Exception as e:
            logger.log(f"Error scanning logs directory {logs_dir}: {e}", "ERROR")
            return False
        
        if not log_files:
            logger.log(f"No ShooterGame_*.log files found in {logs_dir}", "WARNING")
            return False
        
        # Cache server info for each log file
        log_file_info = {}
        for log_path in log_files:
            try:
                info = extract_server_info_from_log(log_path)
                if info:
                    log_file_info[log_path] = info
            except Exception as e:
                logger.log(f"Error processing log file {log_path}: {e}", "ERROR")
        
        # Process each server to find the best log file match
        for i, server in enumerate(SERVERS):
            server_name = server["name"]
            current_log_file = server.get("server_log_path")
            # Skip servers without a log file path
            if not current_log_file:
                current_log_file = ""
            
            # If current log file is valid and exists, don't overwrite it
            if current_log_file and os.path.exists(current_log_file):
                logger.log(f"Log file already correct for {server_name}: {os.path.basename(current_log_file)}", "INFO")
                assigned_log_files.add(current_log_file)
                continue

                
            # Find the best matching log file for this server
            best_match = find_matching_log_file(server, assigned_log_files)
            
            if best_match:
                 logger.log(f"Best match for {server_name}: {os.path.basename(best_match)}", "INFO")
            
            # If we found a match and it's different from the current one, update it
            if best_match and best_match != current_log_file:
                logger.log(f"Updating log file for {server_name}:", "INFO")
                logger.log(f"  From: {os.path.basename(current_log_file)}", "INFO")
                logger.log(f"  To:   {os.path.basename(best_match)}", "INFO")
                
                # Update the server config
                SERVERS[i]["server_log_path"] = best_match
                assigned_log_files.add(best_match)
                updates_made = True
            elif best_match:  # Log file is already correct
                logger.log(f"Log file already correct for {server_name}: {os.path.basename(best_match)}", "INFO")
                assigned_log_files.add(best_match)
        
        # Save config if updates were made
        if updates_made:
            try:
                with open("config.json", "w", encoding="utf-8") as f:
                    # Update parameters are already in the SERVERS list reference (which points to config object)
                    # We just need to dump the config object.
                    # Explicitly ensuring the correct key is updated if we were using a disconnected list
                    if "cluster_servers" in config:
                        config["cluster_servers"] = SERVERS
                    else:
                        config["servers"] = SERVERS
                    
                    json.dump(config, f, indent=2)
                logger.log("Dynamic log file detection completed", "INFO")
            except Exception as e:
                logger.log(f"Failed to update config.json: {e}", "ERROR")
        
        return updates_made
        
    except Exception as e:
        logger.log(f"Error in update_server_log_files: {e}", "ERROR")
        return False


# -----------------------
# Main
# -----------------------
if __name__ == "__main__":
    try:
        # Initialize RCON and start monitoring
        
        rcon = MultiRCON(SERVERS)
        logger.log(f"Starting chat monitoring for {len(SERVERS)} servers", "INFO")
        
        # Always run detection on startup to resolve log_dir -> log_file
        update_server_log_files()
        
        if not os.path.exists(RCON_CLI_PATH):
            logger.log(f"RCON tool not found: {RCON_CLI_PATH}", "ERROR")
            sys.exit(1)
        
        # Start status thread
        status_thread = threading.Thread(target=status_loop, daemon=True)
        status_thread.start()
        
        # Start log following threads for each server
        log_threads = []
        for server in SERVERS:
            t = threading.Thread(
                target=follow_log,
                args=(server,),
                daemon=True,
                name=server["name"],
            )
            t.start()
            log_threads.append(t)
        
        # Verify all threads are running
        running_threads = sum(1 for t in log_threads if t.is_alive())
        logger.log(f"All {running_threads} log threads are active and running", "INFO")

        try:
            # Keep the main thread alive
            while not shutdown_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.log("Shutdown requested via keyboard interrupt", "INFO")
            shutdown_event.set()
        except Exception as e:
            logger.log(f"Unexpected error: {e}", "ERROR")
            shutdown_event.set()
        finally:
            logger.log("Shutting down RaptorChat...", "INFO")
            
            # Signal all threads to stop
            shutdown_event.set()
            
            # Wait for log threads to finish with a timeout
            for i, t in enumerate(log_threads):
                if t.is_alive():
                    logger.log(f"Waiting for log thread {i} to finish...", "INFO")
                    t.join(timeout=5)
                    if t.is_alive():
                        logger.log(f"Log thread {i} did not shut down cleanly", "WARNING")
            
            # Wait for status thread
            if status_thread and status_thread.is_alive():
                logger.log("Waiting for status thread to finish...", "INFO")
                status_thread.join(timeout=5)
                if status_thread.is_alive():
                    logger.log("Status thread did not shut down cleanly", "WARNING")
            
            logger.log("Shutdown complete", "INFO")
            sys.exit(0)
        
    except Exception as e:
        import traceback
        logger.log(f"Fatal error: {e}\n{traceback.format_exc()}", "ERROR")
        shutdown_event.set()
        sys.exit(1)
{{ ... }}
