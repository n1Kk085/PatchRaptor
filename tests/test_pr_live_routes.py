import pytest
from unittest.mock import MagicMock, patch, mock_open
import json
import base64
import os
import sys

# Setup path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import pr_live

# Helper to create a test client
@pytest.fixture
def client():
    # Patch dependencies to prevent side effects during init
    with patch('pr_live.ConfigManager'), \
         patch('pr_live.ServerStatusCache'), \
         patch('pr_live.MapImageResolver'), \
         patch('pr_live.asyncio.new_event_loop'), \
         patch('builtins.open', mock_open(read_data='{}')), \
         patch('json.load', return_value={}):
         
        # Instantiate the REAL class
        panel = pr_live.PatchRaptorPanel()
        
        # Configure mocked config for generic usage
        panel.webpanel_config = {'auth': {'username': 'admin', 'password': 'password'}}
        
        # Ensure cache returns something valid
        panel.server_status_cache.get_dict.return_value = {'status': 'ok'}
        
        # The app is already created in __init__
        app = panel.app
        app.config['TESTING'] = True
        
        with app.test_client() as client:
            yield client

def get_auth_headers(username, password):
    return {
        'Authorization': 'Basic ' + base64.b64encode(f"{username}:{password}".encode()).decode('utf-8')
    }

def test_index_unauthorized(client):
    response = client.get('/')
    assert response.status_code == 401
    assert 'Login Required' in response.data.decode()

def test_index_authorized(client):
    headers = get_auth_headers('admin', 'password')
    # Use patch to mock send_from_directory to avoid file system errors
    with patch('pr_live.send_from_directory') as mock_send:
        mock_send.return_value = "Index Page"
        response = client.get('/', headers=headers)
        assert response.status_code == 200

def test_status_unauthorized(client):
    response = client.get('/api/status')
    assert response.status_code == 401

def test_status_authorized(client):
    headers = get_auth_headers('admin', 'password')
    response = client.get('/api/status', headers=headers)
    assert response.status_code == 200
    assert response.json == {'status': 'ok'}

def test_me_endpoint(client):
    headers = get_auth_headers('admin', 'password')
    response = client.get('/api/me', headers=headers)
    assert response.status_code == 200
    assert response.json['username'] == 'admin'

def test_favicon(client):
    with patch('pr_live.send_from_directory') as mock_send:
        mock_send.return_value = "Favicon"
        response = client.get('/favicon.ico')
        assert response.status_code == 200

def test_no_auth_configured():
    # Rerecreating fixture logic locally for this specific test case
    with patch('pr_live.ConfigManager'), \
         patch('pr_live.ServerStatusCache'), \
         patch('pr_live.MapImageResolver'), \
         patch('pr_live.asyncio.new_event_loop'), \
         patch('builtins.open', mock_open(read_data='{}')), \
         patch('json.load', return_value={}):
         
        panel = pr_live.PatchRaptorPanel()
        panel.webpanel_config = {} # No Auth
        panel.server_status_cache.get_dict.return_value = {}
        
        app = panel.app
        app.config['TESTING'] = True
        
        with app.test_client() as client:
            response = client.get('/api/status')
            assert response.status_code == 200
