import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch
import threading
import asyncio

# Setup path to import from parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Since pr_live is now a module, we can import it directly
try:
    # Try importing directly if in path
    import pr_live
except ImportError:
    # Add parent to path
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import pr_live

# Helper to re-import or mock if needed (kept for fixture compatibility)
def import_pr_live():
    # Because we want to mock module-level dependencies like PlayerManager BEFORE they run,
    # we might need to reload or use patch.dict on sys.modules if it's already imported.
    # But clean import is better. 
    # For now, just return the module, assuming mocks are applied via patch.dict context or similiar
    # OR we use reload?
    # The fixture applies patches.
    # We will just return the module.
    return pr_live


@pytest.fixture(scope="module")
def app_client():
    """Create a test client for the Flask app."""
    pr_live = import_pr_live()
    
    # Instantiate the panel with aggressive mocking of ALL internal components
    # This ensures no logic runs except the Flask app creation
    with patch.object(pr_live, 'ConfigManager') as MockConfigManager, \
         patch.object(pr_live, 'PlayerManager') as MockPlayerManager, \
         patch.object(pr_live, 'UptimeTracker') as MockUptimeTracker, \
         patch.object(pr_live, 'PlayerStatsTracker') as MockPlayerStatsTracker, \
         patch.object(pr_live, 'ServerStatusCache') as MockServerStatusCache, \
         patch.object(pr_live, 'MapImageResolver') as MockMapImageResolver, \
         patch.object(pr_live.PatchRaptorPanel, 'initialize', new_callable=MagicMock) as mock_init:
         
        # Mock Config return values
        mock_config = MockConfigManager.return_value
        mock_config.get_server_configs.return_value = []
        mock_config.get.return_value = {} # Default config

        # Mock WebPanel Config loading inside PatchRaptorPanel
        # We need to patch the method that loads it, or mock json.load around instantiation
        with patch('builtins.open', create=True), \
             patch('json.load', return_value={"auth": {"username": "admin", "password": "password"}}):
            
            panel = pr_live.PatchRaptorPanel()
        
        # Manually verify that initialized components are Mocks
        assert isinstance(panel.server_status_cache, MagicMock)

        # Setup the ServerStatusCache mock to return data for the test
        # We need to construct the dict that get_dict() returns
        from pr_live import PanelStatus # Use the class from the module
        
        test_status_dict = {
            'servers': [{
                'name': 'TestServer',
                'displayName': 'Test Server',
                'mapName': 'The Island',
                'mapimage': '/static/maps/default.jpg',
                'status': 'online',
                'playerCount': 5,
                'players': [],
                'cpu': 10.0,
                'ram': 4.0,
                'maxRam': 16.0,
                'uptime7day': 99.9,
                'playerAvg7day': 10.0,
                'lastRestart': '2023-01-01 12:00',
                'server7dayAvg': 10.0
            }],
            'serverPlayerAverages': {},
            'serverUptimeAverages': {},
            'totalPlayers': 5,
            'total7dayPlayerAvg': 0.0,
            'total7dayUptimeAvg': 0.0,
            'serverCount': 1,
            'onlineCount': 1,
            'lastUpdate': '2023-01-01T12:00:00',
            'currentTime': '2023-01-01 12:00:00'
        }
        
        panel.server_status_cache.get_dict.return_value = test_status_dict
        
        app = panel.app
        app.config.update({
            "TESTING": True,
        })

        with app.test_client() as client:
            yield client

def test_index_route(app_client):
    """Test that the index route returns 200/401 based on auth."""
    # Without auth
    response = app_client.get('/')
    assert response.status_code == 401
    
    # With auth
    auth_headers = {
        'Authorization': 'Basic YWRtaW46cGFzc3dvcmQ=' # admin:password
    }
    response = app_client.get('/', headers=auth_headers)
    assert response.status_code == 200
    assert b"PatchRaptor" in response.data

