import subprocess
import asyncio
import shlex
import re
from .models import ServerConfig
from .log_manager import logger
from .exceptions import (
    RCONError,
    RCONConnectionError,
    RCONCommandError,
    RCONValidationError
)

class RCONManager:
    """Manages RCON communications"""
    def __init__(self, rcon_tool: str):
        self.rcon_tool = rcon_tool
    
    def _validate_rcon_command(self, cmd: str) -> None:
        """Validate RCON command to prevent injection attacks"""
        logger.debug_rcon(f"Validating RCON command: {cmd}")
        
        # Block potentially dangerous characters that could enable command injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '{', '}', '<', '>', '\\', '\n', '\r']
        
        for char in dangerous_chars:
            if char in cmd:
                logger.debug_rcon(f"Command validation failed - dangerous character: '{char}'")
                raise RCONValidationError(cmd, f"Command contains dangerous character: '{char}'")
        
        # Allow specific safe RCON commands used in the codebase
        safe_patterns = [
            r'^GetGameLog$',            # Get game log
            r'^SaveWorld$',             # Save world command
            r'^ShowPlayers$',           # Show players command
            r'^ServerChat .+$',         # ServerChat with any message
            r'^KickPlayer .+$',         # KickPlayer with player name
            r'^BanPlayer .+$',          # BanPlayer with player name
            r'^UnbanPlayer .+$',        # UnbanPlayer with player name/ID
            r'^ListPlayers$',           # List players command
            r'^DoExit$',                # Server shutdown command
        ]
        for pattern in safe_patterns:
            if re.match(pattern, cmd):
                logger.debug_rcon(f"Command validation successful - matched pattern: {pattern}")
                return
        
        # If no pattern matches, command is not allowed
        logger.debug_rcon(f"Command validation failed - no matching safe pattern")
        raise RCONValidationError(cmd, "Command not in allowed safe patterns")
    def create_command_args(self, ip: str, port: int, password: str, cmd: str) -> list:
        """Create safe RCON command arguments with validation"""
        logger.debug_rcon(f"Creating command arguments for {ip}:{port}, command: {cmd}")

        # Validate command to prevent injection
        self._validate_rcon_command(cmd)

        # Construct the command arguments list
        cmd_args = [
            self.rcon_tool,
            f"ip={ip}",
            f"port={port}",
            f"pwd={password}",
            f"cmd={cmd}"
        ]
        logger.debug_rcon(f"Command arguments created successfully: {cmd_args}")
        return cmd_args
    
    async def execute_command(self, ip: str, port: int, password: str, cmd: str) -> str:
        """Execute RCON command safely with validation to prevent injection"""
        import time
        start_time = time.time()
        logger.debug_rcon(f"Executing RCON command: {cmd} on {ip}:{port}")
        try:
            # Create the safe command arguments
            cmd_args = self.create_command_args(ip, port, password, cmd)
            logger.debug_rcon(f"RCON command args: {cmd_args}")

            # For DoExit commands, don't use check=True since they often return non-zero exit codes when successful
            if cmd == "DoExit":
                logger.debug_rcon(f"Executing DoExit command (special handling)")
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd_args,
                    shell=False,
                    capture_output=True,
                    text=True,
                    check=False,  # Don't check return code for DoExit
                    stdin=subprocess.DEVNULL,
                    creationflags=creationflags
                )
                execution_time = time.time() - start_time
                logger.debug_rcon(f"DoExit execution time: {execution_time:.2f}s")
                
                # For DoExit, we consider it successful if it ran without stderr and no RCON exception, even with non-zero exit code
                if result.stderr:
                    logger.debug_rcon(f"DoExit stderr: {result.stderr.strip()}")
                    raise RCONCommandError(cmd, f"{ip}:{port}", result.stderr.strip())
                
                # Check for RCON exception pattern in stdout
                stdout_content = result.stdout.strip()
                logger.debug_rcon(f"DoExit stdout: {stdout_content[:200]}...")
                if "RCON Exception" in stdout_content or "One or more errors occurred" in stdout_content:
                    logger.debug_rcon(f"DoExit detected RCON exception in output")
                    raise RCONCommandError(cmd, f"{ip}:{port}", stdout_content)
                
                logger.debug_rcon(f"DoExit command successful")
                return stdout_content
            else:
                logger.debug_rcon(f"Executing regular RCON command")
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd_args,
                    shell=False,
                    capture_output=True,
                    text=True,
                    check=True,  # Use check=True for other commands
                    stdin=subprocess.DEVNULL,
                    creationflags=creationflags
                )
                execution_time = time.time() - start_time
                logger.debug_rcon(f"RCON execution time: {execution_time:.2f}s")
                
                if result.stderr:
                    logger.debug_rcon(f"RCON stderr: {result.stderr.strip()}")
                    raise RCONCommandError(cmd, f"{ip}:{port}", result.stderr.strip())
                
                stdout_content = result.stdout.strip()
                logger.debug_rcon(f"RCON stdout: {stdout_content[:200]}...")
                logger.debug_rcon(f"RCON command successful")
                return stdout_content
            
        except subprocess.CalledProcessError as e:
            execution_time = time.time() - start_time
            error_msg = e.stderr.strip() if e.stderr else f"Process exited with code {e.returncode}"
            logger.debug_rcon(f"RCON CalledProcessError after {execution_time:.2f}s: {error_msg}")
            raise RCONCommandError(cmd, f"{ip}:{port}", error_msg)
        except RCONValidationError:
            logger.debug_rcon(f"RCON validation error for command: {cmd}")
            # Re-raise validation errors as-is
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            logger.debug_rcon(f"RCON connection error after {execution_time:.2f}s: {str(e)}")
            raise RCONConnectionError(f"{ip}:{port}", str(e))

    async def execute_for_server(self, server: ServerConfig, cmd: str) -> str:
        """Execute RCON command for a specific server"""
        logger.debug_rcon(f"Executing command for server: {server.name} ({server.rcon_ip}:{server.rcon_port})")
        result = await self.execute_command(server.rcon_ip, server.rcon_port, server.rcon_password, cmd)
        logger.debug_rcon(f"Command execution completed for server: {server.name}")
        return result
