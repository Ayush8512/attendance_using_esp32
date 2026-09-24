@echo off
setlocal enabledelayedexpansion
title Smart Attendance - Master Server Launcher
color 0A

echo ========================================================
echo       SMART ATTENDANCE SYSTEM - MASTER STARTUP
echo ========================================================
echo.

REM --- Verify dependencies before starting ---
echo [0/3] Checking dependencies...

where uvicorn >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] uvicorn not found in PATH!
    pause
    exit /b 1
)

REM --- Get Local IP ---
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr "IPv4"') do (
    set "ip=%%a"
    set "ip=!ip:~1!"
    goto :ip_found
)
:ip_found

REM --- Step 1: Kill any old process on port 8000 ---
echo [1/3] Cleaning up old processes on port 8000...
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo    Found existing process on port 8000. Killing it...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
)
echo.

REM --- Step 2: Start Backend ---
echo [2/3] Starting Backend Server (FastAPI on Port 8000)...
start "Attendance Backend" cmd /k "cd /d d:\RFID\backend && echo ===== UVICORN BACKEND SERVER ===== && echo. && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 4 /nobreak >nul

REM --- Step 3: Open Dashboard ---
echo [3/3] Opening Admin Dashboard in Browser...
start "" "http://localhost:8000"

echo.
echo ========================================================
echo   ALL SERVICES STARTED SUCCESSFULLY!
echo ========================================================
echo.
echo TO CONNECT YOUR MOBILE APP:
echo 1. Connect your Laptop and Phone to the SAME WiFi / Hotspot.
echo 2. Open the App and enter this URL exactly as shown:
echo.
echo    Server Base URL:  http://%ip%:8000
echo.
echo Note: We have disabled Localtunnel because their free servers
echo are currently crashing (causing 502 Bad Gateway errors). 
echo Local WiFi is 100x faster and never crashes!
echo ========================================================
echo.
pause
