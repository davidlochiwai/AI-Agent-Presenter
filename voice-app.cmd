@echo off
setlocal
cd /d "%~dp0"
".\.venv\Scripts\python.exe" -m voice_app --presenter-window %*
