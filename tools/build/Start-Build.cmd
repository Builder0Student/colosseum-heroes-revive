@echo off
title Colosseum Heroes - 64-bit build
cd /d "%~dp0"
echo Colosseum Heroes 64-bit build
echo.
echo Step 1: install Unity 2019.4.41f2, Unity Hub and Android Build Support on D:
echo         Windows will ask for administrator rights - click Yes.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_android.ps1"
if errorlevel 1 (
  echo.
  echo Setup did not finish - see setup.log in this folder.
  pause
  exit /b 1
)
if exist "%~dp0license-done.txt" goto build
echo.
echo Step 2: free Unity license. Unity Hub is opening:
echo   1. Sign in with your Unity account, or create a free one.
echo   2. If Hub offers a free Personal license, accept it. Otherwise open Preferences
echo      (gear icon) - Licenses - Add - Get a free personal license.
echo   3. Skip any offer to install another Unity version.
echo Then come back to this window.
start "" "D:\Unity Hub\Unity Hub.exe"
echo.
pause
echo ok> "%~dp0license-done.txt"
:build
echo.
echo Step 3: building the game. Leave this window open.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_loop.ps1"
pause
