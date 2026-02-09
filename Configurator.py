# Copyright (c) 2026 n1Kk085/PatchRaptor
# Licensed under the PATCHRAPTOR LICENSE AGREEMENT.
# See LICENSE file for details. Distribution prohibited.

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image
import customtkinter as ctk
from customtkinter import CTkImage

import os
import json
import ctypes
import sys

def resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        # Running from PyInstaller bundle folder
        base_path = sys._MEIPASS
    else:
        # Running in normal python environment
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

EULA_STATUS_FILE = "eula_accepted.json"

GENERAL_KEYS = [
    "bot_token", "channel_id",
    "steamcmd_path", "server_dir",
    "discord_webhook", "rcon_tool"
]

SERVER_KEYS = [
    "server_name", "server_display_name", "map_abbrev", "server_map_name",
    "server_save_path", "server_log_dir", "server_rcon_ip", "server_rcon_port",
    "server_rcon_password", "server_start_command"
]

BUTTON_COLOR = "#5B83C9"
FONT_NAME = "Consolas"
FONT_SIZE = 12

class ConfigApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PatchRaptor Configurator")
        self.root.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.servers = []
        self.general_entries = {}
        self.server_entries = {}
        self.webhook_entries = {}
        self.imported_webhook_messages = {}  # Store webhook messages to preserve them

        self.create_widgets()
        self.center_window()

        self.center_window()
        
        if self.check_eula_status():
            print("EULA already accepted. Starting normally.")
        else:
            print("EULA not accepted. Showing popup.")
            self.show_eula()

    def on_eula_accept(self, eula_window):
        self.save_eula_status()
        eula_window.destroy()
        
    def center_window(self):
        window_width = 675
        window_height = 1065

        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        pos_x = int((screen_width - window_width) / 2)
        pos_y = int((screen_height - window_height) / 2)

        self.root.geometry(f"{window_width}x{window_height}")

        self.root.update_idletasks()

        self.root.geometry(f"+{pos_x}+{pos_y}")

    def browse_path(self, key):
        path = filedialog.askdirectory(title=f"Select folder for {key}")
        if path:
            if key in self.general_entries:
                self.general_entries[key].delete(0, tk.END)
                self.general_entries[key].insert(0, path)
            elif key in self.server_entries:
                self.server_entries[key].delete(0, tk.END)
                self.server_entries[key].insert(0, path)

    def check_eula_status(self):
        """Check if EULA has been accepted by looking for the status file."""
        return os.path.exists(EULA_STATUS_FILE)

    def save_eula_status(self):
        """Save EULA acceptance status to local file."""
        try:
            with open(EULA_STATUS_FILE, 'w') as f:
                json.dump({"accepted": True}, f)
        except Exception as e:
            print(f"Failed to save EULA status: {e}")
        
    def show_eula(self):
        eula_text = """PATCHRAPTOR SOURCE-AVAILABLE LICENSE

Copyright (c) 2026 n1Kk085

---

1. GRANT OF LICENSE
   The author (n1Kk085) grants you a worldwide, royalty-free, non-exclusive license to:
   
   (a) USE the Software for personal or commercial server administration purposes, including servers that generate revenue.
   (b) VIEW the source code for transparency, security auditing, and verification purposes.
   (c) MODIFY the source code for your own private use.

2. RESTRICTIONS
   You may NOT:
   
   (a) Redistribute the Software (source code or binaries) in any form.
   (b) Sell, rent, lease, or sublicense the Software or any portion thereof.
   (c) Remove or modify copyright notices, license text, or attribution.

3. OFFICIAL DISTRIBUTION
   Only the author (n1Kk085) has the exclusive right to distribute official pre-compiled binaries and installers. 
   Official downloads are available exclusively at https://patchraptor.online

4. SOURCE CODE TRANSPARENCY
   The source code is made publicly available on GitHub for transparency, security auditing, and verification ONLY.
   The availability of source code does NOT constitute permission to redistribute or create derivative distributions.

5. FEEDBACK AND CONTRIBUTIONS
   We welcome feedback, bug reports, and feature suggestions via our Discord server: https://discord.gg/NmHbruVs56
   Note: We do not accept pull requests or code contributions. All development is managed solely by n1Kk085.

6. NO WARRANTY
   THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED. IN NO EVENT SHALL THE 
   AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY.

7. DINO DISCLAIMER
   By using this software, you acknowledge that we are not responsible if you are stunned by Purlovia, if your 
   servers are eaten by a Giga, if you are stepped on by a Bronto, or if your players are chased by a pack of 
   angry Terror Birds. This software is provided "as is" and we can't promise it won't bite.

---

TRADEMARK DISCLAIMER
PatchRaptor is an unofficial tool and is not affiliated with, endorsed by, or associated with Studio Wildcard 
or Snail Games. ARK: Survival Ascended is a trademark of Studio Wildcard.

---

THIRD-PARTY SOFTWARE LICENSES

The Software incorporates certain third-party software components that are subject to their respective open 
source licenses:

### Python Software Foundation License
Copyright (c) 2001-2023 Python Software Foundation; All Rights Reserved

### MIT License (CustomTkinter, discord.py)
Copyright (c) 2023 Tom Schimansky (CustomTkinter)
Copyright (c) 2015-2023 Rapptz (discord.py)

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated 
documentation files (the "Software"), to deal in the Software without restriction, including without limitation 
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software.

### Apache License 2.0 (aiohttp)
Copyright (c) 2013-2023 aiohttp contributors

### BSD 3-Clause License (psutil)
Copyright (c) 2009, Giampaolo Rodola'. All rights reserved.

### HPND License (Pillow/PIL)
Copyright © 1997-2011 by Secret Labs AB
Copyright © 1995-2011 by Fredrik Lundh
Copyright © 2010-2023 by Pillow Contributors

---

Last updated: February 8, 2026"""


        top = ctk.CTkToplevel(self.root)
        top.title("License Agreement")
        top.geometry("600x600")
        top.resizable(False, False)

        # Center the window on the screen
        top.update_idletasks()  # Ensure window size info is updated
        window_width = 600
        window_height = 600
        screen_width = top.winfo_screenwidth()
        screen_height = top.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        top.geometry(f"{window_width}x{window_height}+{x}+{y}")

        top.transient(self.root)
        top.grab_set()
        top.focus_force()

        text_area = ctk.CTkTextbox(top, wrap="word", font=(FONT_NAME, FONT_SIZE))
        text_area.insert("0.0", eula_text)
        text_area.configure(state="disabled")
        text_area.pack(expand=True, fill="both", padx=10, pady=10)

        btn_frame = ctk.CTkFrame(top)
        btn_frame.pack(pady=10)

        accept_btn = ctk.CTkButton(
            btn_frame,
            text="Accept",
            width=100,
            fg_color=BUTTON_COLOR,
            hover_color="#4665a7",
            command=lambda: self.on_eula_accept(top),
            font=(FONT_NAME, FONT_SIZE)
        )
        accept_btn.pack(side="left", padx=10)

        decline_btn = ctk.CTkButton(
            btn_frame,
            text="Decline",
            width=100,
            fg_color="#666666",
            hover_color="#444444",
            command=self.root.quit,
            font=(FONT_NAME, FONT_SIZE)
        )
        decline_btn.pack(side="left", padx=10)

    def save_server(self):
        server_data = {key: self.server_entries[key].get() for key in SERVER_KEYS}
        if all(not v.strip() for v in server_data.values()):
            return
        save_name = self.get_display_name(server_data)
        existing_indices = [i for i, s in enumerate(self.servers) if self.get_display_name(s) == save_name]
        if existing_indices:
            self.servers[existing_indices[0]] = server_data
        else:
            self.servers.append(server_data)
        self.update_server_listbox()

    def load_server(self):
        selected = self.server_listbox.get(tk.ACTIVE)
        if not selected or selected == "No servers yet":
            return
        for s in self.servers:
            if self.get_display_name(s) == selected:
                for key in SERVER_KEYS:
                    entry = self.server_entries[key]
                    entry.delete(0, tk.END)
                    value = s.get(key, "")
                    if value:  # Only insert if there's actual data
                        entry.insert(0, value)
                        entry.configure(text_color='white')  # Set text color to white for real data
                break

    def delete_server(self):
        selected = self.server_listbox.get(tk.ACTIVE)
        if not selected or selected == "No servers yet":
            return
        self.servers = [s for s in self.servers if self.get_display_name(s) != selected]
        self.update_server_listbox()
        if self.servers:
            self.load_server()
        else:
            self.clear_server_fields()

    def update_server_listbox(self):
        self.server_listbox.delete(0, tk.END)
        if self.servers:
            for s in self.servers:
                self.server_listbox.insert(tk.END, self.get_display_name(s))
            self.server_listbox.selection_set(tk.END)
        else:
            self.server_listbox.insert(tk.END, "No servers yet")

    def clear_server_fields(self):
        for key in SERVER_KEYS:
            self.server_entries[key].delete(0, tk.END)
        
        # Re-add placeholders after clearing
        self.add_placeholder(self.server_entries["server_name"], "eg scorched")
        self.add_placeholder(self.server_entries["server_display_name"], "eg Scorched Earth") 
        self.add_placeholder(self.server_entries["server_map_name"], "ScorchedEarth_WP")
        self.add_placeholder(self.server_entries["server_save_path"], "eg C:/...ShooterGame/Saved/Ragnarok")
        self.add_placeholder(self.server_entries["server_rcon_ip"], "127.0.0.1")
        self.add_placeholder(self.server_entries["server_rcon_port"], "eg 27015")
        self.add_placeholder(self.server_entries["server_rcon_password"], "change-me")
        self.add_placeholder(self.server_entries["server_start_command"], "eg C:/.../ShooterGame/Binaries/Win64/start.bat")

    def get_display_name(self, server):
        for key in ["server_name", "server_display_name", "map_abbrev", "server_map_name"]:
            val = server.get(key, "").strip()
            if val:
                return val
        return "<unnamed>"

    def add_placeholder(self, entry, placeholder):
        def on_focus_in(event):
            if entry.get() == placeholder:
                entry.delete(0, tk.END)
                entry.configure(text_color='white')
                
        def on_focus_out(event):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.configure(text_color='grey')
                
        entry.insert(0, placeholder)
        entry.configure(text_color='grey')
        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)

    def generate_config(self):
        # Get all general keys except backup-related and webhook-related ones
        backup_related_keys = ["backup_path", "backup_retention_count", "message_delete_seconds"]
        webhook_related_keys = ["webhook_shutdown", "webhook_reboot"]
        general_keys_filtered = [key for key in GENERAL_KEYS if key not in ["backup_retention_count", "message_delete_seconds"] and key not in webhook_related_keys]
       
        config = {key: self.general_entries[key].get() for key in general_keys_filtered}
        config["app_id"] = "2430930"  # Hardcoded for ARK
       
        # Add webhook messages with defaults
        # Add webhook messages (Preserve imported or use defaults)
        webhook_messages = {}
        webhook_messages["shutdown"] = self.imported_webhook_messages.get("shutdown", "Server is shutting down for maintenance.")
        webhook_messages["reboot"] = self.imported_webhook_messages.get("reboot", "Server is rebooting.")
        config["webhook_messages"] = webhook_messages
       
        # Add backup information
        backup_path_value = self.general_entries["backup_path"].get().strip()
        if backup_path_value.startswith("eg ") or not backup_path_value:
            backup_path_value = "C:\\Servers\\backups"

        backup_config = {
            "backup_path": backup_path_value,
            "backup_retention_count": 10,
            "message_delete_seconds": 86400
        }
        config["backup_config"] = backup_config
       
        # Add servers
        cluster_servers = []
        for server in self.servers:
            cluster_servers.append({
                "name": server.get("server_name", ""),
                "display_name": server.get("server_display_name", ""),
                "map_abbrev": server.get("map_abbrev", ""),
                "map_name": server.get("server_map_name", ""),
                "rcon_ip": server.get("server_rcon_ip", ""),
                "rcon_port": server.get("server_rcon_port", ""),
                "rcon_password": server.get("server_rcon_password", ""),
                "start_command": server.get("server_start_command", ""),
                "server_save_path": server.get("server_save_path", ""),
                "log_dir": server.get("server_log_dir", "")
            })
        config["cluster_servers"] = cluster_servers
        return config

    def save_config_with_modal(self):
        config = self.generate_config()
        try:
            with open("config.json", "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
            messagebox.showinfo("Success", "Config saved to config.json successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Error saving config:\n{e}")

    def import_config_with_modal(self):
        file_path = filedialog.askopenfilename(
            title="Select config.json file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not file_path:
            return
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for key in GENERAL_KEYS:
                if key in config:
                    self.general_entries[key].delete(0, tk.END)
                    self.general_entries[key].insert(0, config[key])
            
            # Handle backup_path from backup_config section
            if "backup_config" in config:
                backup_path = config["backup_config"].get("backup_path", "")
                if backup_path:
                    self.general_entries["backup_path"].delete(0, tk.END)
                    self.general_entries["backup_path"].insert(0, backup_path)

            # Preserve webhook messages
            if "webhook_messages" in config:
                self.imported_webhook_messages = config["webhook_messages"]
                    
            if "cluster_servers" in config:
                self.servers = []
                for server in config["cluster_servers"]:
                    self.servers.append({
                        "server_name": server.get("name", ""),
                        "server_display_name": server.get("display_name", ""),
                        "map_abbrev": server.get("map_abbrev", ""),
                        "server_map_name": server.get("map_name", ""),
                        "server_rcon_ip": server.get("rcon_ip", ""),
                        "server_rcon_port": server.get("rcon_port", ""),
                        "server_rcon_password": server.get("rcon_password", ""),
                        "server_start_command": server.get("start_command", ""),
                        "server_save_path": server.get("server_save_path", ""),
                        "server_log_dir": server.get("log_dir", "")
                    })
                self.update_server_listbox()
            messagebox.showinfo("Success", "Config imported successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Error importing config:\n{e}")
            
    def create_widgets(self):
        # Load and place logo
        try:
            image_path = resource_path("pr40.png")
            pil_image = Image.open(image_path)
            pil_image = pil_image.resize((40, 40), Image.Resampling.LANCZOS)
            self.logo_img = CTkImage(light_image=pil_image, dark_image=pil_image, size=(40, 40))
        except Exception as e:
            print("Failed to load image:", e)
            self.logo_img = None

        top_frame = ctk.CTkFrame(self.root, fg_color="#222222")
        top_frame.pack(fill="x", padx=5, pady=10)

        if self.logo_img:
            logo_label = ctk.CTkLabel(top_frame, image=self.logo_img, fg_color="#222222", text="")
            logo_label.pack(side="left", padx=(0, 5))
        else:
            print("No logo image to display")

        title_label = ctk.CTkLabel(top_frame, text="PatchRaptor Configurator",
                                   text_color=BUTTON_COLOR,
                                   font=(FONT_NAME, 20, "bold"))
        title_label.pack(side="left", padx=(0, 0))

        eula_button = ctk.CTkButton(top_frame, text="EULA", width=50,
                                    fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                    command=self.show_eula,
                                    font=(FONT_NAME, FONT_SIZE))
        eula_button.pack(side="right", padx=15)

        # General Configuration
        general_label = ctk.CTkLabel(self.root, text="General Configuration",
                                     text_color=BUTTON_COLOR,
                                     font=(FONT_NAME, 16, "bold"))
        general_label.pack(anchor="w", padx=10, pady=(10, 0))

        general_frame = ctk.CTkFrame(self.root, fg_color="#222222")
        general_frame.pack(fill="x", padx=10, pady=(0, 10))

        for key, label, placeholder, needs_browse in [
            ("bot_token", "Discord Bot Token", "MVsUj...07vE", False),
            ("channel_id", "Discord Channel ID", "1234567890", False),
            ("discord_webhook", "Discord Webhook URL (opt)", "https://discord.com/api/webhooks/...", False),
            ("steamcmd_path", "Path to steamcmd.exe", "eg C:/steamcmd/steamcmd.exe", True), 
            ("server_dir", "Path to Server Install", "eg C:/.../binaries/win64", True),
            ("rcon_tool", "Path to RCON Tool", "C:/rcon/rcon.exe", True),
            ("backup_path", "Backup Location", "eg C:/servers/backups", True)
            
        ]:
            row = ctk.CTkFrame(general_frame, fg_color="#222222")
            row.pack(fill="x", pady=2)

            label_widget = ctk.CTkLabel(row, text=label,
                                        width=200,
                                        anchor="w",
                                        text_color="white",
                                        font=(FONT_NAME, FONT_SIZE))
            label_widget.pack(side="left", padx=5)

            entry = ctk.CTkEntry(row, width=365, font=(FONT_NAME, FONT_SIZE),
                                placeholder_text=placeholder)
            entry.pack(side="left", padx=5, pady=3, fill="x")
            
            self.general_entries[key] = entry

            if needs_browse:
                browse_btn = ctk.CTkButton(row, text="Browse", width=60,
                                          fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                          command=lambda k=key: self.browse_path(k),
                                          font=(FONT_NAME, FONT_SIZE))
                browse_btn.pack(side="left", padx=5)
            else:
                spacer = tk.Label(row, width=8, bg="#222222")
                spacer.pack(side="left", padx=5)

        # Server Configuration
        server_label = ctk.CTkLabel(self.root, text="Server Configuration",
                                    text_color=BUTTON_COLOR,
                                    font=(FONT_NAME, 16, "bold"))
        server_label.pack(anchor="w", padx=10, pady=(10, 0))

        server_frame = ctk.CTkFrame(self.root, fg_color="#222222")
        server_frame.pack(fill="x", padx=10, pady=(0, 10))

        for key, label, placeholder, needs_browse in [
            ("server_name", "Server Short Name", "", False),
            ("server_display_name", "Server Display Name", "", False),
            ("map_abbrev", "Map Abbreviation", "eg SE", False),
            ("server_map_name", "Map Identifier", "", False),
            ("server_rcon_ip", "RCON IP Address", "", False),
            ("server_rcon_port", "RCON Port", "", False),
            ("server_rcon_password", "RCON Password", "", False),
            ("server_start_command", "Path to Start.bat", "", True),
            ("server_save_path", "Save Folder Path", "", True),
            ("server_log_dir", "Log Directory", "eg .../Saved/Logs", True)
        ]:
            row = ctk.CTkFrame(server_frame, fg_color="#222222")
            row.pack(fill="x", pady=2)

            label_widget = ctk.CTkLabel(row, text=label,
                                        width=200,
                                        anchor="w",
                                        text_color="white",
                                        font=(FONT_NAME, FONT_SIZE))
            label_widget.pack(side="left", padx=5)

            entry = ctk.CTkEntry(row, width=365, font=(FONT_NAME, FONT_SIZE),
                                 placeholder_text=placeholder)
            entry.pack(side="left", padx=5, pady=3, fill="x")
            
            self.server_entries[key] = entry

            if needs_browse:
                browse_btn = ctk.CTkButton(row, text="Browse", width=60,
                                          fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                          command=lambda k=key: self.browse_path(k),
                                          font=(FONT_NAME, FONT_SIZE))
                browse_btn.pack(side="left", padx=5)
            else:
                spacer = tk.Label(row, width=8, bg="#222222")
                spacer.pack(side="left", padx=5)

        # Server Listbox and Controls
        listbox_frame = ctk.CTkFrame(self.root, fg_color="#222222")
        listbox_frame.pack(fill="both", padx=15, pady=(0, 10), expand=False)

        self.server_listbox = tk.Listbox(listbox_frame, height=10,
                                         font=(FONT_NAME, FONT_SIZE),
                                         activestyle='none',
                                         highlightthickness=1,
                                         fg="white",
                                         bg="#222222",
                                         selectbackground=BUTTON_COLOR,
                                         selectforeground="white")
        self.server_listbox.pack(side="left", fill="both", expand=True, pady=5)

        btn_frame = ctk.CTkFrame(self.root, fg_color="#222222")
        btn_frame.pack(fill="x", padx=10, pady=(0, 15))

        save_btn = ctk.CTkButton(btn_frame, text="Save", width=80,
                                 fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                 command=self.save_server,
                                 font=(FONT_NAME, FONT_SIZE))
        save_btn.pack(side="left", padx=5)

        load_btn = ctk.CTkButton(btn_frame, text="Load", width=80,
                                 fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                 command=self.load_server,
                                 font=(FONT_NAME, FONT_SIZE))
        load_btn.pack(side="left", padx=5)

        delete_btn = ctk.CTkButton(btn_frame, text="Delete", width=80,
                                   fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                   command=self.delete_server,
                                   font=(FONT_NAME, FONT_SIZE))
        delete_btn.pack(side="left", padx=5)

        clear_btn = ctk.CTkButton(btn_frame, text="Clear", width=80,
                                  fg_color=BUTTON_COLOR, hover_color="#4665a7",
                                  command=self.clear_server_fields,
                                  font=(FONT_NAME, FONT_SIZE))
        clear_btn.pack(side="left", padx=5)

        save_config_btn = ctk.CTkButton(btn_frame, text="Save Config", width=110,
                                        fg_color=BUTTON_COLOR,
                                        hover_color="#4665a7",
                                        command=self.save_config_with_modal,
                                        font=(FONT_NAME, FONT_SIZE))
        save_config_btn.pack(side="right", padx=5)
        
        import_btn = ctk.CTkButton(btn_frame, text="Import Config", width=110,
                                   fg_color=BUTTON_COLOR,
                                   hover_color="#4665a7",
                                   command=self.import_config_with_modal,
                                   font=(FONT_NAME, FONT_SIZE))
        import_btn.pack(side="right", padx=5)

        self.add_placeholder(self.server_entries["server_name"], "eg scorched")
        self.add_placeholder(self.server_entries["server_display_name"], "eg Scorched Earth") 
        self.add_placeholder(self.server_entries["server_map_name"], "ScorchedEarth_WP")
        self.add_placeholder(self.server_entries["server_save_path"], "eg C:/...ShooterGame/Saved/Ragnarok")
        self.add_placeholder(self.server_entries["server_rcon_ip"], "127.0.0.1")
        self.add_placeholder(self.server_entries["server_rcon_port"], "eg 27015")
        self.add_placeholder(self.server_entries["server_rcon_password"], "change-me")
        self.add_placeholder(self.server_entries["server_start_command"], "eg C:/.../ShooterGame/Binaries/Win64/start.bat")
        self.add_placeholder(self.server_entries["server_log_dir"], "eg .../ShooterGame/Saved/Logs")

    def run(self):
        self.update_server_listbox()
        self.root.mainloop()


if __name__ == "__main__":
    root = ctk.CTk()
    app = ConfigApp(root)
    app.run()
