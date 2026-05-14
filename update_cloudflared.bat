@echo off
title PatchRaptor Cloudflared Updater
color 07

REM Define ESC character for ANSI colors if supported
for /F "tokens=1,2 delims=#" %%a in ('"prompt #$H#$E# & echo on & for %%b in (1) do rem"') do set "ESC=%%b"

echo.
echo ==========================================
echo   PatchRaptor Cloudflare Updater
echo ==========================================
echo.

echo [1/3] Stopping active cloudflared processes...
taskkill /f /im cloudflared.exe >nul 2>&1

echo [2/3] Downloading latest binary...
echo URL: https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
echo.

REM Using curl which is built-in on modern Windows 10/11
curl -L -o "cloudflared.exe.new" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Download failed! Please check your internet connection.
    if exist "cloudflared.exe.new" del "cloudflared.exe.new"
    pause
    exit /b 1
)

echo.
echo [3/3] Finalizing update...
if exist "cloudflared.exe" (
    del /f /q "cloudflared.exe"
)

move /y "cloudflared.exe.new" "cloudflared.exe" >nul

echo.
echo ==========================================
echo   [OK] cloudflared.exe is now up to date!
echo ==========================================
echo.
pause
