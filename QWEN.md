# QWEN.md - PatchRaptor Development Context

## Project Overview

**PatchRaptor** is a production-oriented automation toolkit for managing **ARK: Survival Ascended** dedicated server clusters. It provides Discord-based control, automated patching, backups, player management, cross-server chat relay (RaptorChat), and a branded web dashboard.

**Key Characteristics:**
- **Source-available software** - Full source code available for security auditing
- **Windows-focused** - Targets Windows Server 2019/2022 and Windows 10/11
- **Manual deployment** - No CI/CD, deployed via direct execution
- **Production-critical** - Manages real game servers in operational environments

---

## Core Architecture

### Entry Points (Level 1 → Level 2)

| Entry Point | File Path | Mode | Purpose |
|-------------|-----------|------|---------|
| `main.py` | Root | Discord Bot (Primary Production) | Async Discord client with supervised background tasks |
| `PatchRaptor.py` | Root | GUI Wrapper | Tkinter/CustomTkinter launcher for config and monitoring |
| `entry.py` | `patchraptor/` | Multi-Mode Orchestrator | Dispatches to gui/bot/chat/web modes (future) |

### Execution Flow Hierarchy

```
Level 1: entry.py (Future dispatcher)
└── Level 2: Mode-specific entries
    ├── main.py ← DISCORD BOT PRODUCTION ENTRY
    ├── PatchRaptor.py ← GUI application entry
    ├── RaptorChat.py ← Chat maintenance subprocess
    └── pr_live.py ← Web panel interface

Level 3: Bootstrap Chain (for main.py)
├── ConfigManager initialization
├── ServiceLocator registration
├── DiscordClient instantiation  
└── on_ready() bootstrap sequence
```

---

## Core Modules (`patchraptor/` Package)

### Critical Systems (P0 - Application Stops If Failed)

| Component | File | Responsibility | State Type |
|-----------|------|----------------|------------|
| `ConfigManager` | `config.py` | Runtime config loading/validation | Dict + ServerConfig[] list |
| `DiscordClient` | `main.py` | Bot lifecycle, message routing | Authenticated WebSocket client |
| `RCONManager` | `rcon_manager.py` | TCP→RCON protocol execution | Ephemeral subprocess calls |

### Operational Systems (P1 - Manual Override Available)

| Component | File | Responsibility | State Type |
|-----------|------|----------------|------------|
| `ScheduleManager` | `schedule_manager.py` | Task queue & timing | schedule.json file |
| `BackupManager` | `backup_manager.py` | Archive creation & retention | Disk path + backup.txt log |
| `TelemetryManager` | `telemetry_manager.py` | Metrics collection, state broadcast | cluster_live.json (atomic writes) |

### Integration Systems (P2 - Manual Workarounds Exist)

| Component | File | Responsibility | External Dependency |
|-----------|------|----------------|---------------------|
| `VersionManager` | `version_manager.py` | Steam version resolution | SteamCMD logs |
| `RaptorChatManager` | `raptorchat_manager.py` | Cross-cluster chat relay | RaptorChat.exe subprocess |

---

## Runtime Architecture

### Background Task Supervision

All background tasks are supervised via `_run_supervisored()` wrapper in `main.py`:

```python
# Pattern: Fire-and-forget with callback monitoring
async def _run_supervisored(self, coro, task_name):
    task = asyncio.create_task(coro)
    task.set_name(task_name)
    self.background_tasks.append(task)
    
    # Failure callback registered on creation
    def _handle_done(t):
        if t.exception():
            logger.error_system(f"Critical background task '{task_name}' failed: {t.exception()}")
```

**Supervised Tasks List:**
- `Telemetry-Echo` (10s interval)
- `Log-Broadcaster` (2s interval, Zero-Drift parsing)
- `Schedule-Runner` (shutdown/reboot/patch/backup)
- `Autoupdate-Checker` (if enabled)
- `RaptorChat-Monitor` (delayed 15s startup)

### Async/Threading Pattern

```python
# Blocking operations MUST use asyncio.to_thread()
result = await asyncio.to_thread(subprocess.run, cmd_args, ...)

# File I/O uses atomic temp file + os.replace() pattern
def _sync_save(self):
    temp_file = self.data_file + ".tmp"
    with open(temp_file, 'w') as f:
        json.dump(self.data, f)
    os.replace(temp_file, self.data_file)  # Atomic O(1) rename
```

