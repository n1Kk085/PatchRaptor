"""
Test Suite for SystemUtils
Validates system recovery coordination and directory size calculation.
"""
import pytest
import os
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from patchraptor.system_utils import SystemUtils


# ─────────────────────────────────────────────────────────────
#  unified_system_recovery
# ─────────────────────────────────────────────────────────────

class TestUnifiedSystemRecovery:
    """Test the coordination of system component recovery."""

    @pytest.mark.asyncio
    async def test_recovery_full_success(self):
        """Coordinates all components correctly on success."""
        mock_tm = MagicMock()
        mock_tm.trigger_log_file_detection_on_restart = AsyncMock()
        
        mock_pm = MagicMock()
        mock_pm.resume = MagicMock()
        
        mock_rcm = MagicMock()
        mock_rcm.start_with_delay = AsyncMock(return_value=True)
        
        mock_dm = MagicMock()
        mock_dm.send_temp_message = AsyncMock()
        
        mock_channel = MagicMock()

        # Mock is_running to return False to ensure delay is preserved for this test
        mock_rcm.is_running.return_value = False

        # Mock is_running to return False initially (to trigger delay) 
        # then True (to simulate successful startup)
        mock_rcm.is_running.side_effect = [False, True]

        await SystemUtils.unified_system_recovery(
            delay=1,
            channel=mock_channel,
            raptorchat_manager=mock_rcm,
            player_manager=mock_pm,
            discord_manager=mock_dm,
            telemetry_manager=mock_tm
        )

        mock_tm.trigger_log_file_detection_on_restart.assert_called_once()
        mock_pm.resume.assert_called_once()
        mock_rcm.start_with_delay.assert_called_once_with(1)
        mock_dm.send_temp_message.assert_called_once()
        
        args = mock_dm.send_temp_message.call_args[0]
        assert "all systems online and operational" in args[1].lower()

    @pytest.mark.asyncio
    async def test_recovery_already_running(self):
        """Skips delay if RaptorChat is already connected."""
        mock_rcm = MagicMock()
        mock_rcm.is_running.return_value = True
        mock_rcm.start_with_delay = AsyncMock(return_value=True)
        
        mock_dm = MagicMock()
        mock_dm.send_temp_message = AsyncMock()
        
        await SystemUtils.unified_system_recovery(
            delay=300,
            channel=MagicMock(),
            raptorchat_manager=mock_rcm,
            player_manager=None,
            discord_manager=mock_dm
        )

        # Verify delay was reset to 0
        mock_rcm.start_with_delay.assert_called_once_with(0)
        args = mock_dm.send_temp_message.call_args[0]
        assert "all systems online and operational" in args[1].lower()

    @pytest.mark.asyncio
    async def test_recovery_raptorchat_failure(self):
            """Reports failure when RaptorChat fails to start."""
            mock_rcm = MagicMock()
            mock_rcm.start_with_delay = AsyncMock(return_value=False)
            mock_rcm.is_running.return_value = False
        
            mock_dm = MagicMock()
            mock_dm.send_temp_message = AsyncMock()
        
            mock_channel = MagicMock()

            await SystemUtils.unified_system_recovery(
                delay=0,
                channel=mock_channel,
                raptorchat_manager=mock_rcm,
                player_manager=None,
                discord_manager=mock_dm
            )

            args = mock_dm.send_temp_message.call_args[0]
            assert "failed" in args[1].lower()

    @pytest.mark.asyncio
    async def test_recovery_handles_exceptions(self):
        """Continues recovery even if individual components raise exceptions."""
        mock_tm = MagicMock()
        mock_tm.trigger_log_file_detection_on_restart = AsyncMock(side_effect=Exception("tm error"))
        
        mock_pm = MagicMock()
        mock_pm.resume = MagicMock(side_effect=Exception("pm error"))
        
        mock_rcm = MagicMock()
        mock_rcm.start_with_delay = AsyncMock(side_effect=Exception("rcm error"))
        
        mock_dm = MagicMock()
        mock_dm.send_temp_message = AsyncMock()
        
        mock_channel = MagicMock()

        await SystemUtils.unified_system_recovery(
            delay=0,
            channel=mock_channel,
            raptorchat_manager=mock_rcm,
            player_manager=mock_pm,
            discord_manager=mock_dm,
            telemetry_manager=mock_tm
        )
        
        # Verify discord was notified of the error
        mock_dm.send_temp_message.assert_called()
        args = mock_dm.send_temp_message.call_args[0]
        assert "error" in args[1].lower()

    @pytest.mark.asyncio
    async def test_recovery_no_managers(self):
        """Completes without error when managers are missing."""
        await SystemUtils.unified_system_recovery(0, None, None, None, None)
        # Should not raise


# ─────────────────────────────────────────────────────────────
#  get_directory_size
# ─────────────────────────────────────────────────────────────

class TestGetDirectorySize:
    """Test recursive directory size calculation."""

    def test_size_nonexistent_path(self):
        """Returns 0 for a path that does not exist."""
        assert SystemUtils.get_directory_size("nonexistent_path_xyz") == 0

    def test_size_empty_dir(self, tmp_path):
        """Returns 0 for an empty directory."""
        assert SystemUtils.get_directory_size(str(tmp_path)) == 0

    def test_size_with_files(self, tmp_path):
        """Calculates correct size for a directory with files."""
        f1 = tmp_path / "file1.txt"
        f1.write_text("hello") # 5 bytes
        
        f2 = tmp_path / "subdir" / "file2.txt"
        f2.parent.mkdir()
        f2.write_text("world!") # 6 bytes
        
        expected = 5 + 6
        assert SystemUtils.get_directory_size(str(tmp_path)) == expected

    def test_size_handles_oserror(self, tmp_path):
        """Handles OSErrors (e.g. permission) gracefully during walk."""
        f1 = tmp_path / "file1.txt"
        f1.write_text("data")
        
        with patch("os.path.getsize", side_effect=OSError("denied")):
            # Should return 0 if all getsize calls fail
            assert SystemUtils.get_directory_size(str(tmp_path)) == 0

    def test_size_skips_symlinks(self, tmp_path):
        """Does not count size of symbolic links."""
        f1 = tmp_path / "real.txt"
        f1.write_text("real data") # 9 bytes
        
        # Mock islink to return True for a path
        with patch("os.path.islink", return_value=True):
             assert SystemUtils.get_directory_size(str(tmp_path)) == 0
