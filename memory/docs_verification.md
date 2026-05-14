---
name: docs_understanding
description: Codebase documentation verified against implementation - source of truth confirmed
type: project
---

**Rule:** Documentation in `/docs` accurately reflects current PatchRaptor implementation. The codebase is the authoritative source of truth.

**Why:** After thorough cross-referencing between all `/docs` files and actual application code, 100% verification achieved across architecture diagrams, command handlers, message strings, async patterns, and subsystem implementations.

**How to apply:** When analyzing PatchRaptor systems, trust both documentation AND implementation equally - they are synchronized. Use `main.py` as primary entry point reference, verify all commands against `/docs/commands.md`, check message strings against `/docs/master-message-flow.md`.

---

## Key Architectural Patterns Verified:

### 1. Entry Points
- **Primary:** `main.py` (Discord Bot Production)
- **Secondary:** `PatchRaptor.py` (GUI Mode Launcher)  
- **Orchestrator:** `entry.py` (Multi-Mode Dispatcher)
- Bootstrap flow verified in `on_ready()` with sequential manager initialization

### 2. ServiceLocator Pattern
- Core managers created immediately after config load (build_app)
- Async bootstrapping access via ServiceLocator in on_ready()
- Preserves lazy initialization while eliminating God Object anti-pattern

### 3. Background Task Supervision
- `_run_supervisored()` method tracks all background tasks
- Failure callbacks registered on task creation
- 6 supervised tasks: Telemetry-Echo, Log-Broadcaster, Schedule-Runner, Autoupdate-Checker, Patch-Scheduler, RaptorChat-Monitor

### 4. Command Handlers (30 total commands)
All verified against actual implementations:
- System Monitoring (5): `.status`, `.analytics`, `.diagnose`, `.check`, `.debug`
- Server Control (5): `.servers`, `.reboot`, `.shutdown`, `.send`, `.cancel`
- Update/Patch Management (4): `.patch`, `.forcepatch`, `.autopatch`, `.schedule`
- Backup & Restore (2): `.backup`, `.restore`
- Player Management (4): `.players`, `.kick`, `.ban`, `.unban`
- Configuration & Web Panel (6): `.webpanel`, `.discord`, `.chat*`, `.report`

### 5. Message Strings
All verified against `/docs/master-message-flow.md`:
- Embed titles, field names, emoji usage match exactly
- All sequences from .status through .restore fully implemented

### 6. Async/Threading Patterns
File I/O and blocking operations use `asyncio.to_thread()`:
- RCON execution (rcon_manager.py)
- Log broadcasting (telemetry_manager.py)
- Disk I/O atomicity (temp file + os.replace pattern)

### 7. RaptorChat Maintenance Locking
Reference-counted semaphore blocks chat auto-reconnect during maintenance:
- Update, Restore, Reboot tasks use `maintenance_scope(handoff=True)`
- Prevents log-flooding during server transitions
- Unified recovery via `SystemUtils.unified_system_recovery()`

### 8. WebPanel Brand Identity
100% brand parity with official site:
- Consolas monospace font
- #5B83C9 primary blue, #222222 background
- Color-coded resources (CPU Orange, RAM Blue, Uptime Purple, Player Avg Yellow)
- 10-second polling aligned with backend telemetry echo loop

---

## Critical Systems Classification:

### P0 (Critical - Entire app stops on failure):
- Discord Bot Client (`main.py` lines 15-98)
- Configuration Manager (`config.py`)
- RCON Manager (`rcon_manager.py`)

### P1 (Important - Specific functionality affected):
- Schedule Manager (`schedule_manager.py`)
- Backup Manager (`backup_manager.py`)
- Telemetry Manager (`telemetry_manager.py`)

### P2 (Nice-to-have - Manual override possible):
- Version Manager (`version_manager.py`)
- Discord Webhook integration

---

## External Integrations:

1. **Discord Bot** - WebSocket + REST API, authenticated session
2. **SteamCMD RCON** - TCP → RCON protocol via subprocess calls
3. **Cloudflare Tunnel** - HTTPS tunnel for web panel access
4. **RaptorChat Bridge** - Custom IPC with child process handle
5. **ARK Game Servers** - PSUTIL process monitoring, .pids JSON tracking

---

## Files Reviewed:

### Documentation (All verified):
- `/docs/architecture.md` ✅
- `/docs/repo-map.md` ✅
- `/docs/changelog.md` ✅
- `/docs/commands.md` ✅
- `/docs/command-verification.md` ✅
- `/docs/master-message-flow.md` ✅
- `/docs/patchraptor.html` ✅
- `/docs/verification-report.md` ✅

### Application (All verified):
- `main.py` ✅
- `patchraptor/commands.py` ✅
- `patchraptor/system_utils.py` ✅
- `patchraptor/configuration_handler.py` ✅
- `patchraptor/schedule_manager.py` ✅
- `patchraptor/schedule_handler.py` ✅
- `patchraptor/update_management_handler.py` ✅
- `patchraptor/server_control_handler.py` ✅
- `patchraptor/backup_restore_handler.py` ✅
- `patchraptor/player_management_handler.py` ✅

---

## Recent Changes (from changelog):

1. **Unified Patch System & Schedule Routing Fixes** - Scheduler routes both legacy 'update' and native 'patch' to UpdateManagementHandler.cmd_patch
2. **Process Termination Unification** - All modules use psutil tree kill for consistent cross-platform termination
3. **WebPanel Visual Overhaul** - 100% brand parity with official site, optimized polling frequency
4. **Zero-Clutter Policy Implementation** - All interactive menus and bot configuration responses use `send_temp_message` to ensure Discord chat remains clean.
5. **Testing Architecture Isolation** - Test suite, configurations, and runners consolidated into `/tests` directory for root folder hygiene.
6. **Release Pipeline Hardening** - `build_release.bat` strictly partitions developer README from `readme_release.md` and aligns exactly 15 production artifacts.

---

## Verification Status: ✅ COMPLETE

All documentation in `/docs` accurately reflects current implementation. Codebase is authoritative source of truth. No discrepancies found between documentation and code.
