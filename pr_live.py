#!/usr/bin/env python3
"""
PatchRaptor Live Web Panel
Standalone web panel for ARK server monitoring
Refactored for Safety, Efficiency, and Modular Design
"""

import datetime
import json
import logging
import os
import subprocess
import sys
import threading
import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from flask import Flask, jsonify, render_template, request, Response, send_from_directory
import psutil
from asgiref.sync import async_to_sync

# --- Logging Setup ---
try:
    from patchraptor.log_manager import logger as pr_logger
    logger = pr_logger
except ImportError:
    # Standard fallback if not running as part of the package
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger("PR-Live")

# --- Import PlayerManager ---
# Try to import PlayerManager from various locations safely
try:
    from patchraptor.player_manager import PlayerManager
except ImportError:
    try:
        # Try local import if in same directory
        from player_manager import PlayerManager
    except ImportError:
        # Try adding 'patchraptor' to path if running from parent
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'patchraptor'))
        try:
             from player_manager import PlayerManager
        except ImportError:
             # Fallback for development/testing structure
             sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
             from patchraptor.player_manager import PlayerManager

# --- Constants & Config ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    TEMPLATE_FOLDER = os.path.join(BASE_DIR, 'templates')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    TEMPLATE_FOLDER = os.path.join(BASE_DIR, 'templates')

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
WEBPANEL_CONFIG_FILE = os.path.join(BASE_DIR, 'webpanel_config.json')

# --- Data Structures ---

@dataclass
class ServerConfig:
    """Server configuration data class"""
    name: str
    display_name: str
    map_name: str
    rcon_ip: str
    rcon_port: int
    rcon_password: str
    start_command: str
    install_dir: str
    server_save_path: str
    server_log_path: str

@dataclass
class ServerStatus:
    name: str
    display_name: str
    map_name: str
    map_image: str
    status: str  # 'online' or 'offline'
    player_count: int
    cpu: float
    ram: float
    uptime_7day: float
    player_avg_7day: float
    server_7day_avg: float

@dataclass
class PanelStatus:
    servers: List[Dict[str, Any]] = field(default_factory=list)
    server_player_averages: Dict[str, float] = field(default_factory=dict)
    server_uptime_averages: Dict[str, float] = field(default_factory=dict)
    total_players: int = 0
    total_7day_player_avg: float = 0.0
    total_7day_uptime_avg: float = 0.0
    server_count: int = 0
    online_count: int = 0
    last_update: str = ""
    current_time: str = ""

# --- Helper Classes ---

class ConfigManager:
    """Manages application configuration and validation"""
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = self._load_config()
        # self._validate_config() # Validation can prevent startup if config changes, rely on .get mostly
        
    def _load_config(self) -> Dict:
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            # If main config fails, we might still want to run if we just need basic settings
            logger.warning(f"Could not load main config {self.config_file}: {e}")
            return {}

    def get(self, key: str, default=None):
        return self.config.get(key, default)
    
    def get_server_configs(self) -> List[ServerConfig]:
        servers = []
        for srv_config in self.config.get("cluster_servers", []):
            try:
                servers.append(ServerConfig(
                    name=srv_config["name"],
                    display_name=srv_config.get("display_name", srv_config["name"]),
                    map_name=srv_config.get("map_name", ""),
                    rcon_ip=srv_config["rcon_ip"],
                    rcon_port=int(srv_config["rcon_port"]),
                    rcon_password=srv_config["rcon_password"],
                    start_command=srv_config["start_command"],
                    install_dir=srv_config.get("install_dir", self.config.get("server_dir", "")),
                    server_save_path=srv_config.get("server_save_path", ""),
                    server_log_path=srv_config.get("server_log_path", "")
                ))
            except KeyError as e:
                logger.error(f"Invalid server config, missing key: {e}")
        return servers

class MapImageResolver:
    """Resolves map names to image files in static/maps"""
    def __init__(self, static_folder: str):
        self.maps_dir = os.path.join(static_folder, 'maps')
        self.image_cache = {}
        self.default_image = '/static/maps/default.jpg'

    def _normalize(self, name: str) -> str:
        # Remove common ASA suffix '_WP' before normalizing
        name = name.lower().replace('_wp', '')
        return name.replace(' ', '').replace('_', '').replace('-', '')

    def get_image_url(self, map_name: str) -> str:
        if not map_name:
            return self.default_image

        normalized_target = self._normalize(map_name)
        
        # Check cache first
        if normalized_target in self.image_cache:
            return self.image_cache[normalized_target]

        # Scan directory
        if not os.path.exists(self.maps_dir):
            return self.default_image

        try:
            for filename in os.listdir(self.maps_dir):
                if filename.lower().endswith(('.jpg', '.png', '.webp', '.jpeg')):
                    base_name = os.path.splitext(filename)[0]
                    if self._normalize(base_name) == normalized_target:
                        url = f'/static/maps/{filename}'
                        self.image_cache[normalized_target] = url
                        return url
            
            # Legacy/Fallback mapping if no file found
            # Keep the old hardcoded list as a fallback for standard maps if user hasn't downloaded images
            # logic: if we didn't find a file, we can check if it's a known map 
            # but usually we expect the file to exist.
            # Returning default if not found.
            self.image_cache[normalized_target] = self.default_image
            return self.default_image
            
        except OSError:
            return self.default_image

