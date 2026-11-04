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
  echo Execute este arquivo dentro da pasta canais-dark.
  pause
  exit /b 1
)

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
  echo ERRO: ambiente .venv nao encontrado em "%~dp0.venv".
  echo Crie com:
  echo   py -3.12 -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt kokoro-onnx soundfile
  pause
  exit /b 1
)

"%PYTHON%" -c "import kokoro_onnx" >nul 2>&1
if errorlevel 1 (
  echo AVISO: kokoro_onnx nao esta instalado na .venv. Instalando...
  "%PYTHON%" -m pip install kokoro-onnx soundfile
)

rem Abre o navegador em um processo separado, sem afetar esta janela
start "" /min cmd /c "timeout /t 3 /nobreak >nul & start "" http://127.0.0.1:8765"

"%PYTHON%" app.py 2>&1

echo.
echo A Fabrica foi encerrada. Codigo de saida: %errorlevel%
pause