---

## Configuration System

### Config Structure (`config.json`)

```json
{
  "bot_token": "...",
  "channel_id": "...",
  "steamcmd_path": "C:\\Path\\To\\steamcmd.exe",
  "server_dir": "C:\\Path\\To\\Server",
  "rcon_tool": "C:\\Path\\To\\rcon.exe",
  "app_id": "2430930",
  "cluster_servers": [
    {
      "name": "island",
      "display_name": "The Island",
      "map_abbrev": "TI",
      "rcon_ip": "127.0.0.1",
      "rcon_port": 27015,
      "rcon_password": "...",
      "start_command": "...",
      "server_save_path": "...",
      "server_log_path": "..."
    }
  ]
}
```

**Validation Rules:**
- Required keys: `bot_token`, `channel_id`, `app_id`, `steamcmd_path`, `server_dir`, `cluster_servers`, `rcon_tool`
- Default patch settings auto-populated if missing

---

## Service Locator Pattern

All managers registered in `ServiceLocator` for cross-module access:

```python
# Registration pattern (main.py — managers registered in main() at startup)
ServiceLocator.register("ConfigManager", config)
ServiceLocator.register("ServerManager", server_manager)
ServiceLocator.register("RCONManager", rcon_manager)
ServiceLocator.register("VersionManager", version_manager)
ServiceLocator.register("BackupManager", backup_manager)
# ... and more

# Access pattern (any module)
from patchraptor.service_locator import ServiceLocator
player_manager = ServiceLocator.get("PlayerManager")
```

---

## Commands Documentation Summary

### System Monitoring
- `.status` - Host hardware metrics
- `.analytics` - 7-day performance trends  
- `.diagnose` - Health check run
- `.check` - Steam update query
- `.debug on|off` - Diagnostic logging toggle

### Server Control
- `.servers` - Live usage/save sizes per map
- `.reboot [map]` - Graceful restart all/specific
- `.shutdown [map]` - Graceful stop all/specific
- `.send <target> "<msg>"` - RCON broadcast
- `.cancel` - Abort active operations

### Update Management
- `.patch` - Start graceful patch (15 min default)
- `.forcepatch` - Immediate update
- `.autopatch on|off` - Toggle auto-updates
- `.schedule add <type> <time>` - Create task

### Backup & Restore
- `.backup [all|<map>]` - Archive save data
- `.restore <map> [<num>]` - List/restore backup

### Player Management
- `.players` / `.players list` - Active player count/detail
- `.kick <player>` - Disconnect player
- `.ban <player>` - Ban across cluster
- `.unban <player>` - Lift ban

### Configuration
- `.webpanel on|off` - Control web panel
- `.discord delete H:MM` - Message deletion time
- `.chat status|reboot|stop` - Chat relay control
- `.report` - Generate log report

---

## Build & Deployment Workflow

### Source Installation
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run Configurator (generates config.json)
python Configurator.py

# 3. Launch GUI or bot directly
python PatchRaptor.py    # GUI mode
python main.py          # Headless bot mode
```

### Compiled Build (`dist/`)
- `PatchRaptor.exe` - Main application executable
- `Configurator.exe` - Self-extracting config app  
- `Instinct.exe` - Installer builder
- `RaptorChat.exe` - Chat module executable
- `WebPanel.exe` - Web panel executable

---

## External Integrations

| Integration | Protocol | Connection Type | State Persistence |
|-------------|----------|-----------------|-------------------|
| Discord Bot | WebSocket + REST | Authenticated session | Client object |
| SteamCMD RCON | TCP → RCON | Subprocess per command | None (ephemeral) |
| Cloudflare Tunnel | HTTPS | Background process | Config file path |
| RaptorChat | Custom IPC | Child subprocess | Child process handle |
| ARK Game Servers | Filesystem | PSUTIL process monitor | `.pids` JSON tracking |

---

## Logging System

Four logger levels in `log_manager.py`:

```python
logger.debug_system()    # Fine-grained bootstrap/debug info
logger.info_system()     # Major operational events (default)
logger.warning_system()  # Non-critical issues requiring attention  
logger.error_system()    # Critical failures needing intervention
logger.debug_rcon()      # RCON protocol debugging only
```

**Default log level:** INFO (DEBUG requires `.debug on` command)

---

## Testing Strategy

### Test Location
All tests in `tests/` directory:

- `test_*.py` - Individual component tests
- `smoke_test.py` - Integration smoke tests
- `conftest.py` - Pytest fixtures (Discord mock, RCON stubs)

### Running Tests
```bash
# Basic test run
python run_tests.bat

