@echo off
setlocal ENABLEEXTENSIONS

set BASE_DIR=%~dp0
set VENV_DIR=%BASE_DIR%.venv
set PYTHON_BIN=%VENV_DIR%\Scripts\python.exe
cd /d "%BASE_DIR%"

echo ==========================================
echo  Iniciando FastAPI (Uvicorn)
echo ==========================================
echo Base dir: %BASE_DIR%
echo.

if not exist "%PYTHON_BIN%" (
  echo No se encontro el interprete del entorno virtual:
  echo %PYTHON_BIN%
  pause
  exit /b 1
)

echo Usando entorno virtual: %VENV_DIR%
echo.

set PYTHONUTF8=1

"%PYTHON_BIN%" -m uvicorn app.main:app ^
  --host 0.0.0.0 ^
  --port 8090 ^
  --log-level warning

echo.
echo Uvicorn detenido
pause
