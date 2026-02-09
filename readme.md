# PatchRaptor 🦖

## About

PatchRaptor is a comprehensive toolkit, designed to enhance your existing SteamCMD Install of ARK: Survival Ascended Dedicated Servers. It combines automation, performance monitoring, player management, an in-game chat relay system and more into a single, easy-to-deploy package. 

PatchRaptor does **not** set up ARK servers for you. It is a management layer that enhances an existing, functional server environment.

> **Note**: This repository contains the source code for transparency and security auditing. For official downloads and support, visit [patchraptor.online](https://patchraptor.online).

## 🛡️ License & Transparency

**PatchRaptor is source-available software** - the code is publicly visible so you can verify it's safe and secure.

- ✅ **Free to use** - Personal and commercial server use allowed (including revenue-generating servers)
- ✅ **Transparent** - Full source code available for security auditing and verification
- ✅ **No redistribution** - Official downloads only from [patchraptor.online](https://patchraptor.online)
- ✅ **Feedback welcome** - Join our [Discord](https://discord.gg/NmHbruVs56) for support and suggestions

See [`LICENSE`](LICENSE) for full terms.

> **Disclaimer**: PatchRaptor is an unofficial tool and is not affiliated with, endorsed by, or associated with Studio Wildcard or Snail Games. ARK: Survival Ascended is a trademark of Studio Wildcard.


## System Requirements

### Operating System
- Windows Server 2019/2022
- Windows 10/11

### Game Server Preparation
- **SteamCMD Installation**: You must have a working SteamCMD installation of ARK: Survival Ascended Dedicated Servers.
- **Start Scripts**: Your servers must be launchable via `start.bat` scripts and run successfully on their own.
- **RCON Enabled**: Servers must have `-RCON` (and preferably `-RCONPort=XXXX`) in their launch arguments.

> [!TIP]
> **Need help setting up your Discord Bot or cluster first?** Check out our guides for creating your discord bot, configuring your Ark: Survival Ascended Dedicated Servers, and more on our website. (https://patchraptor.online/guides)

### Software Dependencies
- **SteamCMD**: Required for automated updates. [Download from Valve](https://developer.valvesoftware.com/wiki/SteamCMD).
- **RCON Tool**: Required for server control. We recommend and use [rcon-cli](https://github.com/gorcon/rcon-cli) (free & lightweight).
- **Discord**: Required for control and alerts. [Create a Bot](https://discord.com/developers/applications) in the Developer Portal.

---

## Installation

### Option 1: Portable
**Recommended for most users.**
If you have downloaded the release archive (e.g., `PatchRaptor.zip`) - **Skip**: Go directly to [Getting Started](#getting-started).

### Option 2: Windows Installer
1. Run **`PatchRaptor_Setup.exe`**.
2. Follow the setup wizard to select your installation folder.
3. Choose to add PatchRaptor.exe as a shortcut to the Desktop.
4. Launch **Configurator** from the install folder for initial setup. Once configured, you can use PatchRaptor.exe from the desktop shortcut.

---

## Components

The release folder contains the following files:

| File | Description |
| :--- | :--- |
| **`PatchRaptor.exe`** | The main GUI Launcher. Use this to Start/Stop the bot and view the console. |
| **`Instinct.exe`** | The core logic of PatchRaptor. This is the background headless process. |
| **`Configurator.exe`** | Settings editor. Use this to setup paths, tokens, and server details. |
| **`RaptorChat.exe`** | Handles the raw log parsing for the in-game chat relay. |
| **`WebPanel.exe`** | Hosts the live status dashboard. |
| `config.example.json` | Template for main configuration. |
| `webpanel_config.example.json` | Template for web panel credentials. |
| `setup_tunnel.bat` | Script to set up Cloudflare Tunnel for remote access. |
| `start_tunnel.bat` | Script to start the Cloudflare Tunnel manually. |
| `discord_setup.md` | Step-by-step guide for creating your bot. |
| `commands.md` | Full reference guide for all Discord commands. |
| `LICENSE` | Controlled Source License. |

## Created Files

During operation, PatchRaptor will create several files. **Do not edit these manually || Removing them can affect bot performance/behavior**:

- `config.json`: Your saved settings from Configurator.
- `webpanel_config.json`: Your web panel credentials.
- `version.txt`: Tracks the current installed server version for update checks.
- `schedule.json`: Stores active scheduled tasks.
- `bans.json`: Caches banned player IDs.
- `eula_accepted.json`: Remembers that you accepted the EULA.
- `player_stats.json`: Tracks player activity history for the Web Panel.
- `uptime_stats.json`: Tracks server uptime history for the Web Panel.
- `logs/`: Directory containing daily log files for troubleshooting.

---

## Getting Started

Follow these steps to get PatchRaptor up and running.

### 1. Configuration (The Configurator)
Run **`Configurator.exe`** to begin. This tool generates your `config.json` and ensures all features are wired correctly.

- **Discord Setup**: 
    - **Bot Token**: From the [Discord Developer Portal](https://discord.com/developers/applications). 
    - **Channel ID**: Enable **Developer Mode** in Discord, right-click your target text channel, and select **Copy ID**.
    - **Intents**: Ensure **Presence**, **Server Members**, and **Message Content** Intents are **ENABLED** in your Bot settings.
- **Server Paths**:
    - Select your `ShooterGameServer.exe` location.
    - Provide the path to your `SteamCMD.exe` for automated updates.
- **Cluster Config**:
    - Add each map in your cluster.
    - **Map Name**: The display name in Discord.
    - **Folder Name**: The literal folder name where that specific map's data resides.
    - **RCON Ports**: Must match your server's launch arguments.

### 2. Launching PatchRaptor
Run **`PatchRaptor.exe`**. This is your control center.
- Click **Start Bot** to initiate the background process (`Instinct.exe`).
- The console will show the bot initializing and connecting to Discord.
- **Keep it running**: PatchRaptor handles everything while active. If you close the main window, the management service will stop.

### 3. First-Run Verification
Once the bot is "Online" in Discord, verify your setup:
1. **The Clickable Dashboard**: Type `.menu` in your configured channel. This confirms the bot can see your messages and respond.
2. **System Health Check**: Type `.diagnose`. This runs a comprehensive scan of your paths, RCON connectivity, and permissions. If everything is green, you are ready for prime time!

### 4. Web Panel & Dashboards (Optional)
To use the live web dashboard:
- Create a username/password in `webpanel_config.example.json` and rename it to `webpanel_config.json`.
- Run **`.webpanel on`** in Discord to start the server.
- Access locally at `http://localhost:8080`.
- For remote access, use **`setup_tunnel.bat`** to configure a Cloudflare Tunnel. (domain required)

---

## Support & community

For the latest news, support and updates, please visit our website
PatchRaptor is available free to the community. If you find value in it and wish to show support, you can buy me a coffee! 🙂

[Support on Buy Me a Coffee](https://buymeacoffee.com/patchraptor)

*n1Kk085*
