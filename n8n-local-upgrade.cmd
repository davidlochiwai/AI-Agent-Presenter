@echo off
setlocal
cd /d "%~dp0"

echo Pulling the current stable n8n image...
docker compose -f compose.n8n.yml pull n8n
if errorlevel 1 exit /b %errorlevel%

docker compose -f compose.n8n.yml up -d n8n
if errorlevel 1 exit /b %errorlevel%

docker compose -f compose.n8n.yml exec n8n n8n --version
