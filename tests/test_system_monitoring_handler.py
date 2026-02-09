import pytest
import asyncio
import psutil
import discord
import urllib.error
from unittest.mock import Mock, MagicMock, patch, AsyncMock, mock_open
from patchraptor.system_monitoring_handler import SystemMonitoringHandler

@pytest.fixture
def mock_deps():
    deps = {
        "server_manager": Mock(),
        "rcon_manager": Mock(),
        "discord_manager": Mock(),
        "version_manager": Mock(),
        "config_manager": Mock(),
        "backup_manager": Mock(),
        "player_manager": Mock(),
        "schedule_manager": Mock(),
        "raptorchat_manager": Mock(),
    }
    
    # Default mock behaviors
    deps["discord_manager"].send_temp_message = AsyncMock()
    deps["version_manager"].get_latest_build_id = AsyncMock()
    deps["server_manager"].servers = []
    deps["config_manager"].get.return_value = "some_value"
    return deps

@pytest.fixture
def handler(mock_deps):
    default_history = {
        "system_metrics": [],
        "rcon_response_times": [],
        "memory_usage": [],
        "disk_usage": [],
        "cpu_usage": []
    }
    with patch("patchraptor.system_monitoring_handler.SystemMonitoringHandler._load_performance_history", return_value=default_history):
        h = SystemMonitoringHandler(
            mock_deps["server_manager"],
            mock_deps["rcon_manager"],
            mock_deps["discord_manager"],
            mock_deps["version_manager"],
            mock_deps["config_manager"],
            mock_deps["backup_manager"],
            mock_deps["player_manager"],
            mock_deps["schedule_manager"],
            mock_deps["raptorchat_manager"]
        )
        return h

@pytest.fixture
def mock_message():
    message = AsyncMock()
    message.channel = Mock()
    message.channel.send = AsyncMock()
    return message

