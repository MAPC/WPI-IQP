@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_pipeline.ps1" %*
set "MAPC_EXIT=%ERRORLEVEL%"
if not "%MAPC_EXIT%"=="0" echo Pipeline failed. Review output\reports and output\logs\pipeline.log.
pause
exit /b %MAPC_EXIT%
