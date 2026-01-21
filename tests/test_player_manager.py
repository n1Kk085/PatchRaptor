import pytest
import re
from patchraptor.player_manager import PlayerManager
from patchraptor.models import ServerConfig

@pytest.fixture
def player_manager():
    # Mock config not needed for regex tests
    return PlayerManager(servers=[])

def test_parse_join_standard(player_manager):
    """Test standard join format"""
    # Use 'SurvivorBob' to avoid 'test' or 'player' validation blocks
    line = "2023.12.01_12.00.00: SurvivorBob [UniqueNetId:0123456789abcdef0123456789abcdef Platform:None] joined this ARK!"
    result = player_manager._parse_player_join(line)
    
    assert result is not None
    name, uid = result
    assert name == "SurvivorBob"
    assert uid == "0123456789abcdef0123456789abcdef"

def test_parse_join_fallback(player_manager):
    """Test fallback extraction"""
    # Malformed timestamp or variation
    line = "LogNet: Join succeeded: SurvivorAlice [UniqueNetId:0123456789abcdef0123456789abcdef] joined"
    result = player_manager._parse_player_join(line)
    
    # Needs to match fallback logic in PlayerManager
    assert result is not None
    name, uid = result
    assert name == "SurvivorAlice"
    assert uid == "0123456789abcdef0123456789abcdef"

def test_parse_leave_standard(player_manager):
    """Test standard leave format"""
    line = "2023.12.01_12.30.00: SurvivorBob [UniqueNetId:0123456789abcdef0123456789abcdef Platform:None] left this ARK!"
    result = player_manager._parse_player_leave(line)
    
    assert result is not None
    name, uid = result
    assert name == "SurvivorBob"
    assert uid == "0123456789abcdef0123456789abcdef"

def test_validate_player_data(player_manager):
    """Test validation rules"""
    valid_id = "0123456789abcdef0123456789abcdef"
    
    assert player_manager._validate_player_data("ValidName123", valid_id) is True
    assert player_manager._validate_player_data("A", valid_id) is False  # Too short
    assert player_manager._validate_player_data("Admin", valid_id) is False # Blocked name
    assert player_manager._validate_player_data("ValidName", "bad_id") is False # Invalid ID
