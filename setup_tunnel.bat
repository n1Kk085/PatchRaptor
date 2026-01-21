@echo off
title PatchRaptor Tunnel Setup
echo ==========================================
echo PatchRaptor Cloudflare Tunnel Setup
echo ==========================================
echo.
echo This script will help you set up a Cloudflare Tunnel for your web panel.
echo You need a Cloudflare account and a connected domain.
echo.

if not exist cloudflared.exe (
    echo [INFO] cloudflared.exe not found.
    echo.
    echo [EXPLANATION]
    echo To allow public access to your Web Panel, we need 'cloudflared.exe'.
    echo This is the official Cloudflare Tunnel client using their secure zero-trust network.
    echo It allows you to share your panel without opening Router Ports.
    echo.
    echo [ACTION REQUIRED]
    echo Please download the official executable from:
    echo https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    echo.
    echo Place the file 'cloudflared.exe' in this directory and run this script again.
    echo.
    pause
    exit /b 1
)

echo Step 1: Login to Cloudflare
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    echo [INFO] Existing Cloudflare certificate found. Skipping login.
) else (
    echo A browser window will open. Please login and select your domain.
    cloudflared.exe tunnel login
    if %errorlevel% neq 0 (
        echo [ERROR] Login failed.
        pause
        exit /b 1
    )
)

echo.
echo Step 2: Create Tunnel
set /p TUNNEL_NAME="Enter a name for your tunnel (e.g., patchraptor-panel): "
echo Creating tunnel '%TUNNEL_NAME%'...

REM Create tunnel and force the credentials file to be named after the tunnel
REM This ensures config.yml can find it easily.
cloudflared.exe tunnel create --cred-file "%USERPROFILE%\.cloudflared\%TUNNEL_NAME%.json" %TUNNEL_NAME%

if %errorlevel% neq 0 (
    echo [WARNING] Failed to create tunnel. It may already exist.
    echo If it exists, ensure "%USERPROFILE%\.cloudflared\%TUNNEL_NAME%.json" exists.
    echo If not, delete the tunnel with 'cloudflared tunnel delete %TUNNEL_NAME%' and try again.
)
echo.
echo Tunnel creation phase complete.
pause

echo.
echo Step 3: Route DNS
set /p DOMAIN_NAME="Enter the full domain to route to (e.g., panel.mydomain.com): "
cloudflared.exe tunnel route dns %TUNNEL_NAME% %DOMAIN_NAME%
echo.
echo DNS routing phase complete.
pause

echo.
echo Step 4: Configure Tunnel
(
echo url: http://127.0.0.1:8080
echo tunnel: %TUNNEL_NAME%
echo credentials-file: %USERPROFILE%\.cloudflared\%TUNNEL_NAME%.json
) > config.yml

echo.
echo [SUCCESS] Tunnel configured! 
echo You can now use '.webpanel on' in Discord to start it.
pause