class TestSystemMonitoringHandler:

    @pytest.mark.asyncio
    async def test_cmd_status_offline(self, handler, mock_message, mock_deps):
        """Test .status when server is offline"""
        mock_deps["server_manager"].is_server_running.return_value = False
        
        # Mock psutil
        with patch("psutil.boot_time", return_value=100000), \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.disk_usage") as mock_disk, \
             patch("datetime.datetime") as mock_dt:
            
            # Setup mock returns
            mock_mem.return_value = MagicMock(used=1024**3, total=8*1024**3)
            mock_disk.return_value = MagicMock(used=50*1024**3, total=500*1024**3)
            # Mock datetime.now() to control uptime calc
            mock_dt.now.return_value.timestamp.return_value = 103600 # 3600s uptime
            
            await handler.cmd_status(mock_message, ".status", ".status")
            
            mock_deps["discord_manager"].send_temp_message.assert_called()
            args, _ = mock_deps["discord_manager"].send_temp_message.call_args
            msg = args[1]
            assert "OFFLINE" in msg
            assert "1.00/8.00 GB" in msg # RAM check

    @pytest.mark.asyncio
    async def test_cmd_status_online(self, handler, mock_message, mock_deps):
        """Test .status when server is online"""
        mock_deps["server_manager"].is_server_running.return_value = True
        
        # Mock psutil
        with patch("psutil.boot_time", return_value=100000), \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.cpu_percent", return_value=15.5), \
             patch("datetime.datetime") as mock_dt:
            
            mock_mem.return_value = MagicMock(used=1024**3, total=8*1024**3)
            mock_disk.return_value = MagicMock(used=50*1024**3, total=500*1024**3)
            mock_dt.now.return_value.timestamp.return_value = 103600
            
            await handler.cmd_status(mock_message, ".status", ".status")
            
            mock_deps["discord_manager"].send_temp_message.assert_called()
            args, _ = mock_deps["discord_manager"].send_temp_message.call_args
            msg = args[1]
            assert "RUNNING" in msg
            assert "15.5%" in msg

    @pytest.mark.asyncio
    async def test_cmd_diagnose_healthy(self, handler, mock_message, mock_deps):
        """Test .diagnose with full health (happy path)"""
        # Mock all sub-check methods to return clean results
        # This isolates the orchestration logic
        
        with patch.object(handler, '_check_configuration', return_value=([], ["✅ Config"])), \
             patch.object(handler, '_check_server_monitoring', return_value=([], ["✅ Monitor"])), \
             patch.object(handler, '_check_rcon', return_value=([], ["✅ RCON"])), \
             patch.object(handler, '_check_server_updates', return_value=([], ["✅ Updates"])), \
             patch.object(handler, '_check_player_management', return_value=([], ["✅ Player"])), \
             patch.object(handler, '_check_backup_system', return_value=([], ["✅ Backup"])), \
             patch.object(handler, '_check_scheduling', return_value=([], ["✅ Schedule"])), \
             patch.object(handler, '_check_advanced_settings', return_value=([], ["✅ Advanced"])), \
             patch.object(handler, '_check_bot_health', return_value=([], ["✅ Bot"])), \
             patch.object(handler, '_check_performance', return_value=([], ["✅ Perf"])), \
             patch.object(handler, '_check_network', return_value=([], ["✅ Net"])), \
             patch.object(handler, '_check_filesystem', return_value=([], ["✅ FS"])), \
             patch.object(handler, '_check_raptorchat', return_value=([], ["✅ Chat"])):
             
             await handler.cmd_diagnose(mock_message, ".diagnose", ".diagnose")
             
             # Should send an embed
             assert mock_message.channel.send.called
             args, kwargs = mock_message.channel.send.call_args
             assert kwargs.get('embed') is not None
             embed = kwargs['embed']
             assert embed.title == "Bot Health Diagnostic"

    @pytest.mark.asyncio
    async def test_check_config_failure(self, handler, mock_deps):
        """Test _check_configuration with missing keys"""
        mock_deps["config_manager"].get.side_effect = lambda k: None # Return None for all keys
        
        issues, results = await handler._check_configuration()
        
        assert len(issues) > 0
        assert "Missing config keys" in issues[0]
        assert "❌ Configuration" in results

    @pytest.mark.asyncio
    async def test_check_monitor_critical(self, handler, mock_deps):
        """Test _check_server_monitoring with high memory shortage"""
        mock_deps["server_manager"].servers = [Mock()]
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        
        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value = MagicMock(percent=99.0) # Critical RAM
            
            issues, results = await handler._check_server_monitoring()
            
            assert any("Critical memory usage" in i for i in issues)
            assert "❌ Server Monitoring" in results

    @pytest.mark.asyncio
    async def test_check_rcon_failure(self, handler, mock_deps):
        """Test _check_rcon with connection error"""
        from patchraptor.exceptions import RCONConnectionError
        server = Mock(name="Server1")
        mock_deps["server_manager"].servers = [server]
        mock_deps["rcon_manager"].execute_for_server.side_effect = RCONConnectionError("Server1", "Timeout") # Fixed args
        
        issues, results = await handler._check_rcon()
        
        assert len(issues) > 0
        assert "Server1" in issues[0]
        assert "Timeout" in issues[0]
        assert "❌ RCON Connectivity" in results

    @pytest.mark.asyncio
    async def test_check_server_updates(self, handler, mock_deps):
        """Test _check_server_updates"""
        # Happy
        with patch("os.path.exists", return_value=True), \
             patch("os.access", return_value=True), \
             patch("patchraptor.system_monitoring_handler.execute_steamcmd_simple", new_callable=AsyncMock) as mock_exec:
             
             mock_exec.return_value.returncode = 0
             mock_deps["config_manager"].get.side_effect = lambda k: "C:/steamcmd" if k == "steamcmd_path" else "C:/servers"
             
             issues, results = await handler._check_server_updates()
             assert not issues
             assert "✅ Server Updates" in results
             
        # Failure
        mock_deps["config_manager"].get.side_effect = lambda k: None
        issues, results = await handler._check_server_updates()
        assert "SteamCMD not found" in issues[0]

    @pytest.mark.asyncio
    async def test_check_player_management(self, handler, mock_deps):
        """Test _check_player_management"""
        # Missing manager
        handler.player_manager = None
        issues, results = await handler._check_player_management()
        assert "Player manager not initialized" in issues[0]
        
        # Log file unreadable
        handler.player_manager = mock_deps["player_manager"]
        server = Mock(name="S1", server_log_path="C:/log.log")
        mock_deps["server_manager"].servers = [server]
        
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", side_effect=PermissionError):
             
             issues, results = await handler._check_player_management()
             assert "read error" in issues[0]

    @pytest.mark.asyncio
    async def test_check_backup_system(self, handler, mock_deps):
        """Test _check_backup_system"""
        # Path not exists
        mock_deps["backup_manager"].backup_path = "C:/backup"
        
        with patch("os.path.exists", return_value=False):
             issues, results = await handler._check_backup_system()
             assert "Backup directory does not exist" in issues[0]

    @pytest.mark.asyncio
    async def test_check_scheduling(self, handler):
        """Test _check_scheduling"""
        # Manager missing
        handler.schedule_manager = None
        issues, results = await handler._check_scheduling()
        assert "Schedule manager not initialized" in issues[0]

    @pytest.mark.asyncio
    async def test_check_advanced_settings(self, handler, mock_deps):
        """Test _check_advanced_settings"""
        # Bad webhook
        mock_deps["config_manager"].get.side_effect = lambda k: "ftp://webhook" if k == "discord_webhook" else None
        
        issues, results = await handler._check_advanced_settings()
        assert "Invalid webhook URL format" in issues[0]

    @pytest.mark.asyncio
    async def test_check_raptorchat(self, handler):
        """Test _check_raptorchat"""
        # Missing
        handler.raptorchat_manager = None
        issues, results = await handler._check_raptorchat()
        assert "RaptorChat manager not initialized" in issues[0]

    @pytest.mark.asyncio
    async def test_check_performance(self, handler):
        """Test _check_performance"""
        # Degraded
        with patch("time.time", side_effect=[0, 2.0, 0, 0, 0, 1.1, 0, 0, 0, 0]), \
             patch("builtins.sum", return_value=0), \
             patch("tempfile.NamedTemporaryFile"), \
             patch("os.unlink"), \
             patch("builtins.open"):
             
             # CPU degraded (diff 2.0)
             issues, results = await handler._check_performance()
             assert any("CPU performance degraded" in i for i in issues)

    @pytest.mark.asyncio
    async def test_check_network(self, handler):
        """Test _check_network"""
        # Ping fail
        with patch("subprocess.run") as mock_run, \
             patch("urllib.request.urlopen"):
             
             mock_run.return_value.returncode = 1
             issues, results = await handler._check_network()
             assert "Cannot reach Google DNS" in issues[0]

    @pytest.mark.asyncio
    async def test_check_filesystem(self, handler, mock_deps):
        """Test _check_filesystem"""
        # Config missing
        with patch("os.path.exists", return_value=False):
            issues, results = await handler._check_filesystem()
            assert "Config file not found" in issues[0]

    @pytest.mark.asyncio
    async def test_check_bot_health(self, handler):
        """Test _check_bot_health check"""
        with patch("psutil.Process") as mock_proc:
            mock_proc.return_value.memory_info.return_value.rss = 1500 * 1024 * 1024 # 1.5GB
            mock_proc.return_value.num_threads.return_value = 100
            
            issues, results = await handler._check_bot_health()
            assert "High memory usage" in issues[0]
            assert "High thread count" in issues[1]

