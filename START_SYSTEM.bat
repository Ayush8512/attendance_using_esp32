@echo off
title Smart Attendance System
color 0A

echo =======================================================
echo Starting Smart Attendance System
echo =======================================================
echo.
echo [1/3] Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (taskkill /PID %%a /F >nul 2>&1)

echo [2/3] Starting Backend Server...
start "Backend Server" cmd /k "cd /d d:\RFID\backend && uvicorn main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul
echo [3/3] Starting Localtunnel (ayush-smart-backend.loca.lt)...
start "Localtunnel" cmd /k "npx localtunnel --port 8000 --subdomain ayush-smart-backend"

start http://localhost:8000

echo.
echo =======================================================
echo System is Running!
echo =======================================================
echo 1. Your Dashboard is open in the browser.
echo 2. The Mobile App will automatically connect to:
echo    https://ayush-smart-backend.loca.lt
echo.
pause
