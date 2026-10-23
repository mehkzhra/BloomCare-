@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
if not exist "frontend\dist\index.html" (
    echo Build the interface first: scripts\update-ui.cmd
    popd
    exit /b 1
)
rem Local computer only. Public hosting uses the separate deployment configuration.
set "FRONTEND_STATIC_DIR=%CD%\frontend\dist"
set "PUBLIC_APP_URL=http://127.0.0.1:8000"
set "ALLOWED_ORIGINS=http://127.0.0.1:8000"
set "COOKIE_SECURE=false"
set "AUTH_PROXY_HEADER=none"
echo Open BloomCare at http://127.0.0.1:8000 after application startup completes.
call "%~dp0start-backend.cmd"
set "BLOOMCARE_LOCAL_EXIT=%ERRORLEVEL%"
popd
exit /b %BLOOMCARE_LOCAL_EXIT%
