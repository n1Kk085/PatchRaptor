# PatchRaptor Discord Commands Reference

**Version:** 2.0 (Accurate Implementation-Based)  
**Last Updated:** Verification against source code implementation  
**Status:** All commands verified against actual handler implementations  

---

## 📋 Command Index (30 Total Commands)

| Category | Commands |
|----------|----------|
| 🔍 **System Monitoring** | `.status`, `.analytics`, `.diagnose`, `.check`, `.debug` |
| ⚙️ **Server Control** | `.servers`, `.reboot`, `.shutdown`, `.send`, `.cancel` |
| 🦖 **Update/Patch Management** | `.patch`, `.forcepatch`, `.autopatch`, `.schedule` |
| 💾 **Backup & Restore** | `.backup`, `.restore` |
| 👥 **Player Management** | `.players`, `.kick`, `.ban`, `.unban` |
| 🎛️ **Configuration & Web Panel** | `.webpanel`, `.discord`, `.chat status/reboot/stop`, `.report` |

---

## 🔍 System Monitoring Commands

### `.status`
- **Description:** View host hardware load and health metrics
- **Handler:** [`system_monitoring_handler.py`](./patchraptor/system_monitoring_handler.py)
- **Examples:**
  ```
  .status
  ```

### `.analytics`
- **Description:** View 7-day performance and player trends
- **Handler:** [`system_monitoring_handler.py`](./patchraptor/system_monitoring_handler.py)
- **Examples:**
  ```
  .analytics
  ```

### `.diagnose`
- **Description:** Run internal system health check
- **Handler:** [`system_monitoring_handler.py`](./patchraptor/system_monitoring_handler.py)
- **Examples:**
  ```
  .diagnose
  ```

### `.check`
- **Description:** Query SteamCMD for pending updates
- **Handler:** [`system_monitoring_handler.py`](./patchraptor/system_monitoring_handler.py)
- **Examples:**
  ```
  .check
  .check update
  ```

### `.debug`
- **Description:** Toggle diagnostic logging mode
- **Handler:** [`system_monitoring_handler.py`](./patchraptor/system_monitoring_handler.py)
- **Examples:**
  ```
  .debug on
  .debug off
  ```

---

## ⚙️ Server Control Commands

### `.servers`
- **Description:** Get live usage and save sizes per map
- **Handler:** [`server_control_handler.py`](./patchraptor/server_control_handler.py)
- **Examples:**
  ```
  .servers
  ```

### `.reboot`
- **Description:** Gracefully restart all servers or specific map
- **Handler:** [`server_control_handler.py`](./patchraptor/server_control_handler.py)
- **Examples:**
  ```
  .reboot                    # Restart all servers
  .reboot <map>              # Restart specific server (e.g., .reboot scorched)
  ```

### `.shutdown`
- **Description:** Gracefully stop all servers or specific map
- **Handler:** [`server_control_handler.py`](./patchraptor/server_control_handler.py)
- **Examples:**
  ```
  .shutdown                  # Shutdown all servers
  .shutdown <map>            # Shutdown specific server
  ```

### `.send`
- **Description:** Send global announcements to in-game players via RCON
- **Handler:** [`server_control_handler.py`](./patchraptor/server_control_handler.py)
- **Examples:**
  ```
  .send all "Server maintenance starting soon!"        # All servers
  .send scorched "Please logout and save your progress"  # Specific server
  ```

### `.cancel`
- **Description:** Abort any active server operation (reboots, shutdowns). Note: standard graceful reboots and shutdowns are non-interruptible once the countdown finishes.
- **Handler:** [`server_control_handler.py`](./patchraptor/server_control_handler.py)
- **Examples:**
  ```
  .cancel                   # Cancel any active operation
  ```

---

## 🦖 Update & Patch Management Commands

### `.patch`
- **Description:** Start graceful patch with countdowns
- **Handler:** [`update_management_handler.py`](./patchraptor/update_management_handler.py)
- **Subcommands:**
  - `.patch` — Start patch with countdown
  - `.patch status` — Display current configuration
  - `.patch timer <minutes>` — Set countdown timer (e.g., `.patch timer 15`)
  - `.patch broadcast "<message>"` — Set RCON broadcast template using `{minutes}` placeholder
  - `.patch intervals <list>` — Set countdown interval times (e.g., `.patch intervals 15,10,5,1`)
  - `.patch webhook <shutdown|reboot> <message>` — Configure Discord notifications for standard maintenance
- **Examples:**
  ```
  .patch                    # Start default patch (15 min timer)
  .patch status             # View current configuration
  .patch timer 20           # Set 20-minute countdown
  .patch broadcast "Save your progress! Maintenance in {minutes} minutes."
  .patch intervals 20,15,10,5,1  # Custom intervals
  .patch webhook reboot "Patch complete! Cluster is back online."
  ```

