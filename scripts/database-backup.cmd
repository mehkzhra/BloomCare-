@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" "scripts\database_backup.py" %*
set "BLOOMCARE_SCRIPT_EXIT=%ERRORLEVEL%"
popd
endlocal & exit /b %BLOOMCARE_SCRIPT_EXIT%
