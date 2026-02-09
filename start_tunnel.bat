@echo off
title PatchRaptor Tunnel
color 07

REM Define ESC character for ANSI colors
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do set "ESC=%%b"

REM Set text color to PatchRaptor Blue (RGB: 91, 131, 201)
echo %ESC%[38;2;91;131;201m

echo.
echo [IMPORTANT]
echo DO NOT CLOSE THIS WINDOW!
echo The tunnel will stop working if you close this window.
echo You can minimize it to the taskbar to keep it running.
echo.

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
    REM pause
    exit /b 1
)

if not exist config.yml (
    echo [ERROR] config.yml not found. Run setup_tunnel.bat first.
    exit /b 1
)

echo Starting tunnel...
if not exist config.yml (
    echo [ERROR] config.yml not found. Please run setup_tunnel.bat first.
    REM pause
    exit /b 1
)

cloudflared.exe tunnel --config config.yml --metrics localhost:0 run
