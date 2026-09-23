@echo off
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
    echo Make sure Python and uvicorn are installed:
    echo   pip install uvicorn fastapi
    pause
    exit /b 1
)

where npx >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npx not found in PATH!
    echo Make sure Node.js is installed from https://nodejs.org
    pause
    exit /b 1
)

echo    All dependencies found. OK!
echo.

REM --- Step 1: Kill any old process on port 8000 ---
echo [1/4] Cleaning up old processes on port 8000...
netstat -ano | findstr ":8000.*LISTENING" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo    Found existing process on port 8000. Killing it...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000.*LISTENING"') do (
        taskkill /PID %%a /F >nul 2>&1
    )
    timeout /t 2 /nobreak >nul
    echo    Done.
) else (
    echo    Port 8000 is free. OK!
)
echo.

REM --- Step 2: Start Backend ---
echo [2/4] Starting Backend Server (FastAPI on Port 8000)...
start "Attendance Backend" cmd /k "cd /d d:\RFID\backend && echo ===== UVICORN BACKEND SERVER ===== && echo. && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 5 /nobreak >nul

REM --- Step 3: Start Cloud Tunnel ---
echo [3/4] Starting Cloud Tunnel (https://ayush-smart-backend.loca.lt)...
start "Attendance Cloud Tunnel" cmd /k "cd /d d:\RFID && echo ===== CLOUD TUNNEL ===== && echo. && npx --yes localtunnel --port 8000 --subdomain ayush-smart-backend"

timeout /t 5 /nobreak >nul

REM --- Step 4: Open Dashboard ---
echo [4/4] Opening Admin Dashboard in Browser...
start "" "http://localhost:8000"

echo.
echo ========================================================
echo   ALL SERVICES STARTED!
echo   Local Dashboard:  http://localhost:8000
echo   Cloud URL:        https://ayush-smart-backend.loca.lt
echo ========================================================
echo.
echo IMPORTANT: Keep the two black windows open:
echo   - "Attendance Backend"
echo   - "Attendance Cloud Tunnel"
echo.
echo If app says "Server Offline":
echo   1. Wait 10-15 seconds for tunnel to connect
echo   2. Swipe down to refresh in the app
echo   3. Check if both cmd windows are still open
echo.
pause
