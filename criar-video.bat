@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p TEMA=Tema do video: 
python criar_video.py exemplo "%TEMA%"
echo.
pause
