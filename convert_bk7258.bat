@echo off
setlocal

if "%~1"=="" (
    echo Usage:
    echo   Drag an MP4 file onto this BAT file, or run:
    echo   convert_bk7258.bat input.mp4 [output.mp4]
    pause
    exit /b 1
)

set "INPUT=%~1"
set "OUTPUT=%~2"

if "%OUTPUT%"=="" (
    python "%~dp0mp4_converter.py" "%INPUT%"
) else (
    python "%~dp0mp4_converter.py" "%INPUT%" -o "%OUTPUT%"
)

if errorlevel 1 (
    echo.
    echo Conversion failed.
    pause
    exit /b 1
)

echo.
echo Conversion complete.
pause
