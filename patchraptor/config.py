import json
import os
from typing import Any, Dict, List
from .models import ServerConfig
from .log_manager import logger

CONFIG_FILE = "config.json"

class ConfigManager:
    """Manages application configuration and validation"""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        from .log_manager import logger
        import sys
        
        # If frozen, ensure we look for config.json next to the executable
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
            config_file = os.path.join(base_dir, CONFIG_FILE)
            
        logger.debug_config(f"Starting ConfigManager initialization with config_file: {config_file}")
        self.config_file = config_file
        logger.debug_config(f"Config file set to: {self.config_file}")
        logger.debug_config("Loading configuration...")
        self.config = self._load_config()
        logger.debug_config("Configuration loaded successfully")
        logger.debug_config("Validating configuration...")
        self._validate_config()
        logger.debug_config("Configuration validation completed")
        logger.debug_config("ConfigManager initialization completed successfully")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file"""
        from .log_manager import logger
        logger.debug_config("Starting _load_config method")
        try:
            logger.debug_config(f"Attempting to load config file: {self.config_file}")
            # Debug: Show what config file we're trying to load
            logger.debug_system(f"Trying to load config file: {self.config_file}")
            logger.debug_system(f"Current working directory: {os.getcwd()}")
            logger.debug_system(f"Absolute config path: {os.path.abspath(self.config_file)}")
            logger.debug_config("Opening config file for reading")
            with open(self.config_file, 'r') as f:
                logger.debug_config("Reading JSON data from config file")
                config_data = json.load(f)
                logger.debug_config(f"Successfully loaded config with {len(config_data)} keys")
                logger.debug_config(f"Config keys: {list(config_data.keys())}")
                return config_data
        except FileNotFoundError:
            logger.debug_config(f"Config file not found: {self.config_file}")
            logger.debug_config(f"Current directory contents: {os.listdir('.')}")
            print(f"ERROR: Configuration file {self.config_file} not found")
            print(f"ERROR: Current directory: {os.getcwd()}")
            print(f"ERROR: Files in current directory: {os.listdir('.')}")
            raise FileNotFoundError(f"Configuration file {self.config_file} not found")
        except json.JSONDecodeError as e:
            logger.debug_config(f"JSON decode error in config file: {e}")
            logger.debug_config(f"Error details - Line: {e.lineno}, Column: {e.colno}, Message: {e.msg}")
            print(f"ERROR: Invalid JSON in config file: {e}")
            print(f"ERROR: Line {e.lineno}, Column {e.colno}: {e.msg}")
            raise ValueError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            logger.debug_config(f"Unexpected error loading config: {e}")
            print(f"ERROR: Unexpected error loading config: {e}")
            raise
    
    def _validate_config(self):
        """Validate required configuration keys"""
        from .log_manager import logger
        logger.debug_config("Starting _validate_config method")
        required_keys = [
            "bot_token", "channel_id", "app_id", "steamcmd_path", 
            "server_dir", "cluster_servers", "rcon_tool"
        ]
        logger.debug_config(f"Required keys to validate: {required_keys}")
        logger.debug_config(f"Current config keys: {list(self.config.keys())}")
        missing = [key for key in required_keys if key not in self.config]
        logger.debug_config(f"Missing keys check completed: {missing if missing else 'None'}")
        if missing:
            logger.debug_config(f"Validation failed - missing keys: {missing}")
            raise ValueError(f"Missing required config keys: {missing}")
        logger.debug_config("Configuration validation passed - all required keys present")
    
    def get(self, key: str, default=None):
        """Get configuration value with optional default"""
        return self.config.get(key, default)
    
    def save(self):
        """Save current configuration to file"""
        from .log_manager import logger
        logger.debug_config("Starting save method")
        logger.debug_config(f"Saving configuration to: {self.config_file}")
        logger.debug_config(f"Configuration data to save: {len(self.config)} keys")
        try:
            logger.debug_config("Opening config file for writing")
            with open(self.config_file, 'w') as f:
                logger.debug_config("Writing JSON data to config file")
                json.dump(self.config, f, indent=2)
                logger.debug_config("Configuration saved successfully")
        except Exception as e:
            logger.debug_config(f"Failed to save configuration: {e}")
            raise RuntimeError(f"Failed to save config: {e}")
    
    def get_server_configs(self) -> List[ServerConfig]:
        """Parse and return server configurations"""
        from .log_manager import logger
        logger.debug_config("Starting get_server_configs method")
        servers: List[ServerConfig] = []
        cluster_servers = self.config.get("cluster_servers", [])
        logger.debug_config(f"Found {len(cluster_servers)} server configurations")
        for i, srv_config in enumerate(cluster_servers):
            logger.debug_config(f"Processing server config {i+1}: {srv_config.get('name', 'Unknown')}")
            # Create sanitized config for logging
            sanitized_config = srv_config.copy()
            if 'rcon_password' in sanitized_config:
                sanitized_config['rcon_password'] = '******'
            logger.debug_config(f"Server config details: {sanitized_config}")
            server_config = ServerConfig(
                name=srv_config["name"],
                display_name=srv_config.get("display_name", srv_config["name"]),
                map_name=srv_config.get("map_name", ""),
                rcon_ip=srv_config["rcon_ip"],
                rcon_port=int(srv_config["rcon_port"]),
                rcon_password=srv_config["rcon_password"],
                start_command=srv_config["start_command"],
                install_dir=srv_config.get("install_dir", self.config["server_dir"]),
                server_save_path=srv_config.get("server_save_path", ""),
                server_log_path=srv_config.get("server_log_path", ""),
                log_dir=srv_config.get("log_dir") or srv_config.get("server_log_dir")
            )
            servers.append(server_config)
            logger.debug_config(f"Created ServerConfig for: {server_config.name}")
        logger.debug_config(f"Returning {len(servers)} server configurations")
        return servers
