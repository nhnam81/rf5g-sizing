@echo off
setlocal enabledelayedexpansion

:: ── rf5g-sizing Windows Installer Builder ──
:: Downloads embedded Python, prepares structure, builds Inno Setup installer

set "BUILDER_DIR=%~dp0"
set "BUILDER_DIR=%BUILDER_DIR:~0,-1%"
set "PROJECT_DIR=%BUILDER_DIR%\.."
set "PYTHON_VERSION=3.12.10"
set "PYTHON_EMBED=python-%PYTHON_VERSION%-embed-amd64"
set "PYTHON_URL=https://www.python.org/ftp/python/%PYTHON_VERSION%/%PYTHON_EMBED%.zip"
set "PYTHON_ZIP=%BUILDER_DIR%\%PYTHON_EMBED%.zip"
set "PYTHON_DIR=%BUILDER_DIR%\python-embed"
set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

echo ============================================
echo   rf5g-sizing Windows Installer Builder
echo ============================================
echo.

:: ── Step 1: Download Embedded Python ──
if not exist "%PYTHON_DIR%\python.exe" (
    echo [1/4] Downloading Python %PYTHON_VERSION% embedded...
    if not exist "%PYTHON_ZIP%" (
        powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%PYTHON_ZIP%'"
        if errorlevel 1 (
            echo [ERROR] Failed to download Python.
            exit /b 1
        )
    )
    
    echo Extracting Python...
    powershell -Command "Expand-Archive -Path '%PYTHON_ZIP%' -DestinationPath '%PYTHON_DIR%' -Force"
    
    :: Enable pip in embedded Python (uncomment import site)
    echo Configuring embedded Python...
    for %%f in ("%PYTHON_DIR%\python3*._pth") do (
        powershell -Command "(Get-Content '%%f') -replace '^#?import site', 'import site' | Set-Content '%%f'"
    )
) else (
    echo [1/4] Python embedded already exists, skipping download.
)

:: ── Step 2: Install pip into embedded Python ──
if not exist "%PYTHON_DIR%\Scripts\pip.exe" (
    echo [2/4] Installing pip...
    "%PYTHON_DIR%\python.exe" -c "import urllib.request; urllib.request.urlretrieve('https://bootstrap.pypa.io/get-pip.py', r'%PYTHON_DIR%\get-pip.py')"
    "%PYTHON_DIR%\python.exe" "%PYTHON_DIR%\get-pip.py" --no-warn-script-location
    del /q "%PYTHON_DIR%\get-pip.py" 2>nul
) else (
    echo [2/4] pip already installed, skipping.
)

:: ── Step 3: Pre-install packages into embedded Python ──
echo [3/4] Pre-installing rf5g-sizing dependencies...
"%PYTHON_DIR%\Scripts\pip.exe" install --no-warn-script-location -r "%BUILDER_DIR%\requirements.txt"
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    exit /b 1
)

:: ── Step 4: Build installer with Inno Setup ──
echo [4/4] Building installer...
if not exist "%ISCC%" (
    echo.
    echo [ERROR] Inno Setup 6 not found at:
    echo         %ISCC%
    echo.
    echo Please install Inno Setup 6 from https://jrsoftware.org/isdl.php
    echo Then re-run this script.
    echo.
    echo Alternatively, you can install it with:
    echo   winget install JRSoftware.InnoSetup
    echo   or: choco install innosetup
    pause
    exit /b 1
)

"%ISCC%" "%BUILDER_DIR%\rf5g-setup.iss"
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed.
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Installer: %PROJECT_DIR%\dist\rf5g-sizing-1.4.0-setup.exe
echo ============================================
pause