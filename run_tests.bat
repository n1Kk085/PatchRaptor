@echo off
REM PatchRaptor Test Runner
REM Runs all tests with pytest

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
    echo   pip install -r requirements-dev.txt
    echo.
    pause
    exit /b 1
)

echo Running all tests...
echo.

REM Run pytest with verbose output
python -m pytest -v

echo.
echo ========================================
echo Test run complete
echo ========================================
echo.
pause
