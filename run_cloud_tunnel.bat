@echo off
title Smart Attendance - Cloud Tunnel
color 0B
echo Starting cloud tunnel for Smart Attendance...
echo.

:loop
echo [%date% %time%] Connecting to https://ayush-smart-backend.loca.lt ...
npx --yes localtunnel --port 8000 --subdomain ayush-smart-backend
echo.
echo [%date% %time%] Tunnel disconnected or interrupted!
echo Reconnecting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
