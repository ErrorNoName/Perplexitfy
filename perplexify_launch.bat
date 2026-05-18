@echo off
setlocal
cd /d "%~dp0"

set "FOOTIX_ROOT=%~dp0..\..\.."
set "PYTHONPATH=%FOOTIX_ROOT%;%FOOTIX_ROOT%\betbrain-core;%PYTHONPATH%"

if "%~1"=="" (
  python -m scraping_lab.perplexity_lab.perplexify chat
) else (
  python -m scraping_lab.perplexity_lab.perplexify %*
)

exit /b %ERRORLEVEL%
