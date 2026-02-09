@echo off
title PatchRaptor Tunnel Setup
color 07

REM Define ESC character for ANSI colors
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do set "ESC=%%b"

REM Set text color to PatchRaptor Blue (RGB: 91, 131, 201)
echo %ESC%[38;2;91;131;201m

echo.
echo ==========================================
echo   PatchRaptor Cloudflare Tunnel Setup
echo ==========================================
echo.
echo This wizard will guide you through setting up a Cloudflare Tunnel
echo for your PatchRaptor Web Panel. This allows secure public access
echo without opening router ports.
echo.
echo REQUIREMENTS:
echo  - Cloudflare account (free)
echo  - A domain connected to Cloudflare
echo  - cloudflared.exe in this directory
echo.
pause

REM Check for cloudflared.exe
if not exist cloudflared.exe (
    echo.
    echo [ERROR] cloudflared.exe not found!
    echo.
    echo Please download it from:
    echo https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    echo.
    echo Rename it to 'cloudflared.exe' and place it in this directory.
    echo.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo   STEP 1: Cloudflare Login
echo ==========================================
echo.

REM Check if already logged in
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    echo [OK] You're already logged in to Cloudflare!
    echo Certificate found at: %USERPROFILE%\.cloudflared\cert.pem
    echo.
    goto create_tunnel
)

echo Starting Cloudflare authentication...
echo.
echo WHAT WILL HAPPEN:
echo  1. A browser window will open with a Cloudflare login page
echo  2. Login with your Cloudflare account
echo  3. Select the domain you want to use for the tunnel
echo  4. Click "Authorize" to grant access
echo.
echo If the browser doesn't open automatically, we'll show you the URL.
echo.
pause

REM Run cloudflared login and capture output
echo Running: cloudflared.exe tunnel login
echo.
cloudflared.exe tunnel login > "%TEMP%\cf_login.txt" 2>&1

REM Check if login succeeded
if exist "%USERPROFILE%\.cloudflared\cert.pem" (
    echo.
    echo [SUCCESS] Login complete!
    echo.
    goto create_tunnel
) else (
    echo.
    echo [INFO] Browser may not have opened automatically.
    echo.
    REM Try to extract and open the URL from the output
    for /f "tokens=*" %%a in ('findstr /i "https://dash.cloudflare.com" "%TEMP%\cf_login.txt"') do (
        echo Opening authorization page...
        start "" "%%a"
        echo.
        echo URL opened in browser: %%a
        echo.
        echo Please complete the authorization in your browser.
        echo This window will wait for you to finish...
        echo.
    )
    
    REM Wait for cert to be created
    :wait_for_cert
    timeout /t 5 /nobreak >nul
    if exist "%USERPROFILE%\.cloudflared\cert.pem" (
        echo.
        echo [SUCCESS] Login complete!
        echo.
        goto create_tunnel
    )
    echo Still waiting for authorization...
    goto wait_for_cert
)

:create_tunnel
echo.
echo ==========================================
echo   STEP 2: Create Tunnel
echo ==========================================
echo.
echo A tunnel is a secure connection between Cloudflare and your server.
echo You'll need to give it a unique name.
echo.
echo EXAMPLE NAMES: patchraptor-panel, my-server-panel, ark-dashboard
echo.
set /p TUNNEL_NAME="Enter tunnel name: "

if "%TUNNEL_NAME%"=="" (
    echo [ERROR] Tunnel name cannot be empty!
    pause
    exit /b 1
)

echo.
echo Creating tunnel '%TUNNEL_NAME%'...
cloudflared.exe tunnel create --cred-file "%USERPROFILE%\.cloudflared\%TUNNEL_NAME%.json" %TUNNEL_NAME%

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Tunnel creation failed. Possible reasons:
    echo  - A tunnel with this name already exists
    echo  - Network connection issue
    echo.
    echo To delete an existing tunnel, run:
    echo   cloudflared.exe tunnel delete %TUNNEL_NAME%
    echo.
    pause
    goto create_tunnel
)

echo.
echo [SUCCESS] Tunnel created!
echo Credentials saved to: %USERPROFILE%\.cloudflared\%TUNNEL_NAME%.json
echo.
pause

echo.
echo ==========================================
echo   STEP 3: Configure DNS
echo ==========================================
echo.
echo Now we'll connect your domain to the tunnel.
echo.
echo IMPORTANT: Enter the FULL domain/subdomain you want to use.
echo.
echo EXAMPLES:
echo  - panel.yourdomain.com
echo  - ark.yourdomain.com
echo  - dashboard.example.net
echo.
set /p DOMAIN_NAME="Enter full domain: "

if "%DOMAIN_NAME%"=="" (
    echo [ERROR] Domain cannot be empty!
    pause
    exit /b 1
)

echo.
echo Routing %DOMAIN_NAME% to tunnel '%TUNNEL_NAME%'...
cloudflared.exe tunnel route dns %TUNNEL_NAME% %DOMAIN_NAME%

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] DNS routing failed. Please check:
    echo  - Domain is added to your Cloudflare account
    echo  - You have permission to modify DNS
    echo.
    pause
    exit /b 1
)

echo.
echo [SUCCESS] DNS configured!
echo.
pause

echo.
echo ==========================================
echo   STEP 4: Create Configuration
echo ==========================================
echo.
echo Creating config.yml for the tunnel...

echo.
set /p PANEL_PORT="Enter Web Panel Port (default 8080): "
if "%PANEL_PORT%"=="" set PANEL_PORT=8080

(
echo url: http://127.0.0.1:%PANEL_PORT%
echo tunnel: %TUNNEL_NAME%
echo credentials-file: %USERPROFILE%\.cloudflared\%TUNNEL_NAME%.json
) > config.yml

echo.
echo [SUCCESS] Configuration created!
echo.
echo ==========================================
echo   SETUP COMPLETE!
echo ==========================================
echo.
echo Your tunnel is ready to use!
echo.
echo NEXT STEPS:
echo  1. Start your PatchRaptor Web Panel (it should be running on port %PANEL_PORT%)
echo  2. Run 'start_tunnel.bat' to activate the tunnel
echo  3. Access your panel at: https://%DOMAIN_NAME%
echo.
echo IMPORTANT: Keep the tunnel running while you want public access.
echo           The Web Panel must also be running on port %PANEL_PORT%.
echo.
echo Configuration saved to: config.yml
echo.
pause
