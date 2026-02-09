# Discord Bot Setup Guide

To use PatchRaptor, you need to create your own Discord bot. This is free and takes about 5 minutes.

## 1. Create the Application
1.  Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2.  Click **New Application** (top right).
3.  Name it (e.g., "PatchRaptor") and click **Create**.

## 2. Create the Bot User
1.  In the left menu, click **Bot**.
2.  Click **Reset Token** (or "Add Bot" if it's new).
3.  **Copy this Token**. You will need this for the `bot_token` field in Configurator.
4.  Uncheck "Public Bot" (recommended for security).
5.  **CRITICAL STEP**: Scroll down to "Privileged Gateway Intents".
    -   Enable **MESSAGE CONTENT INTENT**.
    -   (Optional) Enable "Server Members Intent" if you plan to use future features.
    -   Click **Save Changes**.

## 3. Invite the Bot
1.  In the left menu, click **OAuth2** -> **URL Generator**.
2.  Under **Scopes**, check `bot`.
3.  Under **Bot Permissions**, check `Administrator` (easiest) OR manually select:
    -   `Send Messages`
    -   `Read Messages/View Channels`
    -   `Embed Links`
    -   `Attach Files`
    -   `Manage Messages` (for auto-delete)
4.  Copy the **Generated URL** at the bottom.
5.  Paste it into your browser, select your server, and click **Authorize**.

## 4. Get the Channel ID
PatchRaptor only listens to commands in one specific channel for security.
1.  Open Discord **User Settings** (cog icon).
2.  Go to **Advanced** and enable **Developer Mode**.
3.  Right-click the text channel you want the bot to use (e.g., `#admin-console`).
4.  Click **Copy Channel ID**.
5.  Paste this into the `channel_id` field in Configurator.
