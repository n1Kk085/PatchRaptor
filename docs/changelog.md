# Changelog

## PatchRaptor (Cherry) - 2026-05-14

### Improved
- **WebPanel Console Professionalism:** Implemented a unified logging format `[date]|INFO|[WEB]` for all web and tunnel activities.
- **Tunnel Logging Cleanup:** Intercepted and "people-ified" technical Cloudflare errors. Cryptic refresh/login stream cancellations are now silenced, and connection instability is reported in plain English.
- **Code Efficiency:** Removed ~355 lines of legacy dead logic (RaptorChat heartbeats, orphan stubs, and unreachable update methods) to streamline the codebase for production.
- **Sync & Verification:** Synchronized all architectural documentation (`architecture.md`, `repo-map.md`) and verified 100% test pass rate (583/583).

### Fixed
- **Log Noise:** Eliminated the "Scorched Earth" image cancellation logs during browser refreshes.
- **Process Lifecycle:** Unified process termination using `psutil` across the tunnel and web modules to prevent zombie executables.
- **Smoke Test:** Updated the health check to remove stale references to deprecated player-extraction methods.

---

## Fixed (2026)

### main.py::build_app() Circular Dependency & God Object Pattern
**Issue:** Created ALL managers synchronously in a single function, violating ServiceLocator lazy initialization contract and making error handling difficult.

**Resolution:** Converted to dependency injection pattern with proper initialization order:
- Core managers created immediately after config load
- ServiceLocator registered for async bootstrapping access in `on_ready()`
- Preserves existing async workflow while eliminating God Object anti-pattern
- Fixes the circular import issue between `telemetry_manager` and main bootstrap

**Impact:**
✅ Eliminates synchronous initialization of all components  
✅ Enables proper lazy initialization via ServiceLocator  
✅ Improves error handling during startup  
✅ Restores clean separation between build-time vs run-time dependencies  

---

## Files Modified
- `patchraptor/main.py` - Refactored `build_app()` to use dependency injection pattern

---

## Fixed (2026)

### Process Termination Unification - Eliminating Zombies & Inconsistent Shutdowns
**Issue:** Different modules used inconsistent termination methods (`taskkill` + hybrid `terminate() → kill()` in configuration_handler.py, direct `.kill()` in raptorchat_manager.py), causing zombie processes and platform-specific failures. GUI "Stop Bot" button used psutil tree kill, but Discord commands did not match this pattern.

**Resolution:** Standardized ALL process termination on `psutil` tree kill across the codebase:
- `configuration_handler.cmd_webpanel()`: Replaced hybrid taskkill/.terminate()/.kill() with unified psutil-based cleanup for both WebPanel.exe and cloudflared.exe
- `configuration_handler.cleanup()`: Updated final cleanup routine to use psutil for WebPanel and Tunnel termination
- `raptorchat_manager.stop()`: Added graceful 2s terminate timeout before force kill, plus child process awareness

**Impact:**
✅ All Discord commands (`.webpanel off`, `.chat stop`) now match GUI "Stop Bot" behavior  
✅ Eliminates zombie RaptorChat.exe server connections and orphaned cloudflared instances  
✅ Consistent cross-platform termination pattern across all controls  
✅ Graceful terminate attempts before force kill, reducing crash artifacts  

**Files Modified:**
- `patchraptor/configuration_handler.py` - cmd_webpanel off section + cleanup() method  
- `patchraptor/raptorchat_manager.py` - stop() method  

---

## Fixed (2026-05-08)

### Unified Patch System & Schedule Routing Fixes
**Issue:** Scheduler was calling non-existent `cmd_update` on `UpdateManagementHandler`. Scheduling logic still permitted legacy `update` event type while the rest of the system moved to `.patch`. Discord menu UI contained non-functional `.cancel` commands and inconsistent section labels.

**Resolution:** Fully synchronized the command suite and scheduling infrastructure:
- **Scheduler Fix:** Updated `ScheduleManager` to route both `update` (legacy) and `patch` events to `UpdateManagementHandler.cmd_patch`.
- **Validation Cleanup:** Updated `ScheduleHandler` to exclusively use `patch` for update tasks and removed legacy `update` validation paths.
- **UI Menu Synchronization:** Renamed Discord button menu sections to "Server Management" and "Patch Management" for consistency. Removed `.cancel` from Server Control.
- **Documentation Alignment:** Updated `commands.md` and `architecture.md` to reflect the current implementation, including the now-functional `.patch webhook` and `.schedule add patch` commands.

**Impact:**
✅ Eliminates "no attribute 'cmd_update'" runtime crashes during scheduled events  
✅ Provides a single, unified command entry point (`.patch`) for all update tasks  
✅ Synchronizes user-facing UI labels with internal documentation  
✅ Verified 31/31 scheduling and handler tests pass  

**Files Modified:**
- `patchraptor/schedule_manager.py`
- `patchraptor/schedule_handler.py`
- `patchraptor/commands.py`
- `docs/command_verification.md`
- `docs/commands.md`
- `docs/architecture.md`
- `tests/test_schedule_manager.py`
- `tests/test_schedule_handler.py`

---

## Improved (2026-05-08)

### WebPanel Visual Overhaul & Branding Alignment
**Issue:** The WebPanel dashboard was functional but visually disconnected from the `patchraptor.online` brand identity. It used inconsistent fonts, colors, and layout patterns, and client-side polling was unnecessarily high-frequency (2s).

**Resolution:** Redesigned the WebPanel frontend to achieve 100% brand parity with the official site:
- **Branding Synchronization:** Adopted `Consolas` monospace font, `#5B83C9` brand blue, and `#222222` background palette derived from the `pr_style` reference.
- **Layout Refinement:** Re-implemented the dashboard using brand-accurate components: `hero-wrapper` for cluster stats and `server-stats-grid` for individual map nodes.
- **Telemetry Optimization:** Adjusted client-side polling frequency to 10 seconds (aligned with the backend echo loop) to reduce network overhead while maintaining a "live" feel.
- **Interactive Enhancements:** Added a glowing pulse animation to the "Live" status indicator and color-coded resource metrics (Orange/Blue/Green/Purple) for improved readability.
- **Bug Fixes:** Resolved a JavaScript scoping error that occasionally prevented map cards from rendering and corrected metric property mapping (`playerAvg7day`).

**Impact:**
✅ WebPanel is now a seamless extension of the PatchRaptor brand identity  
✅ Improved visual hierarchy and readability of real-time server metrics  
✅ Reduced client-side resource usage via optimized 10s polling  
✅ Verified responsive layout across desktop and mobile viewports  

**Files Modified:**
- `static/style.css`
- `static/index.html`
- `static/dashboard.js`
- `pr_live.py` (MapImageResolver consistency)
