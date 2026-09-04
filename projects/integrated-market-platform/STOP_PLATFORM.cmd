@echo off
setlocal
cd /d "%~dp0"
set "IMP_LAUNCHER_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%IMP_LAUNCHER_PYTHON%" (
  echo ERROR: Repository Python 3.11 environment is missing.
  pause
  exit /b 2
)
"%IMP_LAUNCHER_PYTHON%" "%~dp0tools\platform\local_launcher.py" stop
set "IMP_EXIT_CODE=%ERRORLEVEL%"
if not "%IMP_EXIT_CODE%"=="0" pause
exit /b %IMP_EXIT_CODE%
