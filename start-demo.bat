@echo off
REM Double-click this file to start the demo. It checks everything first, then opens the app.
setlocal

REM Always run from the folder this file lives in, whatever folder you launched it from.
cd /d "%~dp0"

echo ==========================================================
echo   AI Production Issue Investigator - starting the demo
echo ==========================================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo [X] The .venv folder is missing.
    echo     Follow the "One-time setup" section in HOW_TO_RUN.md
    echo.
    pause
    exit /b 1
)
echo [OK] Python environment found.

ollama list >nul 2>&1
if errorlevel 1 (
    echo [X] Ollama is not running.
    echo     Open the Start menu, type "Ollama", press Enter, wait 10 seconds,
    echo     then double-click this file again.
    echo.
    pause
    exit /b 1
)
echo [OK] Ollama is running.

REM If the app is already up, don't start a second copy on a port that is taken.
netstat -ano | findstr /r /c:"TCP.*:8501 .*LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo [OK] The app is ALREADY running.
    echo.
    echo Opening http://localhost:8501 in your browser...
    start "" "http://localhost:8501"
    echo.
    echo Nothing else to do. You can close this window.
    pause
    exit /b 0
)
echo.

echo Running the pre-demo checks...
echo.
.venv\Scripts\python.exe scripts\verify_setup.py
if errorlevel 1 (
    echo.
    echo [X] A check failed. See the Troubleshooting table in HOW_TO_RUN.md
    echo.
    pause
    exit /b 1
)

echo.
echo Starting the web app. Your browser will open at http://localhost:8501
echo.
echo   *** Leave this black window OPEN while you demo. ***
echo   *** Closing it stops the app. Press Ctrl+C to stop on purpose. ***
echo.

.venv\Scripts\python.exe -m streamlit run app/ui.py --server.port 8501

echo.
echo The app has stopped.
pause
