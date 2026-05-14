@echo off
title PatchRaptor Tunnel
color 07
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do set "ESC=%%b"
if not exist cloudflared.exe (
    echo [INFO] cloudflared.exe not found.
    echo.
    echo [EXPLANATION]
    echo 'cloudflared.exe' is required to start the Web Panel tunnel.
    echo.
    echo [ACTION REQUIRED]
    echo Please download it from:
    echo https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    echo.
    echo Rename the download file to 'cloudflared.exe' and place it in this folder and try again.
    echo.
    exit /b 1
)
if not exist config.yml (
    echo [ERROR] config.yml not found. Run setup_tunnel.bat first.
    exit /b 1
)
cloudflared.exe tunnel --config config.yml --metrics localhost:0 --loglevel warn run 2>&1 | python -u -c "import sys, datetime, re; last={}; [sys.stdout.write(f'{now.strftime(\"%%d-%%m-%%y %%H:%%M:%%S\")}|INFO|[WEB] {msg}\n') for l in sys.stdin for now in [datetime.datetime.now()] for msg in [(\"Tunnel connection is unstable, reconnecting...\" if \"control stream encountered a failure\" in l else re.sub(r\"^.*Z\s+\w+\s+\", \"\", l.strip()).replace(\"failed to dial to target\", \"Waiting for WebPanel...\"))] if not (\"canceled by remote\" in l or \"context canceled\" in l) and (msg not in last or (now - last[msg]).total_seconds() > 1) and not last.update({msg: now})]"
