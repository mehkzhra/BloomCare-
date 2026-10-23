@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
"backend\.venv\Scripts\python.exe" scripts\configure_whatsapp.py %*
set "BLOOMCARE_EXIT=%ERRORLEVEL%"
popd
exit /b %BLOOMCARE_EXIT%
