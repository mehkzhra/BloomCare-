@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "BLOOMCARE_PYTHON=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%BLOOMCARE_PYTHON%" (
    echo Set up the BloomCare backend environment first.
    popd
    exit /b 1
)
"%BLOOMCARE_PYTHON%" -m ml.retrain_legacy_pe %*
set "BLOOMCARE_EXIT=%ERRORLEVEL%"
popd
exit /b %BLOOMCARE_EXIT%