class TestPerformanceHistory:
    @pytest.mark.asyncio
    async def test_performance_cycle(self, handler, mock_deps):
        """Test load -> collect -> save -> analyze flow"""
        # Load (Already handled by init, but we can re-call)
        
        # Collect
        mock_server = Mock(name="S1")
        mock_deps["server_manager"].servers = [mock_server]
        mock_deps["rcon_manager"].execute_for_server = AsyncMock()
        
        with patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.cpu_percent", return_value=10), \
             patch("builtins.open", mock_open()), \
             patch("json.dump") as mock_json_dump:
             
             mock_mem.return_value.percent = 50
             mock_disk.return_value.used = 100
             mock_disk.return_value.total = 1000
             
             await handler._collect_performance_metrics()
             
             # Check if history updated
             assert len(handler.performance_history["system_metrics"]) == 1
             assert handler.performance_history["system_metrics"][0]["cpu_percent"] == 10
             mock_json_dump.assert_called()

    @pytest.mark.asyncio
    async def test_analyze_trends(self, handler):
        """Test trend analysis"""
        # Setup fake history
        import datetime
        now = datetime.datetime.now()
        
        # Increasing memory trend
        handler.performance_history["system_metrics"] = []
        for i in range(50):
            t = (now - datetime.timedelta(hours=50-i)).isoformat()
            mem = 20 if i < 25 else 40 # Jump from 20 to 40
            handler.performance_history["system_metrics"].append({
                "timestamp": t,
                "memory_percent": mem,
                "disk_percent": 10,
                "cpu_percent": 10
            })
            
        trends = handler._analyze_performance_trends()
        assert trends["memory_trend"] == "increasing"
        assert len(trends["issues"]) > 0

