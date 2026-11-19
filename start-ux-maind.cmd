@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [UX-mAInd] Erstinstallation wird ausgefuehrt ...
    powershell -ExecutionPolicy Bypass -File "%~dp0install.ps1"
    if errorlevel 1 pause & exit /b 1
)

set "PORT=8465"
set "URL=http://127.0.0.1:%PORT%/"

echo [UX-mAInd] Starte lokalen Studio-Server auf %URL% ...
start "UX-mAInd Server" /min "%~dp0.venv\Scripts\python.exe" -m ux_maind.app.studio --port %PORT% --no-browser

timeout /t 2 /nobreak >nul

set "EDGE_EXE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" set "EDGE_EXE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"

if exist "%EDGE_EXE%" (
    start "" "%EDGE_EXE%" --app=%URL% --window-size=1680,980
) else (
    start "" "%URL%"
)
