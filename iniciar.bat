@echo off
setlocal
chcp 65001 >nul
title Fabrica de videos - mantenha esta janela aberta

cd /d "%~dp0"
if errorlevel 1 (
  echo ERRO: nao foi possivel acessar a pasta do projeto: "%~dp0"
  pause
  exit /b 1
)

if not exist "%~dp0app.py" (
  echo ERRO: app.py nao foi encontrado ao lado de iniciar.bat.
  echo Execute este arquivo dentro da pasta canais-darks.
  pause
  exit /b 1
)

start "" /b powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8765'"

where py >nul 2>&1
if not errorlevel 1 (
  py app.py
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo ERRO: nem o launcher py nem python foram encontrados no PATH.
    pause
    exit /b 1
  )
  python app.py
)

if errorlevel 1 echo A Fabrica foi encerrada com erro.
echo.
pause
