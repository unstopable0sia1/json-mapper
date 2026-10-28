@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 goto pylauncher
where python >nul 2>nul
if not errorlevel 1 goto pythonlauncher
echo Khong tim thay Python. Cai Python 3.10+ kem Tcl/Tk va chay lai.
pause
exit /b 1
:pylauncher
py -3 app.py
if errorlevel 1 pause
exit /b
:pythonlauncher
python app.py
if errorlevel 1 pause
