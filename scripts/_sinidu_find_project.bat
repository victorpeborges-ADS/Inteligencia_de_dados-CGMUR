@echo off
rem Resolve PROJECT_DIR para os launchers Windows do SINIDU.
rem 1) pasta pai de scripts\  2) SINIDU_DIR.txt ao lado  3) %SINIDU_PROJECT_DIR%  4) pasta do .bat
set "SINIDU_SCRIPT_DIR=%~dp0"
if "%SINIDU_SCRIPT_DIR:~-1%"=="\" set "SINIDU_SCRIPT_DIR=%SINIDU_SCRIPT_DIR:~0,-1%"
set "PROJECT_DIR="

if exist "%SINIDU_SCRIPT_DIR%\..\docker-compose.yml" goto from_scripts_parent
if exist "%SINIDU_SCRIPT_DIR%\SINIDU_DIR.txt" goto from_dir_txt
if defined SINIDU_PROJECT_DIR goto from_env
if exist "%SINIDU_SCRIPT_DIR%\docker-compose.yml" goto from_script_dir
set "PROJECT_DIR="
goto :eof

:from_scripts_parent
for %%I in ("%SINIDU_SCRIPT_DIR%\..") do set "PROJECT_DIR=%%~fI"
goto :eof

:from_dir_txt
set /p PROJECT_DIR=<"%SINIDU_SCRIPT_DIR%\SINIDU_DIR.txt"
set "PROJECT_DIR=%PROJECT_DIR:"=%"
goto :eof

:from_env
set "PROJECT_DIR=%SINIDU_PROJECT_DIR%"
goto :eof

:from_script_dir
set "PROJECT_DIR=%SINIDU_SCRIPT_DIR%"
goto :eof
