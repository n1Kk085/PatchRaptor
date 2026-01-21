import asyncio
import subprocess
import json
import os
from typing import Optional, Dict, Any
from .log_manager import logger

VERSION_FILE = "version.txt"

class VersionManager:
    """Manages version tracking using version.txt"""
    
    def __init__(self, steamcmd_path: str, app_id: str):
        self.steamcmd_path = steamcmd_path
        self.app_id = app_id
    
    def save_version(self, build_id: str):
        from .log_manager import logger
        logger.debug_update(f"Starting save_version with build_id: {build_id}")
        try:
            # Use absolute path relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            version_path = os.path.join(base_dir, VERSION_FILE)
            
            logger.debug_update(f"Opening {version_path} for writing")
            with open(version_path, "w") as f:
                logger.debug_update(f"Writing build_id {build_id} to file")
                f.write(str(build_id))
            logger.debug_update(f"Successfully saved build ID {build_id} to {VERSION_FILE}")
            logger.log(f"Saved build ID {build_id} to {VERSION_FILE}")
        except Exception as e:
            logger.debug_update(f"Failed to save version to {VERSION_FILE}: {e}")
            logger.error_system(f"Failed to save version to {VERSION_FILE}: {e}")
    
    def get_current_version(self) -> str:
        from .log_manager import logger
        logger.debug_update("Starting get_current_version method")
        try:
            # Use absolute path relative to this file
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            version_path = os.path.join(base_dir, VERSION_FILE)
            
            logger.debug_update(f"Opening {version_path} for reading")
            if not os.path.exists(version_path):
                logger.debug_update("Version file does not exist")
                return "Unknown"
                
            with open(version_path, "r") as f:
                logger.debug_update("Reading version from file")
                version = f.read().strip()
                logger.debug_update(f"Successfully read version: {version}")
                return version
        except Exception as e:
            logger.debug_update(f"Failed to read version from {VERSION_FILE}: {e}")
            logger.debug_update("Returning 'Unknown' as fallback")
            return "Unknown"
    
    async def get_latest_build_id(self) -> str | None:
        from .log_manager import logger
        logger.debug_update("Starting get_latest_build_id method")
        try:
            logger.debug_update(f"Building SteamCMD command with app_id: {self.app_id}")
            cmd_args = [
                self.steamcmd_path,
                "+login", "anonymous",
                "+app_info_print", self.app_id,
                "+quit"
            ]
            logger.debug_update(f"SteamCMD command args: {cmd_args}")
            logger.debug_update("Executing SteamCMD command in separate thread")
            
            # Add timeout to prevent hanging
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        subprocess.run,
                        cmd_args,
                        shell=False,
                        capture_output=True,
                        text=True,
                        encoding='utf-8',
                        errors='replace'
                    ),
                    timeout=300  # 5 minute timeout
                )
            except asyncio.TimeoutError:
                logger.error_system("SteamCMD command timed out after 5 minutes")
                return None
                
            logger.debug_update(f"SteamCMD command completed with return code: {result.returncode}")
            
            # Log first 200 chars of stdout/stderr for debugging
            logger.debug_update(f"SteamCMD stdout (first 200 chars): {result.stdout[:200]}...")
            if result.stderr:
                logger.debug_update(f"SteamCMD stderr (first 200 chars): {result.stderr[:200]}...")
            
            if result.returncode != 0:
                logger.error_system(f"SteamCMD command failed with return code: {result.returncode}")
                if "Not logged in" in result.stderr:
                    logger.error_system("SteamCMD authentication failed - check network connectivity")
                return None
            
            # More robust parsing of build ID
            for line in result.stdout.split('\n'):
                line = line.strip()
                if 'buildid' in line.lower():
                    # Try to extract from "buildid" "12345"
                    if 'buildid' in line and '"' in line:
                        parts = [p.strip('"\' ') for p in line.split('"') if p.strip()]
                        for i, part in enumerate(parts):
                            if 'buildid' in part.lower() and i + 1 < len(parts):
                                build_id = parts[i + 1]
                                logger.debug_update(f"Extracted build_id: {build_id}")
                                return build_id
                    
                    # If still not found, try splitting by whitespace
                    if ' ' in line:
                        for part in line.split():
                            if part.isdigit() and len(part) > 5:  # Build IDs are usually long numbers
                                logger.debug_update(f"Extracted build_id from whitespace: {part}")
                                return part
            
            logger.error_system("Could not parse build ID from SteamCMD output")
            logger.debug_update(f"First 500 chars of output: {result.stdout[:500]}")
            return None
            
        except Exception as e:
            logger.error_system(f"Unexpected error in get_latest_build_id: {str(e)}", exc_info=True)
            return None