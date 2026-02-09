import asyncio
import datetime
import os
import subprocess
import tempfile
import discord
import psutil
import json
import time
import threading
import urllib.request
import urllib.error
from .log_manager import logger, LOG_PATH, execute_steamcmd_simple
from .server_manager import ServerManager
from .rcon_manager import RCONManager
from .discord_manager import DiscordManager
from .version_manager import VersionManager
from .config import ConfigManager
from .exceptions import RCONConnectionError, RCONCommandError
import urllib.parse


class SystemMonitoringHandler:
    """Handles system monitoring commands: status, diagnose, check, report"""
    
    def __init__(
        self,
        server_manager: ServerManager,
        rcon_manager: RCONManager,
        discord_manager: DiscordManager,
        version_manager: VersionManager,
        config_manager: ConfigManager,
        backup_manager,
        player_manager,
        schedule_manager,
        raptorchat_manager
    ):
        self.server_manager = server_manager
        self.rcon_manager = rcon_manager
        self.discord_manager = discord_manager
        self.version_manager = version_manager
        self.config_manager = config_manager
        self.backup_manager = backup_manager
        self.player_manager = player_manager
        self.schedule_manager = schedule_manager
        self.raptorchat_manager = raptorchat_manager
        
        # Performance tracking initialization
        self.performance_history_file = os.path.join(LOG_PATH, "performance_history.json")
        self.performance_history = self._load_performance_history()
        self.bot_start_time = datetime.datetime.now()

    async def _check_configuration(self):
        """Perform configuration checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            required_keys = ["bot_token", "channel_id", "app_id", "steamcmd_path", 
                           "server_dir", "cluster_servers", "rcon_tool"]
            missing_keys = [key for key in required_keys if not self.config_manager.get(key)]
            
            invalid_servers = []
            for server in self.server_manager.servers:
                if not server.rcon_ip or not server.rcon_port or not server.rcon_password:
                    invalid_servers.append(server.name)
            
            if missing_keys or invalid_servers:
                config_issues = []
                if missing_keys:
                    config_issues.append(f"Missing config keys: {', '.join(missing_keys)}")
                if invalid_servers:
                    config_issues.append(f"Invalid RCON config for servers: {', '.join(invalid_servers)}")
                
                issues.append(f"Configuration check failed - {' | '.join(config_issues)}")
                check_results.append("❌ Configuration")
            else:
                check_results.append("✅ Configuration")
        except Exception as e:
            issues.append(f"Configuration check failed - Unable to validate config file: {e}")
            check_results.append("❌ Configuration")
        return issues, check_results

    async def _check_server_monitoring(self):
        """Perform server monitoring checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            # Check if we can detect processes and get system resources
            expected_servers = len(self.server_manager.servers)
            running_count = sum(1 for server in self.server_manager.servers 
                               if self.server_manager.is_specific_server_running(server))
            
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent(interval=0.1)
            
            monitoring_issues = []
            if running_count == 0 and expected_servers > 0:
                monitoring_issues.append("No ARK server processes detected")
            elif running_count != expected_servers:
                monitoring_issues.append(f"Only {running_count}/{expected_servers} servers running")
            
            if memory.percent > 95:
                monitoring_issues.append(f"Critical memory usage: {memory.percent}%")
            
            if monitoring_issues:
                issues.append(f"Server Monitoring check failed - {' | '.join(monitoring_issues)}")
                check_results.append("❌ Server Monitoring")
            else:
                check_results.append("✅ Server Monitoring")
        except Exception as e:
            issues.append(f"Server Monitoring check failed - Cannot access system resources: {e}")
            check_results.append("❌ Server Monitoring")
        return issues, check_results

    async def _check_rcon(self):
        """Perform RCON connectivity checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            rcon_failures = []
            for server in self.server_manager.servers:
                try:
                    await self.rcon_manager.execute_for_server(server, "GetGameLog")
                except (RCONConnectionError, RCONCommandError) as e:
                    rcon_failures.append(f"{server.name}: {e.reason}")
            
            if rcon_failures:
                issues.append(f"RCON check failed: {' | '.join(rcon_failures)}")
                check_results.append("❌ RCON Connectivity")
            else:
                check_results.append("✅ RCON Connectivity")
        except Exception as e:
            issues.append(f"RCON check failed: {e}")
            check_results.append("❌ RCON Connectivity")
        return issues, check_results

    async def _check_server_updates(self):
        """Perform server update component checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            steamcmd_path = self.config_manager.get("steamcmd_path")
            server_dir = self.config_manager.get("server_dir")
            
            update_issues = []
            if not steamcmd_path or not os.path.exists(steamcmd_path):
                update_issues.append("SteamCMD not found")
            else:
                # Quick test if SteamCMD is executable
                test_cmd_args = [steamcmd_path, "+quit"]
                result = await execute_steamcmd_simple(test_cmd_args)
                
                if result.returncode != 0:
                    update_issues.append("SteamCMD not functional")
            
            if not server_dir or not os.path.exists(server_dir):
                update_issues.append("Server directory not found")
            elif not os.access(server_dir, os.W_OK):
                update_issues.append("Server directory not writable")
            
            if update_issues:
                issues.append(f"Server Updates check failed - {' | '.join(update_issues)}")
                check_results.append("❌ Server Updates")
            else:
                check_results.append("✅ Server Updates")
        except Exception as e:
            issues.append(f"Server Updates check failed - Cannot validate update components: {e}")
            check_results.append("❌ Server Updates")
        return issues, check_results

    async def _check_player_management(self):
        """Perform player management checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            player_issues = []
            inaccessible_logs = []
            
            for server in self.server_manager.servers:
                if server.server_log_path:
                    if not os.path.exists(server.server_log_path):
                        inaccessible_logs.append(f"{server.name} (not found)")
                    else:
                        try:
                            with open(server.server_log_path, 'r', encoding='utf-8') as f:
                                f.read(1)
                        except Exception:
                            inaccessible_logs.append(f"{server.name} (read error)")
            
            if inaccessible_logs:
                player_issues.append(f"Log files inaccessible: {', '.join(inaccessible_logs)}")
            
            if not hasattr(self, 'player_manager') or not self.player_manager:
                player_issues.append("Player manager not initialized")
            
            if player_issues:
                issues.append(f"Player Management check failed - {' | '.join(player_issues)}")
                check_results.append("❌ Player Management")
            else:
                check_results.append("✅ Player Management")
        except Exception as e:
            issues.append(f"Player Management check failed - Cannot validate player tracking: {e}")
            check_results.append("❌ Player Management")
        return issues, check_results

    async def _check_backup_system(self):
        """Perform backup system checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            backup_issues = []
            backup_path = self.backup_manager.backup_path
            
            if not os.path.exists(backup_path):
                backup_issues.append(f"Backup directory does not exist (checked: {backup_path})")
            elif not os.access(backup_path, os.W_OK):
                backup_issues.append("Backup directory not writable")
            
            save_path_issues = []
            for server in self.server_manager.servers:
                if server.server_save_path:
                    if not os.path.exists(server.server_save_path):
                        save_path_issues.append(f"{server.name} save path not found")
                    elif not os.access(server.server_save_path, os.W_OK):
                        save_path_issues.append(f"{server.name} save path not writable")
            
            if save_path_issues:
                backup_issues.extend(save_path_issues)
            
            if backup_issues:
                issues.append(f"Backup System check failed - {' | '.join(backup_issues)}")
                check_results.append("❌ Backup System")
            else:
                check_results.append("✅ Backup System")
        except Exception as e:
            issues.append(f"Backup System check failed - Cannot validate backup system: {e}")
            check_results.append("❌ Backup System")
        return issues, check_results

    async def _check_scheduling(self):
        """Perform scheduling system checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            schedule_issues = []
            
            if not hasattr(self, 'schedule_manager') or not self.schedule_manager:
                schedule_issues.append("Schedule manager not initialized")
            else:
                # Test if we can access schedule data
                try:
                    schedules = self.schedule_manager.get_events()
                    # Basic validation that schedules are accessible
                except Exception as e:
                    schedule_issues.append(f"Cannot access schedule data: {e}")
            
            if schedule_issues:
                issues.append(f"Scheduling check failed - {' | '.join(schedule_issues)}")
                check_results.append("❌ Scheduling")
            else:
                check_results.append("✅ Scheduling")
        except Exception as e:
            issues.append(f"Scheduling check failed - Cannot validate scheduling system: {e}")
            check_results.append("❌ Scheduling")
        return issues, check_results

    async def _check_advanced_settings(self):
        """Perform advanced settings checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            advanced_issues = []
            
            # Check Discord webhook functionality
            webhook_url = self.config_manager.get("discord_webhook")
            if webhook_url:
                # Basic webhook URL validation
                if not webhook_url.startswith(("http://", "https://")):
                    advanced_issues.append("Invalid webhook URL format")
            
            # Check web panel configuration
            webpanel_path = self.config_manager.get("webpanel_path")
            if webpanel_path and not os.path.exists(webpanel_path):
                advanced_issues.append("Web panel executable not found")
            
            if advanced_issues:
                issues.append(f"Advanced Settings check failed - {' | '.join(advanced_issues)}")
            # Check History Engine (.nerd) status - removed from diagnose output as requested
            # if self.history_loop_task and not self.history_loop_task.done():
            #     check_results.append("✅ History Engine (Active)")
            # else:
            #     issues.append("History Engine loop is not running")
            #     check_results.append("❌ History Engine (Stopped)")
        except Exception as e:
            issues.append(f"Advanced Settings check failed - Cannot validate advanced settings: {e}")
            check_results.append("❌ Advanced Settings")
        return issues, check_results

    async def _check_raptorchat(self):
        """Perform RaptorChat checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            raptorchat_issues = []
            
            if not hasattr(self, 'raptorchat_manager') or not self.raptorchat_manager:
                raptorchat_issues.append("RaptorChat manager not initialized")
            else:
                # Check if RaptorChat files exist
                if not os.path.exists(self.raptorchat_manager.raptorchat_path):
                    raptorchat_issues.append("RaptorChat executable not found")
                
                # Check if RaptorChat is running
                try:
                    if hasattr(self.raptorchat_manager, 'is_running'):
                        self.raptorchat_manager.is_running()
                        # Note: We don't fail if it's not running, just checking accessibility
                except Exception:
                    raptorchat_issues.append("Cannot check RaptorChat status")
            
            if raptorchat_issues:
                issues.append(f"RaptorChat check failed - {' | '.join(raptorchat_issues)}")
                check_results.append("❌ RaptorChat")
            else:
                check_results.append("✅ RaptorChat")
        except Exception as e:
            issues.append(f"RaptorChat check failed - Cannot validate RaptorChat system: {e}")
            check_results.append("❌ RaptorChat")
        return issues, check_results

    async def _check_performance(self):
        """Perform performance stress tests for the diagnose command."""
        issues = []
        check_results = []
        try:
            stress_issues = []
            stress_results = []
            
            # CPU Stress Test (brief)
            try:
                start_time = time.time()
                # Perform a brief CPU-intensive calculation
                for _ in range(100000):
                    _ = sum(i * i for i in range(100))
                cpu_test_time = time.time() - start_time
                
                if cpu_test_time > 1.0:  # More than 1 second is concerning
                    stress_issues.append(f"CPU performance degraded: {cpu_test_time:.3f}s")
                    stress_results.append("❌ CPU Stress")
                else:
                    stress_results.append("✅ CPU Stress")
            except Exception as e:
                stress_issues.append(f"CPU stress test failed: {e}")
                stress_results.append("❌ CPU Stress")
            
            # Memory Stress Test
            try:
                start_time = time.time()
                # Test memory allocation and deallocation
                test_data = [i for i in range(100000)]  # Allocate memory
                _ = sum(test_data)  # Use the data
                del test_data  # Deallocate
                memory_test_time = time.time() - start_time
                
                if memory_test_time > 0.3:  # More than 0.3 seconds is concerning
                    stress_issues.append(f"Memory performance degraded: {memory_test_time:.3f}s")
                    stress_results.append("❌ Memory Stress")
                else:
                    stress_results.append("✅ Memory Stress")
            except Exception as e:
                stress_issues.append(f"Memory stress test failed: {e}")
                stress_results.append("❌ Memory Stress")
            
            # Disk I/O Stress Test
            try:
                start_time = time.time()
                # Test disk write speed
                with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                    test_data = "x" * (1024 * 1024)  # 1MB of data
                    tmp_file.write(test_data.encode())
                    tmp_file.flush()
                    tmp_file_path = tmp_file.name
                
                # Test disk read speed
                with open(tmp_file_path, 'r') as tmp_file:
                    _ = tmp_file.read()
                
                os.unlink(tmp_file_path)  # Clean up
                disk_test_time = time.time() - start_time
                
                if disk_test_time > 1.0:  # More than 1 second is concerning
                    stress_issues.append(f"Disk I/O performance degraded: {disk_test_time:.3f}s")
                    stress_results.append("❌ Disk I/O Stress")
                else:
                    stress_results.append("✅ Disk I/O Stress")
            except Exception as e:
                stress_issues.append(f"Disk I/O stress test failed: {e}")
                stress_results.append("❌ Disk I/O Stress")
            
            if stress_issues:
                issues.extend(stress_issues)
            check_results.extend(stress_results)
        except Exception as e:
            issues.append(f"Performance stress test failed: {e}")
            check_results.append("❌ Test failed")
        return issues, check_results

    async def _check_network(self):
        """Perform network connectivity checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            network_issues = []
            network_results = []
            
            # Internet Connectivity Test
            try:
                result = subprocess.run(['ping', '-n', '1', '8.8.8.8'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    network_results.append("✅ Internet")
                else:
                    network_issues.append("Cannot reach Google DNS (8.8.8.8)")
                    network_results.append("❌ Internet")
            except Exception as e:
                network_issues.append(f"Internet connectivity test failed: {e}")
                network_results.append("❌ Internet")
            
            # Steam API Connectivity Test
            try:
                start_time = time.time()
                try:
                    with urllib.request.urlopen('https://api.steampowered.com/ISteamApps/GetAppList/v2/', timeout=10) as response:
                        if response.status == 200:
                            network_results.append("✅ Steam API")
                        else:
                            network_issues.append(f"Steam API returned status {response.status}")
                            network_results.append("❌ Steam API")
                except urllib.error.URLError as e:
                    network_issues.append(f"Cannot reach Steam API: {e}")
                    network_results.append("❌ Steam API")
                
                steam_response_time = time.time() - start_time
                if steam_response_time > 5.0:  # More than 5 seconds is concerning
                    network_issues.append(f"Steam API response slow: {steam_response_time:.1f}s")
            except Exception as e:
                network_issues.append(f"Steam API connectivity test failed: {e}")
                network_results.append("❌ Steam API")
            
            # Discord Connectivity Test - Skipped (command is running via Discord, so it's obviously working)
            network_results.append("✅ Discord (Skipped test)")
            
            if network_issues:
                issues.extend(network_issues)
            check_results.extend(network_results)
        except Exception as e:
            issues.append(f"Network connectivity test failed: {e}")
            check_results.append("❌ Test failed")
        return issues, check_results

    async def _check_filesystem(self):
        """Perform file system integrity checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            fs_issues = []
            fs_results = []
            
            # Config File Access Test
            try:
                config_path = self.config_manager.config_file if hasattr(self.config_manager, 'config_file') else 'config.json'
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        _ = f.read()  # Try to read
                    fs_results.append("✅ Config File")
                else:
                    fs_issues.append("Config file not found")
                    fs_results.append("❌ Config File")
            except Exception as e:
                fs_issues.append(f"Config file access failed: {e}")
                fs_results.append("❌ Config File")
            
            # Log Directory Write Test
            try:
                test_log_path = os.path.join(LOG_PATH, "diagnose_test.log")
                with open(test_log_path, 'w') as f:
                    f.write("Diagnose test - safe to delete")
                
                # Verify we can read it back
                with open(test_log_path, 'r') as f:
                    content = f.read()
                
                if "Diagnose test" in content:
                    fs_results.append("✅ Log Directory")
                    os.unlink(test_log_path)  # Clean up
                else:
                    fs_issues.append("Log directory write verification failed")
                    fs_results.append("❌ Log Directory")
            except Exception as e:
                fs_issues.append(f"Log directory write test failed: {e}")
                fs_results.append("❌ Log Directory")
            
            # Server Directory Access Test
            try:
                server_dir = self.config_manager.get("server_dir", ".")
                if os.path.exists(server_dir):
                    # Test if we can list contents
                    _ = os.listdir(server_dir)
                    fs_results.append("✅ Server Directory")
                else:
                    fs_issues.append("Server directory not found")
                    fs_results.append("❌ Server Directory")
            except Exception as e:
                fs_issues.append(f"Server directory access failed: {e}")
                fs_results.append("❌ Server Directory")
            
            if fs_issues:
                issues.extend(fs_issues)
            check_results.extend(fs_results)
        except Exception as e:
            issues.append(f"File system integrity test failed: {e}")
            check_results.append("❌ Test failed")
        return issues, check_results

    async def _check_bot_health(self):
        """Perform bot self-health checks for the diagnose command."""
        issues = []
        check_results = []
        try:
            health_issues = []
            health_results = []
            
            # Memory Usage Test
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024
                
                if memory_mb > 1000:  # More than 1GB is concerning
                    health_issues.append(f"High memory usage: {memory_mb:.1f} MB")
                    health_results.append("❌ Memory Usage")
                else:
                    health_results.append(f"✅ Memory Usage ({memory_mb:.1f} MB)")
            except Exception as e:
                health_issues.append(f"Memory usage test failed: {e}")
                health_results.append("❌ Memory Usage")
            
            # Thread Count Test
            try:
                process = psutil.Process()
                thread_count = process.num_threads()
                
                if thread_count > 50:  # More than 50 threads might indicate thread leaks
                    health_issues.append(f"High thread count: {thread_count}")
                    health_results.append("❌ Thread Count")
                else:
                    health_results.append(f"✅ Thread Count ({thread_count})")
            except Exception as e:
                health_issues.append(f"Thread count test failed: {e}")
                health_results.append("❌ Thread Count")
            
            if health_issues:
                issues.extend(health_issues)
            check_results.extend(health_results)
        except Exception as e:
            issues.append(f"Bot self-health test failed: {e}")
            check_results.append("❌ Test failed")
        return issues, check_results
    
    def _load_performance_history(self):
        """Load historical performance data"""
        try:
            if os.path.exists(self.performance_history_file):
                with open(self.performance_history_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.debug_system(f"Could not load performance history: {e}")
        
        # Initialize with empty structure
        return {
            "system_metrics": [],
            "rcon_response_times": [],
            "memory_usage": [],
            "disk_usage": [],
            "cpu_usage": []
        }
    
    def _save_performance_history(self):
        """Save historical performance data"""
        try:
            with open(self.performance_history_file, 'w') as f:
                json.dump(self.performance_history, f, indent=2)
        except Exception as e:
            logger.debug_system(f"Could not save performance history: {e}")
    
    async def _collect_performance_metrics(self):
        """Collect current performance metrics and store in history"""
        timestamp = datetime.datetime.now().isoformat()
        
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.config_manager.get("server_dir", "."))
        
        system_metrics = {
            "timestamp": timestamp,
            "memory_percent": memory.percent,
            "disk_percent": disk.used / disk.total * 100,
            "cpu_percent": psutil.cpu_percent(interval=0.1)
        }
        
        # RCON response times (if servers are running)
        rcon_times = []
        if self.server_manager.servers:
            for server in self.server_manager.servers[:3]:  # Test first 3 servers
                try:
                    start_time = time.time()
                    await self.rcon_manager.execute_for_server(server, "GetVersion")
                    end_time = time.time()
                    rcon_times.append({
                        "timestamp": timestamp,
                        "server": server.name,
                        "response_time": (end_time - start_time) * 1000  # ms
                    })
                except Exception:
                    pass  # Skip if RCON fails
        
        # Store in history (keep last 100 entries)
        self.performance_history["system_metrics"].append(system_metrics)
        self.performance_history["rcon_response_times"].extend(rcon_times)
        
        # Trim history to last 100 entries
        for key in self.performance_history:
            if len(self.performance_history[key]) > 100:
                self.performance_history[key] = self.performance_history[key][-100:]
        
        self._save_performance_history()
    
    def _analyze_performance_trends(self):
        """Analyze performance trends and detect regressions"""
        trends = {
            "memory_trend": "stable",
            "disk_trend": "stable", 
            "cpu_trend": "stable",
            "rcon_trend": "stable",
            "issues": []
        }
        
        try:
            # Analyze memory trend (last 24 hours vs previous 24 hours)
            system_metrics = self.performance_history["system_metrics"]
            if len(system_metrics) >= 48:  # Need at least 48 data points (assuming hourly)
                recent_24h = system_metrics[-24:]
                previous_24h = system_metrics[-48:-24]
                
                recent_avg_memory = sum(m["memory_percent"] for m in recent_24h) / len(recent_24h)
                previous_avg_memory = sum(m["memory_percent"] for m in previous_24h) / len(previous_24h)
                
                memory_change = recent_avg_memory - previous_avg_memory
                if memory_change > 10:  # More than 10% increase
                    trends["memory_trend"] = "increasing"
                    trends["issues"].append(f"Memory usage increased by {memory_change:.1f}% over 24h")
                elif memory_change < -5:
                    trends["memory_trend"] = "decreasing"
            
            # Analyze disk trend
            recent_avg_disk = sum(m["disk_percent"] for m in recent_24h) / len(recent_24h)
            previous_avg_disk = sum(m["disk_percent"] for m in previous_24h) / len(previous_24h)
            
            disk_change = recent_avg_disk - previous_avg_disk
            if disk_change > 5:  # More than 5% increase
                trends["disk_trend"] = "increasing"
                trends["issues"].append(f"Disk usage increased by {disk_change:.1f}% over 24h")
            
            # Analyze CPU trend
            recent_avg_cpu = sum(m["cpu_percent"] for m in recent_24h) / len(recent_24h)
            previous_avg_cpu = sum(m["cpu_percent"] for m in previous_24h) / len(previous_24h)
            
            cpu_change = recent_avg_cpu - previous_avg_cpu
            if cpu_change > 20:  # More than 20% increase
                trends["cpu_trend"] = "increasing"
                trends["issues"].append(f"CPU usage increased by {cpu_change:.1f}% over 24h")
            
            # Analyze RCON response times
            rcon_times = self.performance_history["rcon_response_times"]
            if len(rcon_times) >= 20:
                recent_rcon = [rt for rt in rcon_times if rt["timestamp"] > system_metrics[-12]["timestamp"]]
                previous_rcon = [rt for rt in rcon_times if system_metrics[-24]["timestamp"] < rt["timestamp"] < system_metrics[-12]["timestamp"]]
                
                if recent_rcon and previous_rcon:
                    recent_avg_rcon = sum(rt["response_time"] for rt in recent_rcon) / len(recent_rcon)
                    previous_avg_rcon = sum(rt["response_time"] for rt in previous_rcon) / len(previous_rcon)
                    
                    rcon_change = recent_avg_rcon - previous_avg_rcon
                    if rcon_change > 50:  # More than 50ms increase
                        trends["rcon_trend"] = "degrading"
                        trends["issues"].append(f"RCON response time increased by {rcon_change:.1f}ms")
        
        except Exception as e:
            logger.debug_system(f"Performance trend analysis failed: {e}")
            trends["issues"].append("Could not analyze performance trends")
        
        return trends

    async def cmd_status(self, message, content: str, content_lower: str):
        """Handle .status command - show system and server status"""
        logger.info_command(".status received")
        
        logger.debug_system("Gathering system status data...")
        
        # Check server status
        logger.debug_system("Checking ARK server process status...")
        proc = self.server_manager.is_server_running()
        
        # Get PC uptime
        logger.debug_system("Calculating PC uptime...")
        pc_uptime_seconds = int(datetime.datetime.now().timestamp() - psutil.boot_time())
        pc_uptime = str(datetime.timedelta(seconds=pc_uptime_seconds))
        logger.debug_system(f"PC uptime: {pc_uptime}")

        # Get memory usage
        logger.debug_system("Gathering memory usage data...")
        mem_info = psutil.virtual_memory()
        ram_used = mem_info.used / (1024 * 1024 * 1024)
        ram_total = mem_info.total / (1024 * 1024 * 1024)
        logger.debug_system(f"Memory: {ram_used:.2f}/{ram_total:.2f} GB")

        # Get disk usage
        logger.debug_system("Gathering disk usage data...")
        server_dir = self.config_manager.get("server_dir") or "."
        disk_info = psutil.disk_usage(server_dir)
        disk_used = disk_info.used / (1024 * 1024 * 1024)
        disk_total = disk_info.total / (1024 * 1024 * 1024)
        logger.debug_system(f"Disk: {disk_used:.2f}/{disk_total:.2f} GB")

        if proc:
            logger.debug_system("Server is running, gathering CPU usage...")
            # Use system-wide CPU usage for consistency with RAM/Disk
            cpu = psutil.cpu_percent(interval=1)
            logger.debug_system(f"System CPU usage: {cpu:.1f}%")
            msg = (
                f"🟢 Server Status : RUNNING\n"
                f"🔌 PC Uptime     : {pc_uptime}\n"
                f"💻 System CPU    : {cpu:.1f}%\n"
                f"⚡ Memory Usage  : {ram_used:.2f}/{ram_total:.2f} GB\n"
                f"💽 Disk Usage    : {disk_used:.2f}/{disk_total:.2f} GB"
            )
        else:
            msg = (
                "🔴 Server Status : OFFLINE\n"
                f"🔌 PC Uptime     : {pc_uptime}\n"
                f"⚡ Memory Usage  : {ram_used:.2f}/{ram_total:.2f} GB\n"
                f"💽 Disk Usage    : {disk_used:.2f}/{disk_total:.2f} GB"
            )
        await self.discord_manager.send_temp_message(message.channel, msg)

    async def cmd_diagnose(self, message, content: str, content_lower: str):
        """Handle .diagnose command - perform bot health check"""
        logger.info_command(".diagnose received")
        import os  # Ensure os module is available
        embed = discord.Embed(title="Bot Health Diagnostic", color=0x99AAB5)
        
        issues = []
        warnings = []
        check_results = []
        
        # Configuration
        config_issues, config_results = await self._check_configuration()
        issues.extend(config_issues)
        check_results.extend(config_results)
        
        # Server Monitoring
        monitoring_issues, monitoring_results = await self._check_server_monitoring()
        issues.extend(monitoring_issues)
        check_results.extend(monitoring_results)
        
        # RCON Connectivity
        rcon_issues, rcon_results = await self._check_rcon()
        issues.extend(rcon_issues)
        check_results.extend(rcon_results)
        
        # Server Updates
        update_issues, update_results = await self._check_server_updates()
        issues.extend(update_issues)
        check_results.extend(update_results)
        
        # Player Management
        player_issues, player_results = await self._check_player_management()
        issues.extend(player_issues)
        check_results.extend(player_results)
        
        # Backup System
        backup_issues, backup_results = await self._check_backup_system()
        issues.extend(backup_issues)
        check_results.extend(backup_results)
        
        # Scheduling
        schedule_issues, schedule_results = await self._check_scheduling()
        issues.extend(schedule_issues)
        check_results.extend(schedule_results)
        
        # Advanced Settings
        advanced_issues, advanced_results = await self._check_advanced_settings()
        issues.extend(advanced_issues)
        check_results.extend(advanced_results)
        
        # RaptorChat
        raptorchat_issues, raptorchat_results = await self._check_raptorchat()
        issues.extend(raptorchat_issues)
        check_results.extend(raptorchat_results)
        
        # Consolidate standard checks into one field to save space
        # Results are consolidated below in 'Health Check Results'


        # Skip heavy performance/network/filesystem stress tests for the standard diagnose command
        # to ensure it returns quickly and doesn't spam the chat.
        # These can be accepted via a ".diagnose full" flag if needed in the future.

        
        # Performance Trends Analysis
        # Removed as per user request (moved to .nerd command)
        # See _analyze_performance_trends for logic if needed later
        
        # Create the embed
        embed.add_field(name="Health Check Results", value="\n".join(check_results), inline=False)
        
        if issues:
            embed.add_field(name="Issues Found", value="\n".join(f"• {issue}" for issue in issues), inline=False)
        else:
            embed.add_field(name="Status", value="✅ All systems operational", inline=False)
        
        # Use default grey color (no color set) to match other embeds
        
        if warnings:
            embed.add_field(name="Warnings", value="\n".join(f"⚠️ {warning}" for warning in warnings), inline=False)
        
        await message.channel.send(embed=embed)

    async def cmd_check(self, message, content: str, content_lower: str):
        """Handle .check command - check for updates"""
        logger.info_command(".check received")
        try:
            current = self.version_manager.get_current_version()
            latest = await self.version_manager.get_latest_build_id()
            
            if not latest:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ Unable to fetch latest version from Steam.")
                return
            
            if current == latest:
                await self.discord_manager.send_temp_message(message.channel, f"✅ Server is up to date (Build {current})")
            else:
                await self.discord_manager.send_temp_message(message.channel, f"🔄 Update available: Build {current} → {latest}")
        except Exception as e:
            await self.discord_manager.send_temp_message(message.channel, f"❌ Failed to check for updates: {e}")
    
    async def cmd_debug(self, message, content: str, content_lower: str):
        """Handle .debug command - toggle debug logging"""
        logger.info_command(".debug received")
        new_state = logger.toggle_debug()
        status = "ON ✅" if new_state else "OFF ❌"
        await self.discord_manager.send_temp_message(message.channel, f"🐛 Debug logging is now **{status}**")
        
        # Log a test debug message to demonstrate the toggle
        if new_state:
            logger.debug_system("Debug logging enabled - test message")

    async def start_monitoring_tasks(self):
        """Start background monitoring tasks - Removed as per user request"""
        pass

    async def _collect_history_loop(self):
        """Background loop to collect validation metrics - Removed as per user request"""
        pass

    async def cmd_nerd(self, message, content: str, content_lower: str):
         """Handle .nerd command - Removed as per user request"""
         await self.discord_manager.send_temp_message(message.channel, "Command removed.")

    async def cmd_report(self, message, content: str, content_lower: str):
        """Handle .report command - generate status report"""
        logger.info_command(".report received")
        
        try:
            # Get all patchraptor log files
            log_files = []
            for file in os.listdir(LOG_PATH):
                if file.startswith('patchraptor_') and file.endswith('.log'):
                    log_files.append(os.path.join(LOG_PATH, file))
            
            if not log_files:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ No log files found.")
                return
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
            
            # Read the last 50 lines from each log file
            all_lines = []
            for log_file in log_files[:3]:  # Limit to 3 most recent files
                try:
                    with open(log_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        all_lines.extend(lines[-50:])  # Last 50 lines
                except Exception as e:
                    logger.error_system(f"Failed to read log file {log_file}: {e}")
                    continue
            
            if not all_lines:
                await self.discord_manager.send_temp_message(message.channel, "⚠️ No log content found.")
                return
            
            # Create report content
            report_content = "".join(all_lines)
            
            # Try to upload as file first
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as temp_file:
                    temp_file.write(report_content)
                    temp_file_path = temp_file.name
                
                await message.channel.send(
                    content="📋 **PatchRaptor Log Report**",
                    file=discord.File(temp_file_path, filename='patchraptor_report.log')
                )
                os.unlink(temp_file_path)
                
            except discord.Forbidden:
                # If file upload is forbidden, send as text chunks
                await message.channel.send("📋 **PatchRaptor Log Report**")
                
                # Split into chunks of 1900 characters to stay under Discord limits
                chunk_size = 1900
                log_chunks = [report_content[i:i+chunk_size] for i in range(0, len(report_content), chunk_size)]
                
                for i, chunk in enumerate(log_chunks):
                    if i > 0:  # Add delay between chunks to avoid rate limiting
                        await asyncio.sleep(0.5)
                    
                    chunk_msg = f"```\n{chunk}```"
                    await message.channel.send(chunk_msg)
        
        except FileNotFoundError:
            await self.discord_manager.send_temp_message(message.channel, "⚠️ Log file not found.")
        except Exception as e:
            logger.error_system(f"Failed to generate report: {e}")
            await self.discord_manager.send_temp_message(
                message.channel, f"❌ Failed to generate report: {e}"
            )
