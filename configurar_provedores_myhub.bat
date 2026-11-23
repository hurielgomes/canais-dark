@echo off
chcp 65001 >nul
cd /d "%~dp0"
py configurar_provedores_myhub.py
if errorlevel 1 (
  echo.
  echo Nao foi possivel atualizar os provedores. Nenhuma chave foi removida.
) else (
  echo.
  echo Configuracao concluida. Reinicie a Fabrica para carregar as alteracoes.
)
pause
