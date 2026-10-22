@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
if not exist "backend\.venv\Scripts\python.exe" (
    echo The backend virtual environment is missing.
    popd
    exit /b 1
)
"backend\.venv\Scripts\python.exe" -u "scripts\check_groq.py"
set "BLOOMCARE_GROQ_EXIT=%ERRORLEVEL%"
popd
endlocal & exit /b %BLOOMCARE_GROQ_EXIT%
