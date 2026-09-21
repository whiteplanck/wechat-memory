@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo WeChat Memory - Windows setup
echo Requires Python 3.11+ and Node.js 22.13+ on Windows x64.
if exist ".venv\Scripts\python.exe" goto install
py -3 -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -e ".[photos]"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m wechat_memory.windows_exporter setup
if errorlevel 1 goto failed
echo Setup complete. Sign in to WeChat, then run init-wechat-windows.cmd.
pause
exit /b 0
:failed
echo Setup failed. Read the error above and docs\windows.md.
pause
exit /b 1
