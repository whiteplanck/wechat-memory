@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
echo Sign in to Windows WeChat before continuing.
echo If process access is denied, right-click this script and Run as administrator.
".venv\Scripts\python.exe" -m wechat_memory.windows_exporter init
if errorlevel 1 goto failed
echo Initialization finished. Run start-windows.cmd next.
pause
exit /b 0
:missing
echo Run setup-windows.cmd first.
:failed
pause
exit /b 1
