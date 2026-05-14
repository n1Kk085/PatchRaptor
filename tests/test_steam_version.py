import asyncio
import subprocess
import os
import sys

# Mocking the VersionManager logic to test parsing
APP_ID = "2430930" # ARK Ascended AppID
STEAMCMD_PATH = r"C:\Users\nikko\Desktop\05-01\steamcmd\steamcmd.exe" # Guessing path or needs config

async def get_latest_build_id():
    cmd_args = [
        STEAMCMD_PATH,
        "+login", "anonymous",
        "+app_info_print", APP_ID,
        "+quit"
    ]
    print(f"Running: {cmd_args}")
    
    process = await asyncio.create_subprocess_exec(
        *cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    
    print(f"Return Code: {process.returncode}")
    print(f"Stdout len: {len(stdout)}")
    
    # Simulation of parsing logic
    for line in stdout.decode('utf-8', errors='replace').split('\n'):
        if 'buildid' in line.lower():
            print(f"DEBUG LINE: {line.strip()}")
            # Original logic
            if 'buildid' in line and '"' in line:
                parts = [p.strip('"\' ') for p in line.split('"') if p.strip()]
                for i, part in enumerate(parts):
                    if 'buildid' in part.lower() and i + 1 < len(parts):
                        build_id = parts[i + 1]
                        print(f"FOUND: {build_id}")
                        return build_id
    print("NOT FOUND")

if __name__ == "__main__":
    # We need to find actual steamcmd path from config (mocking here for quick test)
    # If the user has it elsewhere, this script fails. 
    # Better to just use the existing class if I can import it.
    pass