# With coverage
python run_tests_with_coverage.bat
```

**Coverage target:** Core modules only (no integration test dependencies)

---

## Production Environment Reality

- **NOT executed on primary dev workstation** - Separate Windows 11 production machine
- **Manual deployment** - Direct file copy and execution
- **No CI/CD pipeline** - Manual validation required
- **Development ≠ Production** - Never assume local availability

---

## Key Design Constraints

### Preservation Rules
- **Preserve existing behavior** - Do not simplify complex logic without verification
- **Task scope isolation** - Only modify systems directly relevant to requested task
- **Implementation authoritative** - Code beats documentation if conflict exists
- **Minimal targeted changes** - Prefer extending over rewriting

### Change Verification Requirements (Before finalizing)
1. Imports remain valid
2. Modified execution paths still function  
3. Existing command flows intact
4. Config compatibility preserved
5. Async/threading behavior unaffected
6. Logging/error handling intact
7. External integrations receive expected data
8. No unrelated regressions

---

## Sensitive Systems (Extra Caution Required)

- License validation (`license_manager.py`)
- Windows registry interaction (not used currently)
- Discord bot initialization (`main.py` on_ready())
- RCON communication (`rcon_manager.py`)
- SteamCMD interaction (`version_manager.py`)
- Startup/bootstrap flow (`main()` in main.py)
- Config loading/saving (`ConfigManager`)
- Scheduler systems (`ScheduleManager`, `ScheduleHandler`)
- Async/threading systems (all managers using `asyncio.to_thread()`)
- Network operations (Discord/Webhook, Cloudflare tunnel)

---

## File Structure Quick Reference

```
.                                    # Root directory
├── main.py                          # Discord bot entry (production primary)
├── PatchRaptor.py                   # GUI wrapper
├── Configurator.py                  # Config generator utility
├── pr_live.py                       # Web panel server
├── patchraptor/                     # Core Python package
│   ├── config.py                    # Configuration management
│   ├── log_manager.py               # Logging abstraction
│   ├── rcon_manager.py              # RCON protocol execution
│   ├── server_manager.py            # Server topology management
│   ├── version_manager.py           # Steam version resolution
│   ├── backup_manager.py            # Backup/restore operations
│   ├── schedule_manager.py          # Task scheduling
│   ├── discord_manager.py           # Discord API integration
│   ├── player_manager.py            # Player data tracking
│   ├── raptorchat_manager.py        # Chat relay management
│   ├── telemetry_manager.py         # Metrics collection
│   ├── commands.py                  # Command routing
│   └── service_locator.py           # Dependency injection
├── tests/                           # Unit test suite
├── RaptorChat/                      # Chat relay module
├── static/                          # Web panel assets
├── docs/                            # System documentation
└── requirements*.txt                # Python dependencies
```

---

## Memory System Guidance

When working on this codebase, use the memory system at `memory/` for:

- **User feedback** about approach corrections or confirmations
- **Project context** like current release goals or active bugs  
- **Reference pointers** to external systems (Linear tickets, Grafana dashboards)

**DO NOT store in memory:**
- Code patterns (read from code directly)
- Git history (use `git log`)
- Current debugging solutions (ephemeral to conversation)
- Things already documented in QWEN.md or AGENTS.md

---

## Quick Start Checklist

### First-Time Setup
1. Read `/docs/architecture.md` and `/docs/repository_map.md`
2. Run `python Configurator.py` to generate `config.json`
3. Test with `python main.py` in headless mode
4. Verify `.diagnose` command works after bot starts

### Daily Operations
- Use `.status` for quick health check
- Use `.diagnose` before major operations
- Check telemetry history in web panel when troubleshooting

---

## Related Files

- `AGENTS.md` - Agent operating rules (read before complex tasks)
- `/docs/architecture.md` - Architecture audit report  
- `/docs/repository_map.md` - Complete folder structure
- `/docs/commands.md` - Full command reference
- `features.md` - Feature set overview
- `testing.md` - Testing documentation

---

*Generated for Qwen Code assistant context. Reference PatchRaptor source truth at `patchraptor/` package.*
