@echo off
setlocal
pushd "%~dp0..\frontend"
if errorlevel 1 exit /b 1
call npm.cmd run dev
set "BLOOMCARE_RUN_EXIT=%ERRORLEVEL%"
popd
endlocal & exit /b %BLOOMCARE_RUN_EXIT%
