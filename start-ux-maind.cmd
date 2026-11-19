@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [UX-mAInd] Erstinstallation wird ausgefuehrt ...
    powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
    if errorlevel 1 pause & exit /b 1
)

set "PORT=8465"
set "NO_BROWSER=0"
set "NEXT_IS_PORT=0"
for %%A in (%*) do (
    if "!NEXT_IS_PORT!"=="1" (
        set "PORT=%%~A"
        set "NEXT_IS_PORT=0"
    ) else if /I "%%~A"=="--port" (
        set "NEXT_IS_PORT=1"
    ) else if /I "%%~A"=="--no-browser" (
        set "NO_BROWSER=1"
    )
)

set "URL=http://127.0.0.1:!PORT!/"

echo [UX-mAInd] Starte lokalen Studio-Server auf !URL! ...
if "!NO_BROWSER!"=="1" (
    "%~dp0.venv\Scripts\python.exe" -m ux_maind.app.studio --port !PORT! --no-browser %*
    exit /b !ERRORLEVEL!
)

start "UX-mAInd Server" /min "%~dp0.venv\Scripts\python.exe" -m ux_maind.app.studio --port !PORT! --no-browser %*

timeout /t 2 /nobreak >nul

set "EDGE_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" set "EDGE_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

if exist "%EDGE_EXE%" (
    start "" "%EDGE_EXE%" --app=!URL! --window-size=1680,980
) else (
    start "" "!URL!"
)
