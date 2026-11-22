@echo off
title Lap Studio
rem Double-click in File Explorer to open Lap Studio (replay viewer, telemetry, coaching, video reviews).
rem Keep this window open while you watch; close it to stop the viewer.
set "HERE=%~dp0."
set "REPO="
for /f "usebackq delims=" %%P in (`wsl.exe -e wslpath -u "%HERE%"`) do set "REPO=%%P"
if not defined REPO (
  echo Could not locate this folder inside WSL: %HERE%
  pause
  exit /b 1
)
echo Starting Lap Studio from %REPO% ...
wsl.exe --cd "%REPO%" -- bash -lc "bash ./replay.sh %*"
if errorlevel 1 pause
