@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
if not exist "backend\.venv\Scripts\python.exe" (
    echo The backend virtual environment is missing.
    popd
    exit /b 1
)
"backend\.venv\Scripts\python.exe" scripts\check_research_status.py
set "BLOOMCARE_STATUS_EXIT=%ERRORLEVEL%"
popd
endlocal & exit /b %BLOOMCARE_STATUS_EXIT%
