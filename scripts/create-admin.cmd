@echo off
setlocal
pushd "%~dp0..\backend"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo The backend virtual environment is missing.
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -m app.manage admin %*
set "BLOOMCARE_CREATE_EXIT=%ERRORLEVEL%"
popd
endlocal & exit /b %BLOOMCARE_CREATE_EXIT%
