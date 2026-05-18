@echo off
setlocal
cd /d "%~dp0"

set "PERPLEXIFY_DIR=%~dp0"
set "FOOTIX_ROOT=%~dp0..\..\.."
set "PYTHONPATH=%PERPLEXIFY_DIR%;%FOOTIX_ROOT%;%FOOTIX_ROOT%\betbrain-core;%PYTHONPATH%"

if "%~1"=="" (
  python cli.py chat
) else (
  python cli.py %*
)

exit /b %ERRORLEVEL%
