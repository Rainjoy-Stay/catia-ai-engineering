@echo off

setlocal

cd /d "%~dp0"

set PYTHONUTF8=1

"release_build\CATIA_Offline_20261012\runtime\python.exe" -X utf8 "release_build\CATIA_Offline_20261012\scripts\portable_self_check.py" --tests --hashes

if errorlevel 1 (

  pause

  exit /b 1

)

echo Offline validation passed. Live CATIA validation is separate.

pause

