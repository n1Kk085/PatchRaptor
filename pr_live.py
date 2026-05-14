"""
PatchRaptor Live Web Panel
Standalone web panel for ARK server monitoring
Refactored for Safety, Efficiency, and Modular Design
"""

import datetime
import json
import logging
import os
import sys
import threading
import time
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from flask import Flask, jsonify, render_template, request, Response, send_from_directory
import psutil
from asgiref.sync import async_to_sync

# Local imports
from patchraptor.log_manager import logger as pr_logger, LOG_PATH
logger = pr_logger
# Monkeypatch missing methods to maintain compatibility with existing LogManager
if not hasattr(logger, 'info_web'):
    logger.info_web = lambda msg, **kwargs: logger.info(msg, **kwargs)
if not hasattr(logger, 'error_web'):
    logger.error_web = lambda msg, **kwargs: logger.error(msg, **kwargs)

from patchraptor.config import ConfigManager as CoreConfigManager
from patchraptor.models import ServerConfig
from patchraptor.ark_log_utils import normalize_map_name

class ConfigManager(CoreConfigManager):
    def __init__(self, config_file: str = None, validate: bool = False):
        super().__init__(config_file=config_file or 'config.json')

# Path configuration
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    UI_FOLDER = os.path.join(BASE_DIR, 'static')
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')
    UI_FOLDER = os.path.join(BASE_DIR, 'static')

CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
WEBPANEL_CONFIG_FILE = os.path.join(BASE_DIR, 'webpanel_config.json')

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
    last_update: str = ''
    current_time: str = ''

class MapImageResolver:
    """Resolves map names to image files in static/maps"""
    def __init__(self, static_folder: str):
        self.maps_dir = os.path.join(static_folder, 'maps')
        self.image_cache = {}
        self.default_image = '/static/maps/default.jpg'

    def get_image_url(self, map_name: str) -> str:
        if not map_name:
            return self.default_image
            
        normalized_target = normalize_map_name(map_name)
        if normalized_target in self.image_cache:
            return self.image_cache[normalized_target]
            
        if not os.path.exists(self.maps_dir):
            return self.default_image
            
        try:
            for filename in os.listdir(self.maps_dir):
                if filename.lower().endswith(('.jpg', '.png', '.webp', '.jpeg')):
                    base_name = os.path.splitext(filename)[0]
                    if normalize_map_name(base_name) == normalized_target:
                        # Use root-relative path for serving
                        url = f'/maps/{filename}'
                        self.image_cache[normalized_target] = url
                        return url
            
            self.image_cache[normalized_target] = '/maps/default.jpg'
            return '/maps/default.jpg'
        except OSError:
            return self.default_image

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
        with self._lock:
            s = self._status
            return {
                'servers': s.servers,
                'serverPlayerAverages': s.server_player_averages,
                'serverUptimeAverages': s.server_uptime_averages,
                'totalPlayers': s.total_players,
                'total7dayPlayerAvg': s.total_7day_player_avg,
                'total7dayUptimeAvg': s.total_7day_uptime_avg,
                'serverCount': s.server_count,
                'onlineCount': s.online_count,
                'lastUpdate': s.last_update,
                'currentTime': s.current_time
            }

