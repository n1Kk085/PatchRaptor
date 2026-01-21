import sys
import os

# Add project root to sys.path to allow imports when running from tests/
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    print(f"Running Smoke Test from: {project_root}")
    print("Verifying imports...")
    from patchraptor import config
    from patchraptor import log_manager
    from patchraptor import player_manager
    from patchraptor import rcon_manager
    from patchraptor import schedule_manager
    from patchraptor import server_control_handler
    from patchraptor import update_management_handler
    from patchraptor import backup_restore_handler
    from patchraptor import system_monitoring_handler
    from patchraptor import configuration_handler
    
    print("Verifying specific fixes...")
    # Check log_manager method
    logger_instance = log_manager.LogManager()
    assert hasattr(logger_instance, 'error_system'), "LogManager missing error_system"
    
    # Check player manager constants/methods
    pm = player_manager.PlayerManager([])
    assert hasattr(pm, '_fallback_player_extraction'), "PlayerManager missing fallback method"
    
    print("SUCCESS: All modules imported and basic checks passed.")
except ImportError as e:
    print(f"FAILURE: ImportError: {e}")
    exit(1)
except AssertionError as e:
    print(f"FAILURE: Assertion Error: {e}")
    exit(1)
except Exception as e:
    print(f"FAILURE: Unexpected Error: {e}")
    exit(1)
