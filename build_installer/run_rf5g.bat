@echo off
title rf5g-sizing — 5G NR RF Coverage Sizing Tool
setlocal enabledelayedexpansion

:: ── Config ──
set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"
set "PYTHON_EXE=%APP_DIR%\python\python.exe"
set "PORT=8501"

:: ── Check embedded Python exists ──
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Embedded Python not found at:
    echo         %PYTHON_EXE%
    echo.
    echo Please reinstall rf5g-sizing.
    pause
    exit /b 1
)

:: ── Launch Streamlit ──
echo Starting rf5g-sizing on http://localhost:%PORT% ...
echo.
echo Press Ctrl+C to stop the server.
echo.

:: Open browser after 3-second delay (gives Streamlit time to start)
start "" cmd /c "timeout /t 3 /nobreak >nul & start http://localhost:%PORT%"

"%PYTHON_EXE%" -m streamlit run "%APP_DIR%\rf5g\web\guided.py" --server.port %PORT% --server.headless true --browser.gatherUsageStats false --global.developmentMode false

echo.
echo rf5g-sizing has stopped.
pause