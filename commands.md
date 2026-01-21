# PatchRaptor - Commands

This document provides a comprehensive guide to every command available in PatchRaptor, organized by the categories found in the interactive `.menu` dashboard.

> **Note:** All commands start with a dot (`.`).
> **Arguments:** `<required>` arguments must be provided. `[optional]` arguments can be omitted.

## Interactive Menu
### `.menu`
Opens an interactive "Clickable Dashboard" in Discord with buttons for all major categories.
- **Trigger:** Type `.menu` in the configured channel.
- **Usage:** Click the buttons to see available commands for that category (ephemeral messages).

---

## Server Monitoring
Commands to check the health and status of your servers.

### `.status`
Quick overview of system health.
- **Output:** CPU %, RAM Usage, Disk Usage, Uptime, Bot Status.

### `.servers`
Displays a detailed status report for all configured servers.
- **Output:** PC Uptime, CPU/RAM usage per server process, and Disk usage for save folders.

### `.check`
Manually checks steam for a new version.
- **Output:** Compares current build ID with latest available on SteamDB.

### `.autoupdate [on|off]`
Manages the background auto-update checker.
- **Usage:**
    - `.autoupdate`: Shows current status and background task state.
    - `.autoupdate on`: Enables auto-checker (checks every 15 minutes).
    - `.autoupdate off`: Disables auto-checker.

---

## Server Controls
Direct control over the server processes.

### `.reboot [map_name]`
Restarts the ARK servers.
- **Usage:**
    - `.reboot`: Restarts **ALL** running servers (staggered by 30s).
    - `.reboot <map_name>`: Restarts a specific server (e.g., `.reboot scorched`).
- **Process:** Stops Chat Relay -> Sends `DoExit` -> Waits for shutdown -> Starts Server -> Waits for Online -> Reconnects Chat.

### `.shutdown [map_name]`
Gracefully stops the ARK servers.
- **Usage:**
    - `.shutdown`: Stops **ALL** servers.
    - `.shutdown <map_name>`: Stops a specific server.
- **Process:** Stops Chat Relay -> Sends `DoExit` -> Waits for shutdown.

### `.cancel`
Cancels any ongoing timer or long-running operation.
- **Trigger:** Use this to abort an update countdown or scheduled operation before it triggers.

---

## Server Updates
Commands related to SteamCMD updates.

### `.update`
Starts a **Scheduled Maintenance Update** with a 15-minute countdown.
- **Process:**
    1.  Broadcasts warnings at 15m, 10m, 5m, 1m.
    2.  Shuts down all servers.
    3.  Updates via SteamCMD.
    4.  Restarts all servers.

### `.forceupdate [map_name]`
Starts an **Immediate Update** (No countdown).
- **Usage:**
    - `.forceupdate`: Updates ALL servers immediately.
    - `.forceupdate <map_name>`: Updates specific server immediately.
- **Warning:** Players will be disconnected instantly.

---

## Server Broadcasts
Send messages to players in-game.

### `.send <target> <message>`
Broacasts a message via RCON.
- **Usage:**
    - `.send all <message>`: Sends to every server in the cluster.
    - `.send <map_name> <message>`: Sends to a specific server.
- **Example:** `.send all Server restart in 10 minutes!`

---

## Player Management
Kick, ban, and track players.

### `.players [list]`
Shows player counts and details.
- **Usage:**
    - `.players`: Shows total count.
    - `.players list`: Shows names, steam IDs, and session times.

### `.kick <player_name_or_id>`
Kicks a player from **ALL** servers.
- **Usage:** `.kick Bob`

### `.ban <player_name_or_id>`
Bans a player from **ALL** servers.
- **Usage:**
    - `.ban Bob`: Bans by name.
    - `.ban 12345678901234567`: Bans by Steam ID.
- **Behavior:** Updates `bans.json` and executes `BanPlayer`.

### `.unban <player_name_or_id>`
Unbans a player from **ALL** servers.
- **Usage:** `.unban Bob` or `.unban 12345678901234567`
- **Behavior:** Removes from `bans.json` and executes `UnbanPlayer`.

---

## Webhook Settings
Customize the bot's automated announcements.

### `.webhook <get|set> <type> [message]`
Configures Discord webhook messages.
- **Usage:**
    - `.webhook set shutdown Server is shutting down!`: Custom shutdown message.
    - `.webhook set reboot Server is restarting!`: Custom reboot message.
    - `.webhook get shutdown`: View current message.

---

## Backup System
Manage your server saves.

### `.backup <target>`
Triggers a manual backup.
- **Usage:**
    - `.backup all`: Backs up ALL servers.
    - `.backup <map_name>`: Backs up a specific map.
    - `.backup amount <number>`: Sets retention count (e.g. `.backup amount 10`).

### `.restore <map_name> [index]`
Restores a previous backup.
- **Usage:**
    - `.restore <map_name>`: Lists available backups.
    - `.restore <map_name> <number>`: Restores specific backup ID.

---

## Scheduling system
Automate repetitive tasks.

### `.schedule`
Manage the task scheduler.
- **Usage:**
    - `.schedule`: Lists all active schedules.
    - `.schedule add <type> [days] <time>`: Adds a new task.
    - `.schedule clear [type]`: Removes tasks.
- **Examples:**
    - `.schedule add reboot 04:00` (Daily)
    - `.schedule add backup all mon fri 05:00` (Weekly)

---

## Advanced Settings
Configuration and deep system diagnostics.

### `.discord delete <time>`
Sets auto-delete timer for bot responses.
- **Usage:** `.discord delete 0:10` (10 mins).

### `.webpanel [on|off]`
Controls the web dashboard.
- **Usage:**
    - `.webpanel`: Status.
    - `.webpanel on`: Start web server + tunnel.
    - `.webpanel off`: Stop web server + tunnel.

### `.report`
Generates a log file report.
- **Action:** Uploads last 50 lines of logs to Discord.

### `.diagnose`
Runs a comprehensive self-health check.
- **Checks:** Permissions, API access, RCON connectivity, Config validity.

---

## RaptorChat
Manage the Discord <-> In-Game chat relay.

### `.chat <status|stop|reboot>`
Controls the chat relay process.
- **Usage:**
    - `.chat status`: Check if running.
    - `.chat reboot`: Restart the process.
    - `.chat stop`: Stop execution.
