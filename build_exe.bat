@echo off
REM ============================================================
REM  Build BluOpticalSim.exe — double-click to run on Windows
REM ============================================================

echo.
echo  Blu Optical Simulation — Build Script
echo  ======================================
echo.

REM Check Python is on PATH
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo  ERROR: Python was not found on your PATH.
    echo  Please install Python 3.10+ from https://python.org
    echo  and make sure "Add Python to PATH" is checked during install.
    pause
    exit /b 1
)

echo  Python found:
python --version
echo.

REM Install / upgrade dependencies
echo  Installing dependencies ...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt --quiet
python -m pip install pyinstaller --quiet
echo  Dependencies installed.
echo.

REM Run the build
echo  Building executable ...
python build_exe.py --zip

if %errorlevel% neq 0 (
    echo.
    echo  Build FAILED. See output above for details.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Build complete!
echo   Find your executable in:  dist\BluOpticalSim\
echo   Distributable zip in:     dist\BluOpticalSim-windows.zip
echo  ============================================================
echo.
pause
