@echo off
setlocal
cd /d "%~dp0"

set "IMP_SETUP_PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%IMP_SETUP_PYTHON%" goto run_setup

where py >nul 2>nul
if not errorlevel 1 (
  echo Using the Python 3.11 launcher to create the project environment.
  py -3.11 "%~dp0tools\platform\bootstrap.py" setup --root "%~dp0"
  set "IMP_EXIT_CODE=%ERRORLEVEL%"
  if not "%IMP_EXIT_CODE%"=="0" (
    pause
    exit /b %IMP_EXIT_CODE%
  )
  goto setup_complete
)

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: CPython 3.11 is required. Install it, then run setup again.
  pause
  exit /b 2
)

:run_setup
if not exist "%IMP_SETUP_PYTHON%" (
  set "IMP_SETUP_PYTHON=python"
)

echo Preparing the Integrated Market Platform...
"%IMP_SETUP_PYTHON%" "%~dp0tools\platform\bootstrap.py" setup --root "%~dp0"
set "IMP_EXIT_CODE=%ERRORLEVEL%"
if not "%IMP_EXIT_CODE%"=="0" (
  pause
  exit /b %IMP_EXIT_CODE%
)

:setup_complete
echo.
echo Setup is complete. Choose what to do next:
choice /c DC /n /m "[D] Enter Demo  [C] Continue setup / exit: "
if errorlevel 2 exit /b 0
call "%~dp0START_PLATFORM.cmd"
exit /b %ERRORLEVEL%
