# PatchRaptor 
**ARK: Survival Ascended - Server Admin Discord Bot**

## Why PatchRaptor?

I've been running SteamCMD servers for ASA since release day, scaling from a single map to a full cluster as the community grew. But as real life got busier, the time involved to manage and update servers was harder to find so I wanted to find a way to guarantee the server uptime and performance our community had grown to expect. 

I needed a way to automate updates, backups, and restarts and also wanted to be able to easily do it from my phone while I'm away. And now we're here. I run PatchRaptor in a test environment on a cluster of 2 servers which can be seen here: ---> https://discord.gg/dS3xKYUK96 and for the last 3 months has been deployed in a production environment managing a cluster of 9 servers.
PatchRaptor is a powerful toolkit designed for server owners to create, manage, and customize their own Discord bot for ARK: Survival Ascended. This tool is specifically designed for Self-Hosted Dedicated Servers (clusters) configured via SteamCMD and Windows OS. This tool is not designed to be used with any commercial hosting providers.
    
## Key Features
    
### 1. Interactive Discord Interface
Designed for ease of use, even for non-technical moderators.
- **Clickable Menu:** The `.menu` command opens a dashboard (interactive for 15 minutes after .menu is triggered).
- **Context-Aware Help:** Clicking a button (e.g., "Server Updates") automatically shows you the available commands.
- **Reduced Training:** New admins don't need to read the manual; the bot guides them to the right commands.

### 2. Comprehensive Update System
PatchRaptor takes the stress out of patch days with a robust update engine.
- **Auto-Update:** Silently monitors Steam for updates every 10 minutes.
- **Safe Process:** Broadcasts warnings (15m/10m/5m/1m), performs a `SaveWorld`, shuts down safely, and updates via SteamCMD, before rebooting safely and sending a discord announcement via Webhook (if configured).
- **Manual Control:** Use `.forceupdate` for emergencies or `.cancel` to abort a countdown.
- **Staggered Restarts:** servers always restart one-by-one with a 30s delay to prevent host CPU overloads and event/update issues.

### 3. Advanced Scheduler
Automate your entire cluster's maintenance schedule with simple natural-language commands.
- **Flexible Timing:** Schedule tasks for specific days (e.g., `mon fri`) or daily (`daily`).
- **Granular Control:** Target specific maps for reboots or backup the entire cluster at once.
- **Easy Control:** View, edit and manage it all from Discord.
- *Example:* `.schedule add backup all daily 06:00`

### 4. Fail-Safe Backup & Restore
Your data is protected by a "Safety Net" architecture that prevents accidental data loss during restorations.
- **Automated Backups:** Regular `.zip` archives of your save folders are created automatically.
- **Smart Restore Process:** When you trigger a restore, the bot performs a safety sequence:
    1.  **Safety Backup:** It immediately backs up your *current* live save folder (e.g., `_before_restore_timestamp`).
    2.  **Clean State:** It safely clears the existing save directory.
    3.  **Restoration:** It extracts the selected backup file.
    *Result:* If you restore the wrong backup, your original data is still safe in the generated `_before_restore` folder.
- **Easy Retrieval:** List and restore backups directly from Discord.

### 5. GUI Configurator
Setting up a bot shouldn't require battling with raw JSON syntax.
- **Visual Interface:** A dedicated Python app (`Configurator.py`) that lets you add servers and configure settings with standard form fields and checkboxes.
- **No Syntax Errors:** Automatically generates strictly valid JSON. Never worry about a missing comma or mismatched bracket crashing your bot again.
- **Path Validation:** Use file pickers to safely select your `SteamCMD.exe` and `ShooterGameServer.exe` paths, ensuring no typos in your directory structure.

