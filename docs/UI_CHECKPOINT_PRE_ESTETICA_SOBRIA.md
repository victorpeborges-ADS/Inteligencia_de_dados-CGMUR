# Checkpoint de UI — antes da estética sóbria

**Objetivo:** poder voltar à aparência do sistema **exatamente como estava** antes da onda 20f.4 (estética sóbria e profissional).

| Campo | Valor |
|-------|--------|
| Tag | `ui-checkpoint-pre-estetica-sobria` |
| Branch | `checkpoint/ui-antes-estetica-sobria` |
| Commit | `3e793f2` (`Corrige launchers Windows: CRLF e localização do projeto`) |
| Escopo visual | árvore `frontend/` (globals, theme, design-system, components, app) |

## Restaurar

```bash
cd "/caminho/para/sinidu mvp"
git fetch origin tag ui-checkpoint-pre-estetica-sobria
git checkout ui-checkpoint-pre-estetica-sobria -- frontend/
# rebuild
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build frontend
```

## Verificar

```bash
git rev-parse ui-checkpoint-pre-estetica-sobria
# deve apontar para 3e793f2…
```

Não apagar a tag/branch até a nova estética estar aprovada.

## O que mudou na 20f.4 (após o checkpoint)

- Tipografia: **Source Sans 3** (substitui Inter)
- Accent de chrome: **teal** (menos indigo/glow)
- Header mais baixo e controles `rounded-md` (sem pills)
- Tabs ativas em teal; KPI/PanelSection sem sombra colorida
- Fluxos e navegação **inalterados**