class UptimeTracker:
    """Tracks server uptime statistics over time."""
    def __init__(self, data_file: str = 'uptime_stats.json'):
        self.data_file = data_file
        self.data = self._load_data()
        self._cleanup_old_entries()
        self._dirty = False
    
    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading uptime stats: {e}")
        return {}
    
    def save(self):
        """Save data to file if marked as dirty."""
        if not self._dirty:
            return
            
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            self._dirty = False
        except Exception as e:
            logger.error(f"Error saving uptime stats: {e}")
    
    def _cleanup_old_entries(self):
        week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        changed = False
        if 'servers' in self.data:
            for server_name in list(self.data['servers'].keys()):
                server_data = self.data['servers'][server_name]
                new_entries = [e for e in server_data.get('entries', []) if e.get('timestamp', 0) >= week_ago]
                if len(new_entries) != len(server_data.get('entries', [])):
                    server_data['entries'] = new_entries
                    changed = True
                if not server_data['entries']:
                    self.data['servers'].pop(server_name, None)
                    changed = True
        
        if changed:
            self._dirty = True
            # We don't save immediately here, caller should call save()

    def record_uptime(self, server_name: str, is_online: bool):
        if not server_name: return
        if 'servers' not in self.data: self.data['servers'] = {}
        if server_name not in self.data['servers']:
            self.data['servers'][server_name] = {'entries': []}
        
        self.data['servers'][server_name]['entries'].append({
            'timestamp': time.time(),
            'is_online': is_online
        })
        self._dirty = True
        # Don't save immediately to avoid I/O spam
    
    def get_server_7day_uptime(self, server_name: str) -> float:
        if not server_name or server_name not in self.data.get('servers', {}): return 0.0
        entries = self.data['servers'][server_name].get('entries', [])
        if not entries: return 0.0
        online_count = sum(1 for e in entries if e.get('is_online', False))
        return (online_count / len(entries)) * 100.0

    def get_average_7day_uptime(self) -> float:
        if not self.data.get('servers'): return 0.0
        total_uptime = 0.0
        server_count = 0
        for server_name in self.data['servers']:
            total_uptime += self.get_server_7day_uptime(server_name)
            server_count += 1
        return total_uptime / server_count if server_count > 0 else 0.0

class PlayerStatsTracker:
    """Tracks player statistics over time."""
    def __init__(self, data_file: str = 'player_stats.json'):
        self.data_file = data_file
        self.data = self._load_data()
        self._cleanup_old_entries()
        self._dirty = False
    
    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading player stats: {e}")
        return {}
    
    def save(self):
        """Save data to file if marked as dirty."""
        if not self._dirty:
            return

        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            self._dirty = False
        except Exception as e:
            logger.error(f"Error saving player stats: {e}")
    
    def _cleanup_old_entries(self):
        week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        changed = False
        if 'servers' in self.data:
            for server_name in list(self.data['servers'].keys()):
                server_data = self.data['servers'][server_name]
                new_entries = [e for e in server_data.get('entries', []) if e.get('timestamp', 0) >= week_ago]
                if len(new_entries) != len(server_data.get('entries', [])):
                    server_data['entries'] = new_entries
                    changed = True
                if not server_data['entries']:
                    self.data['servers'].pop(server_name, None)
                    changed = True
        
        if changed:
            self._dirty = True
            
    def record_players(self, server_name: str, map_name: str, player_count: int):
        if not server_name: return
        if 'servers' not in self.data: self.data['servers'] = {}
        if server_name not in self.data['servers']:
            self.data['servers'][server_name] = {'map_name': map_name, 'entries': []}
            
        self.data['servers'][server_name]['entries'].append({
            'timestamp': time.time(),
            'player_count': player_count
        })
        self._dirty = True # Mark for saving

    def get_server_7day_avg(self, server_name: str) -> float:
        if not server_name or server_name not in self.data.get('servers', {}): return 0.0
        entries = self.data['servers'][server_name].get('entries', [])
        if not entries: return 0.0
        total_players = sum(e.get('player_count', 0) for e in entries)
        return total_players / len(entries)

    def get_total_7day_avg(self) -> float:
        if not self.data.get('servers'): return 0.0
        total_players = 0
        total_entries = 0
        
        # Determine strict 7 day window
        now = time.time()
        seven_days_ago = now - (7 * 24 * 60 * 60)
        
        for server_data in self.data['servers'].values():
            recent_entries = [e for e in server_data.get('entries', []) if e.get('timestamp', 0) >= seven_days_ago]
            if recent_entries:
                total_players += sum(e.get('player_count', 0) for e in recent_entries)
                total_entries += len(recent_entries)
                
        return round(total_players / total_entries, 1) if total_entries > 0 else 0.0