### 6. Player Management & Community Tracking
Manage your community effectively while keeping players informed.
- **Live Census:** Tracks player activity in real-time, feeding live player *counts* and 7-day averages to the **Web Panel** (Privacy Focus: No player names are shown on the web, only numbers).
- **Cluster Intelligence:** Use `.players` for quick totals, or `.players list` for a detailed manifesto of every survivor (Name, SteamID, Map, Uptime).
- **Global Moderation:** One command (`.ban <name>`) enforces bans across your **entire cluster** instantly.
- **Remote Action:** Kick or Ban problem players directly from Discord, without needing to launch the game or expose specific RCON ports.

### 7. Web Panel(Optional)
A lightweight, read-only dashboard for your community controlled by **`.webpanel on`**.
- **Local Mode:** Runs privately on your machine by default. Perfect for local monitoring without setup.
- **BYO Cloudflare:** Ready to go public? Use the included `setup_tunnel.bat` to securely link your own domain (e.g. `status.yoursite.com`).
- **Secure Authentication:** Public access is HTTPS encrypted and locked behind a username/password you configure.
- **Private IP Protection:** The tunnel allows access without port-forwarding or exposing your home server's IP address.


##  Quick Start (Running from Source)


### Prerequisites
*   **Windows OS** (Server 2019/2022, Windows 10/11)
*   **Administrator Access** (Required to manage server processes)
*   [**Python 3.10+**](https://www.python.org/downloads/) (Ensure "Add to PATH" is checked during install)
*   [**SteamCMD**](https://developer.valvesoftware.com/wiki/SteamCMD) (Installed and ready)
*   **RCON Tool** (Ideally [gorcon/rcon-cli](https://github.com/gorcon/rcon-cli) or similar)
*   **Startup Scripts**: You must have existing `.bat` files to launch your ARK servers.

### 1. Installation
1.  Download or Clone this repository.
2.  Double-click **`install_requirements.bat`**.
    *   Select **Option 1 (Production)** for standard usage.
    *   Select **Option 2 (Development)** if you plan to run tests or build the EXE.

### 2. Configuration
**Method A: Using the GUI (Recommended)**
1.  Run **`Configurator.py`**.
2.  **General Settings:**
    *   **Bot Token:** Paste your Discord Bot Token. (Enable "Message Content Intent" in Discord Dev Portal).
    *   **Paths:** Set paths for SteamCMD, RCON, etc.
3.  **Servers:**
    *   Add your ARK servers. Point "Path to Start.bat" to your existing startup scripts.
4.  Click **"Save Config"**.

**Method B: Manual Setup**
1.  Copy `config.example.json` to `config.json`.
2.  Edit `config.json` with your text editor.


### 3. Launching PatchRaptor
*   **Run the Bot:** Double-click **`PatchRaptor.py`**.
    *   A GUI dashboard will open showing the bot's status and logs.
*   **Verify:** Check your Discord channel. If the specific "Online" message appears, you are ready!


## 3 Web Panel (Optional)
PatchRaptor includes a secure, read-only web dashboard to view player counts and server status remotely.

1.  **Setup Config:** 
    *   Copy `webpanel_config.example.json` to `webpanel_config.json`.
    *   Edit the file to set your `admin` password.
2.  **Start the Panel:** Run '.webpanel on' **`pr-live.py`**.
3.  **Access Locally:** Open `http://localhost:8080`.
4.  **Public Access (Cloudflare Tunnel):**
    *   Run **`setup_tunnel.bat`** to initialize setup of the secure tunnel. (launches setup script to configure Cloudflare Tunnel)
    *   Run **`start_tunnel.bat`** to bring the tunnel online.


##  Project Structure

*   **`PatchRaptor.py`** - Main Application Entry Point (GUI).
*   **`Configurator.py`** - Settings Manager.
*   **`pr-live.py`** - Standalone Web Panel Server.
*   **`patchraptor/`** - Core Logic Package (Managers for RCON, Backup, Discord).

## Support

Join our discord for help and to make initial bug reports!
Thanks for using PatchRaptor!
https://discord.gg/dS3xKYUK96

##  License
MIT License. Free to use, modify, and distribute.
