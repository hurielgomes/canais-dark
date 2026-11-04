@echo off
chcp 65001 >nul
title Dependencias da Fabrica de Videos
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt
echo.
echo Dependencias instaladas. FFmpeg e FFprobe precisam estar no PATH.
pause
