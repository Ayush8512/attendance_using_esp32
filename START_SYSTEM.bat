@echo off
setlocal enabledelayedexpansion
title Smart Attendance System
color 0A

echo =======================================================
echo     SMART ATTENDANCE SYSTEM - STARTING...
echo =======================================================
echo.

echo [1/3] Cleaning up old processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (taskkill /PID %%a /F >nul 2>&1)
taskkill /F /IM node.exe >nul 2>&1

echo     Waiting 12 seconds for tunnel subdomain to be released...
timeout /t 12 /nobreak >nul

echo [2/3] Starting Backend Server...
start "Backend Server" cmd /k "cd /d d:\RFID\backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 4 /nobreak >nul

echo [3/3] Starting Tunnel (ayush-smart-backend.loca.lt)...
start "Localtunnel" cmd /k "npx localtunnel --port 8000 --subdomain ayush-smart-backend"
timeout /t 3 /nobreak >nul

start http://localhost:8000

echo.
echo =======================================================
echo   SYSTEM IS RUNNING!
echo =======================================================
echo.
echo   Mobile App URL (fixed, already set in app):
echo   https://ayush-smart-backend.loca.lt
echo.
echo   Keep this window open. Close to stop everything.
echo =======================================================
pause