class PatchRaptorPanel:
    def __init__(self):
        self.config_manager = ConfigManager(validate=False)
        self.webpanel_config = self._load_webpanel_config()
        self.servers = self.config_manager.get_server_configs()
        self.live_state_file = os.path.join(LOG_PATH, 'cluster_live.json')
        self.server_status_cache = ServerStatusCache()
        self.map_image_resolver = MapImageResolver(STATIC_FOLDER)
        self.event_loop = asyncio.new_event_loop()
        self.app = self._create_flask_app()
        
        class WebCategoryFilter(logging.Filter):
            def filter(self, record):
                if isinstance(record.msg, str) and not record.msg.startswith('['):
                    record.msg = f'[WEB] {record.msg}'
                return True
        
        logging.getLogger().addFilter(WebCategoryFilter())
        logging.getLogger('waitress').addFilter(WebCategoryFilter())
        logging.getLogger('werkzeug').addFilter(WebCategoryFilter())

    def _load_webpanel_config(self) -> Dict:
        try:
            with open(WEBPANEL_CONFIG_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error_web(f"Failed to load webpanel config: {e}")
            sys.exit(1)

    def _create_flask_app(self):
        app = Flask(__name__, static_folder=STATIC_FOLDER, static_url_path='')
        
        # Ensure maps directory exists for resolver
        os.makedirs(os.path.join(STATIC_FOLDER, 'maps'), exist_ok=True)

        @app.route('/')
        def index():
            if not self._check_auth():
                return self._authenticate()
            return send_from_directory(STATIC_FOLDER, 'index.html')

        # Serve static assets from root for compatibility with various UI versions
        @app.route('/js/<path:path>')
        def send_js(path):
            return send_from_directory(STATIC_FOLDER, path)
            
        @app.route('/css/<path:path>')
        def send_css(path):
            return send_from_directory(STATIC_FOLDER, path)
            
        @app.route('/images/<path:path>')
        def send_images(path):
            return send_from_directory(STATIC_FOLDER, path)

        @app.route('/maps/<path:path>')
        def send_maps(path):
            return send_from_directory(os.path.join(STATIC_FOLDER, 'maps'), path)

        @app.route('/static/<path:path>')
        def send_static(path):
            return send_from_directory(STATIC_FOLDER, path)

        @app.route('/style.css')
        def send_style():
            return send_from_directory(STATIC_FOLDER, 'style.css')

        @app.route('/dashboard.js')
        def send_dashboard():
            return send_from_directory(STATIC_FOLDER, 'dashboard.js')
            
        @app.route('/api/status')
        def status():
            if not self._check_auth():
                return self._authenticate()
            return jsonify(self.server_status_cache.get_dict())
            

            
        @app.route('/api/me')
        def me():
            if not self._check_auth():
                return self._authenticate()
            auth = request.authorization
            return jsonify({'username': auth.username if auth else 'Guest'})
            
        @app.route('/favicon.ico')
        def favicon():
            return Response(b'', mimetype='image/x-icon')
            
        @app.after_request
        def set_security_headers(response):
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self';"
            response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
            response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=(), payment=()'
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            return response
            
        import logging as flask_logging
        flask_logging.getLogger('werkzeug').setLevel(flask_logging.ERROR)
        
        return app

    def _check_auth(self):
        auth = request.authorization
        config_auth = self.webpanel_config.get('auth', {})
        if not config_auth or not config_auth.get('username') or not config_auth.get('password'):
            return True
            
        return auth and auth.username == config_auth.get('username') and auth.password == config_auth.get('password')

    def _authenticate(self):
        return Response('Login Required', 401, {'WWW-Authenticate': 'Basic realm="PatchRaptor Panel"'})

    async def initialize(self):
        asyncio.create_task(self._background_update_loop())

    async def _background_update_loop(self):
        while True:
            try:
                await self._update_server_status()
            except Exception as e:
                logger.error_web(f"Error in telemetry subscriber: {e}")
            await asyncio.sleep(2)

    async def _update_server_status(self):
        if not os.path.exists(self.live_state_file):
            return
            
        try:
            with open(self.live_state_file, 'r') as f:
                web_data = json.load(f)
                
            for server in web_data.get('servers', []):
                server['mapimage'] = self.map_image_resolver.get_image_url(server.get('mapName', ''))
                
            panel_status = PanelStatus(
                servers=web_data.get('servers', []),
                server_player_averages=web_data.get('serverPlayerAverages', {}),
                server_uptime_averages=web_data.get('serverUptimeAverages', {}),
                total_players=web_data.get('totalPlayers', 0),
                total_7day_player_avg=web_data.get('total7dayPlayerAvg', 0.0),
                total_7day_uptime_avg=web_data.get('total7dayUptimeAvg', 0.0),
                server_count=web_data.get('serverCount', 0),
                online_count=web_data.get('onlineCount', 0),
                last_update=web_data.get('lastUpdate', ''),
                current_time=web_data.get('currentTime', '')
            )
            
            self.server_status_cache.update(panel_status)
        except json.JSONDecodeError:
            # Transient race condition or empty file - skip this pulse
            pass
        except Exception as e:
            logger.error_web(f"Failed to read live telemetry: {e}")

    def _save_pid(self):
        pid_file = os.path.join(BASE_DIR, '.webpanel.pid')
        try:
            with open(pid_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception:
            pass

    def run(self):
        self._save_pid()
        
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
            
        t = threading.Thread(target=run_loop, args=(self.event_loop,), daemon=True)
        t.start()
        
        try:
            future = asyncio.run_coroutine_threadsafe(self.initialize(), self.event_loop)
            future.result(timeout=30)
            
            logger.info_web("Real-time server monitor active...")
            logger.info_web("Syncing with server telemetry stats...")
            
            from waitress import serve
            host = self.webpanel_config.get('host', '0.0.0.0')
            port = int(self.webpanel_config.get('port', 8095))
            
            logger.info_web(f"🌐 WebPanel is ready for local connections on port {port}")
            serve(self.app, host=host, port=port)
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
        except KeyboardInterrupt:
            pass
        finally:
            self.event_loop.call_soon_threadsafe(self.event_loop.stop())

def main():
    try:
        panel = PatchRaptorPanel()
        panel.run()
    except Exception as e:
        logger.error_web(f"Fatal error starting panel: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
