@echo off
chcp 65001 >nul
cd /d "%~dp0"
py verificar_chat_scope.py
echo.
pause
