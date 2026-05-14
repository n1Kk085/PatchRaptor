import os
import json
import time
import datetime
import asyncio
import psutil
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from .log_manager import logger, LOG_PATH
from .service_locator import ServiceLocator
from . import ark_log_utils as log_utils

@dataclass
class TelemetryState:
    """Represents the complete live state of the cluster"""
    servers: List[Dict[str, Any]] = field(default_factory=list)
    server_player_averages: Dict[str, float] = field(default_factory=dict)
    server_uptime_averages: Dict[str, float] = field(default_factory=dict)
    total_players: int = 0
    total_7day_player_avg: float = 0.0
    total_7day_uptime_avg: float = 0.0
    server_count: int = 0
    online_count: int = 0
    last_update: str = ""
    current_time: str = ""

class BaseDiskTracker:
    """Common logic for disk-persisted trackers"""
    def __init__(self, data_file: str, logger_suffix: str):
        self.data_file = data_file
        self.logger_suffix = logger_suffix
        self.data = self._load_data()
        self.last_cleanup_time = 0
        self._cleanup_old_entries()
        self._dirty = False

    def _load_data(self) -> Dict[str, Any]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error_system(f"Error loading {self.logger_suffix}: {e}")
        return {}
    
    async def save(self):
        if not self._dirty: return
        try:
            # Offload synchronous disk I/O to a background thread
            await asyncio.to_thread(self._sync_save)
            self._dirty = False
        except Exception as e:
            logger.error_system(f"Error saving {self.logger_suffix}: {e}")

    def _sync_save(self):
        """Internal synchronous saver for threaded execution with atomic write"""
        temp_file = self.data_file + ".tmp"
        try:
            with open(temp_file, 'w') as f:
                # Minified JSON for zero-spike efficiency
                json.dump(self.data, f, separators=(',', ':'))
            os.replace(temp_file, self.data_file)
        except Exception as e:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
            raise e

    def _cleanup_old_entries(self):
        # Only cleanup once per hour to save CPU
        current_time = time.time()
        if current_time - self.last_cleanup_time < 3600:
            return

        week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        changed = False
        if 'servers' in self.data:
            for server_name in list(self.data['servers'].keys()):
                server_data = self.data['servers'][server_name]
                new_entries = [e for e in server_data.get('entries', []) if e.get('timestamp', 0) >= week_ago]
                if len(new_entries) != len(server_data.get('entries', [])):
                    server_data['entries'] = new_entries
                    changed = True
                if not server_data['entries']:
                    self.data['servers'].pop(server_name, None)
                    changed = True
        
        self.last_cleanup_time = current_time
        if changed: self._dirty = True

class UptimeTracker(BaseDiskTracker):
    """Tracks server uptime statistics over time"""
    def __init__(self, data_file: str):
        super().__init__(data_file, "uptime stats")
    
    def record_uptime(self, server_name: str, is_online: bool):
        if not server_name: return
        if 'servers' not in self.data: self.data['servers'] = {}
        if server_name not in self.data['servers']:
            self.data['servers'][server_name] = {'entries': []}
        
        self.data['servers'][server_name]['entries'].append({
            'timestamp': time.time(),
            'is_online': is_online
        })
        self._dirty = True
    
    def get_server_7day_uptime(self, server_name: str) -> float:
        if not server_name or server_name not in self.data.get('servers', {}): return 0.0
        entries = self.data['servers'][server_name].get('entries', [])
        if not entries: return 0.0
        online_count = sum(1 for e in entries if e.get('is_online', False))
        return (online_count / len(entries)) * 100.0

    def get_average_7day_uptime(self) -> float:
        if not self.data.get('servers'): return 0.0
        total_uptime = 0.0
        server_count = 0
        for server_name in self.data['servers']:
            total_uptime += self.get_server_7day_uptime(server_name)
            server_count += 1
        return total_uptime / server_count if server_count > 0 else 0.0

