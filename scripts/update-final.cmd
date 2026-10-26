@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
set "BLOOMCARE_PYTHON=%CD%\backend\.venv\Scripts\python.exe"
if not exist "%BLOOMCARE_PYTHON%" (
    echo Complete the existing BloomCare backend setup before this update.
    goto failed
)
echo BloomCare complete delivery update v1.3.0
echo Stop the backend and frontend servers before continuing this update.
echo Checking dependencies and the existing database...
"%BLOOMCARE_PYTHON%" -m pip check
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -c "import numpy, shap, sklearn"
if errorlevel 1 (
    "%BLOOMCARE_PYTHON%" -m pip install -r backend\research-requirements.txt
    if errorlevel 1 goto failed
)
"%BLOOMCARE_PYTHON%" -m ruff check backend scripts ml deploy --select I --fix --config backend\pyproject.toml
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -m ruff check backend scripts ml deploy --config backend\pyproject.toml
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" scripts\verify_pe_model.py
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -m pytest -c ml\pytest.ini ml\tests
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" scripts\prepare_backend.py
if errorlevel 1 goto failed
echo Saving a PostgreSQL backup before any application database changes...
"%BLOOMCARE_PYTHON%" scripts\database_backup.py backup
if errorlevel 1 goto failed
echo Checking the frontend...
call npm.cmd --prefix frontend run lint
if errorlevel 1 goto failed
call npm.cmd --prefix frontend test
if errorlevel 1 goto failed
call npm.cmd --prefix frontend run build
if errorlevel 1 goto failed
echo Checking all migrations and workflows in a separate temporary PostgreSQL database...
"%BLOOMCARE_PYTHON%" scripts\test_postgres.py
if errorlevel 1 goto failed
echo Applying the verified upgrade to the existing application database...
pushd backend
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" -m alembic upgrade head
if errorlevel 1 goto failed_backend
"%BLOOMCARE_PYTHON%" -m alembic check
if errorlevel 1 goto failed_backend
popd
echo Consolidating verified obsolete release files...
"%BLOOMCARE_PYTHON%" scripts\clean_project.py --apply
if errorlevel 1 goto failed
"%BLOOMCARE_PYTHON%" scripts\verify_delivery.py
if errorlevel 1 goto failed
echo BloomCare v1.3.0 complete update passed.
echo Start backend and frontend in separate CMD windows, then refresh with Ctrl+F5.
echo Read docs\DEPLOYMENT.md for provider setup and final live checks.
popd
endlocal
exit /b 0
:failed_backend
popd
:failed
echo The complete update stopped. Read the error above; completed checks and backups remain available.
popd
endlocal
exit /b 1
