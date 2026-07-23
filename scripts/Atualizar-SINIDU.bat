@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul 2>&1
title SINIDU — Atualizar do Git

rem =====================================================================
rem  Atualizar SINIDU (Windows)
rem  Duplo clique para baixar atualizacoes do GitHub e reconstruir
rem  os containers essenciais.
rem =====================================================================

cd /d "%~dp0.."
set "PROJECT_DIR=%CD%"
set "COMPOSE=docker compose -f docker-compose.yml -f docker-compose.dev.yml"
set "CORE=db redis backend frontend"
set "EXITCODE=0"

echo.
echo  ========================================
echo   SINIDU+Clima — atualizar do Git
echo  ========================================
echo.
echo  Pasta: %PROJECT_DIR%
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Git nao encontrado no PATH.
  echo Instale o Git for Windows: https://git-scm.com/download/win
  echo.
  pause
  exit /b 1
)

if not exist "%PROJECT_DIR%\.git" (
  echo [ERRO] Esta pasta nao e um repositorio Git.
  echo Clone o projeto primeiro e rode este script de dentro da copia.
  echo.
  pause
  exit /b 1
)

for /f "delims=" %%b in ('git branch --show-current 2^>nul') do set "BRANCH=%%b"
if not defined BRANCH set "BRANCH=(detached)"

for /f "delims=" %%r in ('git remote get-url origin 2^>nul') do set "REMOTE=%%r"
if not defined REMOTE set "REMOTE=(sem origin)"

echo  Branch atual: %BRANCH%
echo  Remote:       %REMOTE%
echo.

rem --- Mudancas locais ---
git status --porcelain > "%TEMP%\sinidu_git_status.txt" 2>nul
set "DIRTY=0"
for /f %%A in ("%TEMP%\sinidu_git_status.txt") do set "DIRTY=1"
if exist "%TEMP%\sinidu_git_status.txt" (
  for %%A in ("%TEMP%\sinidu_git_status.txt") do if %%~zA gtr 0 set "DIRTY=1"
)

if "%DIRTY%"=="1" (
  echo [AVISO] Ha alteracoes locais nao commitadas:
  git status -sb
  echo.
  echo Opcoes:
  echo   [1] Guardar temporariamente ^(git stash^) e atualizar
  echo   [2] Cancelar ^(recomendado se voce nao sabe o que sao as mudancas^)
  echo.
  choice /C 12 /N /M "Escolha 1 ou 2: "
  if errorlevel 2 (
    echo.
    echo Atualizacao cancelada. Nenhuma mudanca foi baixada.
    echo.
    pause
    exit /b 0
  )
  echo.
  echo Guardando alteracoes locais ^(stash^)...
  git stash push -u -m "SINIDU auto-stash antes de atualizar %DATE% %TIME%"
  if errorlevel 1 (
    echo [ERRO] Nao foi possivel fazer stash. Atualizacao abortada.
    echo.
    pause
    exit /b 1
  )
  set "DID_STASH=1"
  echo Stash criado. Para recuperar depois: git stash pop
  echo.
) else (
  set "DID_STASH=0"
)

echo [1/4] Buscando atualizacoes no GitHub...
git fetch --prune origin
if errorlevel 1 (
  echo [ERRO] Falha no git fetch.
  echo Verifique internet e autenticacao ^(GitHub login / token^).
  echo.
  pause
  exit /b 1
)

rem Detecta upstream
set "UPSTREAM="
for /f "delims=" %%u in ('git rev-parse --abbrev-ref --symbolic-full-name @{u} 2^>nul') do set "UPSTREAM=%%u"
if not defined UPSTREAM (
  if not "%BRANCH%"=="(detached)" (
    echo Branch sem rastreamento remoto. Tentando origin/%BRANCH% ...
    git show-ref --verify --quiet "refs/remotes/origin/%BRANCH%"
    if not errorlevel 1 (
      git branch --set-upstream-to="origin/%BRANCH%" "%BRANCH%" >nul 2>&1
      set "UPSTREAM=origin/%BRANCH%"
    )
  )
)

if not defined UPSTREAM (
  echo [ERRO] Nao ha branch remota correspondente a "%BRANCH%".
  echo Publique o branch ou mude para um branch com remote ^(ex.: main^).
  echo.
  pause
  exit /b 1
)

for /f %%c in ('git rev-list --count HEAD..@{u} 2^>nul') do set "AHEAD=%%c"
if not defined AHEAD set "AHEAD=0"
for /f %%c in ('git rev-list --count @{u}..HEAD 2^>nul') do set "BEHIND_LOCAL=%%c"
if not defined BEHIND_LOCAL set "BEHIND_LOCAL=0"

echo  Remoto: %UPSTREAM%
echo  Commits novos no remoto: %AHEAD%
echo  Commits locais nao enviados: %BEHIND_LOCAL%
echo.

if "%AHEAD%"=="0" (
  echo Sistema ja esta atualizado com o remoto.
) else (
  echo [2/4] Baixando %AHEAD% commit^(s^) ^(fast-forward only^)...
  git pull --ff-only
  if errorlevel 1 (
    echo.
    echo [ERRO] Nao foi possivel atualizar com fast-forward.
    echo Pode haver divergencia local. Opcoes manuais:
    echo   git status
    echo   git pull --rebase
    echo.
    set "EXITCODE=1"
    goto after_pull
  )
  echo Atualizacao Git concluida.
)

:after_pull
echo.
echo Ultimos commits:
git log -5 --oneline --decorate
echo.

where docker >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Docker nao encontrado — pulei a reconstrucao dos containers.
  echo Depois de instalar o Docker Desktop, rode Abrir-SINIDU.bat.
  goto finish
)

docker info >nul 2>&1
if errorlevel 1 (
  echo [AVISO] Docker Desktop nao esta pronto — pulei a reconstrucao.
  echo Abra o Docker e rode Abrir-SINIDU.bat depois.
  goto finish
)

echo [3/4] Reconstruindo containers essenciais: %CORE%
echo ^(pode demorar alguns minutos na primeira vez^)
%COMPOSE% up -d --build %CORE%
if errorlevel 1 (
  echo [ERRO] Falha ao reconstruir containers.
  set "EXITCODE=1"
) else (
  echo Containers atualizados.
)

echo.
echo [4/4] Checagem rapida da API...
set "API_OK=0"
set /a _attempt=0
:wait_api
set /a _attempt+=1
curl.exe -fsS "http://localhost:8000/health/live" >nul 2>&1
if not errorlevel 1 (
  set "API_OK=1"
  goto api_done
)
if !_attempt! geq 30 goto api_done
timeout /t 2 /nobreak >nul
goto wait_api
:api_done
if "%API_OK%"=="1" (
  echo API respondendo em http://localhost:8000
) else (
  echo [AVISO] API ainda nao respondeu. Aguarde ou rode Avaliar-SINIDU.bat.
)

:finish
echo.
echo  ========================================
if "!EXITCODE!"=="0" (
  echo  RESULTADO: atualizacao concluida
) else (
  echo  RESULTADO: falhou — veja mensagens acima
)
echo  Branch: %BRANCH%
if "%DID_STASH%"=="1" echo  Stash local criado — recupere com: git stash pop
echo  Abrir sistema:  Abrir-SINIDU.bat
echo  Avaliar saude:  Avaliar-SINIDU.bat
echo  ========================================
echo.
pause
exit /b !EXITCODE!
