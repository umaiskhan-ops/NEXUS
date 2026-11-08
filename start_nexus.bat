@echo off
title SUP Agentic Mesh (Powered by NEXUS) - Master System Launcher
color 0B
cd /d "%~dp0"

echo ========================================================================
echo    SUP AGENTIC MESH (POWERED BY NEXUS) - 1-COMMAND MASTER LAUNCHER
echo    [Web Studio + Owner Telegram Bot + IDE + P2P Market + Supercomputer]
echo ========================================================================
echo.

set PY_CMD=

:: 1. Check python command in PATH
python -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set PY_CMD=python
    goto :launch
)

:: 2. Check py launcher in PATH
py -3 -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set PY_CMD=py -3
    goto :launch
)
py -c "import sys" >nul 2>&1
if not errorlevel 1 (
    set PY_CMD=py
    goto :launch
)

:: 3. Check AppData local user Python installations
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python314\python.exe" & goto :launch
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe" & goto :launch
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & goto :launch
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe" & goto :launch
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python310\python.exe" & goto :launch
if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python39\python.exe" & goto :launch

:: 4. Check Program Files Python installations
if exist "%ProgramFiles%\Python314\python.exe" set PY_CMD="%ProgramFiles%\Python314\python.exe" & goto :launch
if exist "%ProgramFiles%\Python313\python.exe" set PY_CMD="%ProgramFiles%\Python313\python.exe" & goto :launch
if exist "%ProgramFiles%\Python312\python.exe" set PY_CMD="%ProgramFiles%\Python312\python.exe" & goto :launch
if exist "%ProgramFiles%\Python311\python.exe" set PY_CMD="%ProgramFiles%\Python311\python.exe" & goto :launch
if exist "%ProgramFiles%\Python310\python.exe" set PY_CMD="%ProgramFiles%\Python310\python.exe" & goto :launch

echo [!] PYTHON NOT FOUND. Please install Python 3.8+ from https://www.python.org/downloads/
pause
exit /b 1

:launch
echo [+] Using Python: %PY_CMD%

:: Auto-detect NVIDIA GPU for Zero-Touch Background QLoRA Training
nvidia-smi >nul 2>&1
if not errorlevel 1 (
    echo [+] NVIDIA GPU Detected! Enabling Autonomous GPU QLoRA Training...
    set NEXUS_AUTO_GPU_TRAINING=1
    %PY_CMD% -c "import torch, transformers, peft" >nul 2>&1
    if errorlevel 1 (
        if exist "requirements-gpu.txt" (
            echo [*] Installing GPU QLoRA Training Stack ^(requirements-gpu.txt^)...
            %PY_CMD% -m pip install -q -r requirements-gpu.txt
        )
    )
) else (
    echo [*] Standard CPU Mode Detected ^(1-Click Lightweight Launch - No GPU Required^).
)

echo [*] Launching Full SUP Agentic Mesh (Web Studio + Owner Telegram + Worker)...
echo.
%PY_CMD% -m sovereign_mesh start
if errorlevel 1 (
    echo.
    echo [!] System exited with code %errorlevel%.
    pause
)
