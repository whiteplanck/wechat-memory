@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -m wechat_memory.server
if errorlevel 1 pause
exit /b
:missing
echo Run setup-windows.cmd first.
pause
exit /b 1
