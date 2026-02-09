import os
import sys
import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch, mock_open
import time
import datetime

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import pr_live directly
try:
    import pr_live
except ImportError:
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)
    import pr_live

# Mock dependencies needed by pr-live top-level code if strictly required,
# but since it's a module we might rely on mocks being patched before usage or 
# assume safe imports.
# pr_live attempts to import PlayerManager. If fails, it handles it.
# However, to be safe during test collection, we might want to ensure patches.
# But standard import is cleaner.

UptimeTracker = pr_live.UptimeTracker
PlayerStatsTracker = pr_live.PlayerStatsTracker
ServerStatusCache = pr_live.ServerStatusCache
MapImageResolver = pr_live.MapImageResolver
PanelStatus = pr_live.PanelStatus

# --- UptimeTracker Tests ---
def test_uptime_tracker_init():
    with patch('os.path.exists', return_value=False):
        tracker = UptimeTracker()
        assert tracker.data == {}
        assert tracker._dirty is False

def test_uptime_tracker_load_save():
    # Use a recent timestamp so it's not cleaned up
    mock_data = {
        "servers": {
            "Test": {
                "entries": [
                    {"timestamp": time.time(), "is_online": True}
                ]
            }
        }
    }
    with patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
         patch('os.path.exists', return_value=True):
        tracker = UptimeTracker()
        assert "Test" in tracker.data["servers"]
    
    # Test Save
    tracker._dirty = True
    with patch('builtins.open', mock_open()) as m:
        tracker.save()
        m.assert_called_with('uptime_stats.json', 'w')
        assert tracker._dirty is False

def test_uptime_tracker_record():
    with patch('os.path.exists', return_value=False):
        tracker = UptimeTracker()
        tracker.record_uptime("TestServer", True)
        assert "TestServer" in tracker.data["servers"]
        assert len(tracker.data["servers"]["TestServer"]["entries"]) == 1
        assert tracker.data["servers"]["TestServer"]["entries"][0]["is_online"] is True
        assert tracker._dirty is True

def test_uptime_tracker_stats():
    with patch('os.path.exists', return_value=False):
        tracker = UptimeTracker()
        # Add entries: 1 online, 1 offline
        tracker.data = {
            "servers": {
                "Test": {
                    "entries": [
                        {"timestamp": time.time(), "is_online": True},
                        {"timestamp": time.time(), "is_online": False}
                    ]
                }
            }
        }
        uptime = tracker.get_server_7day_uptime("Test")
        assert uptime == 50.0 # 1/2
        
        avg = tracker.get_average_7day_uptime()
        assert avg == 50.0

# --- PlayerStatsTracker Tests ---
def test_player_tracker_record():
    with patch('os.path.exists', return_value=False):
        tracker = PlayerStatsTracker()
        tracker.record_players("TestServer", "Map1", 5)
        assert "TestServer" in tracker.data["servers"]
        entry = tracker.data["servers"]["TestServer"]["entries"][0]
        assert entry["player_count"] == 5
        assert tracker._dirty is True

def test_player_tracker_stats():
    with patch('os.path.exists', return_value=False):
        tracker = PlayerStatsTracker()
        tracker.data = {
            "servers": {
                "Test": {
                    "entries": [
                        {"timestamp": time.time(), "player_count": 10},
                        {"timestamp": time.time(), "player_count": 20}
                    ]
                }
            }
        }
        avg = tracker.get_server_7day_avg("Test")
        assert avg == 15.0 # (10+20)/2
        
        total_avg = tracker.get_total_7day_avg()
        assert total_avg == 15.0

# --- MapImageResolver Tests ---
def test_map_resolver():
    with patch('os.path.exists', return_value=True), \
         patch('os.listdir', return_value=['TheIsland.jpg']):
        resolver = MapImageResolver('/static')
        
        # Match
        url = resolver.get_image_url('The Island')
        assert url == '/static/maps/TheIsland.jpg'
        
        # No Match
        url = resolver.get_image_url('InvalidMap')
        assert url == '/static/maps/default.jpg'

# --- ServerStatusCache Tests ---
def test_server_cache():
    cache = ServerStatusCache()
    status = PanelStatus(total_players=10)
    cache.update(status)
    
    retrieved = cache.get()
    assert retrieved.total_players == 10
    
    d = cache.get_dict()
    assert d['totalPlayers'] == 10

# --- ConfigManager Tests ---
ConfigManager = pr_live.ConfigManager