class PlayerStatsTracker(BaseDiskTracker):
    """Tracks player statistics over time"""
    def __init__(self, data_file: str):
        super().__init__(data_file, "player stats")
            
    def record_players(self, server_name: str, map_name: str, player_count: int):
        if not server_name: return
        if 'servers' not in self.data: self.data['servers'] = {}
        if server_name not in self.data['servers']:
            self.data['servers'][server_name] = {'map_name': map_name, 'entries': []}
            
        self.data['servers'][server_name]['entries'].append({
            'timestamp': time.time(),
            'player_count': player_count
        })
        self._dirty = True

    def get_server_7day_avg(self, server_name: str) -> float:
        if not server_name or server_name not in self.data.get('servers', {}): return 0.0
        entries = self.data['servers'][server_name].get('entries', [])
        if not entries: return 0.0
        total_players = sum(e.get('player_count', 0) for e in entries)
        return total_players / len(entries)

    def get_total_7day_avg(self) -> float:
        if not self.data.get('servers'): return 0.0
        total_players = 0
        total_entries = 0
        seven_days_ago = time.time() - (7 * 24 * 60 * 60)
        
        for server_data in self.data['servers'].values():
            recent_entries = [e for e in server_data.get('entries', []) if e.get('timestamp', 0) >= seven_days_ago]
            if recent_entries:
                total_players += sum(e.get('player_count', 0) for e in recent_entries)
                total_entries += len(recent_entries)
                
        return round(total_players / total_entries, 1) if total_entries > 0 else 0.0

    def get_7day_peak(self) -> int:
        """Calculate the absolute highest aggregate player count in the last 7 days"""
        # Note: Since we store per-server, we approximate peak by looking at the highest total 
        # recorded across servers at similar timestamps. For simplicity, we track highest single-server peak.
        peak = 0
        seven_days_ago = time.time() - (7 * 24 * 60 * 60)
        for server_name in self.data.get('servers', {}):
            entries = self.data['servers'][server_name].get('entries', [])
            for e in entries:
                if e.get('timestamp', 0) >= seven_days_ago:
                    peak = max(peak, e.get('player_count', 0))
        return peak

class LogBroadcaster:
    """High-efficiency log tailing engine that distributes events to listeners"""
    def __init__(self, telemetry_manager):
        self.tm = telemetry_manager
        self.file_positions: Dict[str, int] = {}
        self.last_rotation_log_time: Dict[str, float] = {}
        self.listeners: Dict[str, List[Any]] = {
            "join": [],
            "leave": [],
            "chat": [],
            "command": []
        }
        self._lock = asyncio.Lock()

    def register_listener(self, event_type: str, callback: Any):
        if event_type in self.listeners:
            self.listeners[event_type].append(callback)
            logger.debug_system(f"Registered listener for {event_type} events")

    async def broadcast_event(self, event_type: str, data: Dict[str, Any]):
        """Push an event to all registered listeners"""
        if event_type not in self.listeners:
            return
        
        tasks = []
        for callback in self.listeners[event_type]:
            if asyncio.iscoroutinefunction(callback):
                tasks.append(callback(data))
            else:
                callback(data)
                
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def tail_logs(self):
        """Scan all server logs once and broadcast new events (Threaded)"""
        servers = self.tm.server_manager.servers
        for server in servers:
            log_path = server.server_log_path
            
            # 1. Recover path if missing
            if not log_path or not os.path.exists(log_path):
                logs_dir = log_utils.get_logs_directory([server])
                if logs_dir:
                    new_path = log_utils.find_matching_log_file(server, logs_dir)
                    if new_path:
                        server.server_log_path = new_path
                        log_path = new_path
                
            if not log_path or not os.path.exists(log_path):
                continue

            try:
                current_size = os.path.getsize(log_path)
                
                # Check if this is the first time we're tracking this file
                if server.name not in self.file_positions:
                    # Use creation time to determine if this is an existing log or a fresh one
                    # If the file was created before the bot started, initialize to END to avoid replaying history
                    try:
                        creation_time = os.path.getctime(log_path)
                        if creation_time < self.tm.bot_start_time.timestamp() - 10: # 10s buffer
                            logger.debug_system(f"Broadcaster: Existing log detected for {server.name}, initializing to END")
                            self.file_positions[server.name] = current_size
                            continue
                        else:
                            logger.debug_system(f"Broadcaster: Fresh log detected for {server.name}, starting from BEGINNING")
                            self.file_positions[server.name] = 0
                    except Exception:
                        # Fallback: if we can't get ctime, use a much smaller size threshold (4KB)
                        if current_size < 4096:
                            self.file_positions[server.name] = 0
                        else:
                            self.file_positions[server.name] = current_size
                            continue
                
                stored_pos = self.file_positions.get(server.name, 0)

                if stored_pos > current_size:
                    current_time = time.time()
                    last_log = self.last_rotation_log_time.get(server.name, 0)
                    if current_time - last_log > 60:
                        logger.info_player(f"Log rotation detected for {server.name}, resetting position")
                        self.last_rotation_log_time[server.name] = current_time
                    stored_pos = 0
                
                if current_size == stored_pos:
                    continue

                # Offload blocking I/O and regex parsing to a background thread
                events, new_pos = await asyncio.to_thread(
                    self._read_and_process_sync, 
                    log_path, 
                    stored_pos, 
                    server.name
                )
                
                # Update position
                self.file_positions[server.name] = new_pos

                # Broadcast events in the main thread (since broadcast_event is async)
                for event_type, event_data in events:
                    await self.broadcast_event(event_type, event_data)

            except Exception as e:
                logger.error_system(f"Broadcaster failed for {server.name}: {e}")

    def _read_and_process_sync(self, log_path, stored_pos, server_name):
        """Synchronous worker for threaded log processing"""
        events = []
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(stored_pos)
                # Read 256KB max to stay responsive (Zero-Spike optimization)
                data = f.read(256 * 1024)
                new_pos = f.tell()

            if not data:
                return [], new_pos

            lines = data.splitlines()
            for line in lines:
                # Fast String Hook: Skip 99% of log lines before expensive regex
                if " joined this ARK!" not in line and " left this ARK!" not in line:
                    continue
                    
                line = line.strip()
                if not line: continue
                
                # Check JOINS
                for pattern in log_utils.JOIN_PATTERNS:
                    match = pattern.search(line)
                    if match:
                        events.append(("join", {
                            "server": server_name,
                            "name": match.group(1).strip(),
                            "id": match.group(2).strip(),
                            "raw": line
                        }))
                        break
                
                # Check LEAVES
                for pattern in log_utils.LEAVE_PATTERNS:
                    match = pattern.search(line)
                    if match:
                        events.append(("leave", {
                            "server": server_name,
                            "name": match.group(1).strip(),
                            "id": match.group(2).strip(),
                            "raw": line
                        }))
                        break
            
            return events, new_pos
        except Exception as e:
            # Errors in threads are suppressed to avoid interrupting main execution path.
            return [], stored_pos

