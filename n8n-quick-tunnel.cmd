@echo off
echo Manual diagnostic tunnel only.
echo Prefer N8N_AUTO_TUNNEL=true and voice-app.cmd — that starts a fresh
echo trycloudflare hostname and updates Retell on every app startup.
echo Do not run this at the same time as automatic mode.
echo.
cloudflared tunnel --url http://127.0.0.1:5678 --no-autoupdate
