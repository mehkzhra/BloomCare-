@echo off
setlocal
pushd "%~dp0.."
if errorlevel 1 exit /b 1
where node >nul 2>&1
if errorlevel 1 (
    echo Install Node.js 24 or later, then run this update again.
    goto failed
)
node -e "if(Number(process.versions.node.split('.')[0]) < 24) { console.error('Node.js 24 or later is required.'); process.exit(1); }"
if errorlevel 1 goto failed
if not exist "frontend\node_modules\.bin\vite.cmd" (
    call npm.cmd --prefix frontend ci
    if errorlevel 1 goto failed
)
echo Checking the BloomCare interface...
call npm.cmd --prefix frontend run lint
if errorlevel 1 goto failed
call npm.cmd --prefix frontend test
if errorlevel 1 goto failed
call npm.cmd --prefix frontend run build
if errorlevel 1 goto failed
echo BloomCare v1.3.0 interface update passed.
echo Restart your existing server and refresh the browser with Ctrl+F5.
echo This interface update makes no database or environment changes.
popd
endlocal
exit /b 0
:failed
echo Interface update stopped. Read the error above before restarting.
popd
endlocal
exit /b 1
