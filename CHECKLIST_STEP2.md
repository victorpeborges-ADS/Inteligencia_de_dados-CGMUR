# CHECKLIST — STEP 2: Agente IA Contextual Persistente

## Widget global
- [x] Botão flutuante 52px, cor teal `#1D9E75`, ícone Sparkles
- [x] Badge vermelho com mensagens não lidas (proativas)
- [x] Painel lateral 380px, slide da direita, `z-index` alto sem cobrir mapa por completo
- [x] Header: "Agente Sinidu · {município}"
- [x] Chat dark + textarea auto-resize + Enter para enviar
- [x] Estado `agenteAberto` e histórico no Zustand (sessão, sem localStorage)

## Contexto de página
- [x] Hook `useAgenteContexto.ts` com `PAGE_CONTEXTS` por rota
- [x] Detecção automática de rota (`/painel`, `/simulacoes`, `/monitor`, etc.)
- [x] Busca de dados reais da página antes do envio (`dados_pagina`)
- [x] Chips de perguntas sugeridas (3) que mudam com a aba

## Backend contextual
- [x] `POST /api/v1/assistant/chat-contextual`
- [x] System prompt dinâmico com município + página + dados JSON
- [x] Bundle de dados municipais via queries internas
- [x] SSE streaming (`text/event-stream`)
- [x] Function calling Mistral (7 ferramentas de leitura)

## Ferramentas do agente
- [x] `get_score_municipio`
- [x] `get_alertas_cemaden`
- [x] `get_catalogo_dados`
- [x] `get_historico_desastres`
- [x] `get_bairros_criticos`
- [x] `get_plano_acao`
- [x] `get_simulacao_resultado`

## Proatividade
- [x] Troca de município (≠ Recife) com confiabilidade ≠ ALTA → alerta
- [x] Monitor com >20 alertas CEMADEN → mensagem proativa
- [x] Geração de PDF de diagnóstico → resumo + oferta de resumo executivo

## Critério de done
- [ ] Abrir qualquer aba, fazer pergunta contextual → resposta com dados reais em **< 8s**
- [ ] Validar com `MISTRAL_API_KEY` configurada no backend
- [ ] Testar chips sugeridos em Painel, Monitor e Simulações
- [ ] Confirmar badge proativo ao trocar município com dados parciais

## Arquivos principais
| Caminho | Função |
|---------|--------|
| `frontend/src/components/AgenteSinidu/index.tsx` | Widget flutuante |
| `frontend/src/hooks/useAgenteContexto.ts` | Contexto + proatividade |
| `frontend/src/stores/useAppStore.ts` | Estado global do agente |
| `backend/app/services/contextual_agent_service.py` | Prompt + SSE + tool loop |
| `backend/app/services/contextual_agent_tools.py` | Ferramentas de leitura |
| `backend/app/api/assistant.py` | Endpoint `/chat-contextual` |

## Teste manual rápido
```bash
# Backend
curl -N -X POST http://localhost:8000/api/v1/assistant/chat-contextual \
  -H "Content-Type: application/json" \
  -d '{"message":"Quais bairros mais vulneráveis?","municipio_codigo":"2611606","pagina_atual":"Painel Principal","dados_pagina":{},"historico":[],"stream":true}'

# Frontend: abrir /painel → botão teal → chip "O que significa Score X?"
```