def test_config_manager_load():
    with patch('builtins.open', mock_open(read_data='{"test": 1}')), \
         patch('os.path.exists', return_value=True):
        cm = ConfigManager()
        assert cm.get("test") == 1
        assert cm.get("missing", 2) == 2

def test_config_manager_servers():
    data = {
        "cluster_servers": [
            {
                "name": "S1",
                "rcon_ip": "1.1.1.1",
                "rcon_port": 10,
                "rcon_password": "pw",
                "start_command": "cmd"
            }
        ]
    }
    with patch('builtins.open', mock_open(read_data=json.dumps(data))), \
         patch('os.path.exists', return_value=True):
        cm = ConfigManager()
        servers = cm.get_server_configs()
        assert len(servers) == 1
        assert servers[0].name == "S1"

# --- PatchRaptorPanel Logic Tests ---
PatchRaptorPanel = pr_live.PatchRaptorPanel
from unittest.mock import AsyncMock

def test_check_auth():
    # Mock request
    with patch('pr_live.request', MagicMock(authorization=None)):
        # 1. No Auth Configured
        panel = MagicMock()
        panel.webpanel_config = {}
        # Bind
        panel._check_auth = PatchRaptorPanel._check_auth.__get__(panel, PatchRaptorPanel)
        assert panel._check_auth()
        
        # 2. Auth Configured
        panel.webpanel_config = {'auth': {'username': 'u', 'password': 'p'}}
        # Returns None because content is None and (None and ...) -> None
        assert not panel._check_auth()

@pytest.mark.asyncio
async def test_update_server_status():
    with patch.object(pr_live, 'ConfigManager'), \
         patch.object(pr_live, 'PlayerManager'), \
         patch.object(pr_live, 'UptimeTracker'), \
         patch.object(pr_live, 'PlayerStatsTracker'), \
         patch.object(pr_live, 'ServerStatusCache'), \
         patch.object(pr_live, 'MapImageResolver'), \
         patch.object(PatchRaptorPanel, 'initialize'):
         
        with patch('builtins.open', create=True), patch('json.load'):
            panel = PatchRaptorPanel()
            
            # Setup State
            server_mock = MagicMock()
            server_mock.name = "S1"
            server_mock.map_name = "map"
            server_mock.rcon_port = 10
            server_mock.display_name = "S1"
            panel.servers = [server_mock]
            
            # Setup Async Mocks
            
            # Setup Async Mocks
            panel.player_manager.update_active_players = AsyncMock()
            panel.player_manager.get_total_players = AsyncMock(return_value=(5, {"S1": []}))
            
            # Mock Process matches
            mock_proc = MagicMock()
            mock_proc.info = {'pid': 1, 'name': 'ShooterGameServer', 'cmdline': ['map', 'S1', '10']}
            mock_proc.name.return_value = 'ShooterGameServer'
            mock_proc.cmdline.return_value = ['map', 'S1', '10']
            mock_proc.cpu_percent.return_value = 5.0
            mock_proc.memory_info.return_value.rss = 100
            
            with patch('psutil.process_iter', return_value=[mock_proc]), \
                 patch('psutil.Process', return_value=mock_proc):
                
                await panel._update_server_status()
                
                panel.uptime_tracker.record_uptime.assert_called()
                args = panel.uptime_tracker.record_uptime.call_args[0]
                assert args[0] == "S1" # name
                assert args[1] is True # is_online

@pytest.mark.asyncio
async def test_update_status_exceptions():
    with patch.object(pr_live, 'ConfigManager'), \
         patch.object(pr_live, 'PlayerManager'), \
         patch.object(pr_live, 'UptimeTracker'), \
         patch.object(pr_live, 'PlayerStatsTracker'), \
         patch.object(pr_live, 'ServerStatusCache'), \
         patch.object(pr_live, 'MapImageResolver'), \
         patch.object(PatchRaptorPanel, 'initialize'):
         
        with patch('builtins.open', create=True), patch('json.load'):
            panel = PatchRaptorPanel()
            panel.servers = []
            panel.player_manager.get_total_players = AsyncMock(return_value=(0, {}))
            panel.player_manager.update_active_players = AsyncMock()
            
            # Test psutil exception handling
            with patch('psutil.process_iter', side_effect=Exception("Scan Error")), \
                 patch.object(pr_live.logger, 'error') as mock_log:
                await panel._update_server_status()
                mock_log.assert_called()