### `.forcepatch`
- **Description:** Instantly force patch without countdown
- **Handler:** [`update_management_handler.py`](./patchraptor/update_management_handler.py)
- **Examples:**
  ```
  .forcepatch               # Immediate update (no countdown)
  ```

### `.autopatch`
- **Description:** Toggle automatic background SteamCMD updates
- **Handler:** [`update_management_handler.py`](./patchraptor/update_management_handler.py)
- **Examples:**
  ```
  .autopatch                # Check current status
  .autopatch on             # Enable automatic updates
  .autopatch off            # Disable automatic updates
  ```

---

## 💾 Backup & Restore Commands

### `.backup`
- **Description:** Archive server save data for specific map or all servers
- **Handler:** [`backup_restore_handler.py`](./patchraptor/backup_restore_handler.py)
- **Subcommands:**
  - `.backup all` — Archive all servers
  - `.backup <map>` — Archive specific server
  - `.backup amount <num>` — Set number of retained backups
- **Examples:**
  ```
  .backup all               # Backup all servers immediately
  .backup scorched          # Backup specific server
  .backup amount 3          # Keep last 3 backup versions
  ```

### `.restore`
- **Description:** List and restore archives for a specific server
- **Handler:** [`backup_restore_handler.py`](./patchraptor/backup_restore_handler.py)
- **Examples:**
  ```
  .restore scorched                     # List available backups
  .restore scorched 3                   # Restore backup #3 (stops, restores, restarts)
  ```

---

## 👥 Player Management Commands

### `.players`
- **Description:** Show total active players across cluster
- **Handler:** [`player_management_handler.py`](./patchraptor/player_management_handler.py)
- **Subcommands:**
  - `.players` — Total count
  - `.players list` — Detailed player info per server
- **Examples:**
  ```
  .players           # Show total active players
  .players list      # Detailed player information
  ```

### `.kick`
- **Description:** Disconnect player from all servers
- **Handler:** [`player_management_handler.py`](./patchraptor/player_management_handler.py)
- **Examples:**
  ```
  .kick <player>        # e.g., .kick Steve or .kick 123456789 (SteamID)
  ```

### `.ban`
- **Description:** Ban player across cluster (Name or SteamID)
- **Handler:** [`player_management_handler.py`](./patchraptor/player_management_handler.py)
- **Examples:**
  ```
  .ban <player>         # e.g., .ban Steve or .ban STEAM_0:1:123456789
  ```

### `.unban`
- **Description:** Lift ban across cluster (Name or SteamID)
- **Handler:** [`player_management_handler.py`](./patchraptor/player_management_handler.py)
- **Examples:**
  ```
  .unban <player>       # e.g., .unban Steve or .unban STEAM_0:1:123456789
  ```

---

## 🎛️ Configuration & Web Panel Commands

### `.webpanel`
- **Description:** Control web panel tunnel and connection status
- **Handler:** [`configuration_handler.py`](./patchraptor/configuration_handler.py)
- **Subcommands:**
  - `.webpanel` — Check status (Online/Offline)
  - `.webpanel on` — Launch web server and open tunnel
  - `.webpanel off` — Shut down web server and close tunnel
- **Examples:**
  ```
  .webpanel              # Check if online
  .webpanel on           # Start web panel (uses Cloudflare tunnel if available)
  .webpanel off          # Stop web panel
  ```

### `.discord`
- **Description:** Set auto-deletion time for bot messages
- **Handler:** [`configuration_handler.py`](./patchraptor/configuration_handler.py)
- **Subcommands:**
  - `.discord delete <time>` — Set deletion time (H:MM format)
  - `.discord delete` — Show current setting
- **Examples:**
  ```
  .discord delete 0:05             # Delete messages after 5 minutes
  .discord delete 24:00            # Delete messages after 24 hours
  .discord delete                  # View current setting
  ```

### `.chat status`
- **Description:** View health of the chat relay service (RaptorChat)
- **Handler:** [`configuration_handler.py`](./patchraptor/configuration_handler.py) / [`raptorchat_manager.py`](./patchraptor/raptorchat_manager.py)
- **Examples:**
  ```
  .chat status                    # Check if RaptorChat is online/offline
  ```

### `.chat reboot`
- **Description:** Forcefully restart the RaptorChat relay service
- **Handler:** [`configuration_handler.py`](./patchraptor/configuration_handler.py) / [`raptorchat_manager.py`](./patchraptor/raptorchat_manager.py)
- **Examples:**
  ```
  .chat reboot                    # Restart chat relay
  ```

### `.chat stop`
- **Description:** Disconnect the chat relay service
- **Handler:** [`configuration_handler.py`](./patchraptor/configuration_handler.py) / [`raptorchat_manager.py`](./patchraptor/raptorchat_manager.py)
- **Examples:**
  ```
  .chat stop                      # Stop chat relay
  ```

