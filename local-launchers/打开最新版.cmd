@echo off

setlocal

cd /d "%~dp0"

set PYTHONUTF8=1

"release_build\CATIA_Offline_20261012\runtime\python.exe" -X utf8 "release_build\CATIA_Offline_20261012\scripts\current_ui.py"

if errorlevel 1 pause

