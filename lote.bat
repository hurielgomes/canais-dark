@echo off
chcp 65001 >nul
cd /d "%~dp0"
python criar_video.py exemplo --lote canais\exemplo\temas.txt
echo.
pause
