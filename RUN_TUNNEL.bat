@echo off
title Permanent Cloud Tunnel [shading-pretzel-mascot.ngrok-free.dev]
color 0A

echo ========================================================
echo   PERMANENT STATIC CLOUD TUNNEL (LIFETIME DOMAIN)
echo   Target: https://shading-pretzel-mascot.ngrok-free.dev
echo ========================================================
echo.

:LOOP
d:\RFID\ngrok.exe http 8000 --url https://shading-pretzel-mascot.ngrok-free.dev
echo.
echo Tunnel session ended. Re-establishing in 3 seconds...
timeout /t 3 /nobreak >nul
goto LOOP
