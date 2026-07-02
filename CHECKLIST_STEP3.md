# CHECKLIST — STEP 3: IA na Interpretação de Simulações

## Backend
- [x] `POST /api/v1/simulations/interpret` — métricas + Mistral
- [x] Extração: área, população, bairros, equipamentos, delta vs referência, S2ID
- [x] System prompt estruturado (resumo, áreas críticas, equipamentos, histórico, recomendações, disclaimer)
- [x] Fallback determinístico sem API key
- [x] `GET /api/v1/simulations/slope-interpretation/{codigo_ibge}` — encostas + COBRADE
- [x] Interpretação diferencial quando comparação 120mm vs 80mm

## Frontend (SimulationPanel)
- [x] Card **Interpretação Sinidu·IA** com borda teal à esquerda
- [x] Loading shimmer: "Analisando resultado da simulação…"
- [x] Badge modelo (Mistral / Regras)
- [x] Seções: Resumo, Áreas críticas, Equipamentos, Histórico, Comparação, Recomendações
- [x] Bloco encostas quando `landslide_zones > 0`
- [x] Botões **Incluir no Relatório PDF** e **Copiar**
- [x] Chamada automática após simulação

## Critério de done
- [ ] Rodar simulação 120mm em Recife → card aparece em **< 10s**
- [ ] Comparação com referência 80mm → bloco "Comparação vs referência"
- [ ] PDF export inclui interpretação (`findings`)
- [ ] `MISTRAL_API_KEY` configurada para respostas enriquecidas

## Teste manual
```bash
curl -X POST http://localhost:8000/api/v1/simulations/interpret \
  -H "Content-Type: application/json" \
  -d '{
    "municipio_codigo":"2611606",
    "tipo_simulacao":"chuva",
    "parametro_atual":120,
    "parametro_referencia":80,
    "resultado_simulacao":{"affected_area_km2":8.4,"affected_population":47000,"affected_bairros":["Centro"],"geometry":{"type":"FeatureCollection","features":[]}}
  }'
```

## Arquivos
| Caminho | Função |
|---------|--------|
| `backend/app/services/simulation_interpreter.py` | Métricas + LLM |
| `backend/app/api/simulations.py` | Endpoints `/interpret` e `/slope-interpretation` |
| `frontend/src/components/Simulation/SimulationPanel.tsx` | Card IA pós-simulação |
