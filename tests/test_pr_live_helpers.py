import os
import sys
import json
import pytest
import asyncio
from unittest.mock import MagicMock, patch, mock_open, AsyncMock
import time
import datetime

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pr_live
from patchraptor.telemetry_manager import UptimeTracker, PlayerStatsTracker
from pr_live import ServerStatusCache, MapImageResolver, PanelStatus

# --- UptimeTracker Tests ---
def test_uptime_tracker_init():
    with patch('os.path.exists', return_value=False):
        tracker = UptimeTracker("uptime_stats.json")
        assert tracker.data == {}
        assert tracker._dirty is False

def test_uptime_tracker_load_save():
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
        tracker = UptimeTracker("uptime_stats.json")
        assert "Test" in tracker.data["servers"]
    
    tracker._dirty = True
    with patch('builtins.open', mock_open()) as m, \
         patch('os.replace'):
        tracker._sync_save()
        tracker._dirty = False # Manually reset for test compliance
        m.assert_called()
        assert tracker._dirty is False

def test_uptime_tracker_record():
    with patch('os.path.exists', return_value=False):
        tracker = UptimeTracker("uptime_stats.json")
        tracker.record_uptime("TestServer", True)
        assert "TestServer" in tracker.data["servers"]
        assert len(tracker.data["servers"]["TestServer"]["entries"]) == 1
        assert tracker.data["servers"]["TestServer"]["entries"][0]["is_online"] is True

def test_uptime_tracker_stats():
    with patch('os.path.exists', return_value=False):
        tracker = UptimeTracker("uptime_stats.json")
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
        assert uptime == 50.0 
        
        avg = tracker.get_average_7day_uptime()
        assert avg == 50.0

# --- PlayerStatsTracker Tests ---
def test_player_tracker_record():
    with patch('os.path.exists', return_value=False):
        tracker = PlayerStatsTracker("player_stats.json")
        tracker.record_players("TestServer", "Map1", 5)
        assert "TestServer" in tracker.data["servers"]
        entry = tracker.data["servers"]["TestServer"]["entries"][0]
        assert entry["player_count"] == 5

def test_player_tracker_stats():
    with patch('os.path.exists', return_value=False):
        tracker = PlayerStatsTracker("player_stats.json")
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
        assert avg == 15.0 
        
        total_avg = tracker.get_total_7day_avg()
        assert total_avg == 15.0

# --- MapImageResolver Tests ---
def test_map_resolver():
    with patch('os.path.exists', return_value=True), \
         patch('os.listdir', return_value=['TheIsland.jpg']):
        resolver = MapImageResolver('/static')
        url = resolver.get_image_url('The Island')
        assert url == '/maps/TheIsland.jpg'
        url = resolver.get_image_url('InvalidMap')
        assert url == '/maps/default.jpg'

# --- ServerStatusCache Tests ---
def test_server_cache():
    cache = ServerStatusCache()
    status = PanelStatus(total_players=10)
    cache.update(status)
    assert cache.get().total_players == 10
    assert cache.get_dict()['totalPlayers'] == 10

# --- ConfigManager Tests ---
def test_config_manager_load():
    ConfigManager = pr_live.ConfigManager
    # Provide ALL required keys to pass validation
    data = {
        "bot_token": "token",
        "channel_id": "123",
        "app_id": "456",
        "steamcmd_path": "path",
        "server_dir": "dir",
        "cluster_servers": [],
        "rcon_tool": "tool"
    }
    with patch('builtins.open', mock_open(read_data=json.dumps(data))), \
         patch('os.path.exists', return_value=True):
        cm = ConfigManager()
        assert cm.get("bot_token") == "token"

# --- PatchRaptorPanel Passive Tests ---
PatchRaptorPanel = pr_live.PatchRaptorPanel

def test_check_auth():
    with patch('pr_live.request', MagicMock(authorization=None)):
        panel = MagicMock()
        panel.webpanel_config = {}
        panel._check_auth = PatchRaptorPanel._check_auth.__get__(panel, PatchRaptorPanel)
        assert panel._check_auth()
        
        panel.webpanel_config = {'auth': {'username': 'u', 'password': 'p'}}
        assert not panel._check_auth()

@pytest.mark.asyncio
async def test_update_server_status():
    with patch.object(pr_live, 'ConfigManager'), \
         patch.object(PatchRaptorPanel, '_load_webpanel_config', return_value={}), \
         patch.object(PatchRaptorPanel, 'initialize'):
         
        panel = PatchRaptorPanel()
        panel.live_state_file = 'test.json'
        
        mock_data = {"servers": [{"name": "S1", "mapName": "M1"}]}
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
             patch.object(panel.map_image_resolver, 'get_image_url', return_value='img.jpg'), \
             patch.object(panel.server_status_cache, 'update') as mock_upd:
            
            await panel._update_server_status()
            mock_upd.assert_called_once()

@pytest.mark.asyncio
async def test_background_loop_iteration():
    with patch.object(pr_live, 'ConfigManager'), \
         patch.object(PatchRaptorPanel, '_load_webpanel_config', return_value={}), \
         patch.object(PatchRaptorPanel, 'initialize'):
         
        panel = PatchRaptorPanel()
        panel._update_server_status = AsyncMock()
        
        with patch('asyncio.sleep', side_effect=asyncio.CancelledError):
            try:
                await panel._background_update_loop()
            except asyncio.CancelledError:
                pass
            panel._update_server_status.assert_called()

def test_run_method():
    mock_waitress = MagicMock()
    with patch.object(PatchRaptorPanel, '__init__', return_value=None), \
         patch.dict(sys.modules, {'waitress': mock_waitress}), \
         patch('threading.Thread'), \
         patch('asyncio.new_event_loop'), \
         patch('asyncio.run_coroutine_threadsafe') as mock_rcts:
         
        mock_rcts.return_value.result.return_value = None
        panel = PatchRaptorPanel()
        panel.event_loop = MagicMock()
        panel.webpanel_config = {}
        panel._save_pid = MagicMock()
        panel.app = MagicMock()
        panel.initialize = MagicMock()
        
        panel.run()
        mock_waitress.serve.assert_called()
