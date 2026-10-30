@echo off
setlocal
cd /d "%~dp0"
set DMAX_WEB_UI=server
if exist .venv\Scripts\python.exe goto :dependencies
for %%V in (3.13 3.12 3.14) do (
  py -%%V -c "import sys,sysconfig; print(sys.version); sys.exit(0 if sysconfig.get_platform() == 'win-amd64' else 1)" >nul 2>&1
  if not errorlevel 1 (
    echo Usando Python %%V.
    py -%%V -m venv .venv
    if errorlevel 1 goto :failure
    goto :dependencies
  )
)
echo Nenhum Python x64 3.12, 3.13 ou 3.14 pode ser executado por esta conta.
goto :failure
:dependencies
.venv\Scripts\python.exe -c "import sys,sysconfig; sys.exit(0 if sys.version_info[:2] in ((3,12),(3,13),(3,14)) and sysconfig.get_platform() == 'win-amd64' else 1)"
if errorlevel 1 goto :unsupported
fc /b requirements.lock .venv\installed.lock >nul 2>&1
if errorlevel 1 (
  if exist wheels\*.whl (
    .venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-index --find-links wheels --only-binary=:all: --require-hashes -r requirements.lock
  ) else (
    .venv\Scripts\python.exe -m pip install --disable-pip-version-check --only-binary=:all: --require-hashes -r requirements.lock
  )
  if errorlevel 1 goto :failure
  copy /y requirements.lock .venv\installed.lock >nul
)
echo.
echo Nome, porta e enderecos serao mostrados abaixo. Ctrl+C encerra o controlador.
.venv\Scripts\python.exe run.py %*
if errorlevel 1 goto :failure
exit /b 0
:failure
echo Nao foi possivel iniciar. Confira o acesso ao Python 3.12, 3.13 ou 3.14 e a mensagem acima.
pause
exit /b 1
:unsupported
echo O ambiente .venv existente nao usa Python x64 3.12, 3.13 ou 3.14.
echo Preserve ou renomeie essa pasta e inicie novamente com Python 3.12, 3.13 ou 3.14.
pause
exit /b 1
