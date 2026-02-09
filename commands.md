# PatchRaptor - Commands

This document provides a comprehensive guide to every command available in PatchRaptor, organized by the categories found in the interactive `.menu` dashboard.

> **Note:** All commands start with a dot (`.`).
> **Arguments:** `<required>` arguments must be provided. `[optional]` arguments can be omitted.

## Interactive Menu
### `.menu`
Opens an interactive "Clickable Dashboard" in Discord with buttons for all major categories. `.menu` is the only command that you need to remember!
- **Trigger:** Type `.menu` in the configured channel.
- **Usage:** Click the category buttons to see all available commands, how to trigger them and a brief description of what they do.

---

## Server Monitoring
Commands to check the health and status of your servers.

### `.status`
Quick overview of Host System Health.
- **Output:** System Status, Host Uptime, System CPU %, RAM Usage and Disk Usage.

### `.servers`
Displays a detailed status report for all configured servers.
- **Output:** Map Name, Server uptime, CPU/RAM usage per server process, and save folder size for each map.

### `.check`
Manually checks steam for a new version.
- **Output:** Compares current build ID (saved in version.txt) with latest available on SteamDB.

### `.autoupdate [on|off]`
Manages the background auto-update checker.
- **Usage:**
    - `.autoupdate`: Shows current status and background task state. (.autoupdate is on by default. The first time you launch PatchRaptor the autoupdate checker will run after 10 minutes, find no version.txt, assume there is an update and trigger the `.update` process. You can avoid this by running `.check` immediately, copy the build update id and save that into a version.txt file in the root directory of PatchRaptor. This will prevent the autoupdate checker from running on first launch.)
    - `.autoupdate on`: Enables auto-checker (checks every 10 minutes).
    - `.autoupdate off`: Disables auto-checker.

---

## Server Controls
Direct control over the server processes.

### `.reboot [map_name]`
Restarts the ARK servers.
- **Usage:**
    - `.reboot`: Restarts **ALL** servers (staggered by 30s).
    - `.reboot <map_name>`: Restarts a specific server (e.g., `.reboot scorched`).
- **Process:** Stops Chat Relay -> Sends `DoExit` -> Waits for shutdown -> Starts Server -> Waits for Online -> Reconnects Chat after 2 minutes.

### `.shutdown [map_name]`
Gracefully stops the ARK servers.
- **Usage:**
    - `.shutdown`: Stops **ALL** servers.
    - `.shutdown <map_name>`: Stops a specific server.
- **Process:** Stops Chat Relay -> Sends `DoExit` -> Waits for shutdown.

### `.cancel`
Cancels any ongoing timer or long-running operation.
- **Trigger:** Use this to cancel an update countdown triggered by `.update`.

---

## Server Updates
Commands related to SteamCMD updates.

### `.update`
Starts a **Scheduled Maintenance Update** with a 15-minute countdown.
- **Process:**
    1.  Sends Webhook Shutdown message (if configured).
    2.  Broadcasts in-game warnings at 15m, 10m, 5m, 1m.
    3.  Shuts down all servers via RCON (DoExit)
    4.  Updates via SteamCMD.
    5.  Restarts all servers with 30s delay
    6.  Confirms servers are online
    7.  Sends Webhook Update message (if configured)
    8.  Waits 5 minutes
    9.  Reconnects Chat Relay


### `.forceupdate [map_name]`
Starts an **Immediate Update** (No countdown).
- **Usage:**
    - `.forceupdate`: Updates ALL servers immediately.
    - `.forceupdate <map_name>`: Updates specific server immediately.
- **Warning:** Players will be disconnected instantly.
- **Process:**
    1.  Shuts down all servers via RCON (DoExit)
    2.  Updates via SteamCMD.
    3.  Restarts all servers with 30s delay
    4.  Confirms servers are online
    5.  Waits 5 minutes
    6.  Reconnects Chat Relay

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


> **Note**: All player bans are issued via RCON/Steam and tracked in a `bans.json` file.

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
Configures Discord webhook messages used by the `.update` command.
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
    - `.backup amount <number>`: Sets retention count (e.g. `.backup amount 10`). In this example if 10 are present and a new backup is triggered, the oldest backup is automatically removed. A backup.txt is created by this process for users to track backups.  

### `.restore <map_name> [index]`
Restores a previous backup.
- **Usage:**
    - `.restore <map_name>`: Lists available backups. The list of backups is created by the `.restore` command reading the configured 'backup_path' in the config.json file.
    - `.restore <map_name> <number>`: Restores specific backup ID.

---

## Scheduling system
Automate repetitive tasks.

### `.schedule`
Manage the task scheduler.
- **Usage:**
    - `.schedule`: Lists all active schedules.
    - `.schedule add <type> [days] <time>`: Adds a new task. When the first task is created, Schedule.json is created. This is how the Scheduler tracks tasks.  
    - `.schedule clear [type]`: Removes tasks of that type (eg .schedule clear reboot - only removes scheduled reboots).
- **Examples:**
    - `.schedule add reboot 04:00` (Daily)
    - `.schedule add backup all mon fri 05:00` (Weekly)

---

## Advanced Settings
Configuration and deep system diagnostics.

### `.discord delete <time>`
Sets auto-delete timer for bot messages sent to your configured CHANNELID.
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

### `.debug`
Toggle debug mode logging.
- **Usage:** `.debug` (Toggles on/off).
- **Effect:** Enables detailed logging to console for troubleshooting.

---

### `.diagnose`
Runs a comprehensive self-health check.
- **Checks:** Permissions, API access, RCON connectivity, Config validity.

---

## RaptorChat
Manage the In-Game chat relay. Allows players to communicate cross-cluster. Starting a chat with '/' in the global channel will send a message to all other servers in the cluster. (eg [RAG] OrokuSaki: Anyone want to join the Foot Clan?)

**Important Note :: In every instance where a server is restarted, RaptorChat is stopped before shutdown. A silent 5 minute wait timer is then triggered once PatchRaptor identifies all servers as online. After this timer expires, RaptorChat is automatically restarted.**

### `.chat <status|stop|reboot>`
Controls the chat relay process.
- **Usage:**
    - `.chat status`: Checks if RaptorChat is running.
    - `.chat reboot`: Restarts RaptorChat.
    - `.chat stop`: Stops RaptorChat.
