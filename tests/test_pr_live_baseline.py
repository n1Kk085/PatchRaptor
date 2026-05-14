import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
import threading
import asyncio

# Setup path to import from parent directory
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pr_live
from pr_live import PatchRaptorPanel, PanelStatus

@pytest.fixture(scope="module")
def app_client():
    """Create a test client for the Flask app (Passive architecture)."""
    with patch('pr_live.ConfigManager') as MockConfigManager, \
         patch('pr_live.PatchRaptorPanel._load_webpanel_config', return_value={"auth": {"username": "admin", "password": "password"}}), \
         patch.object(PatchRaptorPanel, 'initialize', new_callable=MagicMock):
         
        panel = PatchRaptorPanel()
        
        test_status_dict = {
            'servers': [{
                'name': 'TestServer',
                'displayName': 'Test Server',
                'mapName': 'The Island',
                'mapimage': '/static/maps/default.jpg',
                'status': 'online',
                'playerCount': 5
            }],
            'serverPlayerAverages': {},
            'serverUptimeAverages': {},
            'totalPlayers': 5,
            'serverCount': 1,
            'onlineCount': 1,
            'lastUpdate': '2026-04-28T12:00:00',
            'currentTime': '2026-04-28 12:00:00'
        }
        
        # Use a real cache but manually update it
        panel.server_status_cache.update(PanelStatus(
            servers=test_status_dict['servers'],
            total_players=5,
            server_count=1,
            online_count=1,
            last_update='2026-04-28T12:00:00',
            current_time='2026-04-28 12:00:00'
        ))
        
        app = panel.app
        app.config.update({"TESTING": True})
        with app.test_client() as client:
            yield client

def test_index_route(app_client):
    """Test that the index route returns 200/401 based on auth."""
    # Without auth
    response = app_client.get('/')
    assert response.status_code == 401
    
    # With auth
    auth_headers = {'Authorization': 'Basic YWRtaW46cGFzc3dvcmQ='} # admin:password
    response = app_client.get('/', headers=auth_headers)
    assert response.status_code == 200

def test_api_status(app_client):
    """Test the status API endpoint."""
    auth_headers = {'Authorization': 'Basic YWRtaW46cGFzc3dvcmQ='}
    response = app_client.get('/api/status', headers=auth_headers)
    assert response.status_code == 200
    data = response.get_json()
    assert data["serverCount"] == 1
    assert data["servers"][0]["name"] == "TestServer"

@pytest.mark.asyncio
async def test_update_server_status_logic():
    """Unit test for _update_server_status logic (Passive read from JSON)."""
    with patch('pr_live.ConfigManager'), \
         patch('pr_live.PatchRaptorPanel._load_webpanel_config', return_value={}):
         
        panel = PatchRaptorPanel()
        
        mock_data = {
            "servers": [{"name": "S1", "mapName": "Map1", "status": "online"}],
            "totalPlayers": 5
        }
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=json.dumps(mock_data))), \
             patch.object(panel.map_image_resolver, 'get_image_url', return_value='img.jpg'):
             
            await panel._update_server_status()
            
            status = panel.server_status_cache.get()
            assert status.total_players == 5
            assert status.servers[0]['name'] == "S1"
            assert status.servers[0]['mapimage'] == 'img.jpg'
