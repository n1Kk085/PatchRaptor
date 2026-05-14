"""
Test Suite for TelemetryManager
Validates all tracker classes, diagnostics, state publishing, and log re-detection.
"""
import pytest
import asyncio
import os
import time
import json
import datetime
from unittest.mock import MagicMock, AsyncMock, patch, mock_open

from patchraptor.telemetry_manager import (
    TelemetryManager, LogBroadcaster, TelemetryState,
    BaseDiskTracker, UptimeTracker, PlayerStatsTracker, PerformanceTracker
)
from patchraptor.models import ServerConfig
from patchraptor.service_locator import ServiceLocator


# ─────────────────────────────────────────────────────────────
#  Shared fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_server():
    return ServerConfig(
        name="TestServer",
        display_name="Test Server",
        map_name="TheIsland_WP",
        server_log_path="C:\\logs\\ShooterGame.log",
        rcon_ip="127.0.0.1",
        rcon_port=27015,
        rcon_password="password",
        start_command="start.bat",
        install_dir="C:\\ark",
        server_save_path="C:\\ark\\Saved"
    )


@pytest.fixture
def telemetry_manager(tmp_path):
    return TelemetryManager(str(tmp_path))


def _make_tracker(cls, tmp_path):
    return cls(str(tmp_path / f"{cls.__name__}.json"))


# ─────────────────────────────────────────────────────────────
#  BaseDiskTracker
# ─────────────────────────────────────────────────────────────

