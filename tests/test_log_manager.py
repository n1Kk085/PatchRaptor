"""
Test suite for LogManager.
"""
import pytest
import os
import time
import tempfile
from unittest.mock import Mock, patch, MagicMock
from patchraptor.log_manager import LogManager, execute_steamcmd_simple


class TestLogManagerInit:
    """Test LogManager initialization."""
    
    def test_init_creates_log_directory(self):
        """Test that initialization creates log directory."""
        with patch('os.makedirs') as mock_makedirs:
            logger = LogManager()
            mock_makedirs.assert_called()
    
    def test_init_sets_debug_disabled(self):
        """Test that debug is disabled by default."""
        logger = LogManager()
        assert logger.debug_enabled is False


class TestLogging:
    """Test logging functionality."""
    
    @pytest.fixture
    def logger(self):
        """Create a LogManager instance for testing."""
        return LogManager()
    
    def test_log_basic(self, logger):
        """Test basic logging."""
        logger.log("Test message", level="INFO")
        # Should not raise exception
    
    def test_log_with_category(self, logger):
        """Test logging with category."""
        logger.log("Test message", level="INFO", category="PLAYER")
        # Should not raise exception
    
    def test_log_with_context(self, logger):
        """Test logging with context."""
        logger.log("Test message", level="INFO", context={"user": "test"})
        # Should not raise exception
    
    def test_log_debug_when_disabled(self, logger):
        """Test that debug messages are skipped when debug is disabled."""
        with patch.object(logger.root_logger, 'log') as mock_log:
            logger.log("Debug message", level="DEBUG")
            mock_log.assert_not_called()
    
    def test_log_debug_when_enabled(self, logger):
        """Test that debug messages are logged when debug is enabled."""
        logger.debug_enabled = True
        with patch.object(logger.root_logger, 'log') as mock_log:
            logger.log("Debug message", level="DEBUG")
            mock_log.assert_called()
    
    def test_log_invalid_level(self, logger):
        """Test logging with invalid level defaults to INFO."""
        logger.log("Test message", level="INVALID")
        # Should not raise exception


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.fixture
    def logger(self):
        return LogManager()
    
    def test_rate_limiting_triggers(self, logger):
        """Test that rate limiting triggers after max count."""
        # Set very low limit for testing
        logger.rate_limits['INFO'] = {'interval': 60, 'max_count': 2}
        
        # First two should pass
        assert not logger._is_rate_limited("Test", "INFO")
        assert not logger._is_rate_limited("Test", "INFO")
        
        # Third should be rate limited
        assert logger._is_rate_limited("Test", "INFO")
    
    def test_rate_limiting_resets(self, logger):
        """Test that rate limiting resets after interval."""
        logger.rate_limits['INFO'] = {'interval': 0.1, 'max_count': 1}
        
        # First message passes
        assert not logger._is_rate_limited("Test", "INFO")
        
        # Second is rate limited
        assert logger._is_rate_limited("Test", "INFO")
        
        # Wait for reset
        time.sleep(0.2)
        
        # Should pass again
        assert not logger._is_rate_limited("Test", "INFO")
    
    def test_rate_limiting_reports_suppressed(self, logger):
        """Test that suppressed messages are reported."""
        logger.rate_limits['WARNING'] = {'interval': 60, 'max_count': 1}
        
        # Trigger rate limiting
        logger._is_rate_limited("Test", "WARNING")
        logger._is_rate_limited("Test", "WARNING")
        
        assert logger.suppressed_counts['WARNING'] > 0
    
    def test_rate_limiting_unknown_level(self, logger):
        """Test that unknown levels are not rate limited."""
        assert not logger._is_rate_limited("Test", "UNKNOWN")


