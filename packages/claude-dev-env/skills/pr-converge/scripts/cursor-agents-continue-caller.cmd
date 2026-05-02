@echo off
setlocal
for /f "delims=" %%P in ('pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0caller-window-pid.ps1"') do set CALLER_PID=%%P
if "%CALLER_PID%"=="" (
    echo [cursor-agents-continue-caller] Failed to resolve caller PID.
    exit /b 1
)
start "" "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe" "%~dp0cursor-agents-continue.ahk" %CALLER_PID% --start-on
endlocal
