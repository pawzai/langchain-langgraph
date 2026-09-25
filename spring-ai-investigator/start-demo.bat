@echo off
setlocal

echo ============================================================
echo   AI Production Issue Investigator - Spring Boot + Spring AI
echo ============================================================
echo.

cd /d "%~dp0"

REM If the app is already up, just open the browser instead of failing on a busy port.
powershell -NoProfile -Command "try { $null = Invoke-WebRequest 'http://localhost:8080/' -UseBasicParsing -TimeoutSec 3; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
    echo The application is already running.
    echo Opening http://localhost:8080 ...
    start "" http://localhost:8080
    goto :eof
)

echo Checking Ollama...
powershell -NoProfile -Command "try { $null = Invoke-WebRequest 'http://localhost:11434/api/tags' -UseBasicParsing -TimeoutSec 5; exit 0 } catch { exit 1 }"
if not %errorlevel%==0 (
    echo.
    echo   Ollama is not responding on port 11434.
    echo   Open a new window and run:  ollama serve
    echo.
    pause
    exit /b 1
)
echo   Ollama is up.
echo.

echo Starting the application. This takes about 10 seconds.
echo Leave this window open. Press Ctrl+C to stop.
echo.

REM Open the browser once the port starts answering.
start "" powershell -NoProfile -Command ^
  "for ($i=0; $i -lt 90; $i++) { try { $null = Invoke-WebRequest 'http://localhost:8080/' -UseBasicParsing -TimeoutSec 2; Start-Process 'http://localhost:8080'; break } catch { Start-Sleep -Seconds 2 } }"

call mvn spring-boot:run

endlocal
