# Testing & Coverage Guide

This document explains how to test PatchRaptor to ensure stability and reliability. We use **pytest** for testing and **pytest-cov** for analyzing code coverage.

## 🧪 Quick Start

### 1. Install Dependencies
Before running tests, ensure you have the development requirements installed:
```bash
pip install -r requirements-dev.txt
```

### 2. Run All Tests
To run the full test suite and verify everything is working:
```bash
run_tests.bat
```
*This executes `pytest -v` to show detailed pass/fail results for each test.*

### 3. Run Tests with Coverage
To see how much of the code is actually being tested:
```bash
run_tests_with_coverage.bat
```
*This runs the tests and generates an HTML report showing exactly which lines of code were executed.*

---

## 📊 Understanding Coverage

**"Code Coverage"** measures what percentage of your source code is executed when the tests run.

-   **High Coverage (80%+)**: Most of your code is being tested. This reduces bugs and makes refactoring safer.
-   **Low Coverage**: Large parts of your application are untested. Bugs could hide in these "dark" areas.

### Viewing the Report
After running `run_tests_with_coverage.bat`, a folder named `htmlcov` is created.
-   Open `htmlcov/index.html` in your browser.
-   Click on any file to see it line-by-line.
    -   **Green Lines**: Code that ran during tests (Verified).
    -   **Red Lines**: Code that did *not* run (Untested/Dead code).

---

## 🧩 Test Structure

Tests are located in the `tests/` directory and mirror the structure of the main application.

| Test File | Component Tested |
| :--- | :--- |
| `test_backup_manager.py` | Creating zips, restoring backups, managing retention. |
| `test_backup_restore_handler.py` | Handlers for backup/restore operations. |
| `test_commands.py` | Discord command logic and permissions. |
| `test_config.py` | Loading/saving JSON settings and default values. |
| `test_configuration_handler.py` | Managing system configuration updates. |
| `test_discord_manager.py` | Sending alerts and handling webhook formatting. |
| `test_exceptions.py` | Custom error handling and exception classes. |
| `test_license_manager.py` | License verification and EULA handling. |
| `test_log_manager.py` | Log rotation, file creation, and management. |
| `test_log_utils.py` | Utilities for parsing and filtering logs. |
| `test_player_management_handler.py` | Handlers for player-related actions (kick/ban). |
| `test_player_manager.py` | Parsing log files for player joins/leaves, RCON lists. |
| `test_pr_live_*.py` | Tests for the `pr_live` web dashboard (routes, helpers, baselines). |
| `test_raptorchat_manager.py` | In-game chat relay system and log parsing. |
| `test_raptorchat_utils.py` | Helper functions for chat formatting and processing. |
| `test_rcon_manager.py` | RCON connection management and command execution. |
| `test_schedule_handler.py` | Execution logic for scheduled tasks. |
| `test_schedule_manager.py` | Parsing cron-like schedules (e.g., "Mon Wed Fri 04:00"). |
| `test_server_control_handler.py` | Handlers for starting, stopping, and restarting servers. |
| `test_server_manager.py` | Process detection and server lifecycle management. |
| `test_system_monitoring_handler.py` | Monitoring CPU/RAM usage and system health. |
| `test_update_management_handler.py` | Auto-update logic for SteamCMD and server files. |
| `test_version_manager.py` | Version checking and update comparison logic. |
### Configuration
-   **`pytest.ini`**: Configuration file for pytest (sets paths, warning filters).
-   **`conftest.py`**: Shared test fixtures (e.g., mock servers, fake config data) used across multiple tests.
