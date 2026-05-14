# PatchRaptor — Master Message Flow (Ground Truth)

> **This document is the single source of truth for all Discord-facing messages.**
> All emojis, phrasing, and formatting are defined here. Do not change message strings
> without updating this document.

---

## 📊 Sequence #1: `.status`
- **Output**: Embed titled `📊 **Host Status Dashboard**`
  - `🔌 PC Uptime     : [duration]`
  - `💻 System CPU    : [X]%`
  - `⚡ Memory Usage  : [X]/[X] GB`
  - `💾 Disk Usage    : [X]/[X] GB ([X]%)`
  - `📈 7-Day Avg     : [X]% Uptime | [X] Players`

---

## 📈 Sequence #2: `.analytics`
- **Output**: Embed titled `📈 Cluster Analytics Dashboard`
  - Fields: `🎮 Player Vitality`, `🕒 Reliability Score`, `💻 Performance Trends`

---

## 🩺 Sequence #3: `.diagnose`
- **Output**: Embed titled `Bot Health Diagnostic`
  - Field: `☑️ All systems operational` (or issue list)

---

## 🔍 Sequence #4: `.check`
- **Up to date**: `☑️ Server is up to date (Build [X])`
- **Update available**: `🔄 Update available: Build [X] → [Y]`
- **Steam error**: `⚠️ Unable to fetch latest version from Steam.`

---

## 🐛 Sequence #5: `.debug`
- **Toggle**: `🐛 Debug logging is now **☑️ ON**` (or `🛑 OFF`)

---

## 📋 Sequence #6: `.report`
- **Output**: `📋 **PatchRaptor Log Report**` + file attachment

---

## 📊 Sequence #7: `.servers`
- **Output**: Embed titled `📊 **Server Details**` per server:
  - `🗺️ Map Name      : [name]`
  - `☑️ Status          : Online` (or `🔲 Status          : Offline`)
  - `🔌 Uptime          : [duration]`
  - `🎮 Players         : [X]`
  - `💻 Process CPU     : [X]%`
  - `⚡ Process RAM     : [X] GB`
  - `💾 Save Size       : [X] GB`

---

## 🦖 Sequence #8: `.reboot` (All Servers)
1. **Initiation**: `🦖 Reboot sequence initiated...`
2. **Relay Pause**: `🖥️ Pausing Telemetry and Chat Relay...`
3. **Shutdown Initiation**: `📡Sending shutdown command to **[X]** servers...`
4. **Shutdown Wait**: `⏳ Waiting for **[X]** servers to shut down completely...`
5. **Ghost Recovery (if needed)**: `👻 [MapName] failed to shut down. Initiating Ghost Recovery...`
6. **Shutdown Success**: `🦕 All servers have shut down successfully`
7. **Startup Initiation (bulk)**: `🦖 Starting **[X]** servers...`
8. **Per-server start**: `🦖 [MapName] is now starting...`
9. **Recovery Wait**: `⏳ Waiting for **[X]** servers to come back online...`
10. **Online Confirmation**: `🦕 All servers are back online`
11. **Final Handoff**: `🖥️ Reconnecting Telemetry and Chat Relay after server reboot...`

---

## 🦖 Sequence #9: `.reboot [map]` (Single Server)
1. **Initiation**: `🦖 Reboot sequence initiated for [MapName]...`
2. **Relay Pause**: `🖥️ Pausing Telemetry and Chat Relay...`
3. **Shutdown Initiation**: `📡Sending shutdown command to [MapName]...`
4. **Shutdown Wait**: `⏳ Waiting for [MapName] to shut down...`
5. **Ghost Recovery (if needed)**: `👻 [MapName] failed to shut down. Initiating Ghost Recovery...`
6. **Shutdown Success**: `🦕 [MapName] has shut down successfully`
7. **Per-server start**: `🦖 [MapName] is now starting...`
8. **Recovery Wait**: `⏳ Waiting for [MapName] to come back online...`
9. **Online Confirmation**: `🦕 [MapName] is back online`
10. **Final Handoff**: `🖥️ Reconnecting Telemetry and Chat Relay after server reboot...`

---

