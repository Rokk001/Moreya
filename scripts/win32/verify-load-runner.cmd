@echo off
setlocal
rem Run both load-runner regressions through cmd.exe and retain both exit codes.
pushd "%~dp0..\.."
if errorlevel 1 exit /b 1

"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -I source/tests/check_run_level_test_port.py
set "port_status=%errorlevel%"
"%LOCALAPPDATA%\Programs\Python\Python314\python.exe" -I source/tests/check_load_process_diagnostics.py
set "diagnostics_status=%errorlevel%"

echo check_run_level_test_port.py exit_code=%port_status%
echo check_load_process_diagnostics.py exit_code=%diagnostics_status%
popd
if not "%port_status%"=="0" exit /b 1
if not "%diagnostics_status%"=="0" exit /b 1
exit /b 0