class TestCommands:
    @pytest.mark.asyncio
    async def test_cmd_check(self, handler, mock_message, mock_deps):
        """Test .check command"""
        # Match
        mock_deps["version_manager"].get_current_version.return_value = "1.0"
        mock_deps["version_manager"].get_latest_build_id.return_value = "1.0"
        
        await handler.cmd_check(mock_message, ".check", ".check")
        mock_deps["discord_manager"].send_temp_message.assert_called()
        args = mock_deps["discord_manager"].send_temp_message.call_args[0]
        assert "up to date" in args[1]
        
        # Mismatch
        mock_deps["version_manager"].get_latest_build_id.return_value = "1.1"
        await handler.cmd_check(mock_message, ".check", ".check")
        args = mock_deps["discord_manager"].send_temp_message.call_args[0]
        assert "Update available" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_debug(self, handler, mock_message, mock_deps):
        """Test .debug command"""
        with patch("patchraptor.system_monitoring_handler.logger") as mock_log:
             mock_log.toggle_debug.return_value = True
             await handler.cmd_debug(mock_message, ".debug", ".debug")
             
             mock_deps["discord_manager"].send_temp_message.assert_called()
             args = mock_deps["discord_manager"].send_temp_message.call_args[0]
             assert "ON" in args[1]

    @pytest.mark.asyncio
    async def test_cmd_report(self, handler, mock_message):
        """Test .report command"""
        # Logs found
        with patch("os.listdir", return_value=["patchraptor_1.log"]), \
             patch("os.path.join", return_value="patchraptor_1.log"), \
             patch("os.path.getmtime", return_value=100), \
             patch("builtins.open", mock_open(read_data="Line 1\nLine 2")), \
             patch("tempfile.NamedTemporaryFile"), \
             patch("os.unlink"):
             
             await handler.cmd_report(mock_message, ".report", ".report")
             assert mock_message.channel.send.called
             
        # No logs
        with patch("os.listdir", return_value=[]):
             await handler.cmd_report(mock_message, ".report", ".report")
             handler.discord_manager.send_temp_message.assert_called_with(mock_message.channel, "⚠️ No log files found.")

    @pytest.mark.asyncio
    async def test_stubs(self, handler, mock_message):
        """Test stub methods"""
        await handler.start_monitoring_tasks()
        await handler._collect_history_loop()
        await handler.cmd_nerd(mock_message, "", "")


