@echo off
setlocal
cd /d "%~dp0"

set "PERPLEXIFY_DIR=%CD%"
set "FOOTIX_ROOT=%~dp0..\..\.."
set "PYTHONPATH=%PERPLEXIFY_DIR%;%FOOTIX_ROOT%;%FOOTIX_ROOT%\betbrain-core;%PYTHONPATH%"

echo.
echo ============================================================
echo  Perplexify CLI - Quick Setup
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found in PATH.
  exit /b 1
)

if /I "%~1"=="check" (
  echo [CHECK] Python is available.
  echo [CHECK] Perplexify folder: %PERPLEXIFY_DIR%
  echo [CHECK] Local requirements file: requirements.txt
  if not exist "requirements.txt" (
    echo [ERROR] Missing requirements.txt
    exit /b 1
  )
  echo [CHECK] Perplexify module import...
  python cli.py --help >nul
  exit /b %ERRORLEVEL%
)

echo [1/3] Installing Perplexify Python dependencies...
python -m pip install -r "requirements.txt"
if errorlevel 1 exit /b 1

echo.
echo [2/3] Installing Playwright Chromium runtime...
python -m playwright install chromium
if errorlevel 1 exit /b 1

echo.
echo [3/3] Launching Perplexify cookie setup...
python cli.py setup
exit /b %ERRORLEVEL%
