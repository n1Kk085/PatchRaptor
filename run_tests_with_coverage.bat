@echo off
REM PatchRaptor Test Runner with Coverage
REM Runs all tests and generates HTML coverage report

echo ========================================
echo PatchRaptor Test Suite (with Coverage)
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

REM Check if pytest-cov is installed
python -c "import pytest_cov" >nul 2>&1
if errorlevel 1 (
    echo ERROR: pytest-cov is not installed
    echo.
    echo Please install test dependencies first:
    echo   pip install -r requirements-dev.txt
    echo.
    pause
    exit /b 1
)

echo Running tests with coverage analysis...
echo.

REM Run pytest with coverage
python -m pytest --cov=patchraptor --cov-report=html --cov-report=term -v

echo.
echo ========================================
echo Coverage report generated
echo ========================================
echo.
echo HTML report: htmlcov\index.html
echo.

REM Ask if user wants to open the report
set /p OPEN="Open coverage report in browser? (y/n): "
if /i "%OPEN%"=="y" (
    start htmlcov\index.html
)

pause
