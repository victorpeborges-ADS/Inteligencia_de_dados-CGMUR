# CHECKLIST STEP 4 — Diagnóstico com Narrativa IA + Modo Apresentação

## Tarefa 1 — Narrativa executiva (Mistral)

- [ ] Migration `015_diagnostic_narrativa_ia.sql` aplicada (`narrativa_ia`, `narrativa_ia_meta`)
- [ ] `POST /api/v1/diagnostic/generate/{codigo_ibge}` gera narrativa após índices
- [ ] Narrativa salva no banco (`diagnosticos_executivos.narrativa_ia`)
- [ ] Fallback determinístico quando Mistral indisponível
- [ ] Resposta API inclui `narrativa_ia` e `narrativa_ia_meta`
- [ ] 3 parágrafos: contexto · prioridades · próximos passos

## Tarefa 2 — Modo Apresentação

- [ ] Rota `/apresentacao/[municipio_codigo]` (8 slides, tela cheia, dark)
- [ ] Navegação ← → teclado e swipe
- [ ] Barra de progresso (8 pontos) + contador "N / 8"
- [ ] ESC / botão X sai da apresentação
- [ ] Botão **APRESENTAR** na Central da Oficina abre a apresentação
- [ ] `GET /api/v1/diagnostic/{codigo}/presentation` retorna payload completo

### Slides

1. Capa (logo, município, data, CGMUR/DDUM/SNDUM/MCID)
2. Resumo executivo + Score em destaque
3. Mapa vulnerabilidade + legenda
4. Top 5 bairros + §2 narrativa
5. Gráfico S2ID por ano
6. CAPAG + RCL + programas federais
7. Plano de ação (3 colunas) + §3 narrativa
8. Encerramento + QR PDF

## Tarefa 3 — Screenshot do mapa

- [ ] `GET /api/v1/map/screenshot/{cod_ibge}?layer=vulnerabilidade`
- [ ] Camadas: `vulnerabilidade`, `socioeconomico`, `inundacao`, `bairros`
- [ ] PNG 1200×700 (matplotlib fallback)
- [ ] Formato alternativo `?format=base64`

## Tarefa 4 — PDF

- [ ] Template `executive_diagnostic.html` — seção "Análise Narrativa" após Score
- [ ] Disclaimer IA + data + 3 parágrafos

## Testes

```bash
cd backend && python -m pytest tests/test_diagnostic_narrative.py -q
```

## Smoke test manual

1. Painel → **Diagnóstico** (gera v13+ com narrativa IA)
2. **Relatório** → PDF contém "Análise Narrativa"
3. **Apresentar** → 8 slides navegáveis para Recife (2611606)
4. Slide 3 exibe mapa colorido; slide 5 gráfico S2ID

## Critério de done

- Botão **APRESENTAR** abre apresentação com 8 slides navegáveis
- Narrativa IA aparece no PDF do diagnóstico
