@echo off
setlocal
python "%~dp0gui_converter.py"
if errorlevel 1 pause