class TestBaseDiskTracker:
    """Test the shared disk persistence layer."""

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Returns an empty dict when the data file does not exist."""
        tracker = UptimeTracker(str(tmp_path / "uptime.json"))
        assert tracker.data == {}

    def test_load_existing_file(self, tmp_path):
        """Loads existing JSON data from disk on init."""
        data_file = tmp_path / "uptime.json"
        fresh_ts = time.time()
        data_file.write_text(json.dumps({"servers": {"S1": {"entries": [{"timestamp": fresh_ts, "is_online": True}]}}}))
        tracker = UptimeTracker(str(data_file))
        assert "S1" in tracker.data.get("servers", {})

    def test_load_corrupted_file_returns_empty(self, tmp_path):
        """Returns empty dict when the file contains invalid JSON."""
        data_file = tmp_path / "uptime.json"
        data_file.write_text("NOT_JSON{{{")
        tracker = UptimeTracker(str(data_file))
        assert tracker.data == {}

    @pytest.mark.asyncio
    async def test_save_only_when_dirty(self, tmp_path):
        """Does not write to disk when no data has changed."""
        tracker = UptimeTracker(str(tmp_path / "uptime.json"))
        tracker._dirty = False
        with patch.object(tracker, "_sync_save") as mock_save:
            await tracker.save()
            mock_save.assert_not_called()

    @pytest.mark.asyncio
    async def test_save_writes_when_dirty(self, tmp_path):
        """Writes to disk and clears dirty flag when data has changed."""
        tracker = UptimeTracker(str(tmp_path / "uptime.json"))
        tracker._dirty = True
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            await tracker.save()
            mock_thread.assert_called_once()
            assert tracker._dirty is False

    def test_cleanup_skips_within_hour(self, tmp_path):
        """Skips cleanup when last cleanup was less than an hour ago."""
        tracker = UptimeTracker(str(tmp_path / "uptime.json"))
        tracker.last_cleanup_time = time.time()  # Just ran
        tracker.data = {"servers": {"S1": {"entries": [{"timestamp": 0, "is_online": True}]}}}
        tracker._cleanup_old_entries()
        # Entries from epoch should still be there — cleanup was skipped
        assert len(tracker.data["servers"]["S1"]["entries"]) == 1

    def test_cleanup_removes_old_entries(self, tmp_path):
        """Removes entries older than 7 days during cleanup."""
        tracker = UptimeTracker(str(tmp_path / "uptime.json"))
        tracker.last_cleanup_time = 0  # Force cleanup
        old_ts = time.time() - (8 * 24 * 60 * 60)  # 8 days ago
        tracker.data = {"servers": {"S1": {"entries": [{"timestamp": old_ts, "is_online": True}]}}}
        tracker._cleanup_old_entries()
        assert "S1" not in tracker.data.get("servers", {})


# ─────────────────────────────────────────────────────────────
#  UptimeTracker
# ─────────────────────────────────────────────────────────────

class TestUptimeTracker:
    """Test uptime recording and average calculation."""

    def test_record_uptime_creates_entry(self, tmp_path):
        """Creates a new entry for a server with online status."""
        tracker = _make_tracker(UptimeTracker, tmp_path)
        tracker.record_uptime("S1", True)
        assert len(tracker.data["servers"]["S1"]["entries"]) == 1
        assert tracker.data["servers"]["S1"]["entries"][0]["is_online"] is True
        assert tracker._dirty is True

    def test_record_uptime_ignores_empty_name(self, tmp_path):
        """Ignores empty server names."""
        tracker = _make_tracker(UptimeTracker, tmp_path)
        tracker.record_uptime("", True)
        assert "servers" not in tracker.data

    def test_get_uptime_unknown_server_returns_zero(self, tmp_path):
        """Returns 0.0 for a server with no recorded entries."""
        tracker = _make_tracker(UptimeTracker, tmp_path)
        assert tracker.get_server_7day_uptime("NonExistent") == 0.0

    def test_get_uptime_all_online(self, tmp_path):
        """Returns 100% when all entries show the server as online."""
        tracker = _make_tracker(UptimeTracker, tmp_path)
        tracker.data = {"servers": {"S1": {"entries": [
            {"timestamp": time.time(), "is_online": True},
            {"timestamp": time.time(), "is_online": True},
        ]}}}
        assert tracker.get_server_7day_uptime("S1") == 100.0

    def test_get_uptime_half_online(self, tmp_path):
        """Returns 50% when half the entries show the server as online."""
        tracker = _make_tracker(UptimeTracker, tmp_path)
        tracker.data = {"servers": {"S1": {"entries": [
            {"timestamp": time.time(), "is_online": True},
            {"timestamp": time.time(), "is_online": False},
        ]}}}
        assert tracker.get_server_7day_uptime("S1") == 50.0

    def test_get_average_uptime_no_servers(self, tmp_path):
        """Returns 0.0 when no servers have been tracked."""
        tracker = _make_tracker(UptimeTracker, tmp_path)
        assert tracker.get_average_7day_uptime() == 0.0

    def test_get_average_uptime_multiple_servers(self, tmp_path):
        """Averages uptime correctly across multiple servers."""
        tracker = _make_tracker(UptimeTracker, tmp_path)
        tracker.data = {"servers": {
            "S1": {"entries": [{"timestamp": time.time(), "is_online": True}]},
            "S2": {"entries": [{"timestamp": time.time(), "is_online": False}]},
        }}
        assert tracker.get_average_7day_uptime() == 50.0


# ─────────────────────────────────────────────────────────────
#  PlayerStatsTracker
# ─────────────────────────────────────────────────────────────

class TestPlayerStatsTracker:
    """Test player count recording and average calculation."""

    def test_record_players_creates_entry(self, tmp_path):
        """Creates a new entry for a server with player count."""
        tracker = _make_tracker(PlayerStatsTracker, tmp_path)
        tracker.record_players("S1", "TheIsland", 5)
        assert tracker.data["servers"]["S1"]["entries"][0]["player_count"] == 5
        assert tracker._dirty is True

    def test_record_players_ignores_empty_name(self, tmp_path):
        """Ignores empty server names."""
        tracker = _make_tracker(PlayerStatsTracker, tmp_path)
        tracker.record_players("", "TheIsland", 5)
        assert "servers" not in tracker.data

    def test_get_server_avg_unknown_server(self, tmp_path):
        """Returns 0.0 for a server with no recorded entries."""
        tracker = _make_tracker(PlayerStatsTracker, tmp_path)
        assert tracker.get_server_7day_avg("NonExistent") == 0.0

    def test_get_server_avg_calculates_correctly(self, tmp_path):
        """Calculates the average player count correctly."""
        tracker = _make_tracker(PlayerStatsTracker, tmp_path)
        tracker.data = {"servers": {"S1": {"map_name": "TheIsland", "entries": [
            {"timestamp": time.time(), "player_count": 4},
            {"timestamp": time.time(), "player_count": 6},
        ]}}}
        assert tracker.get_server_7day_avg("S1") == 5.0

    def test_get_total_avg_no_servers(self, tmp_path):
        """Returns 0.0 when no servers have been tracked."""
        tracker = _make_tracker(PlayerStatsTracker, tmp_path)
        assert tracker.get_total_7day_avg() == 0.0

    def test_get_peak_returns_highest(self, tmp_path):
        """Returns the highest player count recorded in the last 7 days."""
        tracker = _make_tracker(PlayerStatsTracker, tmp_path)
        tracker.data = {"servers": {"S1": {"entries": [
            {"timestamp": time.time(), "player_count": 3},
            {"timestamp": time.time(), "player_count": 12},
            {"timestamp": time.time(), "player_count": 7},
        ]}}}
        assert tracker.get_7day_peak() == 12

    def test_get_peak_excludes_old_entries(self, tmp_path):
        """Ignores entries older than 7 days when calculating peak."""
        tracker = _make_tracker(PlayerStatsTracker, tmp_path)
        old_ts = time.time() - (8 * 24 * 60 * 60)
        tracker.data = {"servers": {"S1": {"entries": [
            {"timestamp": old_ts, "player_count": 100},
            {"timestamp": time.time(), "player_count": 5},
        ]}}}
        assert tracker.get_7day_peak() == 5


# ─────────────────────────────────────────────────────────────
#  PerformanceTracker
# ─────────────────────────────────────────────────────────────

class TestPerformanceTracker:
    """Test system metric recording and rolling averages."""

    def test_record_metric_appends_entry(self, tmp_path):
        """Appends a metric entry and marks tracker as dirty."""
        tracker = _make_tracker(PerformanceTracker, tmp_path)
        tracker.record_metric(10.0, 50.0, 30.0)
        assert len(tracker.history["system_metrics"]) == 1
        assert tracker._dirty is True

    def test_record_metric_caps_at_100(self, tmp_path):
        """Trims metric history to keep only the last 100 entries."""
        tracker = _make_tracker(PerformanceTracker, tmp_path)
        for i in range(105):
            tracker.record_metric(float(i), 50.0, 30.0)
        assert len(tracker.history["system_metrics"]) == 100

    def test_get_rolling_averages_no_data(self, tmp_path):
        """Returns zero averages when no metrics have been recorded."""
        tracker = _make_tracker(PerformanceTracker, tmp_path)
        result = tracker.get_rolling_averages()
        assert result == {"cpu": 0.0, "ram": 0.0, "disk": 0.0}

    def test_get_rolling_averages_calculates_correctly(self, tmp_path):
        """Calculates the rolling average of CPU, RAM, and Disk correctly."""
        tracker = _make_tracker(PerformanceTracker, tmp_path)
        tracker.history["system_metrics"] = [
            {"cpu_percent": 20.0, "memory_percent": 40.0, "disk_percent": 60.0},
            {"cpu_percent": 40.0, "memory_percent": 60.0, "disk_percent": 80.0},
        ]
        result = tracker.get_rolling_averages()
        assert result["cpu"] == 30.0
        assert result["ram"] == 50.0
        assert result["disk"] == 70.0

    @pytest.mark.asyncio
    async def test_save_skips_when_not_dirty(self, tmp_path):
        """Does not write to disk when no data has changed."""
        tracker = _make_tracker(PerformanceTracker, tmp_path)
        tracker._dirty = False
        with patch.object(tracker, "_sync_save") as mock_save:
            await tracker.save()
            mock_save.assert_not_called()

    def test_load_missing_file_returns_defaults(self, tmp_path):
        """Returns default empty structure when no data file exists."""
        tracker = _make_tracker(PerformanceTracker, tmp_path)
        assert "system_metrics" in tracker.history


# ─────────────────────────────────────────────────────────────
#  TelemetryManager: _publish_state / _sync_publish
# ─────────────────────────────────────────────────────────────

class TestPublishState:
    """Test state serialization and file publishing."""

    @pytest.mark.asyncio
    async def test_publish_state_writes_file(self, telemetry_manager, tmp_path):
        """Writes minified JSON to the cluster_live.json state file."""
        telemetry_manager.current_state = TelemetryState(
            servers=[], total_players=3, server_count=2, online_count=1,
            last_update="2024-01-01", current_time="2024-01-01 00:00:00"
        )
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            await telemetry_manager._publish_state()
            mock_thread.assert_called_once()

    def test_sync_publish_writes_camelcase_keys(self, telemetry_manager, tmp_path):
        """Writes camelCase keys for Web Dashboard compatibility."""
        state_dict = {
            "servers": [],
            "server_player_averages": {},
            "server_uptime_averages": {},
            "total_players": 0,
            "total_7day_player_avg": 0.0,
            "total_7day_uptime_avg": 0.0,
            "server_count": 0,
            "online_count": 0,
            "last_update": "",
            "current_time": ""
        }
        with patch("builtins.open", mock_open()) as mock_file, \
             patch("os.replace") as mock_replace:
            telemetry_manager._sync_publish(state_dict)
            written = "".join(call.args[0] for call in mock_file().write.call_args_list)
            assert "totalPlayers" in written
            assert "serverCount" in written
            mock_replace.assert_called_once()


# ─────────────────────────────────────────────────────────────
#  TelemetryManager: trigger_log_file_detection_on_restart
# ─────────────────────────────────────────────────────────────

class TestLogFileDetection:
    """Test log file position reset and re-detection."""

    @pytest.mark.asyncio
    async def test_trigger_clears_positions(self, telemetry_manager, mock_server):
        """Clears file positions and resets server log paths on restart."""
        mock_sm = MagicMock(servers=[mock_server])
        ServiceLocator.register("ServerManager", mock_sm)

        telemetry_manager.broadcaster.file_positions["TestServer"] = 9999
        mock_server.server_log_path = "C:\\logs\\old.log"

        telemetry_manager.broadcaster.tail_logs = AsyncMock()

        await telemetry_manager.trigger_log_file_detection_on_restart()

        assert "TestServer" not in telemetry_manager.broadcaster.file_positions
        assert mock_server.server_log_path == ""
        telemetry_manager.broadcaster.tail_logs.assert_called_once()


# ─────────────────────────────────────────────────────────────
#  TelemetryManager: get_diagnostics
# ─────────────────────────────────────────────────────────────

class TestGetDiagnostics:
    """Test the full diagnostics suite."""

    @pytest.fixture
    def diag_manager(self, tmp_path):
        """TelemetryManager with all ServiceLocator dependencies mocked."""
        ServiceLocator.clear()
        tm = TelemetryManager(str(tmp_path))

        cm = MagicMock()
        cm.get.side_effect = lambda key, default=None: {
            "bot_token": "tok", "channel_id": "123", "app_id": "456",
            "steamcmd_path": "C:\\steamcmd\\steamcmd.exe", "server_dir": str(tmp_path)
        }.get(key, default)

        sm = MagicMock()
        sm.servers = []

        rcon = AsyncMock()

        ServiceLocator.register("ConfigManager", cm)
        ServiceLocator.register("ServerManager", sm)
        ServiceLocator.register("RCONManager", rcon)
        return tm

    @pytest.mark.asyncio
    async def test_diagnostics_config_ok(self, diag_manager, tmp_path):
        """Reports Configuration as OK when all required keys are present."""
        with patch("os.path.exists", return_value=True), \
             patch("socket.create_connection"), \
             patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.cpu_percent", return_value=20.0), \
             patch("psutil.boot_time", return_value=time.time() - 3600):
            mock_disk.return_value = MagicMock(used=10e9, total=100e9, percent=10.0)
            mock_mem.return_value = MagicMock(used=4e9, total=16e9)
            result = await diag_manager.get_diagnostics()
        assert any("☑️ Configuration" in r for r in result["results"])

    @pytest.mark.asyncio
    async def test_diagnostics_missing_config_key(self, tmp_path):
        """Reports Configuration as failed when required keys are missing."""
        tm = TelemetryManager(str(tmp_path))
        cm = MagicMock()
        cm.get.return_value = None  # All keys missing
        sm = MagicMock(servers=[])
        ServiceLocator.register("ConfigManager", cm)
        ServiceLocator.register("ServerManager", sm)

        with patch("os.path.exists", return_value=False), \
             patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.cpu_percent", return_value=0.0), \
             patch("psutil.boot_time", return_value=time.time()):
            mock_disk.return_value = MagicMock(used=0, total=100e9, percent=0)
            mock_mem.return_value = MagicMock(used=0, total=16e9)
            result = await tm.get_diagnostics()
        assert any("❌ Configuration" in r for r in result["results"])

    @pytest.mark.asyncio
    async def test_diagnostics_no_servers_online(self, diag_manager):
        """Reports Server Monitoring as failed when no servers are online."""
        diag_manager.current_state.server_count = 2
        diag_manager.current_state.online_count = 0

        with patch("os.path.exists", return_value=True), \
             patch("socket.create_connection"), \
             patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.cpu_percent", return_value=5.0), \
             patch("psutil.boot_time", return_value=time.time()):
            mock_disk.return_value = MagicMock(used=10e9, total=100e9, percent=10.0)
            mock_mem.return_value = MagicMock(used=4e9, total=16e9)
            result = await diag_manager.get_diagnostics()
        assert any("❌ Server Monitoring" in r for r in result["results"])

    @pytest.mark.asyncio
    async def test_diagnostics_disk_critical(self, diag_manager, tmp_path):
        """Reports Disk Space as failed when usage exceeds 95%."""
        with patch("os.path.exists", return_value=True), \
             patch("socket.create_connection"), \
             patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.cpu_percent", return_value=5.0), \
             patch("psutil.boot_time", return_value=time.time()):
            mock_disk.return_value = MagicMock(used=96e9, total=100e9, percent=96.0)
            mock_mem.return_value = MagicMock(used=4e9, total=16e9)
            result = await diag_manager.get_diagnostics()
        assert any("❌ Disk Space" in r for r in result["results"])

    @pytest.mark.asyncio
    async def test_diagnostics_returns_system_metrics(self, diag_manager):
        """Returns CPU, RAM, and disk info in diagnostics result."""
        with patch("os.path.exists", return_value=True), \
             patch("socket.create_connection"), \
             patch("psutil.disk_usage") as mock_disk, \
             patch("psutil.virtual_memory") as mock_mem, \
             patch("psutil.cpu_percent", return_value=42.0), \
             patch("psutil.boot_time", return_value=time.time() - 1000):
            mock_disk.return_value = MagicMock(used=10e9, total=100e9, percent=10.0)
            mock_mem.return_value = MagicMock(used=8e9, total=16e9)
            result = await diag_manager.get_diagnostics()
        assert "cpu_usage" in result
        assert "ram_used" in result
        assert "disk_info" in result


# ─────────────────────────────────────────────────────────────
#  LogBroadcaster: sync reader
# ─────────────────────────────────────────────────────────────

class TestSyncReader:
    """Test the synchronous log processing worker."""

    def test_read_and_process_join(self, telemetry_manager, tmp_path):
        """Extracts a JOIN event from a log line."""
        uid = "A" * 32
        log_content = f"2024.01.01_00.00.00: Survivor [UniqueNetId:{uid} Platform:Steam] joined this ARK!\n"
        log_file = tmp_path / "ShooterGame.log"
        log_file.write_text(log_content)

        events, pos = telemetry_manager.broadcaster._read_and_process_sync(
            str(log_file), 0, "TestServer"
        )
        assert len(events) == 1
        assert events[0][0] == "join"
        assert events[0][1]["name"] == "Survivor"

    def test_read_and_process_leave(self, telemetry_manager, tmp_path):
        """Extracts a LEAVE event from a log line."""
        uid = "B" * 32
        log_content = f"2024.01.01_00.00.00: Survivor [UniqueNetId:{uid} Platform:Steam] left this ARK!\n"
        log_file = tmp_path / "ShooterGame.log"
        log_file.write_text(log_content)

        events, pos = telemetry_manager.broadcaster._read_and_process_sync(
            str(log_file), 0, "TestServer"
        )
        assert len(events) == 1
        assert events[0][0] == "leave"

    def test_read_and_process_empty_file(self, telemetry_manager, tmp_path):
        """Returns no events and advances position for an empty file."""
        log_file = tmp_path / "ShooterGame.log"
        log_file.write_text("")

        events, pos = telemetry_manager.broadcaster._read_and_process_sync(
            str(log_file), 0, "TestServer"
        )
        assert events == []

    def test_read_and_process_unrelated_lines(self, telemetry_manager, tmp_path):
        """Skips lines that contain no player join or leave events."""
        log_file = tmp_path / "ShooterGame.log"
        log_file.write_text("Random log line with no events\nAnother line\n")

        events, pos = telemetry_manager.broadcaster._read_and_process_sync(
            str(log_file), 0, "TestServer"
        )
        assert events == []

    def test_read_and_process_file_error(self, telemetry_manager):
        """Returns empty results gracefully when the log file cannot be read."""
        events, pos = telemetry_manager.broadcaster._read_and_process_sync(
            "C:\\nonexistent\\path.log", 0, "TestServer"
        )
        assert events == []
        assert pos == 0


# ─────────────────────────────────────────────────────────────
#  LogBroadcaster: sync callback path
# ─────────────────────────────────────────────────────────────

class TestBroadcastEventSync:
    """Test that sync callbacks are called correctly in broadcast_event."""

    @pytest.mark.asyncio
    async def test_sync_callback_is_called(self, telemetry_manager):
        """Calls synchronous (non-async) listeners directly."""
        sync_cb = MagicMock()
        telemetry_manager.broadcaster.register_listener("join", sync_cb)
        event = {"type": "join", "name": "P1", "id": "uid", "server": "S1"}
        await telemetry_manager.broadcaster.broadcast_event("join", event)
        sync_cb.assert_called_once_with(event)

    @pytest.mark.asyncio
    async def test_unknown_event_type_ignored(self, telemetry_manager):
        """Silently ignores broadcasts for unregistered event types."""
        await telemetry_manager.broadcaster.broadcast_event("unknown_event", {})