def test_cleanup_logic():
    # Uptime Tracker
    with patch('builtins.open', mock_open(read_data='{}')), patch('os.path.exists', return_value=True):
        tracker = UptimeTracker()
        tracker.data = {
            "servers": {
                "S1": {"entries": [{"timestamp": 0, "is_online": True}]} # Very old
            }
        }
        tracker._cleanup_old_entries()
        assert "S1" not in tracker.data["servers"]
        assert tracker._dirty is True

@pytest.mark.asyncio
async def test_initialize_logic():
    with patch('builtins.open', create=True), patch('json.load'):
        # We need to NOT mock initialize here to test it
        # But we must mock the background loop to NOT run forever
        with patch.object(PatchRaptorPanel, '_background_update_loop') as mock_loop:
            mock_loop.return_value = None # AsyncMock handled by auto-await if needed? 
            # initialize calls asyncio.create_task(self._background_update_loop())
            # create_task expects a coroutine.
            
            async def mock_coro():
                pass
            mock_loop.side_effect = mock_coro
            
            panel = PatchRaptorPanel()
            panel.player_manager = AsyncMock()
            
            with patch('asyncio.create_task') as mock_create_task:
                await panel.initialize()
                panel.player_manager.initialize.assert_called()
                mock_create_task.assert_called()

def test_player_stats_cleanup():
    with patch('builtins.open', mock_open(read_data='{}')), patch('os.path.exists', return_value=True):
        tracker = PlayerStatsTracker()
        # Old Entry
        tracker.data = {
            "servers": {
                "S1": {"entries": [{"timestamp": 0, "player_count": 0}]}
            }
        }
        tracker._cleanup_old_entries()
        assert "S1" not in tracker.data["servers"]
        assert tracker._dirty is True

def test_player_stats_exceptions():
    # Load Exception
    with patch('builtins.open', side_effect=OSError("Read Error")), \
         patch('os.path.exists', return_value=True):
        tracker = PlayerStatsTracker()
        assert tracker.data == {} # Should fallback to empty
    
    # Save Exception
    tracker = PlayerStatsTracker()
    tracker._dirty = True
    with patch('builtins.open', side_effect=OSError("Write Error")):
        tracker.save() # Should log error but not crash

@pytest.mark.asyncio
async def test_background_loop_iteration():
    with patch.object(pr_live, 'ConfigManager'), \
         patch.object(pr_live, 'PlayerManager'), \
         patch.object(pr_live, 'UptimeTracker'), \
         patch.object(pr_live, 'PlayerStatsTracker'), \
         patch.object(pr_live, 'ServerStatusCache'), \
         patch.object(PatchRaptorPanel, 'initialize'):
         
        with patch('builtins.open', create=True), patch('json.load'):
            panel = PatchRaptorPanel()
            panel._update_server_status = AsyncMock()
            
            # Mock sleep to raise exception to break loop
            with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
                try:
                    await panel._background_update_loop()
                except asyncio.CancelledError:
                    pass
                
                panel._update_server_status.assert_called()



def test_run_method():
    mock_waitress = MagicMock()
    with patch.object(pr_live.PatchRaptorPanel, '__init__', return_value=None), \
         patch.dict(sys.modules, {'waitress': mock_waitress}), \
         patch('threading.Thread'), \
         patch('asyncio.new_event_loop'), \
         patch('asyncio.set_event_loop'), \
         patch('webbrowser.open'):
         
        panel = PatchRaptorPanel()
        panel.app = MagicMock()
        panel.host = "127.0.0.1"
        panel.port = 8080
        panel.server_thread = None
        panel.loop = MagicMock()
        panel.webpanel_config = {}
        
        # We need to ensure event_loop is set for run() logic
        panel.event_loop = MagicMock()

        # run() calls asyncio.run_coroutine_threadsafe
        # We need to mock that too to avoid issues with our mocked loop
        with patch('asyncio.run_coroutine_threadsafe') as mock_rcts:
             mock_rcts.return_value.result.return_value = None
             
             panel.run()
             
             # Verify serve called?
             # run() calls serve(self.app, ...)
             mock_waitress.serve.assert_called()

def test_main_function():
    with patch('pr_live.ConfigManager') as MockConfig, \
         patch('pr_live.PatchRaptorPanel') as MockPanel:
        
        MockConfig.return_value.get.return_value = 8080 # port
        
        pr_live.main()
        
        MockPanel.assert_called()
        MockPanel.return_value.run.assert_called()
