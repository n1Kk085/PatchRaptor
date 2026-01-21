@echo off
title PatchRaptor Local Verification
echo ==========================================
echo PatchRaptor Local Verification
echo ==========================================
echo.
echo Running verification checks...
echo.

echo [1/3] Checking Development Environment...
pip show pytest >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] 'pytest' not found. Please run install_requirements.bat and select Development.
    pause
    exit /b 1
)

echo [2/3] Running Smoke Tests...
python tests/smoke_test.py
if %errorlevel% neq 0 (
    echo [FAILURE] Smoke tests failed!
    pause
    exit /b 1
)

echo [3/3] Running Full Test Suite...
pytest tests/
if %errorlevel% neq 0 (
    echo [FAILURE] Unit tests failed!
    pause
    exit /b 1
)

echo.
echo [SUCCESS] All verification checks passed! You are safe to commit/push.
echo.
pause
