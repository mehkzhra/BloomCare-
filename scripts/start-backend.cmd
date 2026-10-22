@echo off
setlocal
pushd "%~dp0..\backend"
if errorlevel 1 exit /b 1
if not exist ".venv\Scripts\python.exe" (
    echo The backend virtual environment is missing.
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -u "..\scripts\prepare_backend.py"
if errorlevel 1 (
    echo Backend startup stopped. Resolve the database message above and run this command again.
    popd
    exit /b 1
)
".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --no-access-log
set "BLOOMCARE_RUN_EXIT=%ERRORLEVEL%"
popd
endlocal & exit /b %BLOOMCARE_RUN_EXIT%