class TestCoverageGaps:
    @pytest.mark.asyncio
    async def test_config_invalid_servers(self, handler, mock_deps):
        """Test invalid server RCON config"""
        s1 = Mock(spec=MagicMock) # Spec ensures name attr works standardly or assign manually
        s1.name = "BadServer" 
        s1.rcon_ip = None
        s1.rcon_port = 7777
        s1.rcon_password = "pw"
        
        mock_deps["server_manager"].servers = [s1]
        
        issues, results = await handler._check_configuration()
        assert "Invalid RCON config" in issues[0]

    @pytest.mark.asyncio
    async def test_mismatched_server_counts(self, handler, mock_deps):
        """Test server count mismatch"""
        mock_deps["server_manager"].servers = [Mock(), Mock()]
        mock_deps["server_manager"].is_specific_server_running.side_effect = [True, False]
        
        issues, results = await handler._check_server_monitoring()
        assert "Only 1/2 servers running" in issues[0]
        
        # Test 0 running - CLEAR SIDE EFFECT
        mock_deps["server_manager"].is_specific_server_running.side_effect = None
        mock_deps["server_manager"].is_specific_server_running.return_value = False
        issues, results = await handler._check_server_monitoring()
        assert "No ARK server processes detected" in issues[0]

    @pytest.mark.asyncio
    async def test_unwritable_dirs(self, handler, mock_deps):
        """Test unwritable directories"""
        # Server dir unwritable
        with patch("os.path.exists", return_value=True), \
             patch("os.access", return_value=False), \
             patch("patchraptor.system_monitoring_handler.execute_steamcmd_simple") as mock_exec:
             
             mock_exec.return_value.returncode = 0
             issues, results = await handler._check_server_updates()
             assert "Server directory not writable" in issues[0]
             
        # Backup dir unwritable
        mock_deps["backup_manager"].backup_path = "C:/backup"
        with patch("os.path.exists", return_value=True), \
             patch("os.access", return_value=False):
             
             issues, results = await handler._check_backup_system()
             assert "Backup directory not writable" in issues[0]

    @pytest.mark.asyncio
    async def test_server_save_paths(self, handler, mock_deps):
        """Test server save paths validation"""
        s1 = Mock(name="S1", server_save_path="C:/save")
        s1.name = "S1"
        mock_deps["server_manager"].servers = [s1]
        mock_deps["backup_manager"].backup_path = "C:/backup"
        
        # Save path not found
        with patch("os.path.exists", side_effect=lambda p: False if "save" in p else True), \
             patch("os.access", return_value=True):
             
             issues, results = await handler._check_backup_system()
             assert "S1 save path not found" in issues[0]

    @pytest.mark.asyncio
    async def test_schedule_exception(self, handler, mock_deps):
        """Test get_events exception"""
        mock_deps["schedule_manager"].get_events.side_effect = Exception("DB Error")
        issues, results = await handler._check_scheduling()
        assert "Cannot access schedule data" in issues[0]

    @pytest.mark.asyncio
    async def test_raptorchat_checks(self, handler, mock_deps):
        """Test RC checks"""
        # Path missing
        mock_deps["raptorchat_manager"].raptorchat_path = "C:/rc.exe"
        with patch("os.path.exists", return_value=False):
            issues, results = await handler._check_raptorchat()
            assert "RaptorChat executable not found" in issues[0]
            
        # Running check exception
        with patch("os.path.exists", return_value=True):
            mock_deps["raptorchat_manager"].is_running.side_effect = Exception("Fail")
            issues, results = await handler._check_raptorchat()
            assert "Cannot check RaptorChat status" in issues[0]

    @pytest.mark.asyncio
    async def test_network_branches(self, handler):
        """Test network checks branches"""
        # Ping success
        with patch("subprocess.run") as mock_run, \
             patch("urllib.request.urlopen") as mock_url, \
             patch("time.time", side_effect=[0, 10.0]): # Slow Steam
             
             mock_run.return_value.returncode = 0
             mock_url.return_value.__enter__.return_value.status = 200
             
             issues, results = await handler._check_network()
             assert "✅ Internet" in results
             assert "Steam API response slow" in issues[0]

    @pytest.mark.asyncio
    async def test_history_loading_saving(self, handler):
        """Test real history load/save logic by bypassing fixture mock"""
        # Test save exception
        handler.performance_history_file = "/invalid/path.json"
        handler._save_performance_history() # Should catch exception and log
        
        # Test history trimming with mocked disk usage to avoid file not found
        handler.performance_history["rcon_response_times"] = [1] * 110
        
        with patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.virtual_memory"), \
             patch("psutil.cpu_percent"):
             
            mock_disk.return_value.used = 100
            mock_disk.return_value.total = 1000
            
            await handler._collect_performance_metrics()
            assert len(handler.performance_history["rcon_response_times"]) == 100

    @pytest.mark.asyncio
    async def test_rcon_trends(self, handler):
        """Test RCON trend logic"""
        handler.performance_history["rcon_response_times"] = []
        import datetime
        now = datetime.datetime.now()
        
        handler.performance_history["system_metrics"] = []
        for i in range(48):
            t = (now - datetime.timedelta(hours=48-i)).isoformat()
            handler.performance_history["system_metrics"].append({"timestamp": t, "memory_percent":0,"disk_percent":0,"cpu_percent":0})
            
        for i in range(12):
            t = (now - datetime.timedelta(hours=6-i)).isoformat() # Very recent
            handler.performance_history["rcon_response_times"].append({
                "timestamp": t, "response_time": 100
            })
            
        for i in range(12):
            t = (now - datetime.timedelta(hours=18-i)).isoformat()
            handler.performance_history["rcon_response_times"].append({
                "timestamp": t, "response_time": 10
            })
            
        trends = handler._analyze_performance_trends()
        assert trends["rcon_trend"] == "degrading"


    @pytest.mark.asyncio
    async def test_report_read_fail(self, handler, mock_message, mock_deps):
        """Test report read exception"""
        with patch("os.listdir", return_value=["patchraptor_bad.log"]), \
             patch("builtins.open", side_effect=Exception("Read fail")), \
             patch("os.path.join", side_effect=lambda a,b: b), \
             patch("os.path.getmtime", return_value=123):
             
             await handler.cmd_report(mock_message, "", "")
             args = mock_deps["discord_manager"].send_temp_message.call_args[0]
             assert "No log content found" in args[1]

    @pytest.mark.asyncio
    async def test_report_upload_fail(self, handler, mock_message):
        """Test report upload exception fallback"""
        # Ensure log file looks valid
        import discord # Assuming discord is available in test context
        with patch("os.listdir", return_value=["patchraptor_good.log"]), \
             patch("builtins.open", mock_open(read_data="DataLine\n")), \
             patch("tempfile.NamedTemporaryFile"), \
             patch("os.unlink"), \
             patch("os.path.join", side_effect=lambda a,b: b), \
             patch("os.path.getmtime", return_value=123), \
             patch("patchraptor.system_monitoring_handler.discord.File", return_value=Mock()) as mock_file: 
             
             # Mock send to raise Forbidden on first call (with file), succeed on second
             # When file is passed, raise Forbidden.
             # We use side_effect on the mock_message.channel.send
             mock_message.channel.send.side_effect = [discord.Forbidden(Mock(), "No"), None, None]
             
             await handler.cmd_report(mock_message, "", "")
             
             # Verify it fell back to text
             # Total calls: 1 (failed) + 1 (header) + 1 (chunk) = 3?
             # Or if send raised, does it count? Yes.
             assert mock_message.channel.send.call_count >= 2
             
             # Check if text chunk was sent
             # We can iterate call_args_list to find the chunk
             calls = mock_message.channel.send.call_args_list
             found = False
             for args, kwargs in calls:
                 if args and "DataLine" in str(args[0]):
                     found = True
                     break
             assert found

