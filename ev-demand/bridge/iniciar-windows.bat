@echo off
setlocal
cd /d "%~dp0"
for %%V in (3.14 3.13 3.12 3.11) do (
  py -%%V -c "import sys;sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
  if not errorlevel 1 (
    py -%%V verificar.py
    if errorlevel 1 goto :failure
    py -%%V main.py %*
    if errorlevel 1 goto :failure
    exit /b 0
  )
)
echo Instale Python 3.11 ou superior do site python.org com o Python Launcher.
pause
exit /b 1
:failure
echo Nao foi possivel iniciar. Confira a mensagem acima. A porta padrao e 8765.
pause
exit /b 1
