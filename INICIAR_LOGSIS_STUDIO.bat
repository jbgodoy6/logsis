@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto python
py -3 LogSis_Studio.py
if errorlevel 1 pause
exit /b
:python
where python >nul 2>nul
if errorlevel 1 goto missing
python LogSis_Studio.py
if errorlevel 1 pause
exit /b
:missing
echo Instale Python 3.10 ou superior, com Tcl/Tk, e abra este arquivo novamente.
echo O Studio usa a biblioteca grafica que acompanha o Python para Windows.
pause