class TestExceptionHandling:
    @pytest.mark.asyncio
    async def test_all_check_exceptions(self, handler, mock_deps):
        """Test general exception handling in all check methods"""
        
        # _check_configuration
        mock_deps["config_manager"].get.side_effect = Exception("Fail")
        issues, results = await handler._check_configuration()
        assert "Configuration check failed" in issues[0]
        
        # _check_server_monitoring
        mock_deps["server_manager"].servers = [Mock(name="S1")] # Add a server
        mock_deps["server_manager"].is_specific_server_running.side_effect = Exception("Fail")
        issues, results = await handler._check_server_monitoring()
        assert "Server Monitoring check failed" in issues[0]

        # _check_rcon - clear side effects first?
        # Mocking execute_for_server to raise generic Exception (not RCONConnectionError which is handled specifically)
        mock_deps["rcon_manager"].execute_for_server.side_effect = Exception("Fail")
        # Need at least one server
        mock_deps["server_manager"].servers = [Mock(name="S", rcon_ip="1")]
        issues, results = await handler._check_rcon()
        assert "RCON check failed" in issues[0]
        
        # _check_server_updates
        # This one is tricky to trigger generic exception before specific logic.
        # We can patch os.path.exists
        with patch("os.path.exists", side_effect=Exception("Fail")):
             issues, results = await handler._check_server_updates()
             assert "Server Updates check failed" in issues[0]
             
        # _check_player_management
        # Force exception by making servers iterable raise
        mock_deps["server_manager"].servers = Mock()
        mock_deps["server_manager"].servers.__iter__ = Mock(side_effect=Exception("IterFail"))
        handler.player_manager = Mock() # Ensure it enters
        issues, results = await handler._check_player_management()
        assert "Player Management check failed" in issues[0]
        
        # _check_backup_system
        # Crash config get
        mock_deps["config_manager"].get.side_effect = Exception("Fail")
        issues, results = await handler._check_backup_system()
        assert "Backup System check failed" in issues[0]

        # _check_scheduling
        # Covered in test_schedule_exception
        
        # _check_advanced_settings
        mock_deps["config_manager"].get.side_effect = Exception("Fail")
        issues, results = await handler._check_advanced_settings()
        assert "Advanced Settings check failed" in issues[0]
        
        # _check_raptorchat
        # Covered in test_raptorchat_checks
        
        # _check_performance
        with patch("time.time", side_effect=Exception("Fail")):
             issues, results = await handler._check_performance()
             # Inner try-except blocks catch errors first
             assert "stress test failed" in issues[0]
             
        # _check_network
        # Covered in test_network_exceptions
        
        # _check_filesystem
        # Covered in test_check_filesystem (Config missing is specific). 
        # Generic:
        with patch("os.path.exists", side_effect=Exception("Fail")):
             issues, results = await handler._check_filesystem()
             assert "Config file access failed" in issues[0]

        # _check_bot_health
        with patch("psutil.Process", side_effect=Exception("Fail")):
             issues, results = await handler._check_bot_health()
             assert "Memory usage test failed" in issues[0]

