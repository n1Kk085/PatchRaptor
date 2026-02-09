from typing import List, Optional
import psutil
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
        from .log_manager import logger
        display_name = server.display_name or server.name
        logger.debug_server(f"Display name for {server.name}: '{display_name}'")
        return display_name

    def is_server_running(self) -> Optional[psutil.Process]:
        """Check if any ARK server process is running"""
        from .log_manager import logger
        logger.debug_server("Checking for ARK server processes...")
        
        try:
            ark_processes_found = 0
            for proc in psutil.process_iter(attrs=["name", "exe", "cmdline"]):
                proc_info = proc.info
                proc_name = proc_info.get("name", "") or ""
                proc_exe = proc_info.get("exe", "") or ""
                cmdline = proc_info.get("cmdline", []) or []
                
                # Convert to lowercase safely
                proc_name = proc_name.lower()
                proc_exe = proc_exe.lower()
                
                # Multiple ways to identify ARK server processes
                is_ark_process = (
                    proc_name == "arkascendedserver.exe" or
                    "arkascendedserver" in proc_name or
                    "ark" in proc_exe and "server" in proc_exe or
                    any("ark" in arg.lower() for arg in cmdline)
                )
                
                if is_ark_process:
                    ark_processes_found += 1
                    logger.debug_server(f"ARK process found: PID {proc.pid} ({proc_name})")
                    return proc
            
            logger.debug_server(f"No ARK processes found (scanned all processes)")
            
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # These are expected exceptions when processes disappear during iteration
            pass
        except psutil.Error as e:
            from .log_manager import logger
            logger.error_system(f"Unexpected psutil error: {e}")
            raise ProcessOperationError("monitor", "ARK server", str(e))
        return None

    def is_specific_server_running(self, server: ServerConfig) -> bool:
        """Check if a specific server is running using multiple identification methods"""
        identifiers = [
            server.map_name.lower() if server.map_name else "",
            server.name.lower(),
            str(server.rcon_port)
        ]
        
        try:
            for proc in psutil.process_iter(attrs=["name", "exe", "cmdline", "cwd"]):
                proc_info = proc.info
                proc_name = proc_info.get("name", "") or ""
                proc_exe = proc_info.get("exe", "") or ""
                proc_cwd = proc_info.get("cwd", "") or ""
                cmdline = proc_info.get("cmdline", []) or []
                
                # Convert to lowercase safely
                proc_name = proc_name.lower()
                proc_exe = proc_exe.lower()
                proc_cwd = proc_cwd.lower()
                
                # First, verify it's an ARK server process
                is_ark_process = (
                    proc_name == "arkascendedserver.exe" or
                    "arkascendedserver" in proc_name or
                    "ark" in proc_exe and "server" in proc_exe
                )
                
                if not is_ark_process:
                    continue
                
                # Multiple matching strategies for server identification
                for ident in identifiers:
                    if not ident:
                        continue
                    
                    # Strategy 1: Check command line arguments for exact matches
                    cmdline_str = " ".join(cmdline).lower()
                    if ident in cmdline_str:
                        # More specific validation - ensure it's not a partial match
                        if self._is_valid_server_match(cmdline_str, ident):
                            return True
                    
                    # Strategy 2: Check working directory
                    if ident in proc_cwd:
                        return True
                    
                    # Strategy 3: Check executable path
                    if ident in proc_exe:
                        return True
                    
                    for arg in cmdline:
                        arg_lower = arg.lower()
                        if ident == arg_lower or f"{ident}?" in arg_lower or f"{ident}=" in arg_lower:
                            return True
                        
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            # These are expected exceptions when processes disappear during iteration
            pass
        except psutil.Error as e:
            from .log_manager import logger
            logger.error_system(f"Unexpected psutil error checking server {server.name}: {e}")
            raise ProcessOperationError("monitor", server.name, str(e))
        except Exception as e:
            from .log_manager import logger
            logger.error_system(f"Unexpected error checking server {server.name}: {e}")
            raise ServerOperationError("monitor", server.name, str(e))
        return False
    
    def _is_valid_server_match(self, cmdline_str: str, identifier: str) -> bool:
        """Validate that the identifier match is not a false positive"""
        # Split the command line into words
        words = cmdline_str.split()
        
        # Look for exact word matches or parameter matches
        for word in words:
            # Exact match
            if word == identifier:
                return True
            
            # Parameter match (e.g., -map=identifier or ?identifier)
            if identifier in word and (word.startswith(identifier) or 
                                     f"?{identifier}" in word or 
                                     f"={identifier}" in word):
                return True
        
        return False

    def start_server(self, server: ServerConfig):
        import subprocess
        import shlex
        from .log_manager import logger
        
        logger.info_system(f"Starting {server.name}...")
        logger.debug_server(f"Starting server: {server.name}")
        
        # Check if server is already running
        logger.debug_server(f"Checking if server {server.name} is already running")
        if self.is_specific_server_running(server):
            logger.debug_server(f"Server {server.name} is already running, cannot start")
            raise ServerAlreadyRunningError(server.name)
        
        logger.debug_server(f"Server {server.name} is not running, proceeding with startup")
        
        try:
            # Debug: Log server configuration details
            logger.debug_server(f"Starting server {server.name}")
            logger.debug_server(f"start_command = '{server.start_command}'")
            logger.debug_server(f"install_dir = '{server.install_dir}'")
            
            # Parse command safely - handle Windows paths properly
            import os
            if os.name == 'nt':  # Windows
                logger.debug_server(f"Parsing Windows command: {server.start_command}")
                # For Windows, we need to handle paths with spaces and backslashes
                # If the command starts with a quoted path, handle it specially
                if server.start_command.startswith('"') and '"' in server.start_command[1:]:
                    # Find the closing quote
                    end_quote = server.start_command.find('"', 1)
                    if end_quote > 1:
                        executable = server.start_command[1:end_quote]
                        args = server.start_command[end_quote+1:].strip()
                        cmd_args = [executable]
                        if args:
                            cmd_args.extend(args.split())
                        logger.debug_server(f"Parsed quoted command: executable='{executable}', args='{args}'")
                    else:
                        # Fallback: just split by spaces
                        cmd_args = server.start_command.split()
                        logger.debug_server(f"Fallback parsing: split by spaces, got {len(cmd_args)} args")
                else:
                    # No quotes, check if it's a single path
                    if ' ' not in server.start_command:
                        cmd_args = [server.start_command]
                        logger.debug_server(f"Single command without spaces: {cmd_args}")
                    else:
                        # Try to split but preserve the first part as the executable
                        parts = server.start_command.split()
                        cmd_args = [parts[0]]
                        if len(parts) > 1:
                            cmd_args.extend(parts[1:])
                        logger.debug_server(f"Multi-part command: executable='{parts[0]}', {len(parts)-1} args")
            else:
                # Unix-like systems, use shlex.split
                logger.debug_server(f"Parsing Unix command using shlex.split")
                cmd_args = shlex.split(server.start_command)
                logger.debug_server(f"Parsed Unix command: {cmd_args}")
            
            logger.debug_server(f"Final cmd_args = {cmd_args}")
            
            # Set working directory to server install directory
            cwd = server.install_dir if server.install_dir else None
            logger.debug_server(f"Working directory (cwd) = {cwd}")
            
            logger.debug_server(f"Executing subprocess.Popen with cmd_args and cwd")
            subprocess.Popen(
                cmd_args,
                shell=False,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                cwd=cwd  # Set working directory to server install directory
            )
            logger.debug_server(f"Server start command executed successfully for {server.name}")
        except (OSError, ValueError) as e:
            logger.error_system(f"Failed to start server {server.name}: {e}")
            logger.debug_server(f"OSError/ValueError starting server {server.name}: {e}")
            raise ServerOperationError("start", server.name, str(e))
        except Exception as e:
            logger.error_system(f"Unexpected error starting server {server.name}: {e}")
            logger.debug_server(f"Unexpected exception starting server {server.name}: {e}")
            raise ServerOperationError("start", server.name, str(e))

    async def wait_for_server_shutdown(self, server: ServerConfig, timeout: int = 300) -> bool:
        """Wait for a specific server to shut down using robust process detection"""
        import asyncio
        from .log_manager import logger
        
        logger.debug_server(f"Waiting for server shutdown: {server.name}, timeout: {timeout}s")
        
        if not self.is_specific_server_running(server):
            logger.debug_server(f"Server {server.name} is already not running, returning True")
            return True  # Server is already not running
        
        logger.debug_server(f"Server {server.name} is currently running, starting shutdown wait loop")
        
        try:
            for i in range(timeout):
                logger.debug_server(f"Shutdown check iteration {i+1}/{timeout}")
                # Use the robust server detection method
                still_running = self.is_specific_server_running(server)
                logger.debug_server(f"Server {server.name} still running: {still_running}")
                
                if not still_running:
                    logger.debug_server(f"Server {server.name} has successfully shut down")
                    return True
                
                logger.debug_server(f"Server still running, sleeping for 1 second")
                await asyncio.sleep(1)
            
            logger.warning_system(f"Timeout waiting for server {server.name} to shut down after {timeout} seconds")
            logger.debug_server(f"Shutdown timeout reached for server {server.name}")
            return False
        except Exception as e:
            logger.error_system(f"Error while waiting for server {server.name} shutdown: {e}")
            logger.debug_server(f"Exception during shutdown wait for server {server.name}: {e}")
            raise ServerOperationError("wait for shutdown", server.name, str(e))
