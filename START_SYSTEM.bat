@echo off
setlocal enabledelayedexpansion
title Smart Attendance System [Permanent Production Mode]
color 0A

echo =======================================================
echo     SMART ATTENDANCE SYSTEM - STARTING...
echo =======================================================
echo.

echo [1/3] Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (taskkill /PID %%a /F >nul 2>&1)
taskkill /F /IM ngrok.exe >nul 2>&1

echo [2/3] Starting High-Concurrency Backend Server...
start "Backend Server" cmd /k "cd /d d:\RFID\backend && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --limit-concurrency 1000 --backlog 2048 --timeout-keep-alive 65"
timeout /t 3 /nobreak >nul

echo [3/3] Starting Permanent Cloud Tunnel (shading-pretzel-mascot.ngrok-free.dev)...
start "Permanent Cloud Tunnel" cmd /k "d:\RFID\RUN_TUNNEL.bat"
timeout /t 2 /nobreak >nul

start http://localhost:8000

echo.
echo =======================================================
echo   SYSTEM IS 100%% ONLINE AND RUNNING!
echo =======================================================
echo.
echo   Permanent Mobile App URL (Fixed Forever):
echo   https://shading-pretzel-mascot.ngrok-free.dev
echo.
echo   Keep both windows open while taking attendance.
echo =======================================================
pause
