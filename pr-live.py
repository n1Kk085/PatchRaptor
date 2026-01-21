#!/usr/bin/env python3
"""
PatchRaptor Live Web Panel
Standalone web panel for ARK server monitoring
"""

import datetime
import json
import logging
import os
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from flask import Flask, jsonify, render_template_string, request, Response
import psutil
import asyncio
from asgiref.sync import async_to_sync

# Import the real PlayerManager from your module
# Adjust the import path based on your project structure
try:
    from player_manager import PlayerManager
except ImportError:
    # If player_manager is in a subdirectory, try this:
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'bot'))
    from patchraptor.player_manager import PlayerManager

# Load web panel configuration - required
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'webpanel_config.json')
try:
    with open(config_path, 'r') as f:
        webpanel_config = json.load(f)
    
    # Require both host and port in config
    HOST = webpanel_config['host']
    PORT = int(webpanel_config['port'])
    
    print(f"Web panel configuration loaded from {config_path}")
    print(f"Host: {HOST}, Port: {PORT}")
    
except FileNotFoundError:
    print(f"Error: webpanel_config.json not found at {config_path}")
    print("Please create the configuration file with 'host' and 'port' settings.")
    sys.exit(1)
    
except (json.JSONDecodeError, KeyError, ValueError) as e:
    print(f"Error: Invalid configuration in {config_path}: {e}")
    print("Please ensure the file contains valid JSON with 'host' and 'port' settings.")
    sys.exit(1)

# Main configuration file
CONFIG_FILE = "config.json"

