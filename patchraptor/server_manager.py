from typing import List, Optional
import psutil
import json
import os
import sys
from .models import ServerConfig
from .exceptions import (
    ServerError,
    ServerNotFoundError,
    ServerNotRunningError,
    ServerAlreadyRunningError,
    ServerOperationError,
    ProcessError,
    ProcessNotFoundError,
    ProcessOperationError
)

class ServerManager:
    """Manages ARK servers and processes"""
    def __init__(self, servers: List[ServerConfig], rcon_tool: str):
        self.servers = servers
        self.rcon_tool = rcon_tool
        self.server_lookup = {srv.name.lower(): srv for srv in servers}
        for srv in servers:
            if srv.map_name:
                self.server_lookup[srv.map_name.lower()] = srv
            if srv.display_name:
                self.server_lookup[srv.display_name.lower()] = srv
        
        # PID Tracking (Phase 2 Hardening)
        self.pids: dict[str, int] = {}
        self._load_pids()

    def find_server(self, identifier: str) -> ServerConfig:
        from .log_manager import logger
        logger.debug_server(f"Looking up server: '{identifier}'")
        
        server = self.server_lookup.get(identifier.lower())
        if not server:
            logger.debug_server(f"Server not found: '{identifier}'")
            raise ServerNotFoundError(identifier)
        
        logger.debug_server(f"Server found: {server.name} -> {server.display_name or server.name}")
        return server

    def get_display_name(self, server: ServerConfig) -> str:
        display_name = server.display_name or server.name
        return display_name

    def _get_pid_file(self) -> str:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.abspath(".")
        return os.path.join(base_dir, ".pids")

    def _load_pids(self):
        pid_file = self._get_pid_file()
        if os.path.exists(pid_file):
            try:
                with open(pid_file, 'r') as f:
                    self.pids = json.load(f)
            except Exception:
                self.pids = {}

    def _save_pids(self):
        pid_file = self._get_pid_file()
        try:
            with open(pid_file, 'w') as f:
                json.dump(self.pids, f)
        except Exception:
            pass

    def get_running_process(self, server: ServerConfig) -> Optional[psutil.Process]:
        """Get the actual psutil.Process object for a server if it's running."""
        # Primary: Check tracked PID
        tracked_pid = self.pids.get(server.name)
        if tracked_pid and isinstance(tracked_pid, (int, float)):
            try:
                proc = psutil.Process(int(tracked_pid))
                if proc.is_running():
                    # Double-check it's still an ARK process (PIDs can be reused)
                    try:
                        cmdline = " ".join(proc.cmdline()).lower()
                        if server.name.lower() in cmdline or (server.map_name and server.map_name.lower() in cmdline):
                            return proc
                    except psutil.AccessDenied:
                        # Fallback for Zombie process where cmdline is denied but name is visible
                        proc_name = proc.name().lower()
                        if "arkascendedserver" in proc_name or "shootergameserver" in proc_name or "ark" in proc_name:
                            from .log_manager import logger
                            logger.warning_system(f"Ghost Recovery fallback: cmdline denied for PID {tracked_pid}, relying on process name '{proc_name}'")
                            return proc
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                # PID no longer valid
                if server.name in self.pids:
                    del self.pids[server.name]
                    self._save_pids()

        # Fallback: Discovery
        identifiers = [
            server.map_name.lower() if server.map_name else "",
            server.name.lower(),
            str(server.rcon_port)
        ]
        
        try:
            for proc in psutil.process_iter(attrs=["name", "exe", "cmdline", "cwd"]):
                pinfo = proc.info
                p_name = (pinfo.get("name") or "").lower()
                p_exe = (pinfo.get("exe") or "").lower()
                p_cwd = (pinfo.get("cwd") or "").lower()
                cmdline_list = pinfo.get("cmdline") or []
                cmdline_str = " ".join(cmdline_list).lower()
                
                # Verify it's an ARK server process
                is_ark = "arkascendedserver" in p_name or "shootergameserver" in p_name or "ark" in p_exe
                if not is_ark:
                    continue
                
                # Check identifiers against cmdline, cwd, or exe
                if any(ident and (ident in cmdline_str or ident in p_cwd or ident in p_exe) for ident in identifiers):
                    # Found via discovery - update tracking
                    self.pids[server.name] = proc.pid
                    self._save_pids()
                    return proc
        except Exception:
            pass
            
        return None

    def is_server_running(self) -> Optional[psutil.Process]:
        """Check if any configured server is running and return its process object."""
        for server in self.servers:
            proc = self.get_running_process(server)
            if proc:
                return proc
        return None

    def is_specific_server_running(self, server: ServerConfig) -> bool:
        """Check if a specific server is running"""
        return self.get_running_process(server) is not None

    def start_server(self, server: ServerConfig):
        import subprocess
        from .log_manager import logger
        
        logger.info_system(f"Starting {server.name}...")
        if self.is_specific_server_running(server):
            raise ServerAlreadyRunningError(server.name)
        
        try:
            cwd = server.install_dir if server.install_dir else None
            
            if os.name == 'nt':
                # On Windows, shell=True with the raw string is more reliable for 
                # complex ARK command lines which often contain dozens of arguments 
                # and nested quotes.
                proc = subprocess.Popen(
                    server.start_command,
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=cwd
                )
            else:
                import shlex
                cmd_args = shlex.split(server.start_command)
                proc = subprocess.Popen(
                    cmd_args,
                    shell=False,
                    cwd=cwd
                )
            self.pids[server.name] = proc.pid
            self._save_pids()
            logger.debug_server(f"Server started (PID: {proc.pid})")
        except Exception as e:
            logger.error_system(f"Failed to start server {server.name}: {e}")
            raise ServerOperationError("start", server.name, str(e))

    async def wait_for_servers_online(self, servers, timeout=600, check_interval=10):
        import asyncio
        from .service_locator import ServiceLocator
        from .log_manager import logger
        
        logger.info_system(f"Waiting for {len(servers)} servers to come online...")
        start_time = asyncio.get_event_loop().time()
        rcon_manager = ServiceLocator.get("RCONManager")
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            all_online = True
            for server in servers:
                if not self.is_specific_server_running(server):
                    all_online = False
                    break
                try:
                    await rcon_manager.execute_for_server(server, "SaveWorld")
                except Exception:
                    all_online = False
                    break
            if all_online: return True
            await asyncio.sleep(check_interval)
        return False

    async def wait_for_server_shutdown(self, server: ServerConfig, timeout: int = 300) -> bool:
        import asyncio
        from .log_manager import logger
        if not self.is_specific_server_running(server):
            return True
        
        try:
            for _ in range(timeout):
                if not self.is_specific_server_running(server):
                    return True
                await asyncio.sleep(1)
            return False
        except Exception as e:
            raise ServerOperationError("wait for shutdown", server.name, str(e))

    def force_stop_server(self, server: ServerConfig) -> bool:
        """
        Ghost Recovery: Forcefully terminate the server process and its children.
        Used as a fallback when graceful shutdown fails.
        """
        import psutil
        from .log_manager import logger
        
        proc = self.get_running_process(server)
        if not proc:
            logger.debug_server(f"No process found to force stop for {server.name}")
            return True
            
        try:
            logger.warning_system(f"Ghost Recovery: Forcefully terminating {server.name} (PID: {proc.pid})")
            
            # Kill children first
            children = proc.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            # Kill the main process
            proc.kill()
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                logger.warning_system(f"{server.name} did not exit after kill, retrying termination")
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
            
            # Clear tracking
            if server.name in self.pids:
                del self.pids[server.name]
                self._save_pids()
                
            logger.info_system(f"Ghost Recovery: {server.name} terminated successfully")
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            logger.debug_server(f"Process already gone or access denied for {server.name}")
            return True
        except Exception as e:
            logger.error_system(f"Ghost Recovery failed for {server.name}: {e}")
            return False