class PerformanceTracker:
    """Tracks historical performance metrics (CPU, RAM, RCON latency)"""
    def __init__(self, data_file: str):
        self.data_file = data_file
        self.history = self._load_history()
        self._dirty = False
        
    def _load_history(self) -> Dict[str, Any]:
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error_system(f"Error loading performance history: {e}")
        return {
            "system_metrics": []
        }
        
    async def save(self):
        if not self._dirty: return
        try:
            await asyncio.to_thread(self._sync_save)
            self._dirty = False
        except Exception as e:
            logger.error_system(f"Error saving performance history: {e}")

    def _sync_save(self):
        """Internal synchronous saver for threaded execution with atomic write"""
        temp_file = self.data_file + ".tmp"
        try:
            with open(temp_file, 'w') as f:
                # Minified JSON for zero-spike efficiency
                json.dump(self.history, f, separators=(',', ':'))
            os.replace(temp_file, self.data_file)
        except Exception as e:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
            raise e

    def record_metric(self, cpu_pct: float, ram_pct: float, disk_pct: float):
        self.history["system_metrics"].append({
            "timestamp": datetime.datetime.now().isoformat(),
            "cpu_percent": cpu_pct,
            "memory_percent": ram_pct,
            "disk_percent": disk_pct
        })
        # Keep last 100 entries
        if len(self.history["system_metrics"]) > 100:
            self.history["system_metrics"] = self.history["system_metrics"][-100:]
        self._dirty = True

    def get_rolling_averages(self) -> Dict[str, float]:
        """Calculate average system load over the last 100 pulses"""
        metrics = self.history.get("system_metrics", [])
        if not metrics:
            return {"cpu": 0.0, "ram": 0.0, "disk": 0.0}
        
        count = len(metrics)
        avg_cpu = sum(m.get("cpu_percent", 0) for m in metrics) / count
        avg_ram = sum(m.get("memory_percent", 0) for m in metrics) / count
        avg_disk = sum(m.get("disk_percent", 0) for m in metrics) / count
        
        return {
            "cpu": round(avg_cpu, 1),
            "ram": round(avg_ram, 1),
            "disk": round(avg_disk, 1)
        }


