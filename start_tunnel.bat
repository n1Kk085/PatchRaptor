@echo off
title PatchRaptor Tunnel
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
    echo Place 'cloudflared.exe' in this folder and try again.
    echo.
    pause
    exit /b 1
)

if not exist config.yml (
    echo [ERROR] config.yml not found. Run setup_tunnel.bat first.
    exit /b 1
)

echo Starting tunnel...
if not exist config.yml (
    echo [ERROR] config.yml not found. Please run setup_tunnel.bat first.
    pause
    exit /b 1
)

cloudflared.exe tunnel --config config.yml run
