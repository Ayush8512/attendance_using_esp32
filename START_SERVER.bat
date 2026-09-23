@echo off
title Smart Attendance - Master Server Launcher
color 0A

echo ========================================================
echo       SMART ATTENDANCE SYSTEM - MASTER STARTUP
echo ========================================================
echo.

echo [1/3] Starting Backend Server (FastAPI on Port 8000)...
start "Attendance Backend" cmd /k "cd /d d:\RFID\backend && uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo [2/3] Starting Cloud Tunnel (https://ayush-smart-backend.loca.lt)...
start "Attendance Cloud Tunnel" cmd /k "cd /d d:\RFID && run_cloud_tunnel.bat"

timeout /t 4 /nobreak >nul

echo [3/3] Opening Admin Dashboard in Browser...
start "" "http://localhost:8000"

echo.
echo ========================================================
echo   ALL SERVICES ARE ACTIVE!
echo   Local Dashboard: http://localhost:8000
echo   Global Cloud URL: https://ayush-smart-backend.loca.lt
echo ========================================================
echo.
echo NOTE: Keep the two black windows ("Attendance Backend" and
echo "Attendance Cloud Tunnel") OPEN while using the system.
echo.
pause
