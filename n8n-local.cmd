@echo off
setlocal
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo Docker Desktop is not ready. Start Docker Desktop, then run this file again.
  exit /b 1
)

docker compose -f compose.n8n.yml up -d
if errorlevel 1 exit /b %errorlevel%

echo.
echo Local n8n is starting at http://127.0.0.1:5678
echo Qdrant knowledge index is starting at http://127.0.0.1:6333
echo Run n8n-local-logs.cmd if the page is not ready after one minute.
start "" http://127.0.0.1:5678
