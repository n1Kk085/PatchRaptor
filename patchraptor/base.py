"""
Core base classes and interfaces for the PatchRaptor system.
Provides abstract base classes and common functionality.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json
import os
from pathlib import Path


@dataclass
class ServerConfig:
    """Unified server configuration data class"""
    name: str
    display_name: str
    map_name: str
    rcon_ip: str
    rcon_port: int
    rcon_password: str
    start_command: str
    install_dir: str
    server_save_path: str
    server_log_path: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "map_name": self.map_name,
            "rcon_ip": self.rcon_ip,
            "rcon_port": self.rcon_port,
            "rcon_password": self.rcon_password,
            "start_command": self.start_command,
            "install_dir": self.install_dir,
            "server_save_path": self.server_save_path,
            "server_log_path": self.server_log_path
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ServerConfig':
        """Create from dictionary"""
        return cls(
            name=data["name"],
            display_name=data.get("display_name", data["name"]),
            map_name=data.get("map_name", ""),
            rcon_ip=data["rcon_ip"],
            rcon_port=int(data["rcon_port"]),
            rcon_password=data["rcon_password"],
            start_command=data["start_command"],
            install_dir=data.get("install_dir", ""),
            server_save_path=data.get("server_save_path", ""),
            server_log_path=data.get("server_log_path", "")
        )



class BaseConfigManager(ABC):
    """Base configuration manager with common functionality"""
    
    def __init__(self, config_file: str = "config.json"):
        super().__init__()
        self.config_file = Path(config_file)
        self._config_data: Dict[str, Any] = {}
        self._watchers = []
    
    async def initialize(self) -> bool:
        """Load configuration from file"""
        try:
            await self._load_config()
            self._initialized = True
            return True
        except Exception as e:
            print(f"Failed to initialize config manager: {e}")
            return False
    
    async def _load_config(self) -> None:
        """Load configuration from JSON file"""
        if not self.config_file.exists():
            raise FileNotFoundError(f"Configuration file {self.config_file} not found")
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._config_data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with optional default"""
        return self._config_data.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value"""
        self._config_data[key] = value
        self._notify_watchers(key, value)
    
    def get_server_configs(self) -> List[ServerConfig]:
        """Parse and return server configurations"""
        servers = []
        for srv_config in self.get("cluster_servers", []):
            try:
                servers.append(ServerConfig.from_dict(srv_config))
            except KeyError as e:
                print(f"Invalid server config, missing key: {e}")
        return servers
    
    def add_config_watcher(self, callback):
        """Add a callback to be notified of config changes"""
        self._watchers.append(callback)
    
    def _notify_watchers(self, key: str, value: Any):
        """Notify watchers of configuration changes"""
        for callback in self._watchers:
            try:
                callback(key, value)
            except Exception as e:
                print(f"Error in config watcher callback: {e}")
    
    async def save_config(self) -> bool:
        """Save current configuration to file"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to save config: {e}")
            return False
    
    async def shutdown(self) -> bool:
        """Shutdown the config manager"""
        self._watchers.clear()
        self._initialized = False
        return True
