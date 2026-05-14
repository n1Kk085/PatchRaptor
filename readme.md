# PatchRaptor 🦖 (Source Code)

## About

PatchRaptor is a comprehensive toolkit, designed to enhance your existing SteamCMD Install of ARK: Survival Ascended Dedicated Servers. It combines automation, performance monitoring, player management, an in-game chat relay system and more into a single, easy-to-deploy package. 

PatchRaptor does **not** set up ARK servers for you. It is a management layer that enhances an existing, functional server environment.

*Internal Designation: PatchRaptor (Cherry)*

> **Note**: This repository contains the source code for transparency and security auditing. For official downloads, visit [patchraptor.online](https://patchraptor.online).

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

### Software Dependencies
- **Python 3.10+**: Required to run from source. [Download Python](https://www.python.org/).
- **SteamCMD**: Required for automated updates. [Download from Valve](https://developer.valvesoftware.com/wiki/SteamCMD).
- **RCON Tool**: Required for server control. We recommend and use [rcon-cli](https://github.com/gorcon/rcon-cli) (free & lightweight).
- **Discord**: Required for control and alerts. [Create a Bot](https://discord.com/developers/applications) in the Developer Portal.

### Game Server Preparation
- **SteamCMD Installation**: You must have a working SteamCMD installation of ARK: Survival Ascended Dedicated Servers.
- **Start Scripts**: Your servers must be launchable via `start.bat` scripts and run successfully on their own.
- **RCON Enabled**: Servers must have `-RCON` (and preferably `-RCONPort=XXXX`) in their launch arguments.

> [!TIP]
> **Need help setting up your Discord Bot or cluster first?** Check out our guides for creating your discord bot, configuring your Ark: Survival Ascended Dedicated Servers, and more on our website. (https://patchraptor.online/guides)

---

## Installation (Source Code)

To run PatchRaptor from source, follow these steps:

1.  **Download from GitHub**: Visit [PatchRaptor on GitHub](https://github.com/n1Kk085/PatchRaptor), click the green **Code** button, and select **Download ZIP**.
2.  **Extract the Files**: Extract the ZIP archive to a folder on your computer.
3.  **Install Dependencies**: Open a terminal in the extracted folder and run:
    ```bash
    pip install -r requirements.txt
    ```
4.  **Initial Configuration**: Run the Configurator to set up your bot:
    ```bash
    python Configurator.py
    ```
5.  **Launch PatchRaptor**: Start the main GUI Launcher:
    ```bash
    python PatchRaptor.py
    ```

---

## Components

The source repository contains the following primary entry points:

| File | Description | Run Command |
| :--- | :--- | :--- |
| **`PatchRaptor.py`** | The main GUI Launcher. Matches the executable experience. | `python PatchRaptor.py` |
| **`main.py`** | The core logic of PatchRaptor (Headless background process). | `python main.py` |
| **`Configurator.py`** | Settings editor for paths, tokens, and server details. | `python Configurator.py` |
| **`RaptorChat.py`** | Handles the raw log parsing for the in-game chat relay. | `python RaptorChat/RaptorChat.py` |
| **`pr_live.py`** | Hosts the live status dashboard (Web Panel). | `python pr_live.py` |
| `config.example.json` | Template for main configuration. | - |
| `webpanel_config.example.json` | Template for web panel credentials. | - |
| `setup_tunnel.bat` | Script to set up Cloudflare Tunnel for remote access. | - |
| `LICENSE` | Controlled Source License. | - |

---

## Getting Started

### 1. Configuration (The Configurator)
Run **`Configurator.py`** to begin. This tool generates your `config.json` and ensures all features are wired correctly.
```bash
python Configurator.py
```

- **Discord Setup**: 
    - **Bot Token**: From the [Discord Developer Portal](https://discord.com/developers/applications). 
    - **Channel ID**: Enable **Developer Mode** in Discord, right-click your target text channel, and select **Copy ID**.
    - **Intents**: Ensure **Presence**, **Server Members**, and **Message Content** Intents are **ENABLED** in your Bot settings.
- **Server Paths**:
    - Select your `ShooterGameServer.exe` location.
    - Provide the path to your `SteamCMD.exe` for automated updates.
- **Cluster Config**:
    - Add each map in your cluster.

### 2. Launching PatchRaptor
Run **`PatchRaptor.py`** for the GUI experience:
```bash
python PatchRaptor.py
```
- Click **Start Bot** to initiate the background process.
- The console will show the bot initializing and connecting to Discord.

### 3. First-Run Verification
Once the bot is "Online" in Discord, verify your setup:
1. **The Clickable Dashboard**: Type `.menu` in your configured channel.
2. **System Health Check**: Type `.diagnose`. This runs a comprehensive scan of your paths and connectivity.

### 4. Brand-Aligned Web Dashboard (Optional)
To use the live, brand-aligned web dashboard:
- Create a username/password in `webpanel_config.example.json` and rename it to `webpanel_config.json`.
- Run **`.webpanel on`** in Discord or launch `pr_live.py` manually:
  ```bash
  python pr_live.py
  ```
- Access the high-performance, real-time interface at `http://localhost:8095`.

---

## Created Files

**Do not edit these manually || Removing them can affect bot performance/behavior**:

- `config.json`: Your saved settings from Configurator.
- `webpanel_config.json`: Your web panel credentials.
- `version.txt`: Tracks the current installed server version.
- `schedule.json`: Stores active scheduled tasks.
- `bans.json`: Caches banned player IDs.
- `eula_accepted.json`: Remembers EULA acceptance.
- `player_stats.json`: Tracks player activity history.
- `uptime_stats.json`: Tracks server uptime history.
- `logs/`: Directory containing daily log files.

---

## Support & community

For the latest news, support and updates, please visit our website
PatchRaptor is available free to the community. If you find value in it and wish to show support, you can buy me a coffee! 🙂

[Support on Buy Me a Coffee](https://buymeacoffee.com/patchraptor)

*n1Kk085*