class TestHappyPaths:
    @pytest.mark.asyncio
    async def test_all_checks_happy(self, handler, mock_deps):
        """Test happy paths for all checks"""
        
        # Backup System
        mock_deps["backup_manager"].backup_path = "C:/backup"
        mock_deps["server_manager"].servers = [Mock(name="S1", server_save_path="C:/save")]
        with patch("os.path.exists", return_value=True), \
             patch("os.access", return_value=True):
             
             issues, results = await handler._check_backup_system()
             assert not issues
             assert "✅ Backup System" in results
             
        # Scheduling
        mock_deps["schedule_manager"].get_events.return_value = []
        issues, results = await handler._check_scheduling()
        assert not issues
        assert "✅ Scheduling" in results
        
        # Player Management
        # Mock file operations for log reading
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="Log Data")):
             
             issues, results = await handler._check_player_management()
             assert not issues
             assert "✅ Player Management" in results

        # Advanced Settings
        mock_deps["config_manager"].get.side_effect = lambda k, d=None: "https://discord.com/api/webhooks/123/token" if k == "discord_webhook" else (None if k == "webpanel_path" else ("." if k == "server_dir" else "dummy_value"))
        issues, results = await handler._check_advanced_settings()
        assert not issues
        assert not results # Advanced settings doesn't output ✅ item on success
        
        # RaptorChat
        mock_deps["raptorchat_manager"].raptorchat_path = "C:/RC.exe"
        with patch("os.path.exists", return_value=True):
            mock_deps["raptorchat_manager"].is_running.return_value = True
            issues, results = await handler._check_raptorchat()
            assert not issues
            assert "✅ RaptorChat" in results
            
        # Filesystem
        mock_deps["config_manager"].config_file = "config.json"
        # Need to mock open for config read and log write/read
        with patch("os.path.exists", return_value=True), \
             patch("builtins.open", mock_open(read_data="Diagnose test - safe to delete")), \
             patch("os.unlink"): # Mock unlink to avoid error
             
             issues, results = await handler._check_filesystem()
             assert not issues
             assert "✅ Config File" in results
             assert "✅ Log Directory" in results
             
        # Bot Health
        with patch("psutil.Process") as mock_proc:
             mock_proc.return_value.memory_info.return_value.rss = 100 * 1024 * 1024 # 100MB
             mock_proc.return_value.num_threads.return_value = 10
             
             issues, results = await handler._check_bot_health()
             assert not issues
             # Bot health returns expanded details
             assert any("Memory Usage" in r for r in results)
             assert any("Thread Count" in r for r in results)
             
        # RCON
        mock_deps["rcon_manager"].execute_for_server = AsyncMock(return_value="OK")
        mock_deps["server_manager"].servers = [Mock(name="S1", rcon_ip="127.0.0.1", rcon_port=7777, rcon_password="pw")]
        issues, results = await handler._check_rcon()
        assert not issues
        assert "✅ RCON Connectivity" in results
        
        
        # Monitoring
        mock_deps["server_manager"].is_specific_server_running.return_value = True
        with patch("psutil.virtual_memory") as mock_vmem, \
             patch("psutil.cpu_percent") as mock_cpu:
            mock_vmem.return_value.percent = 50.0  # Safe memory usage
            mock_cpu.return_value = 25.0  # Safe CPU usage
            issues, results = await handler._check_server_monitoring()
            assert not issues
            assert "✅ Server Monitoring" in results
        
        # Config
        mock_deps["server_manager"].servers[0].rcon_ip = "127.0.0.1" # Valid
        issues, results = await handler._check_configuration()
        assert not issues
        assert "✅ Configuration" in results
