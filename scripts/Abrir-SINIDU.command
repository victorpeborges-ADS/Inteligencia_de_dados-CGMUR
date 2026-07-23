#!/bin/zsh
# Copie para a Area de Trabalho:
#   cp scripts/Abrir-SINIDU.command ~/Desktop/"Abrir SINIDU.command" && chmod +x ~/Desktop/"Abrir SINIDU.command"
#
# Se o macOS bloquear o duplo-clique: clique com o botao direito → Abrir → Abrir.

set -u

PROJECT_DIR="/Users/vic/MCID/sinidu mvp"
API_URL="http://localhost:8000"
APP_URL="http://localhost:3000"
CORE_SERVICES=(db redis backend frontend)
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)

echo "Iniciando o SINIDU..."
echo

# PATH do Docker Desktop (Terminal.app às vezes nao herda)
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI nao encontrado no PATH."
  echo "Instale o Docker Desktop e tente novamente."
  echo
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

if ! open -a Docker >/dev/null 2>&1; then
  echo "Nao foi possivel abrir o Docker Desktop."
  echo "Verifique se o Docker esta instalado em /Applications/Docker.app"
  echo
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

# IMPORTANTE: nao reiniciar o Docker a cada ~30s — no Mac Intel o Engine
# costuma demorar 1–3 min; quit/open no meio impede o motor de subir.
echo "Aguardando o Docker ficar pronto (ate 5 min)..."
echo "Deixe o Docker Desktop aberto; nao feche a janela 'Starting the Docker Engine'."
restarted_once=0
for attempt in {1..150}; do
  if docker info >/dev/null 2>&1; then
    break
  fi

  # Um unico restart suave so apos ~2 min sem resposta (motor realmente travado)
  if [ "$attempt" -eq 60 ] && [ "$restarted_once" -eq 0 ]; then
    echo "Motor ainda parado apos 2 min — reiniciando Docker Desktop uma vez..."
    osascript -e 'quit app "Docker"' >/dev/null 2>&1 || true
    sleep 5
    open -a Docker
    restarted_once=1
  fi

  if [ $((attempt % 15)) -eq 0 ]; then
    st=$(docker desktop status 2>/dev/null | awk '/Status/{print $2}')
    echo "  ... aguardando ($((attempt * 2))s) status=${st:-iniciando}"
  fi

  if [ "$attempt" -eq 150 ]; then
    echo
    echo "O Docker nao ficou pronto a tempo."
    echo "Faca: Docker Desktop → Quit Docker Desktop, abra de novo, aguarde o icone verde,"
    echo "depois rode este script outra vez (sem fechar o Docker no meio)."
    echo
    read "REPLY?Pressione Enter para sair..."
    exit 1
  fi

  sleep 2
done

echo "Docker pronto."
echo"

cd "$PROJECT_DIR" || {
  echo "Nao encontrei a pasta do projeto: $PROJECT_DIR"
  read "REPLY?Pressione Enter para sair..."
  exit 1
}

# Container legado de produção costuma ficar com Cmd=node server.js (quebra o dev)
frontend_cmd="$(docker inspect sinidu_frontend --format '{{json .Config.Cmd}}' 2>/dev/null || true)"
if print "$frontend_cmd" | grep -q 'server.js'; then
  echo "Detectado frontend em modo producao antigo — recriando em modo desenvolvimento..."
  "${COMPOSE[@]}" rm -sf frontend >/dev/null 2>&1 || true
fi

echo "Subindo servicos essenciais: ${CORE_SERVICES[*]}"
if ! "${COMPOSE[@]}" up -d --build "${CORE_SERVICES[@]}" 2>&1; then
  echo
  echo "Falha ao subir os containers."
  echo "Abra o Docker Desktop, confirme que ha espaco em disco e tente novamente."
  echo
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

echo
echo "Aguardando a API (backend) em $API_URL (ate 5 min)..."
backend_ok=0
for attempt in {1..150}; do
  if curl -fsS "$API_URL/health/ready" >/dev/null 2>&1; then
    echo "Backend pronto (API + banco de dados)."
    backend_ok=1
    break
  fi
  if curl -fsS "$API_URL/health/live" >/dev/null 2>&1; then
    echo -n "."
  elif [ $((attempt % 10)) -eq 0 ]; then
    echo "  ... ainda iniciando ($((attempt * 2))s)"
  fi
  sleep 2
done

if [ "$backend_ok" -eq 0 ]; then
  echo
  echo "AVISO: backend ainda nao respondeu em $API_URL/health/ready"
  echo "Verifique: docker compose -f docker-compose.yml logs backend --tail 40"
fi

echo
echo "Aguardando a interface em $APP_URL (ate 5 min)..."
frontend_ok=0
for attempt in {1..150}; do
  if curl -fsS "$APP_URL" >/dev/null 2>&1; then
    echo "Frontend pronto."
    frontend_ok=1
    break
  fi
  # Se o container caiu com server.js, tenta recuperar uma vez
  if [ "$attempt" -eq 15 ]; then
    status="$(docker inspect -f '{{.State.Status}}' sinidu_frontend 2>/dev/null || echo missing)"
    if [ "$status" != "running" ]; then
      echo "Frontend parado — recriando..."
      "${COMPOSE[@]}" up -d --force-recreate --build frontend 2>&1 || true
    fi
  fi
  if [ $((attempt % 10)) -eq 0 ]; then
    echo "  ... ainda iniciando frontend ($((attempt * 2))s)"
  fi
  sleep 2
done

if [ "$backend_ok" -eq 1 ] && [ "$frontend_ok" -eq 1 ]; then
  echo "SINIDU pronto. Abrindo navegador..."
  open "$APP_URL"
  echo
  read "REPLY?Pressione Enter para fechar esta janela..."
  exit 0
fi

echo
echo "Alguns servicos ainda nao responderam."
echo "Backend: $([ "$backend_ok" -eq 1 ] && echo OK || echo pendente)"
echo "Frontend: $([ "$frontend_ok" -eq 1 ] && echo OK || echo pendente)"
echo
echo "Logs recentes do frontend:"
docker logs sinidu_frontend --tail 25 2>&1 || true
echo
echo "Abrindo mesmo assim: $APP_URL"
open "$APP_URL"
echo
read "REPLY?Pressione Enter para fechar esta janela..."
