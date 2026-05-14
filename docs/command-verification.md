# PatchRaptor Command Verification Checklist

This document tracks the verification status of all commands wired into the `CommandHandler`.

Marking a command as `[x]` serves as proof that its runtime behavior and implementation logic have been tested and are confirmed working in the production or test environment.


### 📊 Server Monitoring
- [x ] `.status` — View host hardware load and health metrics.
- [x ] `.servers` — Get live CPU/RAM usage and save sizes per map.
- [x ] `.check` — Query SteamCMD to see if any updates are pending.
- [x ] `.analytics` — View 7-day performance and player trends.

### 🔧 Server Management
- [x ] `.reboot` — Gracefully restart all servers in the cluster.
- [x ] `.reboot <map>` — Gracefully restart a specific server.
- [x ] `.shutdown` — Gracefully stop all servers.
- [x ] `.shutdown <map>` — Gracefully stop a specific server.

### 🦖 Update Management
- [x ] `.patch` — Start a graceful patch sequence with countdowns.
- [x ] `.forcepatch` — Instantly force a patch without any countdown warnings.
- [x ] `.patch status` — View your current patch configuration (timers, alerts).
- [x ] `.patch timer <minutes>` — Set the patch countdown timer.
- [x ] `.patch intervals <intervals>` — Set the broadcast intervals (e.g. 15,10,5,1).
- [x ] `.patch broadcast <template>` — Set the RCON broadcast template.
- [x ] `.patch webhook <shutdown|reboot> <message>` — Set Discord webhook messages.
- [x ] `.autopatch on|off` — Toggle automatic background patching.
- [x ] `.cancel` — Abort any active patch sequence.

### 💬 Server Broadcasts
- [x ] `.send all <message>` — Broadcast an RCON alert to all running servers.
- [x ] `.send <map> <message>` — Broadcast an RCON alert to a specific server.

### 💾 Backup & Restore
- [x ] `.backup all` — Instantly archive all server save data.
- [x ] `.backup <map>` — Archive save data for a specific server.
- [x ] `.backup amount <num>` — Set the number of historical backups to retain.
- [x ] `.restore <map>` — List available backup archives for a specific server.
- [x ] `.restore <map> <num>` — Stop the server, restore the specified archive, and restart.

### 📅 Automation & Scheduling
- [x ] `.schedule` — View all active scheduled tasks.
- [x ] `.schedule add <type> <time/day>` — Create a new task (e.g., `.schedule add reboot scorched 04:00`, `.schedule add patch sun 01:00`).
- [x ] `.schedule clear` — Remove all scheduled tasks.
- [x ] `.schedule clear <type>` — Remove tasks of a specific type (e.g., `.schedule clear backup`).

### ⚙️ Advanced Settings & Diagnostics
- [x ] `.discord delete <time>` — Set the auto-deletion timer for bot messages.
- [x ] `.report` — Generate and download a system log diagnostic report.
- [x ] `.diagnose` — Run an internal system health and integrity check.
- [x ] `.debug` — Toggle the diagnostic logging mode.

### 🎮 Player Management
- [x ] `.players` — Show the total number of active players across the cluster.
- [x ] `.players list` — Show detailed information about currently online players.
- [x ] `.kick <player>` — Disconnect a player from all servers.
- [x ] `.ban <player>` — Ban a player across the cluster (by Name or ID).
- [x ] `.unban <player>` — Lift a ban across the cluster (by Name or ID).

### 🦖 Chat Relay
- [x ] `.chat status` — View the health and connection status of the chat relay.
- [x ] `.chat reboot` — Forcefully restart the chat relay service.
- [x ] `.chat stop` — Disconnect the chat relay.

### 🌐 Web Panel
- [x ] `.webpanel` — View the web panel tunnel URL and connection status.
- [x ] `.webpanel on` — Launch the web server and open the secure tunnel.
- [x ] `.webpanel off` — Shut down the web server and close the tunnel.

### 📱 Menu
- [x ] `.menu` — Displays the interactive Discord UI button menu to access all the above categories visually.
