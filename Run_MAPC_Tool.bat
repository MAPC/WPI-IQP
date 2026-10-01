@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" "%~dp0launch_mapc.py"
    goto finish
)
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0launch_mapc.py"
    goto finish
)
where python >nul 2>nul
if not errorlevel 1 (
    python "%~dp0launch_mapc.py"
    goto finish
)
echo MAPC Tool could not run.
echo.
echo Install Python 3.12 or newer from python.org, then run this launcher again.
pause
exit /b 1
:finish
set "MAPC_EXIT=%ERRORLEVEL%"
if not "%MAPC_EXIT%"=="0" pause
exit /b %MAPC_EXIT%