# HTML Template for the web panel
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PatchRaptor - Player Panel</title>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.development.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.development.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
    <script src="https://unpkg.com/feather-icons@4.29.0/dist/feather.min.js"></script>
    <script src="https://cdn.tailwindcss.com"></script>
  </head>
  <body class="bg-gray-900 text-white font-mono">
    <div id="root"></div>
    <script type="text/babel">
        const { useState, useEffect } = React;
        
        // Status badge component
        const StatusBadge = ({ status }) => (
            React.createElement('div', { 
                className: `flex items-center text-xs px-2 py-1 rounded-full ${
                    status === 'online' 
                        ? 'bg-green-900 text-green-300 border border-green-700' 
                        : 'bg-red-900 text-red-300 border border-red-700'
                }`
            },
                React.createElement('div', { 
                    className: `w-2 h-2 rounded-full mr-1 ${status === 'online' ? 'bg-green-400' : 'bg-red-400'}` 
                }),
                status.toUpperCase()
            )
        );
        
        const FeatherIcon = ({name, className}) => {
            useEffect(() => {
                feather.replace();
            });
            return React.createElement('i', {
                'data-feather': name,
                className: className
            });
        };

        // Icon components
        const Users = ({className}) => React.createElement(FeatherIcon, {name: 'users', className});
        const Cpu = ({className}) => React.createElement(FeatherIcon, {name: 'cpu', className});
        const Clock = ({className}) => React.createElement(FeatherIcon, {name: 'clock', className});
        const Server = ({className}) => React.createElement(FeatherIcon, {name: 'server', className});
        const Activity = ({className}) => React.createElement(FeatherIcon, {name: 'activity', className});
        const Memory = ({className}) => React.createElement(FeatherIcon, {name: 'hard-drive', className});

        const ARKPlayerPanel = () => {
            const [serverData, setServerData] = React.useState({
                servers: [],
                totalPlayers: 0,
                total7dayPlayerAvg: 0,
                lastUpdate: null
            });
            
            // Memoize the update function to prevent unnecessary re-renders
            const updateServerData = React.useCallback(async () => {
                try {
                    console.log('[FRONTEND] Fetching server data...');
                    const response = await fetch('/api/status');
                    if (response.ok) {
                        const data = await response.json();
                        console.log('[FRONTEND] Received server data:', data);
                        
                        // Calculate 7-day average for each server
                        const serversWithAverages = Array.isArray(data.servers) 
                            ? data.servers.map(server => ({
                                ...server,
                                server7dayAvg: data.serverPlayerAverages?.[server.name] || 0,
                                uptime7day: data.serverUptimeAverages?.[server.name] || 0
                            }))
                            : [];
                        
                        setServerData(prevData => ({
                            ...prevData,
                            servers: serversWithAverages,
                            totalPlayers: data.totalPlayers || 0,
                            total7dayPlayerAvg: data.total7dayPlayerAvg || 0,
                            lastUpdate: data.lastUpdate || new Date().toISOString()
                        }));
                    } else {
                        console.error('[FRONTEND] Failed to fetch data:', response.status);
                    }
                } catch (err) {
                    console.error('[FRONTEND] Error updating data:', err);
                }
            }, []);
            
            // Set up polling
            React.useEffect(() => {
                let isMounted = true;
                let intervalId = null;

                const fetchData = async () => {
                    if (!isMounted) return;
                    try {
                        await updateServerData();
                    } catch (err) {
                        console.error('[FRONTEND] Error in fetch:', err);
                    }
                };
                
                fetchData();
                intervalId = setInterval(fetchData, 30000);
                
                return () => {
                    isMounted = false;
                    if (intervalId) clearInterval(intervalId);
                };
            }, [updateServerData]);
            
            // Debug effect to log server data changes
            React.useEffect(() => {
                if (serverData?.servers?.length > 0) {
                    console.log('[FRONTEND] Server data updated:', {
                        serverCount: serverData.servers.length,
                        totalPlayers: serverData.totalPlayers,
                        lastUpdate: serverData.lastUpdate,
                        servers: serverData.servers.map(s => ({
                            name: s.name,
                            playerCount: s.playerCount || 0,
                            playerList: s.players?.length || 0
                        }))
                    });
                }
            }, [serverData]);

            return (
                React.createElement('div', { className: 'min-h-screen bg-gray-900 text-white font-mono' },
                    React.createElement('div', { className: 'max-w-7xl mx-auto p-4' },
                        React.createElement('div', { 
                            className: 'flex items-center justify-between mb-6 bg-gray-800 rounded-lg p-3 border border-gray-700'
                        },
                            React.createElement('div', { className: 'flex items-center space-x-3' },
                                React.createElement('div', { 
                                    className: 'w-8 h-8 bg-blue-600 rounded flex items-center justify-center'
                                }, React.createElement(Server, { className: 'w-4 h-4' })),
                                React.createElement('div', null,
                                    React.createElement('h1', { className: 'text-xl font-bold text-blue-400' }, 'PatchRaptor'),
                                    React.createElement('p', { className: 'text-gray-400 text-xs' }, 'Server Metrics Panel')
                                )
                            ),
                            React.createElement('div', { className: 'text-right' },
                                React.createElement('div', { className: 'flex items-center space-x-2 text-green-400 text-sm' },
                                    React.createElement(Activity, { className: 'w-3 h-3' }),
                                    React.createElement('span', null, 'Live')
                                ),
                                React.createElement('p', { className: 'text-xs text-gray-500' },
                                    serverData.lastUpdate ? new Date(serverData.lastUpdate).toLocaleTimeString() : 'Never'
                                )
                            )
                        ),

                        React.createElement('div', { className: 'grid grid-cols-4 gap-3 mb-6' },
                            React.createElement('div', { className: 'bg-gray-800 rounded-lg p-3 border border-gray-700 text-center' },
                                React.createElement('div', { className: 'flex items-center justify-center mb-1' },
                                    React.createElement(Users, { className: 'w-4 h-4 text-blue-400 mr-1' }),
                                    React.createElement('span', { className: 'text-xs text-gray-400' }, 'Total Players')
                                ),
                                React.createElement('p', { className: 'text-xl font-bold text-blue-400' }, serverData.totalPlayers)
                            ),
                            React.createElement('div', { className: 'bg-gray-800 rounded-lg p-3 border border-gray-700 text-center' },
                                React.createElement('div', { className: 'flex items-center justify-center mb-1' },
                                    React.createElement(Server, { className: 'w-4 h-4 text-green-400 mr-1' }),
                                    React.createElement('span', { className: 'text-xs text-gray-400' }, 'Online')
                                ),
                                React.createElement('p', { className: 'text-xl font-bold text-green-400' }, 
                                    serverData.servers.filter(s => s.status === 'online').length
                                )
                            ),
                            React.createElement('div', { className: 'bg-gray-800 rounded-lg p-3 border border-gray-700 text-center' },
                                React.createElement('div', { className: 'flex items-center justify-center mb-1' },
                                    React.createElement(Clock, { className: 'w-4 h-4 text-purple-400 mr-1' }),
                                    React.createElement('span', { className: 'text-xs text-gray-400' }, 'Avg Uptime')
                                ),
                                React.createElement('p', { className: 'text-xl font-bold text-purple-400' },
                                    `${serverData.servers.length > 0 ? (serverData.servers.reduce((sum, s) => sum + (s.uptime7day || 0), 0) / serverData.servers.length).toFixed(1) : 0}%`
                                )
                            ),
                            React.createElement('div', { className: 'bg-gray-800 rounded-lg p-3 border border-gray-700 text-center' },
                                React.createElement('div', { className: 'flex items-center justify-center mb-1' },
                                    React.createElement(Activity, { className: 'w-4 h-4 text-yellow-400 mr-1' }),
                                    React.createElement('span', { className: 'text-xs text-gray-400' }, 'Avg Players')
                                ),
                                React.createElement('p', { className: 'text-xl font-bold text-yellow-400' },
                                    serverData.total7dayPlayerAvg.toFixed(1)
                                )
                            )
                        ),

                        // Server list container
                        (() => {
                            
                            // No servers state
                            if (serverData.servers.length === 0) {
                                return React.createElement('div', { 
                                    key: 'no-servers',
                                    className: 'col-span-2 text-center py-8' 
                                },
                                    React.createElement('p', { className: 'text-gray-400' }, 'No servers available')
                                );
                            }
                            
                            // Success state - render server list
                            return React.createElement('div', { 
                                key: 'server-list',
                                className: 'grid grid-cols-1 sm:grid-cols-2 gap-4 w-full' 
                            },
                                serverData.servers.map((server, index) =>
                                    React.createElement('div', { 
                                        key: index, 
                                        className: 'bg-gray-800 rounded-lg border border-gray-700 p-4'
                                    },
                                        // Map image with overlay for server info
                                        React.createElement('div', { className: 'relative mb-3 rounded-md overflow-hidden' },
                                            React.createElement('img', { 
                                                src: server.mapimage || '/static/maps/default.jpg',
                                                alt: server.displayname || server.name,
                                                className: 'w-full h-32 object-cover opacity-80 hover:opacity-100 transition-opacity',
                                                onError: (e) => { 
                                                    try { 
                                                        e.target.src = '/static/maps/default.jpg';
                                                        e.target.onerror = null;
                                                    } catch (err) {
                                                        console.error('Error setting fallback image:', err);
                                                    }
                                                }
                                            }),
                                            // Overlay with server info
                                            React.createElement('div', { className: 'absolute inset-0 bg-gradient-to-t from-black/80 to-transparent p-3 flex flex-col justify-between' },
                                                React.createElement('div', { className: 'flex justify-between items-start' },
                                                    React.createElement('h3', { className: 'text-lg font-bold text-white' }, 
                                                        server.displayName
                                                    ),
                                                    React.createElement('div', { className: 'flex items-center space-x-2 bg-black/60 px-2 py-1 rounded' },
                                                        React.createElement(Users, { className: 'w-4 h-4 text-white' }),
                                                        React.createElement('span', { className: 'text-white font-bold' }, server.playerCount || 0)
                                                    )
                                                ),
                                                React.createElement('div', { className: 'flex justify-between items-center' },
                                                    React.createElement(StatusBadge, { status: server.status }),
                                                    React.createElement('span', { className: 'text-xs text-gray-300' }, server.mapName)
                                                )
                                            )
                                        ),

                                        React.createElement('div', { className: 'mt-3 pt-3 border-t border-gray-700' },
                                            React.createElement('div', { className: 'grid grid-cols-4 gap-2 text-center text-xs' },
                                                // CPU
                                                React.createElement('div', { className: 'flex flex-col items-center' },
                                                    React.createElement('div', { className: 'flex items-center text-orange-400' },
                                                        React.createElement(Cpu, { className: 'w-3 h-3 mr-1' }),
                                                        React.createElement('span', null, 'CPU')
                                                    ),
                                                    React.createElement('span', { className: 'font-mono text-white' },
                                                        `${server && typeof server.cpu === 'number' ? server.cpu.toFixed(1) : '0.0'}%`
                                                    )
                                                ),
                                                // RAM
                                                React.createElement('div', { className: 'flex flex-col items-center' },
                                                    React.createElement('div', { className: 'flex items-center text-blue-400' },
                                                        React.createElement(Memory, { className: 'w-3 h-3 mr-1' }),
                                                        React.createElement('span', null, 'RAM')
                                                    ),
                                                    React.createElement('span', { className: 'font-mono text-white' },
                                                        `${server && typeof server.ram === 'number' ? server.ram.toFixed(1) : '0.0'} GB`
                                                    )
                                                ),
                                                // 7d Uptime
                                                React.createElement('div', { className: 'flex flex-col items-center' },
                                                    React.createElement('div', { className: 'flex items-center text-green-400' },
                                                        React.createElement(Clock, { className: 'w-3 h-3 mr-1' }),
                                                        React.createElement('span', null, 'Uptime')
                                                    ),
                                                    React.createElement('span', { className: 'font-mono text-white' },
                                                        `${server && typeof server.uptime7day === 'number' ? server.uptime7day.toFixed(1) : '0.0'}%`
                                                    )
                                                ),
                                                // 7d Avg Players
                                                React.createElement('div', { className: 'flex flex-col items-center' },
                                                    React.createElement('div', { className: 'flex items-center text-purple-400' },
                                                        React.createElement(Users, { className: 'w-3 h-3 mr-1' }),
                                                        React.createElement('span', null, '7d Avg')
                                                    ),
                                                    React.createElement('span', { className: 'font-mono text-white' },
                                                        server.server7dayAvg.toFixed(1)
                                                    )
                                                )
                                            )
                                        )
                                    )
                                )
                            )
                        })(),

                        // Bottom text
                        React.createElement('div', { className: 'mt-6 text-center text-gray-500 text-xs' },
                            React.createElement('p', null, 'Auto-refreshes every 30 seconds • Metrics updated in real-time')
                        )
                    )
                )
            );
        };

        const root = ReactDOM.createRoot(document.getElementById('root'));
        root.render(React.createElement(ARKPlayerPanel));
    </script>
  </body>
  </html>
