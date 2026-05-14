import os
import sys
import json
import pytest
from unittest.mock import MagicMock, patch, mock_open
import asyncio

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pr_live
from pr_live import PatchRaptorPanel, PanelStatus

@pytest.fixture
def passive_panel():
    with patch('pr_live.ConfigManager'), \
         patch('pr_live.PatchRaptorPanel._load_webpanel_config', return_value={'auth': {}}), \
         patch('os.makedirs'):
        panel = PatchRaptorPanel()
        return panel

@pytest.mark.asyncio
async def test_passive_update_logic(passive_panel):
    """Verify that PatchRaptorPanel reads cluster_live.json correctly (Passive Subscriber)."""
    
    mock_telemetry = {
        "servers": [
            {
                "name": "TestServer",
                "mapName": "TheIsland",
                "status": "online",
                "playerCount": 10
            }
        ],
        "totalPlayers": 10,
        "serverCount": 1,
        "onlineCount": 1,
        "lastUpdate": "2026-04-28T12:00:00",
        "currentTime": "2026-04-28 12:00:00"
    }
    
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', mock_open(read_data=json.dumps(mock_telemetry))), \
         patch.object(passive_panel.map_image_resolver, 'get_image_url', return_value='/static/maps/TheIsland.jpg'):
        
        await passive_panel._update_server_status()
        
        # Verify cache was updated
        status = passive_panel.server_status_cache.get()
        assert status.total_players == 10
        assert status.server_count == 1
        assert status.servers[0]['name'] == "TestServer"
        assert status.servers[0]['mapimage'] == '/static/maps/TheIsland.jpg'

def test_flask_routes_passive(passive_panel):
    """Verify Flask routes work with the Passive architecture."""
    client = passive_panel.app.test_client()
    
    # Mock cache data
    test_dict = {'servers': [], 'totalPlayers': 0}
    with patch.object(passive_panel.server_status_cache, 'get_dict', return_value=test_dict):
        response = client.get('/api/status')
        assert response.status_code == 200
        assert response.get_json() == test_dict
