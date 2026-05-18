@echo off
setlocal
cd /d "%~dp0"

set "FOOTIX_ROOT=%~dp0..\..\.."
set "PYTHONPATH=%FOOTIX_ROOT%;%FOOTIX_ROOT%\betbrain-core;%PYTHONPATH%"

if exist "go-tui\dist\perplexify.exe" (
  "go-tui\dist\perplexify.exe" %*
  exit /b %ERRORLEVEL%
)

echo [INFO] dist\perplexify.exe not found. Falling back to go run.
call "%~dp0perplexify_go_run.bat"
exit /b %ERRORLEVEL%
