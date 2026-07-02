# CHECKLIST — Step 1: Auditoria e Correção de Dados (60 municípios)

## Pré-requisitos

- [ ] Backend rodando (`docker compose up -d backend db redis`)
- [ ] Migration `014_municipio_data_honesty.sql` aplicada (boot automático)
- [ ] `MISTRAL_API_KEY` no `.env` (assistente; não afeta recarga IBGE)
- [ ] Volume `ibge_mesh_cache` montado (`/data/ibge`)

## Tarefa 1 — Auditoria

- [ ] Executar: `python3 scripts/auditoria_municipios.py --persist`
- [ ] Verificar CSV gerado: `auditoria_municipios_YYYY-MM-DD.csv`
- [ ] Colunas presentes: `flag_malha`, `flag_socio`, `flag_seg`, `flag_score`, `confiabilidade_geral`
- [ ] Recife (2611606) excluído por padrão (piloto com malha CTM)

### Critérios de flags

| Flag malha | Condição |
|------------|----------|
| MALHA_OK | IBGE oficial ou ≥85 bairros Recife |
| MALHA_ESTIMADA | Voronoi / nomes genéricos |
| MALHA_AUSENTE | 0 polígonos |

| Flag socio | Condição |
|------------|----------|
| SOCIOEC_REAL | SIDRA/CTM/IBGE censitário |
| SOCIOEC_ESTIMADO | Interpolação Sinidu+Clima |
| SOCIOEC_AUSENTE | Sem setores |

## Tarefa 2 — Recarga IBGE (por município)

```bash
curl -X POST "http://localhost:8000/api/v1/municipios/3550308/recarregar-dados-reais" \
  -H "Content-Type: application/json" \
  -d '{"fontes": ["malha_ibge", "socioeconomico_censo", "s2id", "cemaden"]}'

curl "http://localhost:8000/api/v1/municipios/3550308/status-recarga"
```

- [ ] Etapa `malha_ibge` concluída (bairros + setores IBGE)
- [ ] Etapa `socioeconomico_censo` concluída (`fonte_renda = ibge_censo2022_sidra`)
- [ ] Etapa `s2id` concluída
- [ ] Etapa `cemaden` concluída
- [ ] `score_confiabilidade` atualizado em `municipios_seed`

## Tarefa 3 — Batch noturno

```bash
chmod +x scripts/recarregar_todos_municipios.sh
./scripts/recarregar_todos_municipios.sh
```

- [ ] 60 municípios processados sequencialmente (60s entre cada)
- [ ] Polling Redis até `status = concluido`
- [ ] Re-auditoria pós-batch: `python3 scripts/auditoria_municipios.py --persist`

## Tarefa 4 — UI (badges de honestidade)

- [ ] Camada bairros: badge **OFICIAL — IBGE Censo 2022** (verde) quando `malha_fonte = ibge_censo2022`
- [ ] Camada bairros: badge **ESTIMADO** (amarelo) + tooltip quando Voronoi
- [ ] Município sem malha: mensagem no painel de camadas + camadas dependentes desativadas
- [ ] Score com indicador: ⬤ Alta / ⚠ Parcial / ⚠ Estimado

## Critério de DONE

- [ ] `auditoria_municipios.csv` com **ALTA ou MEDIA** em ≥ **40 dos 61** municípios
- [ ] Nenhum município com `MALHA_AUSENTE` após recarga batch
- [ ] Camadas socio/vulnerabilidade bloqueadas apenas quando malha realmente ausente

## Comandos úteis

```bash
# Auditoria rápida de um município
curl "http://localhost:8000/api/v1/municipios/3550308/auditoria"

# Meta de camadas (malha_disponivel, camadas_bloqueadas)
curl "http://localhost:8000/api/v1/indicators/layers/meta?codigo_ibge=3550308"

# Job batch malha IBGE (alternativa admin)
curl -X POST "http://localhost:8000/api/v1/system/jobs/bairros-batch?limit=61&force=true"
```

## Arquivos entregues

| Arquivo | Função |
|---------|--------|
| `scripts/auditoria_municipios.py` | Auditoria CSV |
| `backend/app/services/municipio_audit_service.py` | Lógica de flags |
| `backend/app/services/malha_ibge_service.py` | Recarga malha + SIDRA |
| `backend/app/services/municipio_recarga_service.py` | Pipeline sequencial |
| `backend/app/api/municipios.py` | Endpoints recarga/auditoria |
| `scripts/recarregar_todos_municipios.sh` | Batch 60 municípios |
| `scripts/municipios_prioritarios.txt` | Lista IBGE (sem Recife) |