class ServerStatusCache:
    """Thread-safe cache for server status"""
    def __init__(self):
        self._lock = threading.Lock()
        self._status = PanelStatus()
    
    def update(self, status: PanelStatus):
        with self._lock:
            self._status = status
            
    def get(self) -> PanelStatus:
        with self._lock:
            return self._status
    
    def get_dict(self) -> Dict:
        """Return dict representation for JSON serialization"""
        with self._lock:
            return {
                'servers': self._status.servers,
                'serverPlayerAverages': self._status.server_player_averages,
                'serverUptimeAverages': self._status.server_uptime_averages,
                'totalPlayers': self._status.total_players,
                'total7dayPlayerAvg': self._status.total_7day_player_avg,
                'total7dayUptimeAvg': self._status.total_7day_uptime_avg,
                'serverCount': self._status.server_count,
                'onlineCount': self._status.online_count,
                'lastUpdate': self._status.last_update,
                'currentTime': self._status.current_time
            }

# --- Main Application Class ---

class PatchRaptorPanel:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.webpanel_config = self._load_webpanel_config()
        
        self.servers = self.config_manager.get_server_configs()
        self.player_manager = PlayerManager(self.servers, read_only=True)
        
        self.uptime_tracker = UptimeTracker()
        self.player_stats_tracker = PlayerStatsTracker()
        self.server_status_cache = ServerStatusCache()
        self.map_image_resolver = MapImageResolver(STATIC_FOLDER)
        
        self.event_loop = asyncio.new_event_loop()
        self.app = self._create_flask_app()
        self.running_processes_cache = {} # Cache psutil objects for accurate cpu_percent
        
    def _load_webpanel_config(self) -> Dict:
        try:
            with open(WEBPANEL_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config
        except Exception as e:
            logger.error(f"Failed to load webpanel config: {e}")
            sys.exit(1)
            
    def _create_flask_app(self) -> Flask:
        app = Flask(__name__, static_folder=STATIC_FOLDER, template_folder=TEMPLATE_FOLDER)
        
        # Ensure maps directory
        os.makedirs(os.path.join(STATIC_FOLDER, 'maps'), exist_ok=True)
        
        # Routes
        @app.route('/')
        def index():
            if not self._check_auth():
                return self._authenticate()
            return send_from_directory(TEMPLATE_FOLDER, 'index.html')
            
        @app.route('/api/status')
        def status():
            if not self._check_auth():
                return self._authenticate()
            return jsonify(self.server_status_cache.get_dict())
            
        @app.route('/static/<path:path>')
        def serve_static(path):
            return app.send_static_file(path)
            
        @app.route('/api/me')
        def me():
            if not self._check_auth():
                return self._authenticate()
            auth = request.authorization
            return jsonify({'username': auth.username if auth else 'Guest'})
            
        @app.route('/favicon.ico')
        def favicon():
            return Response(b'', mimetype='image/x-icon')
        
        # Minimal logging
        import logging as flask_logging
        flask_logging.getLogger('werkzeug').setLevel(flask_logging.ERROR)
        
        return app

    def _check_auth(self):
        auth = request.authorization
        config_auth = self.webpanel_config.get('auth', {})
        if not config_auth or not config_auth.get('username') or not config_auth.get('password'):
            return True # Open access if no auth configured
            
        return (auth and 
                auth.username == config_auth.get('username') and 
                auth.password == config_auth.get('password'))

    def _authenticate(self):
        return Response(
            'Login Required', 401,
            {'WWW-Authenticate': 'Basic realm="PatchRaptor Panel"'}
        )

    async def initialize(self):
        logger.info("Initializing PlayerManager...")
        await self.player_manager.initialize()
        
        # Start background task
        asyncio.create_task(self._background_update_loop())
        logger.info("Background update task started")

    async def _background_update_loop(self):
        while True:
            try:
                await self._update_server_status()
                # Periodic cleanup of trackers to save I/O
                self.uptime_tracker._cleanup_old_entries()
                self.player_stats_tracker._cleanup_old_entries()
                
                # Save data once per cycle if dirty
                self.uptime_tracker.save()
                self.player_stats_tracker.save()
                
            except Exception as e:
                logger.error(f"Error in background update: {e}")
                # import traceback
                # traceback.print_exc()
            await asyncio.sleep(30)

    async def _update_server_status(self):
        # 1. Update active players
        await self.player_manager.update_active_players()
        total_players, details = await self.player_manager.get_total_players()
        
        # 2. Bulk get process info for efficiency
        current_pids = set()
        
        try:
            # First pass: Identify relevant processes and ensure we have psutil objects
            for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
                try:
                    pinfo = proc.info
                    name = (pinfo['name'] or '').lower()
                    if 'arkascendedserver' in name or 'shootergameserver' in name:
                        pid = pinfo['pid']
                        current_pids.add(pid)
                        
                        # Cache process object if new to allow cpu_percent(interval=None) to work
                        if pid not in self.running_processes_cache:
                             self.running_processes_cache[pid] = psutil.Process(pid)
                             # Prime it
                             self.running_processes_cache[pid].cpu_percent()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Remove stale processes from cache
            stale_pids = set(self.running_processes_cache.keys()) - current_pids
            for pid in stale_pids:
                del self.running_processes_cache[pid]
                
        except Exception as e:
            logger.error(f"Error scanning processes: {e}")

        # 3. Build Server Status list
        servers_data = []
        server_player_avgs = {}
        server_uptime_avgs = {}
        online_count = 0
        
        for server in self.servers:
            # Check if running
            is_online = False
            cpu = 0.0
            ram = 0.0
            
            # Match process
            identifiers = [
                server.map_name.lower() if server.map_name else "",
                server.name.lower(),
                str(server.rcon_port)
            ]
            valid_idents = [i for i in identifiers if i]
            
            for pid, process_obj in self.running_processes_cache.items():
                try:
                    cmdline = ' '.join(process_obj.cmdline()).lower()
                    if any(ident in cmdline for ident in valid_idents):
                        is_online = True
                        # Get cached CPU percent (non-blocking if called previously)
                        cpu = process_obj.cpu_percent() / psutil.cpu_count()
                        ram = process_obj.memory_info().rss / (1024 ** 3)
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                     continue
            
            if is_online:
                online_count += 1
            
            # Track stats - Record in memory
            self.uptime_tracker.record_uptime(server.name, is_online)
            display_name = server.display_name or server.name
            player_list = details.get(display_name, [])
            count = len(player_list)
            self.player_stats_tracker.record_players(server.name, server.map_name, count)
            
            # Get Averages
            uptime_7d = self.uptime_tracker.get_server_7day_uptime(server.name)
            p_avg_7d = self.player_stats_tracker.get_server_7day_avg(server.name)
            
            server_player_avgs[server.name] = p_avg_7d
            server_uptime_avgs[server.name] = uptime_7d
            
            # Resolve Image
            map_image = self.map_image_resolver.get_image_url(server.map_name)

            server_status = {
                'name': server.name,
                'displayName': display_name,
                'mapName': (server.map_name or 'Unknown').replace('_', ' ').title(),
                'mapimage': map_image,
                'status': 'online' if is_online else 'offline',
                'playerCount': count,
                'cpu': round(cpu, 1),
                'ram': round(ram, 1),
                'uptime7day': round(uptime_7d, 1),
                'playerAvg7day': round(p_avg_7d, 1),
                'server7dayAvg': round(p_avg_7d, 1)
            }
            servers_data.append(server_status)

        # 4. Update Cache
        panel_status = PanelStatus(
            servers=servers_data,
            server_player_averages=server_player_avgs,
            server_uptime_averages=server_uptime_avgs,
            total_players=total_players,
            total_7day_player_avg=self.player_stats_tracker.get_total_7day_avg(),
            total_7day_uptime_avg=self.uptime_tracker.get_average_7day_uptime(),
            server_count=len(self.servers),
            online_count=online_count,
            last_update=datetime.datetime.now().isoformat(),
            current_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
        self.server_status_cache.update(panel_status)

    def run(self):
        # Threading for loop
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
            
        t = threading.Thread(target=run_loop, args=(self.event_loop,), daemon=True)
        t.start()
        
        # Init async
        future = asyncio.run_coroutine_threadsafe(self.initialize(), self.event_loop)
        try:
            future.result(timeout=30)
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            
        # Run Web Server
        from waitress import serve
        host = self.webpanel_config.get('host', '0.0.0.0')
        port = int(self.webpanel_config.get('port', 8080))
        
        logger.info(f"Starting PatchRaptor Web Panel on {host}:{port}")
        logger.info(f"Serving static files from: {STATIC_FOLDER}")
        
        try:
            serve(self.app, host=host, port=port)
        except KeyboardInterrupt:
            pass
        finally:
            self.event_loop.call_soon_threadsafe(self.event_loop.stop)


# --- Entry Point ---

def main():
    try:
        panel = PatchRaptorPanel()
        panel.run()
    except Exception as e:
        logger.error(f"Fatal error starting panel: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
