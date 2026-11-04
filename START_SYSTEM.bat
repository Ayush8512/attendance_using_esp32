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
taskkill /F /IM cloudflared.exe >nul 2>&1

echo [2/3] Starting High-Concurrency Backend Server...
start "Backend Server" cmd /k "d:\RFID\RUN_SERVER.bat"
ping 127.0.0.1 -n 4 >nul

echo [3/3] Starting Permanent Cloudflare Tunnel...
start "Cloudflare Tunnel" cmd /k "d:\RFID\RUN_CLOUDFLARE_TUNNEL.bat"
ping 127.0.0.1 -n 5 >nul

start https://attendancesystemiert.dpdns.org

echo.
echo =======================================================
echo   SYSTEM IS 100%% ONLINE AND RUNNING!
echo =======================================================
echo.
echo   Permanent Mobile App URL (Fixed Forever):
echo   https://attendancesystemiert.dpdns.org
echo.
echo   Local Admin Portal:
echo   http://127.0.0.1:8000
echo.
echo   Keep both black windows open while taking attendance.
echo =======================================================
pause
