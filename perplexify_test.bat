@echo off
setlocal
cd /d "%~dp0"

set "FOOTIX_ROOT=%~dp0..\..\.."
set "PYTHONPATH=%~dp0;%FOOTIX_ROOT%;%FOOTIX_ROOT%\betbrain-core;%PYTHONPATH%"

echo.
echo ============================================================
echo  Perplexify CLI - Live Smoke Test
echo ============================================================
echo.

python smoke_test.py --live
exit /b %ERRORLEVEL%
