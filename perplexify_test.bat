@echo off
setlocal
cd /d "%~dp0"

set "PYTHONPATH=%~dp0;%PYTHONPATH%"

echo.
echo ============================================================
echo  Perplexify CLI - Live Smoke Test
echo ============================================================
echo.

python smoke_test.py --live
exit /b %ERRORLEVEL%
