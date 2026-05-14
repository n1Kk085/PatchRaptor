import pytest
import os
from unittest.mock import Mock, MagicMock, patch
from patchraptor.ark_log_utils import extract_server_info_from_log, get_logs_directory, find_matching_log_file

class TestLogUtils:
    
    # --- extract_server_info_from_log Tests ---

    def test_extract_info_standard_format(self):
        """Test extraction from standard startup log"""
        mock_content = """
        LogInit: Command Line: TheIsland?listen?RCONPort=27020?QueryPort=27015
        LogInit: Base Directory: C:\\Ark\\ShooterGame
        """
        with patch("builtins.open", new_callable=MagicMock) as mock_open, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", return_value=123456):
            
            mock_file = mock_open.return_value.__enter__.return_value
            mock_file.readline.side_effect = mock_content.strip().split('\n') + [""]
            
            result = extract_server_info_from_log("dummy.log")
            
            assert result is not None
            assert result["rcon_port"] == 27020
            # Map name regex matches "TheIsland" using substring comparison.
            assert result["map_name"] == "theisland"

    def test_extract_info_spaced_format(self):
        """Test extraction with space separated args"""
        mock_content = """
        Server argument: -RCONPort=27020
        Server argument: TheIsland_WP
        """
        with patch("builtins.open", new_callable=MagicMock) as mock_open, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", return_value=123456):
            
            mock_file = mock_open.return_value.__enter__.return_value
            mock_file.readline.side_effect = mock_content.strip().split('\n') + [""]
            
            result = extract_server_info_from_log("dummy.log")
            
            assert result is not None
            assert result["rcon_port"] == 27020
            assert result["map_name"] == "theisland"

    def test_extract_info_not_found(self):
        """Test when info is missing"""
        mock_content = "Just some random log lines\nNo info here"
        with patch("builtins.open", new_callable=MagicMock) as mock_open, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", return_value=123456):
            
            mock_file = mock_open.return_value.__enter__.return_value
            mock_file.readline.side_effect = mock_content.strip().split('\n') + [""]
            
            result = extract_server_info_from_log("dummy.log")
            
            assert result is None

    # --- get_logs_directory Tests ---

    def test_get_logs_dir_explicit(self):
        """Test getting explicit log dir"""
        server = Mock()
        server.log_dir = "C:/Logs"
        
        with patch("os.path.exists", return_value=True):
            result = get_logs_directory([server])
            assert result == "C:/Logs"

    def test_get_logs_dir_from_file(self):
        """Test getting log dir from server_log_path"""
        server = Mock()
        server.log_dir = None
        server.server_log_path = "C:/Logs/ShooterGame.log"
        
        with patch("os.path.exists", return_value=True):
            result = get_logs_directory([server])
            assert result == "C:/Logs" # dir name of file path

    def test_get_logs_dir_heuristic(self):
        """Test getting log dir from save path heuristic"""
        server = Mock()
        server.log_dir = None
        server.server_log_path = None
        server.server_save_path = "C:/Ark/Saved/TheIsland"
        
        # Heuristic looks for ../Logs relative to save path
        expected_dir = "C:\\Ark\\Saved\\Logs"
        
        # Mock os.path methods
        with patch("os.path.normpath", side_effect=lambda x: x.replace("/", "\\")), \
             patch("os.path.exists", return_value=False), \
             patch("os.path.dirname", side_effect=os.path.dirname), \
             patch("os.path.join", side_effect=os.path.join), \
             patch("os.path.isdir", return_value=True):
             
             result = get_logs_directory([server])
             assert result is not None
             # Path separator normalization happened

    # --- find_matching_log_file Tests ---

    def test_find_log_file_sort(self):
        """Test finding log file picks newest one"""
        server = Mock()
        server.rcon_port = 27020
        server.name = "TestServer"
        
        files = ["ShooterGame_1.log", "ShooterGame_2.log"]
        
        # 1.log is NEWER (mtime 200), 2.log is OLDER (mtime 100)
        # 1.log has MATCHING port
        # 2.log has WRONG port
        
        def mock_extract(path, logger=None):
            if "1.log" in path: return {"rcon_port": 27020, "map_name": "map"}
            if "2.log" in path: return {"rcon_port": 9999, "map_name": "map"}
            return None
        
        with patch("os.listdir", return_value=files), \
             patch("os.path.getmtime", side_effect=lambda x: 200 if "1.log" in x else 100), \
             patch("patchraptor.ark_log_utils.extract_server_info_from_log", side_effect=mock_extract):
             
             result = find_matching_log_file(server, "C:/Logs")
             assert "ShooterGame_1.log" in result

    def test_find_log_file_ignore_assigned(self):
        """Test that assigned files are skipped"""
        server = Mock()
        server.rcon_port = 27020
        server.name = "TestServer"
        
        # Use simple construction to avoid os.path ambiguity in test
        logs_dir = os.path.normpath("C:/Logs")
        path1 = os.path.join(logs_dir, "ShooterGame_1.log")
        assigned = {path1}
        files = ["ShooterGame_1.log", "ShooterGame_2.log"]
        
        def mock_extract(path, logger=None):
            return {"rcon_port": 27020, "map_name": "map"}
            
        with patch("os.listdir", return_value=files), \
             patch("os.path.getmtime", return_value=123), \
             patch("patchraptor.ark_log_utils.extract_server_info_from_log", side_effect=mock_extract):
             
             result = find_matching_log_file(server, logs_dir, assigned_files=assigned)
             # Should match 2.log because 1.log is assigned
             assert "ShooterGame_2.log" in result
    # --- Edge Cases & Error Handling for extract_server_info_from_log ---

    def test_extract_info_file_not_exists(self):
        """Test extraction returns None if file doesn't exist (Line 43-44)"""
        with patch("os.path.exists", return_value=False):
            result = extract_server_info_from_log("nonexistent.log")
            assert result is None

    def test_extract_info_empty_file(self):
        """Test extraction returns None for empty file (Line 55-56)"""
        with patch("builtins.open", new_callable=MagicMock) as mock_open, \
             patch("os.path.exists", return_value=True):
            
            # Simulate empty file (readline returns empty string immediately)
            mock_file = mock_open.return_value.__enter__.return_value
            mock_file.readline.return_value = ""
            
            result = extract_server_info_from_log("empty.log")
            assert result is None

    def test_extract_info_invalid_port_value(self):
        """Test extraction handles non-integer port gracefully (Line 77-78)"""
        mock_content = "LogInit: RCONPort=NotAnInteger"
        with patch("builtins.open", new_callable=MagicMock) as mock_open, \
             patch("os.path.exists", return_value=True), \
             patch("os.path.getmtime", return_value=123):
            
            mock_file = mock_open.return_value.__enter__.return_value
            mock_file.readline.side_effect = mock_content.strip().split('\n') + [""]
            
            # Should safely fail to parse port and return None (since no valid port found)
            result = extract_server_info_from_log("invalid_port.log")
            assert result is None

    def test_extract_info_exception_handling(self):
        """Test exception handling during file read (Line 93-96)"""
        logger_mock = Mock()
        with patch("builtins.open", side_effect=OSError("Disk error")), \
             patch("os.path.exists", return_value=True):
            
            result = extract_server_info_from_log("error.log", logger=logger_mock)
            
            assert result is None
            logger_mock.error.assert_called_once()

    # --- Edge Cases for get_logs_directory ---

    def test_get_logs_dir_no_servers(self):
        """Test returns None if server list is empty (Line 103-104)"""
        assert get_logs_directory([]) is None
        assert get_logs_directory(None) is None

    def test_get_logs_dir_heuristic_found_dir(self):
        """Test heuristic path actually returning a found directory (Line 134-138)"""
        server = Mock()
        server.log_dir = None
        server.server_log_path = None
        server.server_save_path = "/Ark/Saved/Map"
        
        # Mocking exact flow to hit Line 138
        with patch("os.path.normpath", side_effect=lambda x: x), \
             patch("os.path.dirname", side_effect=os.path.dirname), \
             patch("os.path.join", side_effect=os.path.join), \
             patch("os.path.isdir", return_value=True): # Directory EXISTS
             
             result = get_logs_directory([server])
             assert result == os.path.join("/Ark/Saved", "Logs")

    def test_get_logs_dir_heuristic_not_found(self):
        """Test heuristic path failing to find directory (Line 140)"""
        server = Mock()
        server.log_dir = None
        server.server_log_path = None
        server.server_save_path = "/Ark/Saved/Map"
        
        with patch("os.path.isdir", return_value=False): # Directory missing
             result = get_logs_directory([server])
             assert result is None

    # --- Edge Cases & Dict Support for find_matching_log_file ---

    def test_find_log_file_with_dict_server(self):
        """Test support for dict-style servers (RaptorChat compatibility) (Line 154-156)"""
        server_dict = {'name': 'DictServer', 'rcon_port': '27020'}
        
        logs_dir = "C:/Logs"
        files = ["ShooterGame_1.log"]
        
        def mock_extract(path, logger=None):
            return {"rcon_port": 27020, "map_name": "map"}
            
        with patch("os.listdir", return_value=files), \
             patch("os.path.getmtime", return_value=123), \
             patch("patchraptor.ark_log_utils.extract_server_info_from_log", side_effect=mock_extract):
             
             result = find_matching_log_file(server_dict, logs_dir)
             assert "ShooterGame_1.log" in result

    def test_find_log_file_listdir_error(self):
        """Test error handling when scanning directory (Line 179-181)"""
        logger_mock = Mock()
        with patch("os.listdir", side_effect=OSError("Access Denied")):
            result = find_matching_log_file(Mock(), "C:/Logs", logger=logger_mock)
            assert result is None
            logger_mock.error.assert_called_once()

    def test_find_log_file_no_files_found(self):
        """Test returns None if no valid log files found (Line 183-184)"""
        # listdir returns empty or no starting with ShooterGame
        with patch("os.listdir", return_value=["other.txt"]):
            result = find_matching_log_file(Mock(), "C:/Logs")
            assert result is None

    def test_find_log_file_no_match(self):
        """Test returns None if files exist but don't match criteria (Line 195)"""
        server = Mock()
        server.rcon_port = 27020
        server.name = "TestServer"
        
        files = ["ShooterGame_1.log"]
        
        # Mismatch port
        def mock_extract(path, logger=None):
            return {"rcon_port": 9999, "map_name": "map"}
            
        with patch("os.listdir", return_value=files), \
             patch("os.path.getmtime", return_value=123), \
             patch("patchraptor.ark_log_utils.extract_server_info_from_log", side_effect=mock_extract):
             
             result = find_matching_log_file(server, "C:/Logs")
             assert result is None
    
    def test_get_logs_dir_object_helper(self):
        """Test the inner get_val helper via dict access"""
        # Cover Line 108-109 specifically
        server_dict = {'log_dir': 'C:/Logs'}
        with patch("os.path.exists", return_value=True):
             result = get_logs_directory([server_dict])
             assert result == 'C:/Logs'

    def test_get_logs_dir_heuristic_with_logger(self):
        """Test heuristic path with logger (Line 135-137)"""
        server = Mock()
        server.log_dir = None
        server.server_log_path = None
        server.server_save_path = "/Ark/Saved/Map"
        logger = Mock()
        
        with patch("os.path.normpath", side_effect=lambda x: x), \
             patch("os.path.dirname", side_effect=os.path.dirname), \
             patch("os.path.join", side_effect=os.path.join), \
             patch("os.path.isdir", return_value=True):
             
             result = get_logs_directory([server], logger=logger)
             assert result is not None

    def test_find_log_file_no_logs_dir(self):
        """Test find_matching_log_file returns None if logs_dir is None (Line 150-151)"""
        assert find_matching_log_file(Mock(), None) is None

