@echo off
title ACC Mechanic
rem Double-click in File Explorer, then drive in ACC. The engineer talks over your speakers,
rem shows a dashboard in your browser and an overlay window, and writes Auto_Tweak.json setups.
rem Keep this window open while you drive; close it to stop the mechanic.
set "HERE=%~dp0."
set "REPO="
for /f "usebackq delims=" %%P in (`wsl.exe -e wslpath -u "%HERE%"`) do set "REPO=%%P"
if not defined REPO (
  echo Could not locate this folder inside WSL: %HERE%
  pause
  exit /b 1
)
echo Starting the ACC mechanic from %REPO% ...
wsl.exe --cd "%REPO%" -- bash -lc "python3 -m external.acc_mechanic %*"
if errorlevel 1 pause
