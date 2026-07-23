@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title SINIDU — Iniciar sistema

rem =====================================================================
rem  Abrir SINIDU (Windows)
rem  Duplo clique neste arquivo ou copie para a Area de Trabalho.
rem  Requisitos: Docker Desktop instalado e em execucao.
rem =====================================================================

cd /d "%~dp0.."
set "PROJECT_DIR=%CD%"
set "API_URL=http://localhost:8000"
set "APP_URL=http://localhost:3000"
set "COMPOSE=docker compose -f docker-compose.yml -f docker-compose.dev.yml"

echo.
echo  ========================================
echo   SINIDU+Clima — iniciando o sistema
echo  ========================================
echo.
echo  Pasta do projeto:
echo    %PROJECT_DIR%
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Docker CLI nao encontrado no PATH.
  echo Instale o Docker Desktop e reinicie o PC, depois tente novamente.
  echo.
  pause
  exit /b 1
)

echo [1/5] Verificando Docker Desktop...
docker info >nul 2>&1
if errorlevel 1 (
  echo Docker ainda nao responde — tentando abrir o Docker Desktop...
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
  ) else if exist "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles(x86)%\Docker\Docker\Docker Desktop.exe"
  ) else (
    echo [ERRO] Docker Desktop nao encontrado em Program Files.
    echo Abra o Docker Desktop manualmente e rode este script de novo.
    echo.
    pause
    exit /b 1
  )

  echo Aguardando o Docker ficar pronto (ate 5 min)...
  set /a _attempt=0
  :wait_docker
  set /a _attempt+=1
  docker info >nul 2>&1
  if not errorlevel 1 goto docker_ready
  if !_attempt! geq 150 (
    echo.
    echo [ERRO] O Docker nao ficou pronto a tempo.
    echo Abra o Docker Desktop, aguarde o icone ficar verde e tente novamente.
    echo.
    pause
    exit /b 1
  )
  if !_attempt! equ 60 echo   ... ainda aguardando (~2 min^)
  if !_attempt! equ 120 echo   ... ainda aguardando (~4 min^)
  timeout /t 2 /nobreak >nul
  goto wait_docker
)
:docker_ready
echo Docker pronto.
echo.

echo [2/5] Subindo servicos essenciais: db redis backend frontend
%COMPOSE% up -d --build db redis backend frontend
if errorlevel 1 (
  echo.
  echo [ERRO] Falha ao subir os containers.
  echo Verifique espaco em disco e logs no Docker Desktop.
  echo.
  pause
  exit /b 1
)
echo.

echo [3/5] Aguardando a API em %API_URL% (ate 5 min)...
set "BACKEND_OK=0"
set /a _attempt=0
:wait_backend
set /a _attempt+=1
curl.exe -fsS "%API_URL%/health/ready" >nul 2>&1
if not errorlevel 1 (
  echo Backend pronto (API + banco de dados^).
  set "BACKEND_OK=1"
  goto backend_done
)
if !_attempt! geq 150 goto backend_done
if !_attempt! equ 30 echo   ... ainda iniciando (~1 min^)
if !_attempt! equ 90 echo   ... ainda iniciando (~3 min^)
timeout /t 2 /nobreak >nul
goto wait_backend
:backend_done
if "%BACKEND_OK%"=="0" (
  echo [AVISO] Backend ainda nao respondeu em %API_URL%/health/ready
  echo Logs: docker compose -f docker-compose.yml logs backend --tail 40
)
echo.

echo [4/5] Aguardando a interface em %APP_URL% (ate 5 min)...
set "FRONTEND_OK=0"
set /a _attempt=0
:wait_frontend
set /a _attempt+=1
curl.exe -fsS "%APP_URL%" >nul 2>&1
if not errorlevel 1 (
  echo Frontend pronto.
  set "FRONTEND_OK=1"
  goto frontend_done
)
if !_attempt! geq 150 goto frontend_done
if !_attempt! equ 15 (
  docker inspect -f "{{.State.Status}}" sinidu_frontend 2>nul | findstr /i "running" >nul
  if errorlevel 1 (
    echo Frontend parado — recriando...
    %COMPOSE% up -d --force-recreate --build frontend >nul 2>&1
  )
)
if !_attempt! equ 30 echo   ... ainda iniciando frontend (~1 min^)
if !_attempt! equ 90 echo   ... ainda iniciando frontend (~3 min^)
timeout /t 2 /nobreak >nul
goto wait_frontend
:frontend_done
echo.

echo [5/5] Abrindo o navegador...
start "" "%APP_URL%"
echo.

if "%BACKEND_OK%"=="1" if "%FRONTEND_OK%"=="1" (
  echo ========================================
  echo  SINIDU pronto.
  echo  Interface: %APP_URL%
  echo  API:       %API_URL%
  echo ========================================
) else (
  echo ========================================
  echo  Alguns servicos ainda nao responderam.
  echo  Backend:  %BACKEND_OK%  ^(1=OK^)
  echo  Frontend: %FRONTEND_OK% ^(1=OK^)
  echo  Abrindo mesmo assim: %APP_URL%
  echo ========================================
  echo.
  echo Logs recentes do frontend:
  docker logs sinidu_frontend --tail 25 2>&1
)

echo.
pause
endlocal
exit /b 0
