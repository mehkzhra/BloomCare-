@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1

set "BLOOMCARE_PYTHON=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%BLOOMCARE_PYTHON%" (
    echo Backend Python environment is missing. Complete the foundation setup first.
    goto failed
)

"%BLOOMCARE_PYTHON%" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 'This checkpoint requires Python 3.12.')"
if errorlevel 1 goto failed

if exist "backend\research-requirements.txt" (
    "%BLOOMCARE_PYTHON%" -m pip install --only-binary=:all: -r backend\research-requirements.txt
) else (
    "%BLOOMCARE_PYTHON%" -m pip install --only-binary=:all: -r ml\requirements.txt
)
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -m pip check
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -m pytest -c backend\pyproject.toml backend\tests
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -m pytest -c ml\pytest.ini ml\tests
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -m ml.fetch_data
if errorlevel 1 goto failed

if exist "ml\artifacts\maternal_rf_v0.2\manifest.json" (
    echo A completed training checkpoint exists. Verifying it without retraining.
) else (
    "%BLOOMCARE_PYTHON%" -m ml.train_maternal
    if errorlevel 1 goto failed
)

"%BLOOMCARE_PYTHON%" -m ml.verify_model
if errorlevel 1 goto failed
echo Maternal-risk training checkpoint passed. Application activation was not changed.
popd
endlocal
exit /b 0

:failed
echo Checkpoint stopped. Read the error above before continuing.
popd
endlocal
exit /b 1
