from typing import Dict, List, Tuple, Optional, Any
from .models import ServerConfig
from .log_manager import logger
import datetime
import os
import re
import asyncio
import time
import json
import sys
from . import ark_log_utils as log_utils

class PlayerManager:
    """Manages active player tracking via events from the Telemetry Hub."""
    def __init__(self, servers: List[ServerConfig], read_only: bool = False):
        self.servers = servers
        self.read_only = read_only
        self.active_players: Dict[str, Dict[str, dict]] = {srv.name: {} for srv in servers}
        self.banned_players = set()
        
        # Handle frozen path resolution
        if getattr(sys, 'frozen', False):
             base_dir = os.path.dirname(sys.executable)
        else:
             base_dir = os.path.join(os.path.dirname(__file__), '..')
             
        self._bans_file = os.path.join(base_dir, 'bans.json')
        
        # Async synchronization locks
        self.players_lock = asyncio.Lock()
        self.bans_lock = asyncio.Lock()
        
        # Pause control for updates
        self._paused = False
        
    def pause(self):
        """Pause player tracking events"""
        logger.info_player("Pausing player manager monitoring")
        self._paused = True
        
    def resume(self):
        """Resume player tracking events"""
        logger.info_player("Resuming player manager monitoring")
        self._paused = False
    
    async def initialize(self):
        """Async initialization method to load bans and register for Hub events"""
        # Only load bans if fully active (not read-only)
        if not self.read_only:
            await self._load_bans()
            
        # Register for log events from TelemetryManager Hub (if available)
        try:
            from .service_locator import ServiceLocator
            try:
                tm = ServiceLocator.get("TelemetryManager")
                if tm and hasattr(tm, "broadcaster"):
                    tm.broadcaster.register_listener("join", self.handle_on_player_join)
                    tm.broadcaster.register_listener("leave", self.handle_on_player_leave)
                    logger.info_system("Synchronizing player tracking with Echo engine...")
            except (KeyError, ImportError):
                # Service not registered; running in standalone mode.
                logger.debug_player("TelemetryManager not found, operating in standalone mode")
                pass
        except Exception as e:
            logger.error_player(f"Registration for Telemetry Hub skipped: {e}")
            
        # Attempt to recover online players from telemetry state
        try:
            from .log_manager import LOG_PATH
            import json
            state_file = os.path.join(LOG_PATH, 'cluster_live.json')
            if os.path.exists(state_file):
                def _read_state():
                    with open(state_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                data = await asyncio.to_thread(_read_state)
                async with self.players_lock:
                    for srv_data in data.get('servers', []):
                        map_name = srv_data.get('mapName')
                        if not map_name: continue
                        
                        # Match map_name to configured server name
                        server_name = next((s.name for s in self.servers if s.display_name == map_name or s.name == map_name), map_name)
                        
                        if server_name not in self.active_players:
                            self.active_players[server_name] = {}
                            
                        for player in srv_data.get('players', []):
                            uid = player.get('unique_id')
                            pname = player.get('name')
                            if uid and pname:
                                session_time_str = player.get('session_time', '0m')
                                try:
                                    minutes = int(session_time_str.replace('m', ''))
                                except ValueError:
                                    minutes = 0
                                approx_join = datetime.datetime.now() - datetime.timedelta(minutes=minutes)
                                self.active_players[server_name][uid] = {
                                    "name": pname,
                                    "join_time": approx_join
                                }
                logger.info_player("Recovered active player state from telemetry cache")
        except Exception as e:
            logger.debug_player(f"Could not recover active player state: {e}")



    async def handle_on_player_join(self, event_data: Dict[str, Any]):
        """Callback for LogBroadcaster join events"""
        if self._paused: return
        
        server_name = event_data.get("server")
        player_name = event_data.get("name")
        unique_id = event_data.get("id")
        
        if not server_name or not player_name or not unique_id:
            return

        async with self.bans_lock:
             if player_name in self.banned_players or unique_id in self.banned_players:
                 logger.warning_player(f"Banned player {player_name} ({unique_id}) tried to join {server_name}")
                 return

        async with self.players_lock:
            if server_name not in self.active_players:
                self.active_players[server_name] = {}
            
            self.active_players[server_name][unique_id] = {
                "name": player_name,
                "join_time": datetime.datetime.now()
            }
        
        logger.info_player(f"Player {player_name} joined {server_name}", player=player_name, id=unique_id)

    async def handle_on_player_leave(self, event_data: Dict[str, Any]):
        """Callback for LogBroadcaster leave events"""
        if self._paused: return

        server_name = event_data.get("server")
        unique_id = event_data.get("id")
        
        if not server_name or not unique_id:
            return

        async with self.players_lock:
            if server_name in self.active_players and unique_id in self.active_players[server_name]:
                player_name = self.active_players[server_name][unique_id].get("name", "Unknown")
                del self.active_players[server_name][unique_id]
                logger.info_player(f"Player {player_name} left {server_name}", player=player_name, id=unique_id)

    async def _load_bans(self):
        """Load banned players from file"""
        try:
            path = os.path.abspath(self._bans_file)
            def _read_file():
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                return None
            
            data = await asyncio.to_thread(_read_file)
            if data and isinstance(data, list):
                self.banned_players = set(data)
                logger.info_player(f"Loaded banned players from file", count=len(self.banned_players))
        except Exception as e:
            logger.error_player(f"Error loading banned players: {e}")

    async def _save_bans(self):
        """Save banned players to file with proper async locking"""
        try:
            path = os.path.abspath(self._bans_file)
            async with self.bans_lock:
                banned_list = sorted(list(self.banned_players))
            
            def _write_file():
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(banned_list, f, indent=2)
            
            await asyncio.to_thread(_write_file)
            logger.info_player(f"Saved banned players to file", count=len(banned_list))
        except Exception as e:
            logger.error_player(f"Error saving banned players", error=str(e))


    async def clear_server_players(self, server_name: str = None):
        """Clear player data for a specific server or all servers"""
        async with self.players_lock:
            if server_name and server_name in self.active_players:
                self.active_players[server_name] = {}
                logger.info_player(f"Cleared player data for server", server=server_name)
            elif server_name is None:
                for srv in self.servers:
                    self.active_players[srv.name] = {}
                logger.info_player(f"Cleared player data for all servers")

    async def ban_player(self, name: str):
        """Ban a player and remove them if currently online"""
        name = name.strip()
        if not name: return False
        
        async with self.bans_lock:
            self.banned_players.add(name)
        await self._save_bans()
        
        async with self.players_lock:
            for srv_name in self.active_players:
                to_remove = [uid for uid, info in self.active_players[srv_name].items() 
                            if uid == name or info.get('name') == name]
                for uid in to_remove:
                    del self.active_players[srv_name][uid]
        
        logger.info_player(f"Banned player", player=name)
        return True

    async def unban_player(self, name: str):
        """Unban a player"""
        name = name.strip()
        if not name: return False
        
        removed = False
        async with self.bans_lock:
            if name in self.banned_players:
                self.banned_players.remove(name)
                removed = True
        
        if removed:
            await self._save_bans()
            logger.info_player(f"Unbanned player", player=name)
            return True
        return False

    async def get_total_players(self) -> Tuple[int, Dict[str, List[Dict[str, str]]]]:
        """Get total players count and details from the local state"""
        total_players = 0
        server_details: Dict[str, List[Dict[str, str]]] = {}
        
        # Performance: Pre-copy banned players outside the lock if possible, 
        # but since it's a small set, we just use it during iteration.
        async with self.players_lock:
            for server in self.servers:
                map_name = server.name
                display_name = server.display_name or server.name
                players = []
                # Note: Banned players are already filtered on JOIN in handle_on_player_join.
                # This secondary check handles players banned while already online.
                for unique_id, info in self.active_players.get(map_name, {}).items():
                    player_name = info.get('name', 'Unknown')
                    session_time = int((datetime.datetime.now() - info['join_time']).total_seconds() // 60)
                    players.append({
                        "name": player_name,
                        "unique_id": unique_id,
                        "session_time": f"{session_time}m"
                    })
                total_players += len(players)
                server_details[display_name] = players
        return total_players, server_details
    
    async def cleanup_old_player_data(self, max_session_time_hours: int = 24):
        """Clean up old player data to prevent state bloat"""
        current_time = datetime.datetime.now()
        max_session_time = datetime.timedelta(hours=max_session_time_hours)
        
        async with self.players_lock:
            for server_name, players in self.active_players.items():
                to_remove = [uid for uid, info in players.items() 
                            if (current_time - info['join_time']) > max_session_time]
                for uid in to_remove:
                    del players[uid]
        return True


    def _validate_player_data(self, player_name: str, unique_id: str) -> bool:
        """Sanitize and validate player identity data"""
        if not player_name or len(player_name) < 2:
            return False
        if not unique_id or len(unique_id) < 10:
            return False
        
        # Prevent reserved words from being used as names
        reserved = ["Server", "Admin", "PatchRaptor", "System"]
        if player_name in reserved:
            return False
            
        return True

    def _validate_player_name(self, name: str) -> bool:
        """Sanitize and validate a player name string"""
        if not name or len(name) < 2:
            return False
        reserved = ["Server", "Admin", "PatchRaptor", "System"]
        if name in reserved:
            return False
        return True

