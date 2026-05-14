import json
import os
import time
import asyncio
from typing import Dict, List, Any
from .log_manager import logger

class HistoryManager:
    """
    Manages historical performance data for servers.
    Retains data for 24 hours to generate trend graphs.
    """
    
    def __init__(self, data_file="history.json"):
        # Store history in a separate file in the backend directory
        self.history_file = os.path.join(os.path.dirname(__file__), '..', data_file)
        self.history: Dict[str, List[Dict[str, Any]]] = {}
        self.lock = asyncio.Lock()
        
        # Configuration
        self.retention_hours = 24
        self.max_points = int(self.retention_hours * 60 / 10) + 12  # 10 min interval + buffer (approx 156 points)
    
    async def initialize(self):
        """Load history from file"""
        await self._load_history()
        
    async def _load_history(self):
        """Load historical data from JSON file"""
        try:
            if os.path.exists(self.history_file):
                def _read():
                    with open(self.history_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                
                data = await asyncio.to_thread(_read)
                if isinstance(data, dict):
                    self.history = data
                    logger.info_system(f"Loaded history data for {len(self.history)} servers")
                else:
                    logger.warning_system("History file corrupted or invalid format, starting fresh")
                    self.history = {}
        except Exception as e:
            logger.error_system(f"Failed to load history file: {e}")
            self.history = {}

    async def _save_history(self):
        """Save history to JSON file (Atomic-ish write)"""
        try:
            def _write():
                # Write to temp file first
                temp_file = self.history_file + ".tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    json.dump(self.history, f, indent=None) # Compact JSON
                # Rename to actual file
                os.replace(temp_file, self.history_file)
                
            await asyncio.to_thread(_write)
        except Exception as e:
            logger.error_system(f"Failed to save history file: {e}")

    async def add_data_point(self, server_name: str, player_count: int, cpu_percent: float, ram_percent: float):
        """Add a new data point for a server"""
        async with self.lock:
            if server_name not in self.history:
                self.history[server_name] = []
            
            timestamp = int(time.time())
            
            point = {
                "t": timestamp,
                "p": player_count,
                "c": round(cpu_percent, 1),
                "r": round(ram_percent, 1)
            }
            
            self.history[server_name].append(point)
            
            # Prune old data
            self._prune_history(server_name)
            
            # Synchronous auto-save ensures data persistence.
            await self._save_history()

    def _prune_history(self, server_name: str):
        """Remove data points older than retention period"""
        cutoff_time = int(time.time()) - (self.retention_hours * 3600)
        
        # Filter mostly by time, but also clamp by max count to be safe
        original_len = len(self.history[server_name])
        
        # 1. Remove old time points
        self.history[server_name] = [
            pt for pt in self.history[server_name] 
            if pt["t"] > cutoff_time
        ]
        
        # 2. Hard clamp count if it somehow got too big
        if len(self.history[server_name]) > self.max_points:
            self.history[server_name] = self.history[server_name][-self.max_points:]

    async def get_history(self, server_name: str) -> List[Dict[str, Any]]:
        """Get history for a server, returns empty list if none"""
        async with self.lock:
            return list(self.history.get(server_name, []))

    async def clear_history(self):
        """Clear all history"""
        async with self.lock:
            self.history = {}
            await self._save_history()
