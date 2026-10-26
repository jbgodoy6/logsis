@echo off
setlocal
cd /d "%~dp0"
if exist .venv\Scripts\python.exe goto :dependencies
for %%V in (3.13 3.12 3.14) do (
  py -%%V -c "import sys; print(sys.version)" >nul 2>&1
  if not errorlevel 1 (
    echo Usando Python %%V.
    py -%%V -m venv .venv
    if errorlevel 1 goto :failure
    goto :dependencies
  )
)
echo Nenhum Python 3.12, 3.13 ou 3.14 pode ser executado por esta conta.
goto :failure
:dependencies
.venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13),(3,14)) else 1)"
if errorlevel 1 goto :unsupported
fc /b requirements.lock .venv\installed.lock >nul 2>&1
if errorlevel 1 (
  .venv\Scripts\python.exe -m pip install -r requirements.lock
  if errorlevel 1 goto :failure
  copy /y requirements.lock .venv\installed.lock >nul
)
echo.
echo Abra http://127.0.0.1:8080 no navegador. Ctrl+C encerra o controlador.
.venv\Scripts\python.exe run.py
if errorlevel 1 goto :failure
exit /b 0
:failure
echo Nao foi possivel iniciar. Confira o acesso ao Python 3.12, 3.13 ou 3.14 e a mensagem acima.
pause
exit /b 1
:unsupported
echo O ambiente .venv existente usa uma versao ainda nao validada.
echo Preserve ou renomeie essa pasta e inicie novamente com Python 3.12, 3.13 ou 3.14.
pause
exit /b 1