class TestContextManagement:
    """Test context management functionality."""
    
    @pytest.fixture
    def logger(self):
        return LogManager()
    
    def test_set_global_context(self, logger):
        """Test setting global context."""
        logger.set_global_context(server="test", map="ragnarok")
        assert "server" in logger.global_context
        assert logger.global_context["server"] == "test"
    
    def test_clear_global_context(self, logger):
        """Test clearing global context."""
        logger.set_global_context(server="test")
        logger.clear_global_context()
        assert len(logger.global_context) == 0
    
    def test_push_pop_context(self, logger):
        """Test push and pop context stack."""
        logger.push_context(operation="backup")
        assert len(logger.context_stack) == 1
        
        logger.pop_context()
        assert len(logger.context_stack) == 0
    
    def test_pop_context_empty_stack(self, logger):
        """Test popping from empty context stack."""
        logger.pop_context()  # Should not raise exception
        assert len(logger.context_stack) == 0
    
    def test_get_current_context(self, logger):
        """Test getting merged context."""
        logger.set_global_context(server="test")
        logger.push_context(operation="backup")
        
        context = logger.get_current_context()
        assert "server" in context
        assert "operation" in context


class TestMessageEnhancement:
    """Test message enhancement functionality."""
    
    @pytest.fixture
    def logger(self):
        return LogManager()
    
    def test_enhance_with_known_category(self, logger):
        """Test message enhancement with known category."""
        enhanced = logger._enhance_message("Test", "PLAYER", None)
        assert "[PLAYER]" in enhanced
    
    def test_enhance_with_unknown_category(self, logger):
        """Test message enhancement with unknown category."""
        enhanced = logger._enhance_message("Test", "CUSTOM", None)
        assert "[CUSTOM]" in enhanced
    
    def test_enhance_with_global_context(self, logger):
        """Test message enhancement with global context."""
        logger.set_global_context(server="test")
        enhanced = logger._enhance_message("Test", None, None)
        assert "server=test" in enhanced
    
    def test_format_context(self, logger):
        """Test context formatting."""
        formatted = logger._format_context({"key": "value"})
        assert "Context:" in formatted
        assert "key=value" in formatted
    
    def test_format_context_empty(self, logger):
        """Test formatting empty context."""
        formatted = logger._format_context({})
        assert formatted == ""