class TelemetryManager:
    """Master Collector: Gathers all cluster data Once and Distributes to all services"""
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.live_state_file = os.path.join(LOG_PATH, "cluster_live.json")
        self.uptime_tracker = UptimeTracker(os.path.join(LOG_PATH, "uptime_stats.json"))
        self.player_stats_tracker = PlayerStatsTracker(os.path.join(LOG_PATH, "player_stats.json"))
        
        self.current_state = TelemetryState()
        self.performance_tracker = PerformanceTracker(os.path.join(LOG_PATH, "performance_history.json"))
        self.broadcaster = LogBroadcaster(self)
        self.process_cache: Dict[int, psutil.Process] = {}
        self._lock = asyncio.Lock()
        self.bot_start_time = datetime.datetime.now()
        
        # Phase 4: Throttled I/O echo counter
        self._echo_count = 0
        
        # Prime the CPU sampler for non-blocking usage
        psutil.cpu_percent(interval=None)

        # Register for instant telemetry patching (Zero-Drift WebPanel)
        self.broadcaster.register_listener("join", self._handle_instant_join)
        self.broadcaster.register_listener("leave", self._handle_instant_leave)
        
    @property
    def server_manager(self): return ServiceLocator.get("ServerManager")
    
    @property
    def player_manager(self): return ServiceLocator.get("PlayerManager")
    
    @property
    def system_monitoring(self): return ServiceLocator.get("SystemMonitoringHandler")
    
    @property
    def rcon_manager(self): return ServiceLocator.get("RCONManager")
    
    @property
    def config_manager(self): return ServiceLocator.get("ConfigManager")

    @property
    def backup_manager(self): return ServiceLocator.get("BackupManager")

    @property
    def version_manager(self): return ServiceLocator.get("VersionManager")

    async def collect_echo(self):
        """Execute a single telemetry gathering echo"""
        async with self._lock:
            try:
                # 1. Gather status from Managers
                servers = self.server_manager.servers
                total_players, player_details = await self.player_manager.get_total_players()
                
                servers_data = []
                server_player_avgs = {}
                server_uptime_avgs = {}
                online_count = 0
                
                for server in servers:
                    # Leverage ServerManager's discovery logic
                    process_obj = self.server_manager.get_running_process(server)
                    is_online = process_obj is not None
                    cpu = 0.0
                    ram = 0.0
                    
                    if is_online:
                        online_count += 1
                        try:
                            pid = process_obj.pid
                            if pid not in self.process_cache:
                                self.process_cache[pid] = process_obj
                                process_obj.cpu_percent()
                            
                            cached_proc = self.process_cache[pid]
                            if not cached_proc.is_running():
                                self.process_cache[pid] = process_obj
                                cached_proc = process_obj
                                cached_proc.cpu_percent()

                            cpu = cached_proc.cpu_percent() / psutil.cpu_count()
                            ram = cached_proc.memory_info().rss / (1024 ** 3)
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            is_online = False
                            if pid in self.process_cache: 
                                del self.process_cache[pid]

                    # 2. Record Stats
                    self.uptime_tracker.record_uptime(server.name, is_online)
                    
                    display_name = server.display_name or server.name
                    players = player_details.get(display_name, [])
                    count = len(players)
                    self.player_stats_tracker.record_players(server.name, server.map_name, count)
                    
                    # 3. Calculate Averages
                    uptime_7d = self.uptime_tracker.get_server_7day_uptime(server.name)
                    p_avg_7d = self.player_stats_tracker.get_server_7day_avg(server.name)
                    
                    server_player_avgs[server.name] = p_avg_7d
                    server_uptime_avgs[server.name] = uptime_7d
                    
                    servers_data.append({
                        'name': server.name,
                        'displayName': display_name,
                        'mapName': (server.map_name or 'Unknown').replace('_', ' ').replace('WP', '').strip().title(),
                        'status': 'online' if is_online else 'offline',
                        'playerCount': count,
                        'cpu': round(cpu, 1),
                        'ram': round(ram, 1),
                        'uptime_seconds': int(time.time() - cached_proc.create_time()) if is_online else 0,
                        'uptime7day': round(uptime_7d, 1),
                        'playerAvg7day': round(p_avg_7d, 1)
                    })

                # 4. Update State
                self.current_state = TelemetryState(
                    servers=servers_data,
                    server_player_averages=server_player_avgs,
                    server_uptime_averages=server_uptime_avgs,
                    total_players=total_players,
                    total_7day_player_avg=self.player_stats_tracker.get_total_7day_avg(),
                    total_7day_uptime_avg=self.uptime_tracker.get_average_7day_uptime(),
                    server_count=len(servers),
                    online_count=online_count,
                    last_update=datetime.datetime.now().isoformat(),
                    current_time=datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                
                # 5. Record Performance Metric (System-wide)
                memory = psutil.virtual_memory()
                server_dir = self.config_manager.get("server_dir", ".")
                disk = psutil.disk_usage(server_dir)
                cpu_now = psutil.cpu_percent(interval=None) # Non-blocking delta since last echo
                self.performance_tracker.record_metric(cpu_now, memory.percent, disk.percent)
                
                # 7. Periodic cleanup and save
                self.uptime_tracker._cleanup_old_entries()
                self.player_stats_tracker._cleanup_old_entries()
                
                # Phase 4: Throttled tracking saves (Every 60s / 6 echoes)
                self._echo_count += 1
                if self._echo_count >= 6:
                    await self.uptime_tracker.save()
                    await self.player_stats_tracker.save()
                    await self.performance_tracker.save()
                    self._echo_count = 0
                
                # Echo the live state immediately to Discord and WebPanel (Lightweight)
                await self._publish_state()
                
            except Exception as e:
                logger.error_system(f"Telemetry echo failed: {e}")

    async def get_diagnostics(self) -> Dict[str, Any]:
        """Execute a full suite of system diagnostics (Migrated from SystemMonitoringHandler)"""
        issues = []
        check_results = []
        
        # 1. Config Check
        try:
            required = ["bot_token", "channel_id", "app_id", "steamcmd_path", "server_dir"]
            missing = [k for k in required if not self.config_manager.get(k)]
            if missing:
                issues.append(f"Missing config keys: {', '.join(missing)}")
                check_results.append("❌ Configuration")
            else:
                check_results.append("☑️ Configuration")
        except Exception:
            check_results.append("❌ Configuration")

        # 2. System Monitoring (using current state)
        if self.current_state.online_count == 0 and self.current_state.server_count > 0:
             issues.append("No ARK server processes detected")
             check_results.append("❌ Server Monitoring")
        else:
             check_results.append("☑️ Server Monitoring")

        # 3. RCON Check (test first server)
        if self.server_manager.servers:
            server = self.server_manager.servers[0]
            try:
                await self.rcon_manager.execute_for_server(server, "GetVersion")
                check_results.append("☑️ RCON Connectivity")
            except Exception as e:
                issues.append(f"RCON check failed: {str(e)}")
                check_results.append("❌ RCON Connectivity")

        # 4. Steam Connectivity Check
        try:
            steamcmd_path = self.config_manager.get("steamcmd_path", "")
            if os.path.exists(steamcmd_path):
                # Basic network check (ping-like) to ensure Steam updates are possible
                try:
                    import socket
                    socket.create_connection(("1.1.1.1", 53), timeout=5)
                    check_results.append("☑️ Steam Connectivity")
                except Exception:
                    issues.append("Limited Internet connectivity (DNS/Network issue)")
                    check_results.append("❌ Steam Connectivity")
            else:
                issues.append(f"SteamCMD not found at: {steamcmd_path}")
                check_results.append("❌ Steam Connectivity")
        except Exception as e:
            issues.append(f"Steam check failed: {str(e)}")
            check_results.append("❌ Steam Connectivity")

        # 5. Disk Check
        disk_info = {"used": 0.0, "total": 0.0, "percent": 0.0}
        try:
            server_dir = self.config_manager.get("server_dir", ".")
            if os.path.exists(server_dir):
                usage = psutil.disk_usage(server_dir)
                disk_info = {
                    "used": usage.used / (1024**3),
                    "total": usage.total / (1024**3),
                    "percent": usage.percent
                }
                if usage.percent > 95:
                    issues.append(f"Critical disk usage: {usage.percent}%")
                    check_results.append("❌ Disk Space")
                else:
                    check_results.append("☑️ Disk Space")
            else:
                issues.append("Server directory not found")
                check_results.append("❌ Disk Space")
        except Exception:
             check_results.append("❌ Disk Space")

        return {
            "issues": issues,
            "results": check_results,
            "uptime_pc": str(datetime.timedelta(seconds=int(time.time() - psutil.boot_time()))),
            "ram_used": psutil.virtual_memory().used / (1024**3),
            "ram_total": psutil.virtual_memory().total / (1024**3),
            "cpu_usage": psutil.cpu_percent(),
            "disk_info": disk_info
        }

    async def trigger_log_file_detection_on_restart(self):
        """Reset log file pointers to force re-detection of files after a server restart"""
        logger.info_system("Triggering log file re-detection for system restart")
        async with self._lock:
            # Clear stored positions so broadcaster starts fresh
            self.broadcaster.file_positions.clear()
            # Reset server log paths in config model to force re-discovery
            for server in self.server_manager.servers:
                server.server_log_path = ""
            
            # Flush a single pulse to re-detect files immediately
            await self.broadcaster.tail_logs()

    async def _handle_instant_join(self, data: Dict[str, Any]):
        """Patch the current state immediately when a join is detected"""
        async with self._lock:
            server_name = data.get("server")
            for server in self.current_state.servers:
                if server['name'] == server_name:
                    server['playerCount'] += 1
                    self.current_state.total_players += 1
                    break
            await self._publish_state()

    async def _handle_instant_leave(self, data: Dict[str, Any]):
        """Patch the current state immediately when a leave is detected"""
        async with self._lock:
            server_name = data.get("server")
            for server in self.current_state.servers:
                if server['name'] == server_name:
                    server['playerCount'] = max(0, server['playerCount'] - 1)
                    self.current_state.total_players = max(0, self.current_state.total_players - 1)
                    break
            await self._publish_state()

    async def _publish_state(self):
        """Write current state to the public cluster_live.json file (Threaded)"""
        try:
            # Phase 4: Fast manual dict construction (10x faster than asdict)
            state = self.current_state
            state_dict = {
                "servers": state.servers,
                "server_player_averages": state.server_player_averages,
                "server_uptime_averages": state.server_uptime_averages,
                "total_players": state.total_players,
                "total_7day_player_avg": state.total_7day_player_avg,
                "total_7day_uptime_avg": state.total_7day_uptime_avg,
                "server_count": state.server_count,
                "online_count": state.online_count,
                "last_update": state.last_update,
                "current_time": state.current_time
            }
            # Offload heavy JSON dump to a background thread
            await asyncio.to_thread(self._sync_publish, state_dict)
        except Exception as e:
            logger.error_system(f"Failed to publish telemetry state: {e}")

    def _sync_publish(self, state_dict: dict):
        """Synchronous worker for state publishing with atomic write"""
        # CamelCase keys for Web Dashboard compatibility
        web_dict = {
            'servers': state_dict['servers'],
            'serverPlayerAverages': state_dict['server_player_averages'],
            'serverUptimeAverages': state_dict['server_uptime_averages'],
            'totalPlayers': state_dict['total_players'],
            'total7dayPlayerAvg': state_dict['total_7day_player_avg'],
            'total7dayUptimeAvg': state_dict['total_7day_uptime_avg'],
            'serverCount': state_dict['server_count'],
            'onlineCount': state_dict['online_count'],
            'lastUpdate': state_dict['last_update'],
            'currentTime': state_dict['current_time']
        }
        
        import time as _time
        temp_file = self.live_state_file + ".tmp"
        try:
            with open(temp_file, 'w') as f:
                # Minified JSON for zero-spike efficiency
                json.dump(web_dict, f, separators=(',', ':'))
            # Retry loop handles transient Windows file locks (WinError 5) from concurrent readers
            for attempt in range(3):
                try:
                    os.replace(temp_file, self.live_state_file)
                    break
                except OSError:
                    if attempt < 2:
                        _time.sleep(0.05)
                    else:
                        raise
        except Exception as e:
            if os.path.exists(temp_file):
                try: os.remove(temp_file)
                except: pass
            raise e

    async def log_tail_loop(self, interval: int = 2):
        """High-frequency background loop for log broadcasting (Zero-Drift)"""
        logger.info_system(f"Log Broadcaster engine started (Interval: {interval}s)")
        while True:
            try:
                await self.broadcaster.tail_logs()
            except Exception as e:
                logger.error_system(f"Log tail loop error: {e}")
            await asyncio.sleep(interval)

    async def telemetry_loop(self, interval: int = 10):
        """Background loop for continuous telemetry collection"""
        logger.info_system(f"Telemetry Collector started (Echo Interval: {interval}s)")
        
        # Immediate first echo to clear stale data and publish current state
        await self.collect_echo()
        
        while True:
            await self.collect_echo()
            await asyncio.sleep(interval)
