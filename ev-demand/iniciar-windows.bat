@echo off
setlocal
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  py -3.12 -m venv .venv
  if errorlevel 1 goto :failure
)
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
echo Nao foi possivel iniciar. Confira o Python 3.12 e a mensagem acima.
pause
exit /b 1
