# Sinidu+Clima — Módulos operacionais (agente e mapa)

O Sinidu+Clima integra análise territorial climática, risco e operação municipal.

## Contingência e alertas
- O módulo Contingência registra planos com zonas de evacuação, rotas de fuga e pontos de apoio.
- Ações são organizadas por nível de alerta (VERDE, AMARELO, LARANJA, VERMELHO), alinháveis ao CEMADEN.
- O **alerta vivo** consolida CEMADEN e monitoramento das últimas 24h e pré-preenche o nível do plano.
- O agente contextual pode consultar alerta vivo, plano de contingência e alertas recentes.

## Calor urbano e LST
- A simulação de ilha de calor estima temperatura local por bairro (impermeabilização e vegetação).
- A LST observada (temperatura de superfície) vem do GeoReDUS/TiTiler e pode ser comparada à simulação.
- Divergência entre LST e modelo é esperada: LST é histórica de superfície; o modelo projeta onda de calor.

## Maturidade informacional
- O score de maturidade avalia fontes: IBGE, SICONFI, CAPAG, S2ID, MapBiomas, SNIS, bairros, plano diretor e clima.
- Classificações (Bronze/Prata/Ouro/Platina) orientam lacunas e prioridade de integração de dados.
- O catálogo de dados lista status Integrado / Estimado / Ausente por município.

## Simulação pluvial
- Cenários de chuva extrema estimam área inundável, bairros afetados e profundidade máxima.
- Resultados alimentam plano de ação e priorização de drenagem / defesa civil.

## ML de alagamento
- Modelos Random Forest por município estimam probabilidade de alagamento a partir da precipitação 24/48/72h.
- Dez capitais/piloto têm artefato dedicado; demais municípios usam baseline on-demand.
- O painel Sistema permite Bootstrap dos modelos; o agente pode consultar risco ML para um cenário de chuva.

Fonte: documentação operacional Sinidu+Clima (MCID MVP).