## 🩹 Sequence #10: `.patch` (Standard with Countdown)
1. **Initiation**: `🦖 Patch sequence initiated. Maintenance countdown started.`
2. **Timer Loop**: `⏳ [Broadcast Template]` (e.g., `Servers will be shutting down for maintenance in 15 minutes`)
3. **Relay Pause**: `🖥️ Pausing Telemetry and Chat Relay...`
4. **Shutdown Initiation**: `📡 Sending shutdown command to [X] servers...`
5. **Shutdown Wait**: `⏳ Waiting for [X] servers to shut down...`
6. **Ghost Recovery (if needed)**: `👻 [MapName] failed to shut down. Initiating Ghost Recovery...`
7. **Shutdown Success**: `🦕 All servers have shut down successfully`
8. **Download Pulse**: `⬇️ Downloading server update...`
9. **Steam Error (if any)**: `❌ SteamCMD Error (Code [X]):\n[details]`
10. **Startup Initiation (bulk)**: `🦖 Starting **[X]** servers...`
11. **Per-server start**: `🦖 [MapName] is now starting...`
12. **Recovery Wait**: `⏳ Waiting for **[X]** servers to come back online...`
13. **Online Confirmation**: `🦕 All servers are back online`
14. **Final Handoff**: `🖥️ Reconnecting Telemetry and Chat Relay after server update...`

---

