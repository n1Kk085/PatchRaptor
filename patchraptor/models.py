from dataclasses import dataclass
from typing import Optional


@dataclass
class ServerConfig:
    """Server configuration data class"""
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
    log_dir: Optional[str] = None