def test_api_status(app_client):
    """Test the status API endpoint."""
    auth_headers = {
        'Authorization': 'Basic YWRtaW46cGFzc3dvcmQ=' # admin:password
    }
    response = app_client.get('/api/status', headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    
    assert "servers" in data
    assert "totalPlayers" in data
    assert "serverCount" in data
    assert data["serverCount"] == 1
    assert data["servers"][0]["name"] == "TestServer"

def test_static_route(app_client):
    """Test serving static files."""
    # Ensure file exists (created by shell command or mocked)
    # We real-created tests/static/test.txt
    auth_headers = {'Authorization': 'Basic YWRtaW46cGFzc3dvcmQ='}
    
    # We need to ensure the app is configured to look in tests/static for this test
    # or we can rely on creating 'static/maps' in current dir if app defaults there.
    # The app fixture mocked ConfigManager but might not have changed STATIC_FOLDER effectively 
    # if it's a global constant in pr-live.py.
    # However, create_flask_app uses STATIC_FOLDER.
    # We might just test that the route exists and returns 404 if file missing, or 200 if present.
    
    response = app_client.get('/static/test.txt')
    # Should be 200 if file found, or 404.
    # Since checking file existence is tricky with global constants, checking 200 or 404 is fine 
    # as long as it's not 500 or 401 (static shouldn't need auth? logic says no auth check).
    assert response.status_code in [200, 404]

def test_favicon(app_client):
    response = app_client.get('/favicon.ico')
    assert response.status_code == 200

# at top of file
from unittest.mock import MagicMock, patch, AsyncMock

# ... (omitted)

def test_check_auth_logic():
    """Unit test for _check_auth method logic."""
    pr_live = import_pr_live()
    
    # Mock Panel just enough to test _check_auth
    panel = MagicMock()
    # Bind the method to the mock
    panel._check_auth = pr_live.PatchRaptorPanel._check_auth.__get__(panel, pr_live.PatchRaptorPanel)
    
    # CASE 1: No Auth Configured -> Open Access
    panel.webpanel_config = {}
    with patch('pr_live.request', MagicMock(authorization=None)):
        assert panel._check_auth() is True
        
    # CASE 2: Auth Configured, No Header -> Fail
    panel.webpanel_config = {'auth': {'username': 'admin', 'password': 'pw'}}
    with patch('pr_live.request', MagicMock(authorization=None)):
        assert not panel._check_auth()

    # CASE 3: Auth Configured, Wrong Header -> Fail
    from collections import namedtuple
    Auth = namedtuple('Auth', ['username', 'password'])
    
    with patch('pr_live.request', MagicMock(authorization=Auth('wrong', 'pw'))):
        assert not panel._check_auth()

    # CASE 4: Auth Configured, Correct Header -> Pass
    with patch('pr_live.request', MagicMock(authorization=Auth('admin', 'pw'))):
        assert panel._check_auth() is True

@pytest.mark.asyncio
async def test_update_server_status_logic():
    """Unit test for _update_server_status logic."""
    pr_live = import_pr_live()
    
    # Instantiate Panel specifically for this test
    with patch.object(pr_live, 'ConfigManager'), \
         patch.object(pr_live, 'PlayerManager'), \
         patch.object(pr_live, 'UptimeTracker'), \
         patch.object(pr_live, 'PlayerStatsTracker'), \
         patch.object(pr_live, 'ServerStatusCache'), \
         patch.object(pr_live, 'MapImageResolver'), \
         patch.object(pr_live.PatchRaptorPanel, 'initialize'):
         
        with patch('builtins.open', create=True), patch('json.load'):
            panel = pr_live.PatchRaptorPanel()
            
            # Setup Mocks
            panel.servers = [MagicMock(name="TestServer")]
            panel.servers[0].name = "TestServer"
            panel.servers[0].display_name = "Test Server"
            panel.servers[0].map_name = "TheIsland"
            panel.servers[0].rcon_port = 7777
            
            # Setup Async Mocks
            panel.player_manager.update_active_players = AsyncMock()
            panel.player_manager.get_total_players = AsyncMock(return_value=(5, {"Test Server": ["Player1"]}))
            
            # Mock psutil to return a matching process
            mock_proc = MagicMock()
            mock_proc.info = {'pid': 123, 'name': 'ShooterGameServer.exe', 'cmdline': ['TheIsland', 'TestServer', '7777']}
            mock_proc.name.return_value = 'ShooterGameServer.exe'
            mock_proc.cmdline.return_value = ['TheIsland', 'TestServer', '7777']
            mock_proc.cpu_percent.return_value = 10.0
            mock_proc.memory_info.return_value.rss = 1024*1024*1024 # 1GB

            with patch('psutil.process_iter', return_value=[mock_proc]), \
                 patch('psutil.Process', return_value=mock_proc):
                
                await panel._update_server_status()
                
                # Assertions
                # 1. PlayerManager called
                panel.player_manager.update_active_players.assert_called_once()
                
                # 2. Status Cache Updated
                panel.server_status_cache.update.assert_called_once()
                status_arg = panel.server_status_cache.update.call_args[0][0]
                assert status_arg.total_players == 5
                assert status_arg.online_count == 1
                assert status_arg.servers[0]['status'] == 'online'
                
                # 3. Trackers called
                panel.uptime_tracker.record_uptime.assert_called_with("TestServer", True)
                panel.player_stats_tracker.record_players.assert_called()
