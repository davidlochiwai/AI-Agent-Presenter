@echo off
setlocal
cd /d "%~dp0"
docker compose -f compose.n8n.yml stop
