@echo off
title Localtunnel KeepAlive [ayush-smart-backend]
color 0B

echo ========================================================
echo   LOCALTUNNEL AUTO-RECONNECT SUPERVISOR
echo   Target Subdomain: ayush-smart-backend.loca.lt
echo ========================================================
echo.

:tunnel_loop
echo [%TIME%] [TUNNEL] Connecting tunnel for port 8000...
call npx localtunnel --port 8000 --subdomain ayush-smart-backend
echo.
echo [%TIME%] [TUNNEL] Tunnel connection closed or dropped!
echo [%TIME%] [TUNNEL] Auto-reconnecting in 3 seconds...
timeout /t 3 /nobreak >nul
echo.
goto tunnel_loop
