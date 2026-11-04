@echo off
title Cloudflare Tunnel - attendancesystemiert.dpdns.org
color 0B
echo =====================================================================
echo       STARTING CLOUDFLARE TUNNEL (attendancesystemiert.dpdns.org)
echo =====================================================================
echo.
cd /d "%~dp0"
echo Working Directory: %CD%
echo Connecting to Cloudflare Global Edge Network...
echo Keep this window open while the attendance server is running.
echo.
cloudflared.exe tunnel run --token eyJhIjoiNzgyYjUxNzJiMWNmZWQ3YzM3YjYwZGE2M2I5YWJkMjciLCJ0IjoiOGViZGI4ZDUtNWI2ZC00MTJhLTg1MjYtYTg4OTYwMjA0MDNiIiwicyI6Ik5qaGxOelZtT1dFdFpXWm1aaTAwTkRObExUa3dOV010WXpFNU56SmtOVGMyWXprNCJ9
echo.
echo [TUNNEL STOPPED] Exit Code: %errorlevel%
pause
