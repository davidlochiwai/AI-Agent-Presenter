@echo off
setlocal
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not ready. Start Docker Desktop, then run this file again.
  exit /b 1
)

docker compose up -d qdrant
if errorlevel 1 exit /b %errorlevel%

echo.
echo Qdrant knowledge index is starting at http://127.0.0.1:6333