class TestConvenienceMethods:
    """Test convenience logging methods."""
    
    @pytest.fixture
    def logger(self):
        return LogManager()
    
    def test_debug_player(self, logger):
        """Test debug_player convenience method."""
        logger.debug_enabled = True
        with patch.object(logger, 'log') as mock_log:
            logger.debug_player("Test")
            mock_log.assert_called_with("Test", level="DEBUG", category="PLAYER", context={})
    
    def test_info_player(self, logger):
        """Test info_player convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.info_player("Test")
            mock_log.assert_called_with("Test", level="INFO", category="PLAYER", context={})
    
    def test_warning_player(self, logger):
        """Test warning_player convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.warning_player("Test")
            mock_log.assert_called_with("Test", level="WARNING", category="PLAYER", context={})
    
    def test_error_player(self, logger):
        """Test error_player convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.error_player("Test")
            mock_log.assert_called_with("Test", level="ERROR", category="PLAYER", context={})
    
    def test_debug_server(self, logger):
        """Test debug_server convenience method."""
        logger.debug_enabled = True
        with patch.object(logger, 'log') as mock_log:
            logger.debug_server("Test")
            mock_log.assert_called_with("Test", level="DEBUG", category="SERVER", context={})
    
    def test_info_server(self, logger):
        """Test info_server convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.info_server("Test")
            mock_log.assert_called_with("Test", level="INFO", category="SERVER", context={})
    
    def test_warning_server(self, logger):
        """Test warning_server convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.warning_server("Test")
            mock_log.assert_called_with("Test", level="WARNING", category="SERVER", context={})
    
    def test_error_server(self, logger):
        """Test error_server convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.error_server("Test")
            mock_log.assert_called_with("Test", level="ERROR", category="SERVER", context={})
    
    def test_debug_performance(self, logger):
        """Test debug_performance convenience method."""
        logger.debug_enabled = True
        with patch.object(logger, 'log') as mock_log:
            logger.debug_performance("Test")
            mock_log.assert_called_with("Test", level="DEBUG", category="PERFORMANCE", context={})
    
    def test_info_performance(self, logger):
        """Test info_performance convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.info_performance("Test")
            mock_log.assert_called_with("Test", level="INFO", category="PERFORMANCE", context={})
    
    def test_info_system(self, logger):
        """Test info_system convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.info_system("Test")
            mock_log.assert_called_with("Test", level="INFO", category="SYSTEM", context={})
    
    def test_info_discord(self, logger):
        """Test info_discord convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.info_discord("Test")
            mock_log.assert_called_with("Test", level="INFO", category="DISCORD", context={})
    
    def test_info_command(self, logger):
        """Test info_command convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.info_command("Test")
            mock_log.assert_called_with("Test", level="INFO", category="DISCORD", context={})
    
    def test_warning_system(self, logger):
        """Test warning_system convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.warning_system("Test")
            mock_log.assert_called_with("Test", level="WARNING", category="SYSTEM", context={})
    
    def test_error_system(self, logger):
        """Test error_system convenience method."""
        with patch.object(logger, 'log') as mock_log:
            logger.error_system("Test")
            mock_log.assert_called_with("Test", level="ERROR", category="SYSTEM", context={})


class TestDebugToggle:
    """Test debug toggle functionality."""
    
    @pytest.fixture
    def logger(self):
        return LogManager()
    
    def test_toggle_debug_enables(self, logger):
        """Test that toggle_debug enables debug."""
        assert not logger.debug_enabled
        result = logger.toggle_debug()
        assert result is True
        assert logger.debug_enabled is True
    
    def test_toggle_debug_disables(self, logger):
        """Test that toggle_debug disables debug."""
        logger.debug_enabled = True
        result = logger.toggle_debug()
        assert result is False
        assert logger.debug_enabled is False
    
    def test_is_debug_enabled(self, logger):
        """Test is_debug_enabled method."""
        assert not logger.is_debug_enabled()
        logger.debug_enabled = True
        assert logger.is_debug_enabled()


class TestLogFileManagement:
    """Test log file management."""
    
    @pytest.fixture
    def logger(self):
        return LogManager()
    
    def test_get_current_log_file(self, logger):
        """Test getting current log file path."""
        log_file = logger.get_current_log_file()
        assert "patchraptor_" in log_file
        assert ".log" in log_file
    
    def test_manage_log_files_cleanup(self, logger):
        """Test that old log files are cleaned up."""
        with patch('os.listdir') as mock_listdir, \
             patch('os.remove') as mock_remove:
            # Simulate 15 log files
            mock_listdir.return_value = [f"patchraptor_01-01-26.log.{i}" for i in range(15)]
            
            logger._manage_log_files()
            
            # Should remove 5 oldest files (keep only 10)
            assert mock_remove.call_count == 5
    
    def test_manage_log_files_skips_same_date(self, logger):
        """Test that cleanup is skipped on same date."""
        import datetime
        logger.last_cleanup_date = datetime.datetime.now().date()
        
        with patch('os.listdir') as mock_listdir:
            logger._manage_log_files()
            mock_listdir.assert_not_called()


class TestSteamCMDExecution:
    """Test SteamCMD execution function."""
    
    @pytest.mark.asyncio
    async def test_execute_steamcmd_simple_success(self):
        """Test successful SteamCMD execution."""
        mock_result = Mock()
        mock_result.stdout = "Success\\nUpdate complete"
        mock_result.stderr = ""
        
        with patch('asyncio.to_thread', return_value=mock_result):
            result = await execute_steamcmd_simple(["steamcmd", "+quit"])
            assert result == mock_result
    
    @pytest.mark.asyncio
    async def test_execute_steamcmd_simple_with_error(self):
        """Test SteamCMD execution with stderr."""
        mock_result = Mock()
        mock_result.stdout = "Output"
        mock_result.stderr = "Error occurred"
        
        with patch('asyncio.to_thread', return_value=mock_result):
            result = await execute_steamcmd_simple(["steamcmd", "+quit"])
            assert result == mock_result