'''

@dataclass
class ServerConfig:
    """Server configuration data class"""
    name: str
    display_name: str
    map_name: str
    rcon_ip: str
    rcon_port: int
    rcon_password: str
    start_command: str
    install_dir: str
    server_save_path: str
    server_log_path: str

class ConfigManager:
    """Manages application configuration and validation"""
    
    def __init__(self, config_file: str = CONFIG_FILE):
        self.config_file = config_file
        self.config = self._load_config()
        self._validate_config()
        
    def _load_config(self) -> Dict:
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file {self.config_file} not found")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file: {e}")
    
    def _validate_config(self):
        """Validate required configuration keys"""
        required_keys = [
            "bot_token", "channel_id", "app_id", "steamcmd_path", 
            "server_dir", "cluster_servers", "rcon_tool"
        ]
        missing = [key for key in required_keys if key not in self.config]
        if missing:
            raise ValueError(f"Missing required config keys: {missing}")
    
    def get(self, key: str, default=None):
        """Get configuration value with optional default"""
        return self.config.get(key, default)
    
    def get_server_configs(self) -> List[ServerConfig]:
        """Parse and return server configurations"""
        servers = []
        for srv_config in self.config.get("cluster_servers", []):
            try:
                servers.append(ServerConfig(
                    name=srv_config["name"],
                    display_name=srv_config.get("display_name", srv_config["name"]),
                    map_name=srv_config.get("map_name", ""),
                    rcon_ip=srv_config["rcon_ip"],
                    rcon_port=int(srv_config["rcon_port"]),
                    rcon_password=srv_config["rcon_password"],
                    start_command=srv_config["start_command"],
                    install_dir=srv_config.get("install_dir", self.config["server_dir"]),
                    server_save_path=srv_config.get("server_save_path", ""),
                    server_log_path=srv_config.get("server_log_path", "")
                ))
            except KeyError as e:
                print(f"Invalid server config, missing key: {e}")
        return servers

class ServerManager:
    """Manages ARK servers and processes"""
    
    def __init__(self, servers: List[ServerConfig], rcon_tool: str):
        self.servers = servers
        self.rcon_tool = rcon_tool
        self.server_lookup = {srv.name.lower(): srv for srv in servers}
        # Add alternative lookups
        for srv in servers:
            if srv.map_name:
                self.server_lookup[srv.map_name.lower()] = srv
            if srv.display_name:
                self.server_lookup[srv.display_name.lower()] = srv
    
    def find_server(self, identifier: str) -> Optional[ServerConfig]:
        """Find server by name, map_name, or display_name"""
        return self.server_lookup.get(identifier.lower())
    
    def get_display_name(self, server: ServerConfig) -> str:
        """Get display name for server"""
        return server.display_name or server.name
    
    def is_server_running(self):
        """Check if any ARK server is running"""
        try:
            for proc in psutil.process_iter(attrs=['name']):
                if proc.info['name'] == "ArkAscendedServer.exe":
                    return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return None
    
    def is_specific_server_running(self, server: ServerConfig) -> bool:
        """Check if specific server is running"""
        try:
            for proc in psutil.process_iter(attrs=['name', 'cmdline']):
                if proc.info['name'] == "ArkAscendedServer.exe":
                    cmdline = " ".join(proc.info.get("cmdline", [])).lower()
                    if server.name.lower() in cmdline or str(server.rcon_port) in cmdline:
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return False

class UptimeTracker:
    """Tracks server uptime statistics over time."""
    
    def __init__(self, data_file: str = 'uptime_stats.json'):
        self.data_file = data_file
        self.data = self._load_data()
        self._cleanup_old_entries()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load uptime stats data from file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading uptime stats: {e}")
        return {}
    
    def _save_data(self):
        """Save uptime stats data to file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            print(f"Error saving uptime stats: {e}")
    
    def _cleanup_old_entries(self):
        """Remove entries older than 7 days."""
        week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        
        if 'servers' in self.data:
            for server_name in list(self.data['servers'].keys()):
                # Clean up old entries
                server_data = self.data['servers'][server_name]
                server_data['entries'] = [
                    entry for entry in server_data.get('entries', [])
                    if entry.get('timestamp', 0) >= week_ago
                ]
                
                # Remove server if no entries left
                if not server_data['entries']:
                    self.data['servers'].pop(server_name, None)
        
        self._save_data()
    
    def record_uptime(self, server_name: str, is_online: bool):
        """Record server status (online/offline) with timestamp."""
        if not server_name:
            return
            
        if 'servers' not in self.data:
            self.data['servers'] = {}
            
        if server_name not in self.data['servers']:
            self.data['servers'][server_name] = {
                'entries': []
            }
        
        # Add entry with timestamp
        self.data['servers'][server_name]['entries'].append({
            'timestamp': time.time(),
            'is_online': is_online
        })
        
        self._cleanup_old_entries()
        self._save_data()
    
    def get_server_7day_uptime(self, server_name: str) -> float:
        """Calculate 7-day uptime percentage for a server."""
        if not server_name or 'servers' not in self.data or server_name not in self.data['servers']:
            return 0.0
            
        entries = self.data['servers'][server_name].get('entries', [])
        if not entries:
            return 0.0
        
        online_count = sum(1 for entry in entries if entry.get('is_online', False))
        return (online_count / len(entries)) * 100.0
    
    def get_average_7day_uptime(self) -> float:
        """Calculate average 7-day uptime across all servers."""
        if 'servers' not in self.data or not self.data['servers']:
            return 0.0
            
        total_uptime = 0.0
        server_count = 0
        
        for server_name, server_data in self.data['servers'].items():
            entries = server_data.get('entries', [])
            if entries:
                online_count = sum(1 for entry in entries if entry.get('is_online', False))
                total_uptime += (online_count / len(entries)) * 100.0
                server_count += 1
        
        return total_uptime / server_count if server_count > 0 else 0.0


class PlayerStatsTracker:
    """Tracks player statistics over time."""
    
    def __init__(self, data_file: str = 'player_stats.json'):
        self.data_file = data_file
        self.data = self._load_data()
        self._cleanup_old_entries()
    
    def _load_data(self) -> Dict[str, Any]:
        """Load player stats data from file."""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading player stats: {e}")
        return {}
    
    def _save_data(self):
        """Save player stats data to file."""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.data, f, indent=2)
        except IOError as e:
            print(f"Error saving player stats: {e}")
    
    def _cleanup_old_entries(self):
        """Remove entries older than 7 days."""
        week_ago = (datetime.datetime.now() - datetime.timedelta(days=7)).timestamp()
        
        if 'servers' in self.data:
            for server_name in list(self.data['servers'].keys()):
                # Clean up old entries
                server_data = self.data['servers'][server_name]
                server_data['entries'] = [
                    entry for entry in server_data.get('entries', [])
                    if entry.get('timestamp', 0) >= week_ago
                ]
                
                # Remove server if no entries left
                if not server_data['entries']:
                    self.data['servers'].pop(server_name, None)
        
        self._save_data()
    
    def record_players(self, server_name: str, map_name: str, player_count: int):
        """Record current player count for a server/map (1:1 relationship)."""
        if not server_name or not map_name:
            return
            
        # Use server_name as the primary key since server:map is 1:1
        if 'servers' not in self.data:
            self.data['servers'] = {}
        if server_name not in self.data['servers']:
            self.data['servers'][server_name] = {
                'map_name': map_name,
                'entries': []
            }
        
        # Add entry with timestamp
        self.data['servers'][server_name]['entries'].append({
            'timestamp': time.time(),
            'player_count': player_count
        })
        
        self._cleanup_old_entries()
    
    def get_server_7day_avg(self, server_name: str) -> float:
        """Get 7-day average player count for a specific server."""
        if not server_name or 'servers' not in self.data or server_name not in self.data['servers']:
            return 0.0
            
        entries = self.data['servers'][server_name].get('entries', [])
        if not entries:
            return 0.0
            
        total_players = sum(entry.get('player_count', 0) for entry in entries)
        return total_players / len(entries)
    
    # Note: get_map_7day_avg was removed since each server has exactly one map,
    # making it functionally equivalent to get_server_7day_avg
    
    def get_total_7day_avg(self) -> float:
        """Get 7-day average player count across all servers."""
        if 'servers' not in self.data or not self.data['servers']:
            return 0.0
        
        total_players = 0
        total_entries = 0
        
        # Get the most recent timestamp from any server
        latest_timestamp = max(
            (entry['timestamp'] 
             for server in self.data['servers'].values() 
             for entry in server.get('entries', [])),
            default=0
        )
        
        # Only consider entries from the last 7 days
        seven_days_ago = latest_timestamp - (7 * 24 * 60 * 60)
        
        for server_name, server_data in self.data['servers'].items():
            # Get entries from the last 7 days
            recent_entries = [
                entry for entry in server_data.get('entries', [])
                if entry.get('timestamp', 0) >= seven_days_ago
            ]
            
            if recent_entries:
                total_players += sum(entry.get('player_count', 0) for entry in recent_entries)
                total_entries += len(recent_entries)
        
        # Round to 1 decimal place for display
        return round(total_players / total_entries, 1) if total_entries > 0 else 0.0

# Global instances
config_manager = None
server_manager = None
player_manager = None
player_stats_tracker = PlayerStatsTracker()
uptime_tracker = UptimeTracker()
event_loop = None

async def background_update_task():
    """Background task to update player data continuously and record statistics"""
    while True:
        try:
            # print("[DEBUG] Running scheduled player data update...")
            await player_manager.update_active_players()
            
            # Log current player counts and record statistics
            total, details = await player_manager.get_total_players()
            # print(f"[DEBUG] Total players online: {total}")
            
            # Record player statistics and uptime for each server
            for server in server_manager.servers:
                display_name = server.display_name or server.name
                player_count = len(details.get(display_name, []))
                
                # Record player count in stats tracker
                player_stats_tracker.record_players(
                    server_name=server.name,
                    map_name=server.map_name,
                    player_count=player_count
                )
                
                # Record server status in uptime tracker
                uptime_tracker.record_uptime(
                    server_name=server.name,
                    is_online=server_manager.is_specific_server_running(server)
                )
                    
        except Exception as e:
            print(f"[ERROR] Failed to update player data: {e}")
            import traceback
            traceback.print_exc()
        
        await asyncio.sleep(30)

def run_event_loop(loop):
    """Run the event loop in a separate thread"""
    asyncio.set_event_loop(loop)
    loop.run_forever()

async def initialize_managers_async():
    """Async initialization of all managers"""
    global config_manager, server_manager, player_manager
    
    print("[DEBUG] Initializing managers...")
    config_manager = ConfigManager()
    servers = config_manager.get_server_configs()
    print(f"[DEBUG] Loaded {len(servers)} server configurations")
    

    
    server_manager = ServerManager(servers, config_manager.get("rcon_tool"))
    
    # Create player manager instance in READ-ONLY mode
    # This safely disables log file LOCKING/WRITING but allows PARSING for counts
    # It also skips loading bans.txt as per user request
    player_manager = PlayerManager(servers, read_only=True)
    
    print("[DEBUG] Initializing PlayerManager in read-only mode")
    await player_manager.initialize()
    print("[DEBUG] PlayerManager initialized (Read-Only)")
    
    # Skip the initial log file scan - we'll let the background task handle updates
    # This matches the bot's behavior for performance
    print("[DEBUG] ========================================")
    print("[DEBUG] Skipping initial log file scan")
    print("[DEBUG] First scan will occur in 30 seconds via background task")
    print("[DEBUG] ========================================")
    
    # Initialize empty player data
    total, details = 0, {server.name: [] for server in servers}
    print("[DEBUG] Initial player count: 0")
    
    # Start the background update task
    asyncio.create_task(background_update_task())
    print("[DEBUG] Managers initialized and background task started")

def initialize_managers():
    """Sync wrapper for async initialization"""
    global event_loop
    
    # Create event loop
    event_loop = asyncio.new_event_loop()
    
    # Start event loop in separate thread
    loop_thread = threading.Thread(target=run_event_loop, args=(event_loop,), daemon=True)
    loop_thread.start()
    
    # Run initialization
    future = asyncio.run_coroutine_threadsafe(initialize_managers_async(), event_loop)
    future.result(timeout=30)  # Wait up to 30 seconds for initialization

def create_web_app():
    """Create Flask web application for player panel"""
    app = Flask(__name__, static_url_path='', static_folder='static')
    # Ensure static directory exists
    os.makedirs('static/maps', exist_ok=True)
    
    # Add a route to serve static files
    @app.route('/static/<path:path>')
    def serve_static(path):
        return app.send_static_file(path)
    
    def check_auth():
        """Check if the provided credentials match the config"""
        auth = request.authorization
        return (auth and 
                'auth' in webpanel_config and 
                auth.username == webpanel_config['auth'].get('username') and 
                auth.password == webpanel_config['auth'].get('password'))

    def authenticate():
        """Sends a 401 response that enables basic auth"""
        return Response(
            'Could not verify your access level for that URL.\n'
            'You need to login with proper credentials', 401,
            {'WWW-Authenticate': 'Basic realm="Login Required"'})

    @app.route('/')
    def player_panel():
        if not check_auth():
            return authenticate()
        return render_template_string(HTML_TEMPLATE)
    
    @app.route('/favicon.ico')
    def favicon():
        return Response(b'', mimetype='image/x-icon')
        


    @app.route('/api/status')
    def get_status():
        """Get server status using the real PlayerManager"""
        # Protect this endpoint with the same auth as the dashboard
        if not check_auth():
            return authenticate()

        try:
            # Get player data from the real PlayerManager using async_to_sync
            total_players, server_details = async_to_sync(player_manager.get_total_players)()
            
            # Get server status
            servers_data = []
            for server in server_manager.servers:
                # Check if server is running
                is_online = server_manager.is_specific_server_running(server)
                
                # Get player data for this server
                display_name = server.display_name or server.name
                players_list = server_details.get(display_name, [])
                player_count = len(players_list)
                
                # Get system stats if available
                cpu_percent = 0.0
                memory_gb = 0.0
                
                if is_online:
                    try:
                        identifiers = [
                            server.map_name.lower() if server.map_name else "",
                            server.name.lower(),
                            str(server.rcon_port)
                        ]
                        
                        for proc in psutil.process_iter(attrs=['pid', 'name', 'cmdline']):
                            try:
                                proc_info = proc.info
                                proc_name = (proc_info.get('name') or '').lower()
                                cmdline_list = proc_info.get('cmdline', [])
                                
                                # Skip if cmdline is not a list or tuple
                                if not isinstance(cmdline_list, (list, tuple)):
                                    cmdline_list = [str(cmdline_list)]
                                
                                # Safely join the command line arguments
                                try:
                                    cmdline = ' '.join(cmdline_list).lower()
                                except (TypeError, AttributeError):
                                    cmdline = ''
                                
                                is_ark_process = (
                                    'arkascendedserver' in proc_name or
                                    'shootergameserver' in proc_name
                                )
                                
                                if is_ark_process and any(ident in cmdline for ident in identifiers if ident):
                                    try:
                                        process = psutil.Process(proc.pid)
                                        cpu_percent = max(0.0, process.cpu_percent(interval=0.1) / psutil.cpu_count())
                                        memory_info = process.memory_info()
                                        memory_gb = round(memory_info.rss / (1024 ** 3), 2)
                                        break
                                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                        continue
                                        
                            except Exception as proc_error:
                                print(f"Error processing process {getattr(proc, 'pid', 'unknown')}: {proc_error}")
                                continue
                    except Exception as e:
                        print(f"Error getting process info for {server.name}: {e}")
                
                # Map names to image paths
                map_images = {
                    'theisland': '/static/maps/theisland.jpg',
                    'scorched': '/static/maps/scorchedearth.jpg',
                    'thecenter': '/static/maps/thecenter.jpg',
                    'ragnarok': '/static/maps/ragnarok.jpg',
                    'aberration': '/static/maps/aberration.jpg',
                    'extinction': '/static/maps/extinction.jpg',
                    'valguero': '/static/maps/valguero.jpg',
                    'genesis': '/static/maps/genesis.jpg',
                    'crystalisles': '/static/maps/crystal.jpg',
                    'lostisland': '/static/maps/lostisland.jpg',
                    'fjordur': '/static/maps/fjordur.jpg',
                    'bobsmissions': '/static/maps/bobsmissions.jpg',
                    'clubark': '/static/maps/clubark.jpg',
                    'astraeos': '/static/maps/astraeos.jpg',
                    'default': '/static/maps/default.jpg'
                }
                
                # Clean and prepare the map name for lookup
                map_name = (server.map_name or '').lower().replace(' ', '').replace('_', '')
                map_key = next(
                    (key for key in map_images.keys() 
                     if key != 'default' and key in map_name),
                    'default'
                )
                map_image = map_images[map_key]
                # Get the 7-day player average from the tracker
                player_7day_avg = player_stats_tracker.get_server_7day_avg(server.name)
                
                server_data = {
                    'name': str(server.name),
                    'displayName': str(display_name),
                    'mapName': (str(server.map_name) if server.map_name else 'Unknown').replace('_', ' ').title(),
                    'mapimage': map_image,
                    'status': 'online' if is_online else 'offline',
                    'playerCount': int(player_count),
                    'players': [], # Sensitive data scrubbed (IDs/Names hidden)
                    'cpu': float(round(cpu_percent, 1)),
                    'ram': float(round(memory_gb, 1)),
                    'maxRam': 16.0,
                    'uptime7day': float(min(100.0, 99.5)),
                    'playerAvg7day': float(round(player_7day_avg, 1)),
                    'lastRestart': (datetime.datetime.now() - datetime.timedelta(hours=12)).strftime('%Y-%m-%d %H:%M')
                }
                
                servers_data.append(server_data)
                
            # Calculate totals and 7-day averages
            online_servers = sum(1 for s in servers_data if s['status'] == 'online')
            
            # Initialize server averages dictionaries
            server_player_averages = {}
            server_uptime_averages = {}
            
            # Get 7-day averages for each server and update server data
            for server_data in servers_data:
                server_name = server_data['name']
                
                # Get player average
                player_avg = player_stats_tracker.get_server_7day_avg(server_name)
                server_data['server7dayAvg'] = player_avg
                server_player_averages[server_name] = player_avg
                
                # Get uptime percentage
                uptime_pct = uptime_tracker.get_server_7day_uptime(server_name)
                server_data['uptime7day'] = uptime_pct
                server_uptime_averages[server_name] = uptime_pct
            
            # Get total 7-day averages
            total_player_avg = player_stats_tracker.get_total_7day_avg()
            total_uptime_avg = uptime_tracker.get_average_7day_uptime()
            
            return jsonify({
                'servers': servers_data,
                'serverPlayerAverages': server_player_averages,
                'serverUptimeAverages': server_uptime_averages,
                'totalPlayers': total_players,
                'total7dayPlayerAvg': total_player_avg,
                'total7dayUptimeAvg': total_uptime_avg,
                'serverCount': len(servers_data),
                'onlineCount': online_servers,
                'lastUpdate': datetime.datetime.now().isoformat(),
                'currentTime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        except Exception as e:
            print(f"Error in web API: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    # Disable Flask's default logging to avoid spam
    import logging as flask_logging
    flask_log = flask_logging.getLogger('werkzeug')
    flask_log.setLevel(flask_logging.ERROR)
    
    return app

def main():
    """Main entry point for the web panel"""
    print("PatchRaptor Live Web Panel")
    print("Initializing managers...")
    
    try:
        # Initialize all managers
        initialize_managers()
        
        from waitress import serve
        print(f"Starting production web server (Waitress) on {HOST}:{PORT}...")
        web_app = create_web_app()
        serve(web_app, host=HOST, port=PORT)
        
    except KeyboardInterrupt:
        print("\nShutting down...")
        if event_loop:
            event_loop.call_soon_threadsafe(event_loop.stop)
    except Exception as e:
        print(f"Error starting web panel: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
