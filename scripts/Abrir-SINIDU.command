#!/bin/zsh
# Copie para a Area de Trabalho: cp scripts/Abrir-SINIDU.command ~/Desktop/"Abrir SINIDU.command" && chmod +x ~/Desktop/"Abrir SINIDU.command"

set -u

PROJECT_DIR="/Users/vic/MCID/sinidu mvp"
API_URL="http://localhost:8000"
APP_URL="http://localhost:3000"
CORE_SERVICES=(db redis backend frontend)

echo "Iniciando o SINIDU..."
echo

if ! open -a Docker >/dev/null 2>&1; then
  echo "Nao foi possivel abrir o Docker Desktop."
  echo "Verifique se o Docker esta instalado."
  echo
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

echo "Aguardando o Docker ficar pronto (ate 3 min)..."
for attempt in {1..90}; do
  if docker info >/dev/null 2>&1; then
    break
  fi

  if [ "$attempt" -eq 1 ] || [ $((attempt % 15)) -eq 0 ]; then
    echo "Reiniciando Docker Desktop (motor parado)..."
    osascript -e 'quit app "Docker"' >/dev/null 2>&1 || true
    sleep 3
    open -a Docker
  fi

  if [ "$attempt" -eq 90 ]; then
    echo
    echo "O Docker nao ficou pronto a tempo."
    echo "Abra o Docker Desktop manualmente, aguarde o icone estabilizar e tente novamente."
    echo
    read "REPLY?Pressione Enter para sair..."
    exit 1
  fi

  sleep 2
done

echo "Docker pronto."
echo

cd "$PROJECT_DIR" || {
  echo "Nao encontrei a pasta do projeto: $PROJECT_DIR"
  read "REPLY?Pressione Enter para sair..."
  exit 1
}

echo "Subindo servicos essenciais: ${CORE_SERVICES[*]}"
if ! docker compose up -d --no-build "${CORE_SERVICES[@]}" 2>&1; then
  echo
  echo "Imagens ausentes — tentando build (pode levar alguns minutos)..."
  if ! docker compose up -d --build "${CORE_SERVICES[@]}" 2>&1; then
    echo
    echo "Falha ao subir os containers."
    echo "Abra o Docker Desktop, confirme que ha espaco em disco e tente novamente."
    echo
    read "REPLY?Pressione Enter para sair..."
    exit 1
  fi
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
  echo "Verifique: docker compose -f \"$PROJECT_DIR/docker-compose.yml\" logs backend --tail 40"
fi

echo
echo "Aguardando a interface em $APP_URL (ate 3 min)..."
frontend_ok=0
for attempt in {1..90}; do
  if curl -fsS "$APP_URL" >/dev/null 2>&1; then
    echo "Frontend pronto."
    frontend_ok=1
    break
  fi
  sleep 2
done

if [ "$backend_ok" -eq 1 ] && [ "$frontend_ok" -eq 1 ]; then
  echo "SINIDU pronto. Abrindo navegador..."
  open "$APP_URL"
  exit 0
fi

echo
echo "Alguns servicos ainda nao responderam."
echo "Backend: $([ "$backend_ok" -eq 1 ] && echo OK || echo pendente)"
echo "Frontend: $([ "$frontend_ok" -eq 1 ] && echo OK || echo pendente)"
echo "Abrindo mesmo assim: $APP_URL"
open "$APP_URL"
