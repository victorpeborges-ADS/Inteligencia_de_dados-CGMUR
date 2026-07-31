#!/bin/zsh
# Atualizar SINIDU do Git (macOS)
# Duplo clique ou: ./scripts/Atualizar-SINIDU.command
#
# Se o macOS bloquear: botao direito → Abrir → Abrir.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.dev.yml)
CORE_SERVICES=(db redis backend frontend)
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

echo
echo "========================================"
echo " SINIDU+Clima — atualizar do Git"
echo "========================================"
echo
echo "Pasta: $PROJECT_DIR"
echo

cd "$PROJECT_DIR" || {
  echo "Nao encontrei a pasta do projeto."
  read "REPLY?Pressione Enter para sair..."
  exit 1
}

if ! command -v git >/dev/null 2>&1; then
  echo "Git nao encontrado. Instale o Xcode CLT ou o Git e tente novamente."
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

if [[ ! -d .git ]]; then
  echo "Esta pasta nao e um repositorio Git."
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

BRANCH="$(git branch --show-current 2>/dev/null || echo '(detached)')"
REMOTE="$(git remote get-url origin 2>/dev/null || echo '(sem origin)')"
echo "Branch atual: $BRANCH"
echo "Remote:       $REMOTE"
echo

DID_STASH=0
if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
  echo "AVISO: ha alteracoes locais nao commitadas:"
  git status -sb
  echo
  echo "Opcoes:"
  echo "  [1] Guardar temporariamente (git stash) e atualizar"
  echo "  [2] Cancelar"
  echo
  read "REPLY?Escolha 1 ou 2: "
  if [[ "$REPLY" != "1" ]]; then
    echo
    echo "Atualizacao cancelada."
    read "REPLY?Pressione Enter para sair..."
    exit 0
  fi
  echo
  echo "Guardando alteracoes locais (stash)..."
  if ! git stash push -u -m "SINIDU auto-stash antes de atualizar $(date '+%Y-%m-%d %H:%M')"; then
    echo "ERRO: nao foi possivel fazer stash."
    read "REPLY?Pressione Enter para sair..."
    exit 1
  fi
  DID_STASH=1
  echo "Stash criado. Para recuperar: git stash pop"
  echo
fi

echo "[1/4] Buscando atualizacoes no GitHub..."
if ! git fetch --prune origin; then
  echo "ERRO: falha no git fetch (internet / autenticacao GitHub)."
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

UPSTREAM="$(git rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null || true)"
if [[ -z "$UPSTREAM" && "$BRANCH" != "(detached)" ]]; then
  if git show-ref --verify --quiet "refs/remotes/origin/$BRANCH"; then
    git branch --set-upstream-to="origin/$BRANCH" "$BRANCH" >/dev/null 2>&1 || true
    UPSTREAM="origin/$BRANCH"
  fi
fi

if [[ -z "$UPSTREAM" ]]; then
  echo "ERRO: branch \"$BRANCH\" sem correspondente remoto."
  read "REPLY?Pressione Enter para sair..."
  exit 1
fi

AHEAD="$(git rev-list --count HEAD..@{u} 2>/dev/null || echo 0)"
LOCAL_AHEAD="$(git rev-list --count @{u}..HEAD 2>/dev/null || echo 0)"
echo "Remoto: $UPSTREAM"
echo "Commits novos no remoto: $AHEAD"
echo "Commits locais nao enviados: $LOCAL_AHEAD"
echo

EXITCODE=0
if [[ "$AHEAD" == "0" ]]; then
  echo "Sistema ja esta atualizado com o remoto."
else
  echo "[2/4] Baixando $AHEAD commit(s) (fast-forward only)..."
  if ! git pull --ff-only; then
    echo
    echo "ERRO: nao foi possivel atualizar com fast-forward."
    echo "Pode haver divergencia. Tente: git status && git pull --rebase"
    EXITCODE=1
  else
    echo "Atualizacao Git concluida."
  fi
fi

echo
echo "Ultimos commits:"
git log -5 --oneline --decorate
echo

if ! command -v docker >/dev/null 2>&1; then
  echo "AVISO: Docker nao encontrado — pulei a reconstrucao."
elif ! docker info >/dev/null 2>&1; then
  echo "AVISO: Docker Desktop nao esta pronto — pulei a reconstrucao."
  open -a Docker >/dev/null 2>&1 || true
else
  echo "[3/4] Reconstruindo containers essenciais: ${CORE_SERVICES[*]}"
  if ! "${COMPOSE[@]}" up -d --build "${CORE_SERVICES[@]}"; then
    echo "ERRO: falha ao reconstruir containers."
    EXITCODE=1
  else
    echo "Containers atualizados."
  fi

  echo
  echo "[4/4] Checagem rapida da API..."
  api_ok=0
  for attempt in {1..30}; do
    if curl -fsS "http://localhost:8000/health/live" >/dev/null 2>&1; then
      api_ok=1
      break
    fi
    sleep 2
  done
  if [[ "$api_ok" -eq 1 ]]; then
    echo "API respondendo em http://localhost:8000"
  else
    echo "AVISO: API ainda nao respondeu. Rode Avaliar-SINIDU depois."
  fi
fi

echo
echo "========================================"
if [[ "$EXITCODE" -eq 0 ]]; then
  echo " RESULTADO: atualizacao concluida"
else
  echo " RESULTADO: falhou — veja mensagens acima"
fi
echo " Branch: $BRANCH"
[[ "$DID_STASH" -eq 1 ]] && echo " Stash local criado — recupere com: git stash pop"
echo " Abrir:    scripts/Abrir-SINIDU.command"
echo "========================================"
echo
read "REPLY?Pressione Enter para fechar..."
exit "$EXITCODE"
