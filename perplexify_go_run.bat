@echo off
setlocal
cd /d "%~dp0"

set "PYTHONPATH=%~dp0;%PYTHONPATH%"

where go >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Go is not installed or not in PATH.
  echo Install Go from https://go.dev/dl/ then run this script again.
  exit /b 1
)

cd go-tui
go mod tidy
if errorlevel 1 exit /b 1

go run .\cmd\perplexify
exit /b %ERRORLEVEL%
