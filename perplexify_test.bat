@echo off
setlocal
cd /d "%~dp0"

set "FOOTIX_ROOT=%~dp0..\..\.."
set "PYTHONPATH=%FOOTIX_ROOT%;%FOOTIX_ROOT%\betbrain-core;%PYTHONPATH%"

echo.
echo ============================================================
echo  Perplexify CLI - Live Smoke Test
echo ============================================================
echo.

python -m scraping_lab.perplexity_lab.perplexify.smoke_test --live
exit /b %ERRORLEVEL%
