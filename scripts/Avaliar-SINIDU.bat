@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title SINIDU - Avaliar sistema

rem =====================================================================
rem  Avaliar SINIDU (Windows) - salve este arquivo com encoding CRLF
rem  Checa Docker, API, frontend e municipios-piloto.
rem  Gera: scripts\avaliacao_ultimo_relatorio.txt
rem =====================================================================

if exist "%~dp0_sinidu_find_project.bat" (
  call "%~dp0_sinidu_find_project.bat"
) else (
  echo [ERRO] Falta _sinidu_find_project.bat ao lado deste arquivo.
  echo Copie tambem _sinidu_find_project.bat ^(e SINIDU_DIR.txt se estiver na Area de Trabalho^).
  pause
  exit /b 1
)
if not defined PROJECT_DIR (
  echo [ERRO] Nao encontrei a pasta do projeto SINIDU.
  echo Crie SINIDU_DIR.txt ao lado deste .bat com o caminho do projeto.
  echo.
  pause
  exit /b 1
)

cd /d "%PROJECT_DIR%"
if errorlevel 1 (
  echo [ERRO] Nao consegui entrar em: %PROJECT_DIR%
  pause
  exit /b 1
)

set "API_URL=http://localhost:8000"
set "FRONTEND_URL=http://localhost:3000"
set "SCRIPT=%CD%\scripts\avaliar_sistema.py"
set "REPORT=%CD%\scripts\avaliacao_ultimo_relatorio.txt"
set "EXITCODE=1"

echo.
echo  ========================================
echo   SINIDU+Clima - avaliacao do sistema
echo  ========================================
echo.
echo  Pasta: %CD%
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Docker CLI nao encontrado.
  echo Instale/inicie o Docker Desktop e tente novamente.
  echo.
  pause
  exit /b 1
)

docker info >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Docker Desktop nao esta pronto.
  echo Abra o Docker Desktop, aguarde o icone verde e rode este script de novo.
  echo Dica: use Abrir-SINIDU.bat para subir o sistema primeiro.
  echo.
  pause
  exit /b 1
)

set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
  where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
  where python3 >nul 2>&1 && set "PY=python3"
)

if defined PY (
  echo Usando Python do host: %PY%
  echo.
  %PY% "%SCRIPT%" "%API_URL%"
  set "EXITCODE=!ERRORLEVEL!"
) else (
  echo Python nao encontrado no host - avaliando via container backend...
  echo.
  docker inspect -f "{{.State.Status}}" sinidu_backend 2>nul | findstr /i "running" >nul
  if errorlevel 1 (
    echo [ERRO] Container sinidu_backend nao esta em execucao.
    echo Rode Abrir-SINIDU.bat primeiro.
    echo.
    pause
    exit /b 1
  )

  if not exist "%SCRIPT%" (
    echo [ERRO] Script nao encontrado: %SCRIPT%
    pause
    exit /b 1
  )

  docker cp "%SCRIPT%" sinidu_backend:/tmp/avaliar_sistema.py >nul 2>&1
  docker exec -e AVALIACAO_SKIP_DOCKER=1 -e FRONTEND_URL=http://host.docker.internal:3000 -e AVALIACAO_REPORT_PATH=/tmp/avaliacao_ultimo_relatorio.txt sinidu_backend python /tmp/avaliar_sistema.py http://127.0.0.1:8000
  set "EXITCODE=!ERRORLEVEL!"
  docker cp sinidu_backend:/tmp/avaliacao_ultimo_relatorio.txt "%REPORT%" >nul 2>&1
)

echo.
if exist "%REPORT%" (
  echo Relatorio:
  echo   %REPORT%
  echo.
)

if "!EXITCODE!"=="0" (
  echo RESULTADO: APROVADO
) else (
  echo RESULTADO: REPROVADO ^(codigo !EXITCODE!^)
  echo Revise o relatorio e os logs: docker compose logs backend --tail 40
)

echo.
pause
exit /b !EXITCODE!
