@echo off
setlocal ENABLEEXTENSIONS

REM ==========================================
REM Crystal Lagoons / FastAPI - Startup Script
REM ==========================================

set BASE_DIR=%~dp0

echo ==========================================
echo  Iniciando FastAPI (Uvicorn)
echo ==========================================
echo Base dir: %BASE_DIR%
echo.

call "%BASE_DIR%.venv\Scripts\activate.bat"
echo Entorno virtual activado
echo.

set PYTHONUTF8=1


uvicorn app.main:app ^
  --host 0.0.0.0 ^
  --port 8000 ^
  --log-level warning

echo.
echo Uvicorn detenido
pause
