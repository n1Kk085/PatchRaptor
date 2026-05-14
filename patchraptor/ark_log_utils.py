import os
import re
import logging

MAP_PATTERNS = ['TheIsland', 'ScorchedEarth', 'Ragnarok', 'TheCenter', 'Aberration', 'Extinction', 'Genesis', 'ClubArk', 'Valguero', 'CrystalIsles', 'LostIsland', 'Astraeos', 'LostColony', 'Fjordur']

RCON_PATTERNS = ['RCONPort=(\\d+)', 'RCONPort\\s+(\\d+)', '-RCONPort[= ](\\d+)', 'RCON.*started.*port\\s+(\\d+)', 'RCON.*listening.*port\\s+(\\d+)', 'RCON.*port\\s+(\\d+)', 'Starting.*RCON.*port\\s+(\\d+)']

JOIN_PATTERNS = [
    re.compile(r'\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}: (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] joined this ARK!$', re.IGNORECASE),
    re.compile(r': (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] joined this ARK!', re.IGNORECASE)
]

LEAVE_PATTERNS = [
    re.compile(r'\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}: (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] left this ARK!$', re.IGNORECASE),
    re.compile(r': (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] left this ARK!', re.IGNORECASE)
]

UNIQUE_ID_PATTERNS = [re.compile(r'[0-9a-f]{32}')]

def extract_server_info_from_log(log_file_path, logger=None):
    if not logger:
        logger = logging.getLogger('LogUtils')
    
    if not os.path.exists(log_file_path):
        return None
        
    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = []
            for _ in range(300):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
                
        if not lines:
            return None
            
        server_info = {
            'map_name': None,
            'rcon_port': None,
            'last_modified': os.path.getmtime(log_file_path)
        }
        
        for line in lines:
            if not server_info['rcon_port']:
                for pattern in RCON_PATTERNS:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        port = int(match.group(1))
                        if 1000 <= port <= 65535:
                            server_info['rcon_port'] = port
                            break
            
            if not server_info['map_name']:
                for map_name in MAP_PATTERNS:
                    if map_name.lower() in line.lower():
                        server_info['map_name'] = map_name.lower()
                        break
                        
            if server_info['rcon_port'] and server_info['map_name']:
                break
                
        if server_info['map_name'] or server_info['rcon_port']:
            return server_info
        return None
        
    except Exception as e:
        if logger:
            logger.error(f"Error reading log file {log_file_path}: {e}")
        return None

def get_val(obj, key):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)

def get_logs_directory(servers, logger=None, get_val=get_val):
    if not servers:
        return None
        
    for server in servers:
        log_dir = get_val(server, 'log_dir')
        if log_dir and os.path.exists(log_dir):
            return log_dir
            
    first_log_file = get_val(servers[0], 'server_log_path')
    if first_log_file and os.path.exists(os.path.dirname(first_log_file)):
        return os.path.dirname(first_log_file)
        
    for server in servers:
        save_path = get_val(server, 'server_save_path')
        if not save_path:
            continue
        save_path = os.path.normpath(save_path)
        saved_dir = os.path.dirname(save_path)
        logs_dir = os.path.join(saved_dir, 'Logs')
        if os.path.isdir(logs_dir):
            return logs_dir
            
    return None

def normalize_map_name(name: str) -> str:
    if not name:
        return ''
    name = name.lower().replace('_wp', '')
    return name.replace(' ', '').replace('_', '').replace('-', '')

def find_matching_log_file(server, logs_dir, assigned_files=None, logger=None):
    if not logger:
        logger = logging.getLogger('LogUtils')
        
    if not logs_dir:
        return None
        
    if isinstance(server, dict):
        server_name = server.get('name')
        expected_rcon_port = int(server.get('rcon_port')) if server.get('rcon_port') else None
    else:
        server_name = getattr(server, 'name')
        expected_rcon_port = getattr(server, 'rcon_port', None)
        
    if assigned_files is None:
        assigned_files = set()
        
    log_files = []
    try:
        for filename in os.listdir(logs_dir):
            if not filename.startswith('ShooterGame') or not filename.endswith('.log'):
                continue
            if 'backup' in filename.lower():
                continue
            log_path = os.path.join(logs_dir, filename)
            if log_path in assigned_files:
                continue
            log_files.append(log_path)
            
        log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        
        if not log_files:
            return None
            
        for log_file in log_files:
            server_info = extract_server_info_from_log(log_file, logger)
            if not server_info:
                continue
            if server_info.get('rcon_port') == expected_rcon_port:
                return log_file
                
        return None
    except Exception as e:
        logger.error(f"Error scanning logs directory {logs_dir}: {e}")
        return None
