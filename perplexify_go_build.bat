@echo off
setlocal
cd /d "%~dp0"

where go >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Go is not installed or not in PATH.
  echo Install Go from https://go.dev/dl/ then run this script again.
  exit /b 1
)

cd go-tui
go mod tidy
if errorlevel 1 exit /b 1

if not exist dist mkdir dist
go build -o dist\perplexify.exe .\cmd\perplexify
if errorlevel 1 exit /b 1

echo [OK] Built go-tui\dist\perplexify.exe
exit /b 0
