@echo off
title PatchRaptor Dependency Installer
echo ==========================================
echo PatchRaptor Dependency Installer
echo ==========================================
echo.
echo Select installation type:
echo 1. Production (Run the bot/panel only)
echo 2. Development (Run tests, build EXE, contribute)
echo.
set /p INST_TYPE="Enter choice (1 or 2): "

python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo [ERROR] Failed to upgrade pip. Is Python installed and in your PATH?
    pause
    exit /b %errorlevel%
)

echo.
if "%INST_TYPE%"=="2" (
    echo [INFO] Installing DEVELOPMENT requirements...
    pip install -r requirements-dev.txt
) else (
    echo [INFO] Installing PRODUCTION requirements...
    pip install -r requirements.txt
)

if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b %errorlevel%
)

echo.
echo [SUCCESS] Dependencies installed successfully!
pause
