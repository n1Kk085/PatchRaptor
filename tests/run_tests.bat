@echo off
REM PatchRaptor Test Runner
REM Runs all tests with pytest

REM Resize window for a sleek, perfectly wrapped view
mode con: cols=120 lines=45

cd %~dp0..

echo ========================================
echo PatchRaptor Test Suite
echo ========================================
echo.

REM Check if pytest is installed
python -m pytest --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pytest is not installed
    echo.
    echo Please install test dependencies first:
    echo   pip install -r tests\requirements-dev.txt
    echo.
    pause
    exit /b 1
)

echo Running all tests...
echo.

REM Run the custom Python runner
python tests\test_runner.py
echo ========================================
echo Test run complete
echo ========================================
echo.
pause
