@echo off
title Backend Server (Auto-Restart Supervisor)
color 0B
cd /d d:\RFID\backend

:server_loop
echo.
echo =======================================================
echo [%date% %time%] Starting Backend Server on Port 8000...
echo =======================================================
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --limit-concurrency 1000 --backlog 2048 --timeout-keep-alive 65
echo.
echo [SUPERVISOR] Backend stopped. Auto-recovering in 2 seconds...
ping 127.0.0.1 -n 3 >nul
goto server_loop
