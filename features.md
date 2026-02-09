# PatchRaptor Feature Set

## 1. 📊 Server Monitoring
- **Real-time Status**: View server status, PC uptime, and system resources (CPU/Memory/Disk usage) via `.status`.
- **Detailed Info**: Get a distinct listing of all configured servers with `.servers`.
- **Process Checking**: Automatically detects running server tasks for accurate status reporting.

## 2. 🔧 Server Controls
- **Power Management**: Remotely Shutdown (`.shutdown`) and Reboot (`.reboot`) servers.
- **Granular Control**: Target all servers at once (`.reboot`) or specific maps individually (`.reboot [map]`).
- **Safety Interlocks**: Cancel pending operations with `.cancel` to prevent accidents.

## 3. 🔄 Server Updates
- **Maintenance Updates**: Schedule updates with automatic warning countdowns using `.update`.
- **Emergency Updates**: Force immediate updates for critical patches via `.forceupdate`.
- **Version Checking**: Compare installed server versions against Steam's latest build with `.check`.

## 4. 📡 Webhook Settings
- **Custom Notifications**: Configure custom messages for the `.update` command.
- **Transparency**: View currently set webhook messages to ensure accuracy (`.webhook get`).

## 5. 💬 Server Broadcasts
- **Global Announcements**: Send RCON messages to every server in your cluster simultaneously (`.send all [message]`).
- **Targeted Messaging**: Send specific instructions to a single map (`.send [map] [message]`).

## 6. 💾 Backup System
- **On-Demand Backups**: Manually trigger backups for one or all servers (`.backup`).
- **One-Click Restore**: List available backups and restore them with a single index number (`.restore`).
- **Retention Policy**: Configurable limit (e.g., keep last 10 backups) to save disk space.

## 7. 📅 Scheduling System
- **Automation**: Schedule recurring tasks like shutdowns, reboots, and updates.
- **Flexibility**: Define specific days (e.g., "Mon Wed Fri") and times.
- **Management**: Easily view (`.schedule`) and clear (`.schedule clear`) active tasks.

## 8. ⚙️ Advanced Settings
- **Health Checks**: Run self-diagnostics on configuration, RCON connectivity, and system health (`.diagnose`).
- **Log Reports**: Generate and upload log files directly to Discord for troubleshooting (`.report`).
- **Web Panel Control**: Toggle the live status dashboard and Cloudflare tunnel (`.webpanel`).
- **Data Hygiene**: Auto-delete bot messages to keep channels clean (`.discord delete`).

## 9. 🎮 Player Management
- **Player Tracking**: View current player counts and detailed player lists (`.players`).
- **Moderation**: Kick (`.kick`) or Ban (`.ban`) players directly from Discord.
- **Unban**: Remove players from the ban list (`.unban`).

## 10. 🦖 RaptorChat
- **Cluster Chat**: Link in-game chat across multiple servers in the cluster.
- **Management**: Monitor status (`.chat status`) or restart the relay service (`.chat reboot`) independently of the servers.
