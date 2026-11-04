@echo off
chcp 65001 >nul
cd /d "%~dp0"
set /p N=Quantas ideias de tema (ex.: 10): 
python criar_video.py exemplo --ideias %N%
echo.
pause
