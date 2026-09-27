@echo off
echo ======================================================================
echo SWARM-X PRO V2 - Real PyBullet 3D Warehouse Simulation System
echo ======================================================================
echo.

REM 1. Activate bullet_env and start FastAPI Backend + PyBullet simulation
echo Starting Backend API and PyBullet 3D Physics Simulator on port 8000...
start "SWARM-X PRO V2 - Backend & PyBullet" cmd /k ".\bullet_env\python.exe -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000"

REM 2. Start React Visualization Dashboard
echo Starting React Autonomous Fleet Control Dashboard on port 3000...
start "SWARM-X PRO V2 - Dashboard" cmd /k "cd visualization && npm run dev"

echo.
echo ======================================================================
echo System successfully launched!
echo - Backend API & WebSockets: http://localhost:8000
echo - React Fleet Dashboard:    http://localhost:3000
echo - PyBullet Native GUI:      Hardware-accelerated OpenGL Window
echo ======================================================================
pause