### `.report`
- **Description:** Generate a downloadable system log report
- **Handler:** [`system_monitoring_handler.py`](./patchraptor/system_monitoring_handler.py)
- **Examples:**
  ```
  .report                        # Generate and download log report
  ```

---

## 📅 Scheduling Commands (⚠️ ACCURATE IMPLEMENTATION)

### `.schedule`
- **Description:** View active scheduled tasks
- **Handler:** [`schedule_handler.py`](./patchraptor/schedule_handler.py)
- **Subcommands:**
  - `.schedule` — List all scheduled events
  - `.schedule add <type> <time>` — Create new task (requires arguments)
  - `.schedule clear [all|<type>]` — Remove scheduled tasks
- **Examples:**
  ```
  .schedule                        # View current schedule

  .schedule add shutdown 03:00     # Daily shutdown at 3 AM
  .schedule add backup all 02:00   # Daily backup at 2 AM
  .schedule add reboot scorched sun 04:00    # Weekly reboot of scorched on Sunday

  .schedule clear                  # Remove all tasks
  .schedule clear shutdown         # Remove only shutdown tasks
  .schedule clear backup           # Remove only backup tasks
  ```

- **Valid Event Types:** `shutdown`, `reboot`, `patch`, `backup`
- **Time Format:** HH:MM (24-hour format, e.g., `03:00`)
- **Scheduling Notes:** 
  - `daily` is default if no days specified
  - Specific days: `mon tue wed thu fri sat sun`
  - For backup: specify target (`all` or map name)

---


---

## 🚀 Command Suite Synchronization

The command suite is strictly synchronized between the `CommandHandler` and documentation. Use `.patch status` to verify your active settings at any time.

---

## 🔄 Command Menu (`.menu`)

```
.menu  # Opens interactive UI menu with categorized buttons
```

The `.menu` command opens a Discord button grid organized into 10 sections corresponding to the categories listed above. Use this for quick navigation when you're unsure which command you need.

---

## 📊 Summary Statistics

| Category | Commands Count | Primary Handler File(s) |
|----------|----------------|-------------------------|
| System Monitoring | 5 | `system_monitoring_handler.py` |
| Server Control | 5 | `server_control_handler.py`, `update_management_handler.py` |
| Update & Patch | 4 | `update_management_handler.py` |
| Backup & Restore | 2 | `backup_restore_handler.py` |
| Player Management | 4 | `player_management_handler.py` |
| Configuration & Web Panel | 6 | `configuration_handler.py`, `raptorchat_manager.py` |
| Scheduling | 3 | `schedule_handler.py` |
| **Total** | **29** + `.menu` | **8 distinct handler files** |

---

## ✅ Verification Notes (Implementation vs. Documentation)

### ✅ Correct (Matched Implementation):
1. All core commands match actual handler implementations
2. File associations are accurate to source code
3. Command syntax aligns with runtime behavior
4. `.patch webhook` and `.schedule patch` are the primary management controls

### ⚠️ Deprecated (Removed):
1. **`.schedule add update`** — Replaced by `.schedule add patch` for consistency.

---

## 📁 Associated Files Hierarchy

```
patchraptor/
├── commands.py                          # Command routing & menu UI
├── system_monitoring_handler.py        (.status, .analytics, .diagnose, .check, .debug, .report)
├── server_control_handler.py           (.servers, .reboot, .shutdown, .send, .cancel)
├── update_management_handler.py        (.patch*, .forcepatch, .autopatch)
├── backup_restore_handler.py           (.backup, .restore)
├── player_management_handler.py        (.players, .kick, .ban, .unban)
├── configuration_handler.py            (.webpanel*, .discord*, .chat*)
├── schedule_handler.py                 (.schedule add/clear/view)
├── raptorchat_manager.py               (used by .chat commands via configuration_handler.py)
└── service_locator.py                  # Cross-module access for ScheduleManager, etc.
```

---

## 🚀 Quick Reference Card

```bash
# Server Control
.servers              # Status of all servers
.reboot               # Restart all
.shutdown             # Stop all
.send "Hello"         # Broadcast to all
.cancel               # Cancel any operation

# Patch Management
.patch                # Start patch (15 min default)
.forcepatch           # Immediate update
.autopatch on|off     # Enable/disable auto-updates
.schedule add backup all 02:00   # Schedule daily backup at 2 AM

# Player Management
.players              # Active player count
.players list         # Detailed info
.kick <player>        # Disconnect player
.ban <player>         # Ban player
.unban <player>       # Unban player

# Configuration
.webpanel on|off      # Control web panel
.discord delete 0:05  # Set message deletion time
.chat status          # Check chat relay
.backup all           # Backup all servers
.restore <map>        # List/restore backups