from typing import Dict, List, Tuple, Optional
from .models import ServerConfig
from .log_manager import logger
import datetime
import os
import re
import asyncio
import time
import json

class PlayerManager:
    """Manages active player tracking by tailing server logs."""
    def __init__(self, servers: List[ServerConfig], read_only: bool = False):
        self.servers = servers
        self.read_only = read_only
        self.active_players: Dict[str, Dict[str, dict]] = {srv.name: {} for srv in servers}
        self.file_positions: Dict[str, int] = {srv.name: 0 for srv in servers}
        self.banned_players = set()
        self._bans_file = os.path.join(os.path.dirname(__file__), '..', 'bans.json')
        
        # Initialize multiple regex patterns for different log formats
        self._init_regex_patterns()
        
        # Async synchronization locks
        self.players_lock = asyncio.Lock()
        self.file_positions_lock = asyncio.Lock()
        self.bans_lock = asyncio.Lock()
        
        # Performance monitoring
        self._performance_stats = {
            'last_update_time': 0,
            'update_count': 0,
            'total_lines_processed': 0,
            'total_file_read_time': 0,
            'total_processing_time': 0
        }
        self._parsing_stats = {
            'lines_processed': 0,
            'joins_found': 0,
            'leaves_found': 0,
        }
        
        # Periodic log file update mechanism (like chat2.py)
        self._last_log_file_update = 0
        self._log_file_update_interval = 1800  # 30 minutes in seconds
    
    async def initialize(self):
        """Async initialization method to load bans and set up dynamic log file detection"""
        # Only load bans if fully active (not read-only) - User Request
        if not self.read_only:
            await self._load_bans()
            
        # Always run dynamic detection so we know where logs are (even in read-only)
        # update_server_log_files handles the read_only check for config writing internally
        await self.update_server_log_files()

    async def _load_bans(self):
        """Load banned players from file"""
        logger.debug_player(f"Loading banned players from file: {self._bans_file}")
        
        try:
            import json
            path = os.path.abspath(self._bans_file)
            logger.debug_player(f"Absolute bans file path: {path}")
            
            def _read_file():
                if os.path.exists(path):
                    logger.debug_player(f"Bans file exists, reading contents")
                    with open(path, 'r', encoding='utf-8') as f:
                        return json.load(f)
                else:
                    logger.debug_player(f"Bans file does not exist, will create new one")
                    return None
            
            data = await asyncio.to_thread(_read_file)
            if data and isinstance(data, list):
                self.banned_players = set(data)
                logger.info_player(f"Loaded banned players from file", count=len(self.banned_players))
                logger.debug_player(f"Successfully loaded {len(self.banned_players)} banned players")
            else:
                logger.debug_player(f"No valid ban data found in file")
        except Exception as e:
            logger.debug_player(f"Error loading banned players: {e}")
            logger.error_player(f"Error loading banned players", error=str(e))

    def _init_regex_patterns(self):
        """Initialize multiple regex patterns for robust log parsing."""
        # Player join patterns - flexible format for ARK: Survival Ascended
        self.join_patterns = [
            # Standard format with timestamp (prefix-agnostic) and Platform wildcards
            re.compile(r"\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}: (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] joined this ARK!$", re.IGNORECASE),
            # More permissive start/end
            re.compile(r": (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] joined this ARK!", re.IGNORECASE),
        ]
        
        # Player leave patterns - flexible format for ARK: Survival Ascended
        self.leave_patterns = [
             # Standard format with timestamp (prefix-agnostic) and Platform wildcards
            re.compile(r"\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}: (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] left this ARK!$", re.IGNORECASE),
            # More permissive start/end
            re.compile(r": (.+?) \[UniqueNetId:([0-9a-f]{32}) Platform:.*?\] left this ARK!", re.IGNORECASE),
        ]
        
        # Unique ID extraction patterns (more specific to the exact format)
        self.unique_id_patterns = [
            re.compile(r"[0-9a-f]{32}"),  # 32-character hex ID (exact match for UniqueNetId)
        ]

    async def _save_bans(self):
        """Save banned players to file with proper async locking"""
        logger.debug_player(f"Saving banned players to file: {self._bans_file}")
        
        try:
            import json
            path = os.path.abspath(self._bans_file)
            logger.debug_player(f"Absolute bans file path: {path}")
            
            # Get banned players with lock
            async with self.bans_lock:
                banned_list = sorted(list(self.banned_players))
                logger.debug_player(f"Retrieved {len(banned_list)} banned players with lock")
            
            # Write to file asynchronously
            def _write_file():
                logger.debug_player(f"Writing {len(banned_list)} banned players to file")
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(banned_list, f, indent=2)
                logger.debug_player(f"Successfully wrote banned players to file")
            
            await asyncio.to_thread(_write_file)
            logger.info_player(f"Saved banned players to file", count=len(banned_list))
            logger.debug_player(f"Banned players saved successfully")
        except Exception as e:
            logger.debug_player(f"Error saving banned players: {e}")
            logger.error_player(f"Error saving banned players", error=str(e))

    def _parse_player_join(self, line: str) -> Optional[Tuple[str, str]]:
        """Parse player join event using multiple regex patterns."""
        line_lower = line.lower()
        
        # Check if line contains join-related keywords
        join_keywords = ["joined", "connected", "join", "connect"]
        if not any(keyword in line_lower for keyword in join_keywords):
            return None
        
        # Try each join pattern
        for i, pattern in enumerate(self.join_patterns):
            match = pattern.search(line)
            if match:
                try:
                    # Extract player name and unique ID
                    groups = match.groups()
                    
                    if len(groups) >= 2:
                        player_name = groups[0].strip()
                        unique_id = groups[1].strip()
                        
                        # Validate extracted data
                        if self._validate_player_data(player_name, unique_id):
                            return player_name, unique_id
                except (IndexError, AttributeError) as e:
                    continue
        
        # Fallback: Try to extract any player name and ID from the line
        result = self._fallback_player_extraction(line, is_join=True)
        return result
    
    def _parse_player_leave(self, line: str) -> Optional[Tuple[str, str]]:
        """Parse player leave event using multiple regex patterns."""
        line_lower = line.lower()
        
        # Check if line contains leave-related keywords
        leave_keywords = ["left", "disconnected", "leave", "disconnect"]
        if not any(keyword in line_lower for keyword in leave_keywords):
            return None
        
        # Try each leave pattern
        for i, pattern in enumerate(self.leave_patterns):
            match = pattern.search(line)
            if match:
                try:
                    # Extract player name and unique ID
                    groups = match.groups()
                    
                    if len(groups) >= 2:
                        player_name = groups[0].strip()
                        unique_id = groups[1].strip()
                        
                        # Validate extracted data
                        if self._validate_player_data(player_name, unique_id):
                            return player_name, unique_id
                except (IndexError, AttributeError) as e:
                    continue
        
        # Fallback: Try to extract any player name and ID from the line
        result = self._fallback_player_extraction(line, is_join=False)
        return result
    
    def _validate_player_data(self, player_name: str, unique_id: str) -> bool:
        """
        Validate extracted player name and unique ID with strict rules.
        
        Args:
            player_name: The player's name to validate
            unique_id: The player's unique ID to validate (32-char hex for ARK: SA)
            
        Returns:
            bool: True if both name and ID are valid, False otherwise
        """
        # Basic input validation
        if not player_name or not isinstance(player_name, str):
            logger.debug_player(f"Invalid player name: {player_name}")
            return False
            
        if not unique_id or not isinstance(unique_id, str):
            logger.debug_player(f"Invalid unique ID: {unique_id}")
            return False
        
        # Player name validation
        name_length = len(player_name)
        if name_length < 2 or name_length > 32:  # Reasonable name length limits
            logger.debug_player(f"Player name length out of range (2-32): {player_name}")
            return False
        
        # Only allow printable characters, no control characters
        if not all(32 <= ord(c) <= 126 for c in player_name):
            logger.debug_player(f"Player name contains invalid characters: {player_name}")
            return False
            
        # Block common system/placeholder names
        invalid_names = [
            "server", "admin", "system", "bot", "npc", "ark", "player", 
            "host", "none", "null", "unknown", "test"
        ]
        lower_name = player_name.lower()
        if any(invalid in lower_name for invalid in invalid_names):
            logger.debug_player(f"Player name matches blocked pattern: {player_name}")
            return False
        
        # Unique ID validation (32-character hex for ARK: SA)
        if not re.fullmatch(r'^[0-9a-f]{32}$', unique_id.lower()):
            logger.debug_player(f"Invalid unique ID format (expected 32-char hex): {unique_id}")
            return False
        
        return True
    
    def _fallback_player_extraction(self, line: str, is_join: bool) -> Optional[Tuple[str, str]]:
        """
        Fallback method to extract player data when primary patterns fail.
        This is a last resort and should rarely be needed with proper patterns.
        
        Args:
            line: The log line to extract from
            is_join: Whether this is a join event (for logging purposes)
            
        Returns:
            Tuple of (player_name, unique_id) if valid data found, else None
        """
        event_type = "join" if is_join else "leave"
        logger.debug_player(f"Using fallback extraction for {event_type} event: {line.strip()}")
        
        # Try to find a 32-char hex ID first (most reliable)
        id_match = re.search(r'([0-9a-f]{32})', line.lower())
        if not id_match:
            logger.debug_player("No valid 32-char hex ID found in line")
            return None
            
        unique_id = id_match.group(1)
        
        # Look for potential player names near the ID
        # Get text around the ID (100 chars before and after)
        start = max(0, id_match.start() - 100)
        end = min(len(line), id_match.end() + 100)
        context = line[start:end]
        
        # Look for potential names (must be before the ID in the line)
        # This is based on the standard log format where name comes before ID
        name_candidates = re.findall(r'([A-Za-z][A-Za-z0-9_\-\[\] ]{1,30})(?=[^\w]*(?:UniqueNetId:|$))', context)
        
        # Filter and validate potential names
        for name in name_candidates:
            name = name.strip(' []')
            if 2 <= len(name) <= 32 and self._validate_player_name(name):
                logger.debug_player(f"Fallback extracted: name='{name}' id='{unique_id}'")
                return name, unique_id
        
        logger.debug_player("No valid player name found near ID")
        return None
        
    def _validate_player_name(self, name: str) -> bool:
        """Helper to validate a player name format."""
        if not name or not isinstance(name, str):
            return False
            
        # Check length
        if len(name) < 2 or len(name) > 32:
            return False
            
        # Check for invalid characters
        if not re.match(r'^[\w\-\[\] ]+$', name):
            return False
            
        # Check against blocked terms
        blocked_terms = ["server", "admin", "system", "bot", "npc", "ark", "player"]
        lower_name = name.lower()
        return not any(term in lower_name for term in blocked_terms)

    async def _read_log_file_async(self, log_path: str, stored_pos: int, current_size: int) -> Tuple[List[str], int]:
        """Read log file asynchronously with optimized large file handling"""
        
        def _read_file():
            try:
                with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                    # Handle file position - use a local variable to avoid scope issues
                    read_pos = stored_pos
                    if read_pos > current_size or read_pos < 0:
                        read_pos = 0
                    
                    f.seek(read_pos)
                    test_char = f.read(1)
                    if test_char:
                        f.seek(read_pos)
                    else:
                        return [], current_size
                    
                    # Calculate how much data to read (optimize for large files)
                    bytes_to_read = current_size - read_pos
                    max_bytes_per_read = 1024 * 1024  # 1MB max per read to prevent memory issues
                    
                    if bytes_to_read > max_bytes_per_read:
                        # For large files, read in chunks and limit lines
                        lines = []
                        max_lines = 10000  # Limit lines per update to prevent blocking
                        bytes_read = 0
                        
                        while bytes_read < bytes_to_read and len(lines) < max_lines:
                            # Read chunk
                            chunk_size = min(max_bytes_per_read, bytes_to_read - bytes_read)
                            chunk = f.read(chunk_size)
                            if not chunk:
                                break
                                
                            bytes_read += len(chunk)
                            
                            # Split into lines, handling partial lines at chunk boundaries
                            chunk_lines = chunk.split('\n')
                            
                            # If this is not the first chunk, the first "line" is probably
                            # a continuation of the last line from the previous chunk
                            if lines and chunk_lines:
                                # Merge the last incomplete line with the first line of new chunk
                                lines[-1] = lines[-1] + chunk_lines[0]
                                chunk_lines = chunk_lines[1:]
                            
                            # Add the new lines (strip whitespace)
                            for line in chunk_lines:
                                stripped_line = line.strip()
                                if stripped_line:  # Only add non-empty lines
                                    lines.append(stripped_line)
                                    
                                    # Stop if we hit the line limit
                                    if len(lines) >= max_lines:
                                        break
                        
                        # Calculate new position (we might not have read everything)
                        new_pos = read_pos + bytes_read
                        return lines[:max_lines], new_pos if new_pos >= 0 else current_size
                    
                    else:
                        # For small files, read all at once (current behavior)
                        lines = []
                        for line in f:
                            lines.append(line.strip())
                        
                        new_pos = f.tell()
                        return lines, new_pos if new_pos >= 0 else current_size
                        
            except (OSError, IOError) as e:
                return [], 0
        
        # Run file reading in separate thread
        result = await asyncio.to_thread(_read_file)
        return result
    
    async def _process_log_lines_batch(self, map_name: str, lines: List[str]):
        """Process log lines in batches to reduce lock contention"""
        
        # Parse all lines first to minimize lock time
        joins = []
        leaves = []
        for line in lines:
            # Player joined - try multiple patterns
            join_result = self._parse_player_join(line)
            if join_result:
                joins.append(join_result)
            
            # Player left - try multiple patterns
            leave_result = self._parse_player_leave(line)
            if leave_result:
                leaves.append(leave_result)
        
        # Get banned players once to minimize lock time
        async with self.bans_lock:
            banned_set = self.banned_players.copy()
        
        # Process joins in batch
        if joins:
            players_to_add = []
            for player_name, unique_id in joins:
                if player_name not in banned_set:
                    players_to_add.append({
                        "name": player_name,
                        "unique_id": unique_id,
                        "join_time": datetime.datetime.now()
                    })
            
            # Add players in single lock operation
            if players_to_add:
                async with self.players_lock:
                    for player in players_to_add:
                        self.active_players[map_name][player["name"]] = {
                            "unique_id": player["unique_id"],
                            "join_time": player["join_time"]
                        }
        
        # Process leaves in batch
        if leaves:
            players_to_remove = [player_name for player_name, _ in leaves]
            
            # Remove players in single lock operation
            async with self.players_lock:
                for player_name in players_to_remove:
                    if player_name in self.active_players.get(map_name, {}):
                        del self.active_players[map_name][player_name]

        # Update and check parsing statistics
        self._parsing_stats['lines_processed'] += len(lines)
        self._parsing_stats['joins_found'] += len(joins)
        self._parsing_stats['leaves_found'] += len(leaves)

        # Check for potential parsing issues if we've processed a significant number of lines
        if self._parsing_stats['lines_processed'] > 1000:
            total_events = self._parsing_stats['joins_found'] + self._parsing_stats['leaves_found']
            match_rate = total_events / self._parsing_stats['lines_processed']
            # If match rate is extremely low (e.g., less than 1 event per 1000 lines), it's suspicious
            if match_rate < 0.001:
                logger.warning_player(
                    f"Low log match rate ({match_rate:.4f}) for {map_name}. "
                    f"Processed {self._parsing_stats['lines_processed']} lines but only found {total_events} player events. "
                    f"The game log format may have changed."
                )
            # Reset stats after checking to avoid repeated warnings
            self._parsing_stats = {'lines_processed': 0, 'joins_found': 0, 'leaves_found': 0}
    
    async def update_active_players(self):
        """Update active players from server logs with exception-based rotation detection (like chat2.py)"""
        # Note: We run this even in read-only mode to get player counts for the web panel
        
        start_time = time.time()
        self._performance_stats['update_count'] += 1
        
        # Note: Periodic log file detection is now handled by external background task
        # This method can be called directly every 30 minutes as needed
        
        servers_processed = 0
        for server in self.servers:
            map_name = server.name
            log_path = server.server_log_path
            
            # Self-healing: If log path is missing, try to find it immediately
            if not log_path:
                logger.info_player(f"Log path missing for {map_name}, running dynamic detection")
                await self.update_server_log_files()
                log_path = server.server_log_path
                
                if not log_path:
                     logger.warning_player(f"Dynamic detection failed to find log for {map_name}, skipping")
                     continue
            
            servers_processed += 1
            
            # Ensure server exists in active_players with lock
            async with self.players_lock:
                if map_name not in self.active_players:
                    self.active_players[map_name] = {}
            
            try:
                # Exception-based log file detection (like chat2.py)
                if not os.path.exists(log_path):
                    logger.debug_player(f"[DEBUG-TRACE] Log file does not exist for {map_name}: {log_path}")
                    logger.info_player(f"Log file not found for {map_name}: {log_path}, running dynamic detection")
                    await self.update_server_log_files()
                    # Update log_path reference after dynamic detection
                    log_path = server.server_log_path
                    if not log_path:
                         logger.debug_player(f"[DEBUG-TRACE] Dynamic detection failed to find log for {map_name}")
                         continue
                
                # Get file size asynchronously
                current_size = await asyncio.to_thread(os.path.getsize, log_path)
                
                # Get stored position with lock and implement smart position management
                async with self.file_positions_lock:
                    stored_pos = self.file_positions.get(map_name, 0)
                    
                    # Detect log rotation or significant file size changes
                    if stored_pos > current_size:
                        # Log rotation detected - file is smaller than our position
                        logger.info_player(f"Log rotation detected for {map_name}, running dynamic detection", 
                                         server=map_name, old_position=stored_pos, new_size=current_size)
                        # Run dynamic log file detection immediately
                        await self.update_server_log_files()
                        # Update log_path reference after dynamic detection
                        log_path = server.server_log_path
                        # Reset position to 0 for the new file
                        self.file_positions[map_name] = 0
                        stored_pos = 0
                        # Get new file size
                        try:
                            current_size = await asyncio.to_thread(os.path.getsize, log_path)
                        except Exception as e:
                            logger.error_player(f"Error getting new file size for {map_name}: {e}")
                            continue
                    elif stored_pos < 0:
                        # Invalid position
                        logger.info_player(f"Invalid file position for {map_name}, resetting", 
                                         server=map_name, position=stored_pos)
                        self.file_positions[map_name] = 0
                        stored_pos = 0
                    elif current_size - stored_pos > 50 * 1024 * 1024:  # 50MB behind
                        # We're too far behind, skip some content to catch up
                        skip_bytes = current_size - stored_pos - 10 * 1024 * 1024  # Keep last 10MB
                        logger.info_player(f"Log file {map_name} is large, skipping {skip_bytes/1024/1024:.1f}MB to catch up", 
                                         server=map_name, skip_mb=skip_bytes/1024/1024, current_mb=current_size/1024/1024)
                        stored_pos += skip_bytes
                        self.file_positions[map_name] = stored_pos
                
                # Read log file asynchronously with timing
                file_read_start = time.time()
                new_lines, new_pos = await self._read_log_file_async(log_path, stored_pos, current_size)
                file_read_time = time.time() - file_read_start
                self._performance_stats['total_file_read_time'] += file_read_time
                
                # Process new lines in batches to reduce lock contention
                if new_lines:
                    processing_start = time.time()
                    await self._process_log_lines_batch(map_name, new_lines)
                    processing_time = time.time() - processing_start
                    
                    # Log performance metrics for large operations
                    if file_read_time > 0.1 or processing_time > 0.1:
                        logger.info_performance(f"Processed {len(new_lines)} lines for {map_name}", 
                                              server=map_name, lines=len(new_lines), 
                                              read_time=f"{file_read_time:.3f}s", 
                                              process_time=f"{processing_time:.3f}s")
                    self._performance_stats['total_processing_time'] += processing_time
                    self._performance_stats['total_lines_processed'] += len(new_lines)
                
                # Update file position with lock
                async with self.file_positions_lock:
                    self.file_positions[map_name] = new_pos
                    
            except FileNotFoundError:
                logger.info_player(f"Log file disappeared for {map_name}, running dynamic detection", 
                                  server=map_name, log_path=log_path)
                await self.update_server_log_files()
                continue
            except PermissionError:
                logger.error_player(f"Permission denied reading log for {map_name}", 
                                  server=map_name, log_path=log_path)
                continue
            except Exception as e:
                logger.error_player(f"Error reading log file", 
                                  server=map_name, error=str(e), log_path=log_path)
                continue
        
        # Update performance stats
        total_time = time.time() - start_time
        self._performance_stats['last_update_time'] = total_time
        
        # Log performance metrics if update took too long
        if total_time > 1.0:  # Log if update takes more than 1 second
            logger.info_performance(f"PlayerManager update took {total_time:.2f}s", 
                                  total_time=f"{total_time:.2f}s",
                                  file_time=f"{self._performance_stats['total_file_read_time']:.2f}s",
                                  processing_time=f"{self._performance_stats['total_processing_time']:.2f}s",
                                  lines_processed=self._performance_stats['total_lines_processed'])

    async def clear_server_players(self, server_name: str = None):
        """Clear player data for a specific server or all servers with proper locking"""
        async with self.players_lock:
            if server_name and server_name in self.active_players:
                self.active_players[server_name] = {}
                logger.info_player(f"Cleared player data for server", server=server_name)
            elif server_name is None:
                for srv in self.servers:
                    self.active_players[srv.name] = {}
                logger.info_player(f"Cleared player data for all servers")

    async def reset_file_positions(self, server_name: str = None):
        """Reset file positions for a specific server or all servers with proper locking"""
        async with self.file_positions_lock:
            if server_name:
                self.file_positions[server_name] = 0
                logger.info_player(f"Reset file position for server", server=server_name)
            else:
                for srv in self.servers:
                    self.file_positions[srv.name] = 0
                logger.info_player(f"Reset file positions for all servers")

    async def ban_player(self, name: str):
        """Ban a player with proper async locking"""
        name = name.strip()
        if not name:
            return False
        
        # Add to banned players with lock
        async with self.bans_lock:
            self.banned_players.add(name)
        await self._save_bans()
        
        # Remove if currently online with lock
        async with self.players_lock:
            for srv in self.servers:
                if name in self.active_players.get(srv.name, {}):
                    del self.active_players[srv.name][name]
        
        logger.info_player(f"Banned player", player=name)
        return True

    async def unban_player(self, name: str):
        """Unban a player with proper async locking"""
        name = name.strip()
        if not name:
            return False
        
        # Remove from banned players
        if name in self.banned_players:
            self.banned_players.remove(name)
            await self._save_bans()
            logger.info_player(f"Unbanned player", player=name)
            return True
        else:
            logger.info_player(f"Player is not banned", player=name)
        return False

    async def get_total_players(self) -> Tuple[int, Dict[str, List[Dict[str, str]]]]:
        """Get total players count and details with proper async locking"""
        total_players = 0
        server_details: Dict[str, List[Dict[str, str]]] = {}
        
        # Get banned players set with lock
        async with self.bans_lock:
            banned_set = self.banned_players.copy()
        
        # Get active players with lock
        async with self.players_lock:
            active_players_copy = {}
            for server_name, players in self.active_players.items():
                active_players_copy[server_name] = players.copy()
        
        # Process data outside locks
        for server in self.servers:
            map_name = server.name
            display_name = server.display_name or server.name
            players = []
            for player_name, info in active_players_copy.get(map_name, {}).items():
                if player_name not in banned_set:
                    session_time = int((datetime.datetime.now() - info['join_time']).total_seconds() // 60)
                    players.append({
                        "name": player_name,
                        "unique_id": info['unique_id'],
                        "session_time": f"{session_time}m"
                    })
            total_players += len(players)
            server_details[display_name] = players
        return total_players, server_details
    
    def get_performance_stats(self) -> Dict[str, any]:
        """Get performance statistics for the PlayerManager"""
        stats = self._performance_stats.copy()
        
        # Calculate averages
        if stats['update_count'] > 0:
            stats['avg_file_read_time'] = stats['total_file_read_time'] / stats['update_count']
            stats['avg_processing_time'] = stats['total_processing_time'] / stats['update_count']
            stats['avg_lines_per_update'] = stats['total_lines_processed'] / stats['update_count']
        else:
            stats['avg_file_read_time'] = 0
            stats['avg_processing_time'] = 0
            stats['avg_lines_per_update'] = 0
        
        return stats
    
    async def optimize_file_positions(self):
        """Optimize file positions by cleaning up old data and detecting rotations"""
        optimization_stats = {
            'servers_checked': 0,
            'rotations_detected': 0,
            'positions_reset': 0,
            'bytes_saved': 0
        }
        
        for server in self.servers:
            map_name = server.name
            log_path = server.server_log_path
            if not log_path:
                continue
                
            optimization_stats['servers_checked'] += 1
            
            try:
                # Check if file exists
                file_exists = await asyncio.to_thread(os.path.exists, log_path)
                if not file_exists:
                    # File doesn't exist, reset position
                    async with self.file_positions_lock:
                        old_pos = self.file_positions.get(map_name, 0)
                        self.file_positions[map_name] = 0
                        if old_pos > 0:
                            optimization_stats['positions_reset'] += 1
                    continue
                
                # Get current file size
                current_size = await asyncio.to_thread(os.path.getsize, log_path)
                
                async with self.file_positions_lock:
                    stored_pos = self.file_positions.get(map_name, 0)
                    
                    # Detect log rotation
                    if stored_pos > current_size:
                        logger.info_player(f"Log rotation detected during optimization", server=map_name)
                        self.file_positions[map_name] = 0
                        optimization_stats['rotations_detected'] += 1
                        optimization_stats['positions_reset'] += 1
                        optimization_stats['bytes_saved'] += stored_pos
                    
                    # Clean up if we're too far behind
                    elif current_size - stored_pos > 100 * 1024 * 1024:  # 100MB behind
                        skip_bytes = current_size - stored_pos - 25 * 1024 * 1024  # Keep last 25MB
                        logger.info_player(f"Optimizing {map_name}: skipping {skip_bytes/1024/1024:.1f}MB", 
                                         server=map_name, skip_mb=skip_bytes/1024/1024)
                        self.file_positions[map_name] = stored_pos + skip_bytes
                        optimization_stats['positions_reset'] += 1
                        optimization_stats['bytes_saved'] += skip_bytes
                        
            except Exception as e:
                logger.error_player(f"Error during file position optimization", 
                                  server=map_name, error=str(e))
        
        # Log optimization results
        if optimization_stats['rotations_detected'] > 0 or optimization_stats['positions_reset'] > 0:
            logger.info_performance(f"File position optimization completed", 
                                  rotations=optimization_stats['rotations_detected'],
                                  resets=optimization_stats['positions_reset'], 
                                  mb_saved=f"{optimization_stats['bytes_saved']/1024/1024:.1f}")
        
        return optimization_stats
    
    async def cleanup_old_player_data(self, max_session_time_hours: int = 24):
        """Clean up old player data to prevent memory bloat"""
        cleanup_stats = {
            'servers_cleaned': 0,
            'players_removed': 0,
            'old_sessions_removed': 0
        }
        
        current_time = datetime.datetime.now()
        max_session_time = datetime.timedelta(hours=max_session_time_hours)
        
        async with self.players_lock:
            for server_name, players in self.active_players.items():
                players_to_remove = []
                
                for player_name, player_info in players.items():
                    session_time = current_time - player_info['join_time']
                    if session_time > max_session_time:
                        players_to_remove.append(player_name)
                        cleanup_stats['old_sessions_removed'] += 1
                
                # Remove old players
                for player_name in players_to_remove:
                    del self.active_players[server_name][player_name]
                    cleanup_stats['players_removed'] += 1
                
                if players_to_remove:
                    cleanup_stats['servers_cleaned'] += 1
        
        if cleanup_stats['players_removed'] > 0:
            logger.info_player(f"Player data cleanup completed", 
                             players_removed=cleanup_stats['players_removed'],
                             servers_cleaned=cleanup_stats['servers_cleaned'],
                             old_sessions_removed=cleanup_stats['old_sessions_removed'])
        
        return cleanup_stats
    
    # Dynamic Log File Detection Methods (copied from chat2.py with adaptations)
    def get_logs_directory(self):
        """Extract the logs directory path from any server's config"""
        if not self.servers:
            return None
        
        # 1. Try to get explicit log_dir from config first (Robust)
        for server in self.servers:
            if hasattr(server, 'log_dir') and server.log_dir and os.path.exists(server.log_dir):
                 return server.log_dir
        
        # 2. Fallback: Get the directory from the first server's log_file path
        first_log_file = self.servers[0].server_log_path
        if first_log_file and os.path.exists(os.path.dirname(first_log_file)):
            return os.path.dirname(first_log_file)
            
        # 3. Fallback: Derive from server_save_path (Smart)
        for server in self.servers:
            save_path = getattr(server, 'server_save_path', None)
            if save_path:
                 # Normalize path
                 save_path = os.path.normpath(save_path)
                 # save_path is typically .../Saved/MapName
                 # Logs are .../Saved/Logs
                 saved_dir = os.path.dirname(save_path)
                 logs_dir = os.path.join(saved_dir, "Logs")
                 
                 if os.path.isdir(logs_dir):
                     logger.debug_player(f"Derived logs directory from save path: {logs_dir}")
                     return logs_dir
            
        return None
    
    def extract_server_info_from_log(self, log_file_path):
        """Extract server identification information from log file content"""
        try:
            if not os.path.exists(log_file_path):
                return None
            
            # Read first 200 lines to find server identification info
            with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = []
                for _ in range(200):  # Read up to 200 lines
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line)
            
            if not lines:
                return None
            
            server_info = {
                "map_name": None,
                "rcon_port": None,
                "last_modified": os.path.getmtime(log_file_path)
            }
            
            # Map patterns to search for in command line
            map_patterns = [
                r"TheIsland",
                "ScorchedEarth",
                "Ragnarok",
                "TheCenter",
                "Aberration",
                "Extinction",
                "Genesis",
                "ClubArk",
                "Valguero",
                "CrystalIsles",
                "LostIsland",
                "Astraeos",
                "Fjordur"
            ]
            
            # RCON port patterns (more specific and in order of preference)
            # Based on RaptorChat.py patterns which are proven to work
            rcon_patterns = [
                r"RCONPort=(\d{4,5})\b",  # Command line parameter
                r"-RCONPort[= ](\d{4,5})\b",  # Command line flag
                r"RCON.*port[= ](\d{4,5})\b", # RCON port 27103
                r"-RCONPort\s+(\d{4,5})",  # Space separator
                r"RCON.*listening.*port\s+(\d{4,5})", # Startup log
                r"Starting.*RCON.*port\s+(\d{4,5})"   # Startup log
            ]
            
            # First pass: Look for command line arguments (usually in first few lines)
            for line in lines:
                # Look for RCON port in command line
                if not server_info["rcon_port"]:
                    for pattern in rcon_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            port = int(match.group(1))
                            # Only accept ports in a reasonable range (1000-65535)
                            if 1000 <= port <= 65535:
                                server_info["rcon_port"] = port
                                break
                
                # Look for map name in command line
                if not server_info["map_name"]:
                    for map_name in map_patterns:
                        if map_name.lower() in line.lower():
                            server_info["map_name"] = map_name.lower()
                            break
                
                # If we found both, we're done
                if server_info["rcon_port"] and server_info["map_name"]:
                    break
            
            # If we still don't have an RCON port, try more aggressive patterns
            if not server_info["rcon_port"]:
                for line in lines:
                    # Look for RCON startup message
                    match = re.search(r"RCON.*port.*?(\d{4,5})\b", line, re.IGNORECASE)
                    if match:
                        port = int(match.group(1))
                        if 1000 <= port <= 65535:
                            server_info["rcon_port"] = port
                            break
            
            return server_info if (server_info["map_name"] or server_info["rcon_port"]) else None
            
        except Exception as e:
            logger.error_player(f"Error reading log file {log_file_path}: {e}")
            return None
    
    def find_matching_log_file(self, server_config, exclude_files=None):
        """Find the correct log file for a server based on its RCON port"""
        logs_dir = self.get_logs_directory()
        if not logs_dir:
            return None
        
        server_name = server_config.name
        expected_rcon_port = getattr(server_config, 'rcon_port', None)
        exclude_files = exclude_files or set()
        
        logger.info_player(f"Searching for correct log file for server: {server_name}")
        
        # Find all ShooterGame_*.log files, excluding backups
        log_files = []
        try:
            for filename in os.listdir(logs_dir):
                if (filename.startswith("ShooterGame") and 
                    filename.endswith(".log") and 
                    'backup' not in filename.lower()):  # Skip backup files
                    log_path = os.path.join(logs_dir, filename)
                    # Skip already assigned files
                    if log_path in exclude_files:
                        continue
                    log_files.append(log_path)
            
            # Sort by modification time (newest first)
            # This is critical: The active log is receiving writes, so it has the latest mtime.
            # Old rotated logs are static.
            log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
        except Exception as e:
            logger.error_player(f"Error scanning logs directory {logs_dir}: {e}")
            return None
        
        if not log_files:
            if exclude_files:
                logger.info_player(f"No available ShooterGame_*.log files found for {server_name} (some may be assigned to other servers)")
            else:
                logger.debug_player(f"[DEBUG-TRACE] No ShooterGame_*.log files found in {logs_dir}")
                logger.info_player(f"No ShooterGame_*.log files found in {logs_dir}")
            return None
        
        # Check each log file for matching RCON port
        for log_file in log_files:
            server_info = self.extract_server_info_from_log(log_file)
            extracted_port = server_info.get("rcon_port") if server_info else "None"
            
            # DEBUG: Log the check
            logger.debug_player(f"[DEBUG-TRACE] Checking {os.path.basename(log_file)}: Extracted RCON={extracted_port} Expected={expected_rcon_port}")
            
            if server_info and server_info.get("rcon_port") == expected_rcon_port:
                logger.info_player(f"Best match for {server_name}: {os.path.basename(log_file)}")
                return log_file
        
        logger.info_player(f"No log file with matching RCON port found for {server_name}")
        return None
    
    async def update_server_log_files(self):
        """Update all server log file paths based on dynamic detection"""
        logger.info_system("Starting dynamic log file detection")
        
        updates_made = False
        assigned_log_files = set()  # Track which log files are already assigned
        
        # Process each server once to avoid duplicate searches
        for server in self.servers:
            matching_log = self.find_matching_log_file(server, assigned_log_files)
            if matching_log and matching_log != server.server_log_path:
                logger.info_player(f"Updating log file for {server.name}:")
                logger.info_player(f"  From: {os.path.basename(server.server_log_path)}")
                logger.info_player(f"  To:   {os.path.basename(matching_log)}")
                server.server_log_path = matching_log
                assigned_log_files.add(matching_log)
                updates_made = True
            elif matching_log and matching_log == server.server_log_path:
                logger.info_player(f"Log file already correct for {server.name}: {os.path.basename(matching_log)}")
        
        if updates_made:
            logger.info_system("Dynamic log file detection completed")
            # Reset file positions when log files are updated
            await self.reset_file_positions()
            # Update the config.json file with new log file paths
            if not self.read_only:
                await self._update_config_json()
        else:
            logger.info_system("Dynamic log file detection completed")
        
        return updates_made
    
    async def _update_config_json(self):
        """Update the config.json file with new log file paths"""
        try:
            # Path to the main config.json file
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
            
            # Load the current config
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Update the server_log_path for each server in the config
            for server in self.servers:
                # Find the matching server in the config
                for config_server in config.get('cluster_servers', []):
                    if config_server.get('name') == server.name:
                        # Update the log file path
                        old_path = config_server.get('server_log_path')
                        new_path = server.server_log_path
                        if old_path != new_path:
                            config_server['server_log_path'] = new_path
            
            # Save the updated config back to the file
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            logger.info_system("Updated config.json with new log file paths")
        except Exception as e:
            logger.error_system(f"Error updating config.json: {e}")
    
    async def trigger_log_file_detection_on_restart(self):
        """Trigger log file detection when servers are confirmed to be back online after restart"""
        logger.info_system("Servers confirmed online - triggering log file detection for restart recovery")
        updates_made = await self.update_server_log_files()
        if updates_made:
            logger.info_system("Log file paths updated after server restart - chat relay should now work")
        else:
            logger.info_system("No log file changes needed after server restart")
        return updates_made
