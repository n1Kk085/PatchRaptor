import os
import re
import logging

# Unified Map Patterns (Merged from PlayerManager and RaptorChat)
MAP_PATTERNS = [
    r"TheIsland",
    r"ScorchedEarth",
    r"Ragnarok",
    r"TheCenter",
    r"Aberration",
    r"Extinction",
    r"Genesis",
    r"ClubArk",
    r"Valguero",
    r"CrystalIsles",
    r"LostIsland",
    r"Astraeos",
    r"LostColony",  # From RaptorChat
    r"Fjordur"
]

# Unified RCON Patterns (Merged from global lists)
RCON_PATTERNS = [
    r"RCONPort=(\d+)",              # Command line parameter
    r"RCONPort\s+(\d+)",            # Alternative format
    r"-RCONPort[= ](\d+)",          # Command line flag (combined)
    r"RCON.*started.*port\s+(\d+)", # Fallback patterns
    r"RCON.*listening.*port\s+(\d+)",
    r"RCON.*port\s+(\d+)",
    r"Starting.*RCON.*port\s+(\d+)"
]

def extract_server_info_from_log(log_file_path, logger=None):
    """
    Extract server identification information from log file content.
    Returns a dict with 'map_name', 'rcon_port', and 'last_modified'.
    """
    if not logger:
        logger = logging.getLogger('LogUtils')

    try:
        if not os.path.exists(log_file_path):
            return None
        
        # Read first 300 lines (increased from 200 for safety) to find server identification info
        with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = []
            for _ in range(300):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
        
        if not lines:
            return None
        
        server_info = {
            "map_name": None,
            "rcon_port": None,
            "last_modified": os.path.getmtime(log_file_path)
        }
        
        # First pass: Look for command line arguments (usually in first few lines)
        for line in lines:
            # Look for RCON port
            if not server_info["rcon_port"]:
                for pattern in RCON_PATTERNS:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        port = int(match.group(1))
                        # Only accept ports in a reasonable range (1000-65535)
                        if 1000 <= port <= 65535:
                            server_info["rcon_port"] = port
                            break
            
            # Look for map name
            if not server_info["map_name"]:
                for map_name in MAP_PATTERNS:
                    if map_name.lower() in line.lower():
                        server_info["map_name"] = map_name.lower()
                        break
            
            # If we found both, we're done
            if server_info["rcon_port"] and server_info["map_name"]:
                break
        
        return server_info if (server_info["map_name"] or server_info["rcon_port"]) else None
        
    except Exception as e:
        if logger:
            logger.error(f"Error reading log file {log_file_path}: {e}")
        return None

def get_logs_directory(servers, logger=None):
    """
    Extract the logs directory path from a list of server configurations.
    'servers' can be a list of dicts (RaptorChat) or objects (PlayerManager).
    """
    if not servers:
        return None
        
    # Helper to get attribute or dict key
    def get_val(obj, key):
        if isinstance(obj, dict):
            return obj.get(key)
        return getattr(obj, key, None)

    # 1. Try to get explicit log_dir from config first (Robust)
    for server in servers:
        log_dir = get_val(server, 'log_dir')
        if log_dir and os.path.exists(log_dir):
            return log_dir
    
    # 2. Fallback: Get the directory from the first server's log_file path
    first_log_file = get_val(servers[0], 'server_log_path')
    if first_log_file and os.path.exists(os.path.dirname(first_log_file)):
        return os.path.dirname(first_log_file)
        
    # 3. Fallback: Derive from server_save_path
    for server in servers:
        save_path = get_val(server, 'server_save_path')
        if save_path:
            # Normalize path
            save_path = os.path.normpath(save_path)
            # save_path is typically .../Saved/MapName
            # Logs are .../Saved/Logs
            saved_dir = os.path.dirname(save_path)
            logs_dir = os.path.join(saved_dir, "Logs")
            
            if os.path.isdir(logs_dir):
                if logger:
                    # Generic debug log
                    pass 
                return logs_dir
    
    return None

def find_matching_log_file(server, logs_dir, assigned_files=None, logger=None):
    """
    Find the correct log file for a server based on its RCON port.
    CRITICAL: Picks the NEWEST file if multiple match.
    """
    if not logger:
        logger = logging.getLogger('LogUtils')
    
    if not logs_dir:
        return None
    
    # Handle dict (RaptorChat) vs Object (PlayerManager)
    if isinstance(server, dict):
        server_name = server.get('name')
        expected_rcon_port = int(server.get('rcon_port') or 0) if server.get('rcon_port') else None
    else:
        server_name = getattr(server, 'name')
        expected_rcon_port = getattr(server, 'rcon_port', None)

    assigned_files = assigned_files or set()
    
    # Find all ShooterGame_*.log files, excluding backups
    log_files = []
    try:
        for filename in os.listdir(logs_dir):
            if (filename.startswith("ShooterGame") and 
                filename.endswith(".log") and 
                'backup' not in filename.lower()):  # Skip backup files
                log_path = os.path.join(logs_dir, filename)
                # Skip already assigned files
                if log_path in assigned_files:
                    continue
                log_files.append(log_path)
        
        # KEY FIX: Sort by modification time (newest first)
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
    except Exception as e:
        logger.error(f"Error scanning logs directory {logs_dir}: {e}")
        return None
    
    if not log_files:
        return None
    
    # Check each log file for matching RCON port
    for log_file in log_files:
        server_info = extract_server_info_from_log(log_file, logger)
        
        # Debug logging would go here if needed
        
        if server_info and server_info.get("rcon_port") == expected_rcon_port:
            return log_file
            
    return None