## ⚡ Sequence #11: `.forcepatch` (No Countdown)
1. **Initiation**: `🦖 Force update sequence initiated...`
2. *(Then follows steps 3–14 of Sequence #10 identically)*

---

## 🔄 Sequence #12: `.autopatch`
1. **Status Check**: `Autopatch status: ☑️ ON` (or `🛑 OFF`)
2. **Toggle ON**: `☑️ Autopatch is now ON.`
3. **Already ON**: `☑️ Autopatch is already ON`
4. **Toggle OFF**: `🛑 Autopatch stopped.`
5. **Already OFF**: `🛑 Autopatch already stopped`

---

## 🤖 Sequence #13: Autopatch — Auto-Detection
1. **Update detected**: `⚠️ New version detected!`
2. *(Then triggers full `.patch` sequence — Sequence #10)*

---

## 🛑 Sequence #14: `.cancel`
- **Cancelled**: `🛑 Process cancelled...`
- **Nothing to cancel**: `⚠️ No active countdown or update to cancel.`

---

## 🛑 Sequence #15: `.shutdown` (All Servers)
1. **Initiation**: `🦖 Shutdown sequence initiated...`
2. **Relay Pause**: `🖥️ Pausing Telemetry and Chat Relay...`
3. **Shutdown Initiation**: `📡Sending shutdown command to **[X]** servers...`
4. **Shutdown Wait**: `⏳ Waiting for **[X]** servers to shut down...`
5. **Ghost Recovery (if needed)**: `👻 [MapName] failed to shut down. Initiating Ghost Recovery...`
6. **Shutdown Success**: `🦕 All servers have shut down successfully`

---

## 🛑 Sequence #16: `.shutdown [map]` (Single Server)
1. **Initiation**: `🦖 Shutdown sequence initiated for [MapName]...`
2. **Relay Pause**: `🖥️ Pausing Telemetry and Chat Relay...`
3. **Shutdown Initiation**: `📡Sending shutdown command to [MapName]...`
4. **Shutdown Wait**: `⏳ Waiting for [MapName] to shut down...`
5. **Ghost Recovery (if needed)**: `👻 [MapName] failed to shut down. Initiating Ghost Recovery...`
6. **Shutdown Success**: `🦕 [MapName] has shut down successfully`

---

## 📡 Sequence #17: `.send`
- **Broadcast all**: `📡Sending broadcast to all servers...`
- **Broadcast single**: `📡Sending broadcast to [MapName]...`
- **Error**: `⚠️ Failed to send to [MapName]: [reason]`

---

## 👥 Sequence #18: `.players`
- **Output**: Embed titled `Player Information`
  - `Total Players Online: [X]`
  - `Servers Checked: [X]`
  - Optional `.players list`: per-server player list

---

## 👢 Sequence #19: `.kick`
- **Success**: `⌨️ Sent kick command for '[name]' to all servers...`
- **Error**: `⚠️ Failed to kick from [MapName]: [reason]`

---

## 🔨 Sequence #20: `.ban`
- **Success**: `⌨️ Sent ban command for '[name]' to all servers...`
- **Error**: `⚠️ Failed to ban from [MapName]: [reason]`

---

## ✅ Sequence #21: `.unban`
- **Success**: `⌨️ Sent unban command for '[name]' to all servers...`
- **No Steam ID**: `⚠️ Cannot unban '[name]' - Steam ID not found. Player must be online to get Steam ID.`
- **Error**: `❌ Failed to unban player '[name]': [reason]`

---

## 🌐 Sequence #22: `.webpanel`
1. **Status Check**: `☑️ Web Panel is Online` (or `🛑 Web Panel is Offline`)
2. **Already running**: `☑️ Web panel is already running`
3. **Toggle ON**:
    - `🚇 Tunnel started` (if tunnel configured and starts OK)
    - `⚠️ Tunnel failed to start. Launching local WebPanel.` (tunnel crashes immediately)
    - `⚠️ Tunnel start error. Launching local WebPanel.` (tunnel raises exception)
    - `⚠️ Tunnel not configured ([reason]). Launching local WebPanel.` (no tunnel script)
    - `🌐 Web Panel is now ON`
4. **Toggle OFF**:
    - `🛑 Tunnel stopped`
    - `🛑 Web Panel stopped`
5. **Already stopped**: `Web panel already stopped 🛑`
6. **Error ON**: `❌ Failed to start web panel: [reason]`
7. **Error OFF**: `❌ Failed to stop web panel: [reason]`

---

## 🦖 Sequence #23: `.chat`
1. **Status (running)**: `☑️ RaptorChat is Online`
2. **Status (stopped)**: `🛑 RaptorChat is Offline`
3. **Stop (not running guard)**: `⚠️ RaptorChat is not running.`
4. **Stop (success)**: `🛑 RaptorChat stopped`
5. **Stop (failure)**: `❌ Failed to stop RaptorChat.`
6. **Reboot (initiating)**: `🔄 Restarting RaptorChat...`
7. **Reboot (success)**: `🦖 RaptorChat restarted`
8. **Reboot (failure)**: `❌ Failed to restart RaptorChat.`
9. **Unknown subcommand**: `⚠️ Unknown subcommand. Use: \`status\`, \`stop\`, or \`reboot\`.`

---

## 🔧 Sequence #24: `.reset chat`
1. `✅ RaptorChat maintenance semaphore reset to 0. Auto-monitor resumed.`
2. *(If not running)*: `🔄 Attempting RaptorChat restart...`
3. **Success**: `✅ RaptorChat restarted successfully.`
4. **Failure**: `❌ Failed to restart RaptorChat. Check logs.`

---

## 💾 Sequence #25: `.backup all`
1. **Initiation**: `🦖 Starting backup of all servers...`
2. **Per-server save trigger**: `💾 Triggering world save for [MapName]...`
3. **Per-server save validation**: `⏳ Validating save flush for [MapName]...`
4. **Save confirmed**: `✅ Save confirmed for [MapName].`
5. **Save slow**: `⚠️ Save validation slow, falling back to safety wait...`
6. **Completion**: `🦖 Backup process completed for all servers.`
7. **Error**: `❌ Failed to backup [name]: [reason]`

---

## 💾 Sequence #26: `.backup [map]`
- Same per-server steps as #25, for a single map.

---

## 🔁 Sequence #27: `.restore [map]`
1. **Shutdown for restore**: `⏹️ Shutting down [MapName] server for restore...`
2. **Waiting for shutdown**: `🦕 Waiting for [MapName] server to shut down...`
3. **Shutdown success**: `🦖 [MapName] server has shut down successfully...`
4. **Creating safety backup**: `💾 Creating backup of current save...`
5. **Extracting backup**: `📂 Extracting backup...`
6. **Restarting**: `🦖 Restarting [MapName] server...`
7. **Recovery Wait**: `⏳ Waiting for [MapName] to come back online...`
8. **Restore complete**: `🦖 Successfully restored backup [filename] for [MapName]...`
9. **Final Handoff**: `Reconnecting system components after [MapName] restore...`

---

## 🗓️ Sequence #28: `.schedule`
- **No events**: `ℹ️ No scheduled events.`
- **List**: Plain text listing of all scheduled events.
- **Add success**: `🦖 Scheduled [description]`
- **Add error**: `❌ Failed to add scheduled event: [reason]`
- **Clear all**: `🦖 Cleared all scheduled events.`
- **Clear type**: `🦖 Removed [X] scheduled '[type]' event(s).`
- **Nothing to clear**: `ℹ️ No scheduled '[type]' events found to remove.`

---

## ⏱️ Sequence #29: `.patch timer / broadcast / intervals / webhook`
- **Timer set**: `☑️ Patch timer set to [X] minutes.`
- **Broadcast set**: `☑️ Patch broadcast template updated.`
- **Intervals set**: `☑️ Broadcast intervals updated.`
- **Webhook set**: `☑️ [Type] webhook message updated.`
- **Settings display**: Embed titled `🦖 Patch Settings`

---

## ⚠️ Global Error Messages
- **Server not found**: `⚠️ No server found with name '[name]'.`
- **RCON failure**: `⚠️ Failed to send shutdown to [MapName]: [reason]`
- **Steam not found**: `❌ Update Error: SteamCMD not found at [path]! Please check your config.json.`
- **Patch in progress**: `⚠️ Patch already in progress.`
- **Patch failed**: `❌ Patch Failed: [error]`
- **Force patch failed**: `❌ Force Patch Failed: [error]`
