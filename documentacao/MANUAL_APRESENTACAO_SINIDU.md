# Manual do apresentador — Sinidu+Clima

**Para:** colega que vai apresentar o sistema em reunião  
**Tempo sugerido:** 20–30 min (pitch + demo) · versão curta 10–12 min  
**Piloto recomendado na tela:** **Recife** (`2611606`)  
**Documento irmão:** `RELATORIO_SISTEMA_SINIDU_COMPLETO.md` · checklist técnico: `CHECKLIST_DEMO_MCID.md`

---

## 1. Em 30 segundos (decorar)

> O **Sinidu+Clima** é a plataforma do MCID/CGMUR de inteligência territorial climática para municípios.  
> Ajuda o gestor a **ver o risco**, **simular chuva e calor**, **cruzar vulnerabilidade social e capacidade do município**, e **agir** com plano de contingência e relatórios — tudo com selos claros do que é dado oficial e do que é estimativa.  
> **Não substitui** o alerta do CEMADEN nem um laudo de engenharia hidrodinâmica: é **triagem e apoio à decisão**.

---

## 2. Antes da reunião (checklist pessoal)

### 2.1 No dia anterior

- [ ] Ler este manual + §1–3 do relatório completo  
- [ ] Decorar a frase de honestidade (§1 e §6)  
- [ ] Saber qual município vai abrir (padrão: Recife)  
- [ ] Pedir a alguém da equipe: stack no ar + smoke (`./scripts/demo-smoke.sh`)  
- [ ] Testar uma simulação de **120 mm** e deixar em **cache** (segunda execução fica rápida)  
- [ ] Abrir abas: Painel → Simulações → Monitor → Contingência (só para conhecer o caminho)

### 2.2 30 minutos antes

- [ ] `http://localhost:3000` (ou URL da demo) abre  
- [ ] Município Recife selecionado  
- [ ] Zoom do mapa ok; sem erro vermelho no console  
- [ ] Zoom de tela / compartilhar tela em **modo janela** (não fullscreen do SO se atrapalhar)  
- [ ] Fonte tipográfica legível; zoom do browser ~100–110%  
- [ ] Plano B: slides estáticos ou prints (ver §8)

### 2.3 Material na mão

| Item | Onde |
|------|------|
| URL do sistema | Combinar com a equipe |
| Este manual | `documentacao/MANUAL_APRESENTACAO_SINIDU.md` |
| Apresentação HTML (se usar) | `docs/apresentacao-sinidu-keynote-light.html` |
| Linguagem permitida | `docs/CHECKLIST_LINGUAGEM_HONESTIDADE.md` |

---

## 3. Sugestão de estrutura da apresentação

### Opção A — 25 minutos (recomendada)

| Min | Bloco | O que fazer |
|----:|-------|-------------|
| 0–2 | Abertura | Problema do gestor + frase dos 30 s |
| 2–5 | Posicionamento | O que é / o que não é · para quem é |
| 5–18 | **Demo ao vivo** | Roteiro §4 |
| 18–22 | Valor e diferenciais | Ciclo ver→agir→auditar · selos · open-data |
| 22–25 | Próximos passos + Q&A | Horizonte curto · perguntas |

### Opção B — 12 minutos (reunião apertada)

| Min | Bloco |
|----:|-------|
| 0–2 | Pitch + o que não é |
| 2–9 | Demo: Painel → simulação 120 mm → 3D → vias/ativos (se visível) |
| 9–12 | Uma frase de próximos passos + Q&A |

### Opção C — Só slides (se o sistema cair)

Usar `docs/apresentacao-sinidu-keynote-light.html` ou prints do §8 + narrativa do §5.

---

## 4. Roteiro de demo ao vivo (falar + clicar)

> Dica: fale **antes** de clicar. Evite silêncio enquanto o mapa carrega — narre o que vai aparecer.

### Passo 1 — Painel executivo (~2 min)

**Clicar:** aba **Painel** · município Recife  

**Falar:**
> Aqui o gestor vê o diagnóstico do município: indicadores de vulnerabilidade climática, risco de inundação e um score que consolida isso.  
> Há narrativa e recomendações — não é só mapa colorido: é leitura para priorizar onde agir.

**Mostrar (se aparecer na tela):** KPIs, semáforo / risco consolidado, badges de qualidade do dado.

---

### Passo 2 — Mapa e camadas (~2 min)

**Clicar:** painel de camadas · ligar 1–2 camadas (ex.: vulnerabilidade + uso do solo ou HAND)

**Falar:**
> Cada camada traz **fonte** e **selo**: Oficial, Referência, Derivado ou Estimado.  
> Isso é deliberado — o município precisa saber o que é dado de entrada oficial e o que é produto do Sinidu.

**Não dizer:** “isso é a verdade oficial do risco”.

---

### Passo 3 — Simulação de chuva (~5 min) — **momento forte**

**Clicar:** aba **Simulações** → cenário **Chuva extrema** → algo como **120 mm** → Rodar  

**Enquanto carrega:**
> Estamos pedindo um exercício: “e se chover X milímetros?”.  
> O motor usa o terreno (DEM), impermeabilidade, e hoje também informações de solo e hidrografia aberta.  
> É **triagem territorial** — serve para priorizar e treinar contingência, não para substituir um estudo HEC-RAS.

**Quando terminar:**
> O mapa vai para o **3D**: a mancha de inundação estimada sobre o terreno.  
> Podemos ver profundidade e cruzar com vias e equipamentos sensíveis — escolas, saúde — para a sala de crise.

**Clicar (se disponível):** resultados · export CSV/KMZ ou lista de impactos · overlays de vias/ativos · camadas HAND / GloFAS (referência)

**Falar sobre GloFAS/HAND (se ligar):**
> HAND mostra suscetibilidade topográfica; GloFAS é um hazard global de referência.  
> Usamos para **confrontar**, não para copiar como se fosse o nosso laudo.

---

### Passo 4 — Monitor ou Contingência (~2 min)

**Clicar:** **Monitor** (alertas) **ou** **Contingência** (plano COBRADE)

**Falar:**
> Do diagnóstico e da simulação passamos para a operação: alertas (integração com fontes como CEMADEN) e planos de contingência alinhados ao COBRADE, com zonas e rotas de apoio.  
> O Sinidu não emite alerta oficial no lugar do CEMADEN — ele **organiza a resposta municipal**.

---

### Passo 5 — Fecho da demo (~1 min)

**Falar:**
> Em uma sessão o gestor: entendeu o território, testou um cenário de chuva, viu impacto em vias e ativos, e tem caminho para contingência e relatório.  
> Esse é o ciclo que o produto fecha.

---

## 5. Roteiro falado (slides / sem demo)

Use como fala contínua se preferir slides.

1. **Problema** — Municípios enfrentam extremos com pouca capacidade de cruzar clima, vulnerabilidade social e ação no mesmo lugar.  
2. **Solução** — Sinidu+Clima: plataforma nacional de inteligência territorial climática (MCID/CGMUR).  
3. **Para quem** — Defesa Civil, planejamento urbano, gabinete.  
4. **O que entrega** — Diagnóstico (IVC, IRI, Score), mapa 2D/3D, simulações, monitoramento, contingência, assistente, relatórios/SEI.  
5. **Honestidade** — Dados oficiais de entrada + estimativas com selo. Não é laudo nem alerta CEMADEN.  
6. **Diferencial** — Fecha o ciclo ver → simular → priorizar → agir → auditar no contexto institucional brasileiro.  
7. **Estado** — Piloto operacional (ex. Recife / PE); evolução contínua de dados e gémeo digital.  
8. **Pedido / próximo passo** — (combinar com a equipe: homologação, município convidado, oficina, etc.)

---

## 6. Frases prontas (copie e cole mentalmente)

### Pode dizer

- “Plataforma de **triagem e apoio à decisão** municipal.”  
- “Usa **dados oficiais de entrada** (IBGE, S2ID, MapBiomas, CEMADEN…) e deixa claro o que é **derivado**.”  
- “A simulação de chuva é um **exercício de priorização**, não um projeto de engenharia.”  
- “O gémeo digital é **incremental**: terreno + edificações LOD1 nos pilotos.”  
- “Ajuda a sala de crise a ver **vias e equipamentos** potencialmente afetados.”

### Evite dizer

| Evitar | Substituir por |
|--------|----------------|
| “É oficial / homologado pela engenharia” | “É triagem com selo explícito” |
| “Substitui o CEMADEN” | “Organiza a resposta; o alerta oficial continua com o CEMADEN” |
| “É igual ao HEC-RAS / 3Di” | “Não compete com hidrodinâmica 2D; outro nicho” |
| “A IA decide sozinha” | “A IA apoia interpretação; a decisão é do gestor” |
| “Probabilidade calibrada em todo o Brasil” | “ML só como probabilidade quando o modelo tem lastro (`full`)” |

**Frase ouro (se cobrarem precisão):**
> O Sinidu+Clima usa dados oficiais de entrada e produz estimativas territoriais com selo explícito. Não é laudo de engenharia nem alerta CEMADEN.

---

## 7. Perguntas frequentes (Q&A)

**“Isso é alerta oficial?”**  
Não. Alertas oficiais seguem CEMADEN / órgãos competentes. O Sinidu apoia a leitura municipal e a contingência.

**“Posso usar isso como laudo para obra?”**  
Não. Para projeto de engenharia use estudos hidrodinâmicos (HEC-RAS, SWMM, etc.). O Sinidu prioriza e treina decisão.

**“Funciona em qualquer município?”**  
Onboarding sob demanda com dados abertos. A **qualidade** varia: onde há LiDAR, CTM, INEP e séries densas, o produto fica mais forte.

**“De onde vêm os dados?”**  
IBGE, MapBiomas, S2ID, CEMADEN, SNIS, INEP/CNES, DEM (SRTM/LiDAR), OSM, e referências como GloFAS/SoilGrids — cada camada com fonte na interface.

**“E a inteligência artificial?”**  
Há assistente normativo (base legal) e agente operacional (contexto da tela). Não substitui o técnico; acelera a leitura.

**“Qual o diferencial?”**  
Não é só mapa nem só modelo: é o **ciclo completo** diagnóstico → simulação → impacto operacional → contingência → auditoria/relatório, no vocabulário do Estado brasileiro.

**“O que vem a seguir?”**  
Polimento de produto (exports e UX), mais dados oficiais (IDF, INEP, ANA), e gémeo mais rico (alturas reais, exposição por edifício) — sem prometer hidrodinâmica 2D no curto prazo.

---

## 8. Plano B — se a demo falhar

1. **Não improvisar debug na reunião.**  
2. Dizer: “Vou mostrar o fluxo com material preparado e retomamos o ao vivo em seguida.”  
3. Abrir:
   - HTML light: `docs/apresentacao-sinidu-keynote-light.html`, **ou**
   - Prints em pasta combinada com a equipe, **ou**
   - Relatório/PDF municipal já gerado.  
4. Manter a narrativa do §5.  
5. Oferecer gravação ou segunda sessão técnica.

---

## 9. Perfis na plateia — ênfase

| Se na sala houver… | Enfatize… | Clique extra |
|--------------------|-----------|--------------|
| Defesa Civil | Alerta, mancha, vias, ativos, contingência | Simulação → Contingência |
| Planejamento / urbanismo | Camadas, prioridade, cobertura, socioeconômico | Painel + Catálogo |
| Gabinete / secretário | Narrativa, KPIs, PDF, “o que fazer” | Painel + apresentação `/apresentacao/...` |
| TI / dados | Fontes, selos, API, auth | Catálogo + (se pedirem) Sistema |

---

## 10. Slides mínimos sugeridos (se montar deck próprio)

1. Título — Sinidu+Clima · MCID/CGMUR  
2. Problema do gestor municipal  
3. O que é (e o que não é) — tabela 2 colunas  
4. Ciclo: ver → simular → agir → auditar  
5. Módulos (ícones: Painel, Mapa, Simulação, Monitor, Contingência)  
6. Print: painel Recife  
7. Print: simulação 3D 120 mm  
8. Print: vias / ativos ou contingência  
9. Selos de qualidade do dado  
10. Estado atual + próximos passos  
11. Contato / como pedir oficina  

*(Opcional: usar os HTML já gerados em `docs/apresentacao-sinidu-*.html`.)*

---

## 11. Glossário rápido para a apresentadora

| Sigla | Em uma linha |
|-------|----------------|
| **IVC** | Índice de Vulnerabilidade Climática (quão sensível é o território) |
| **IRI** | Índice de Risco de Inundação |
| **Score** | Consolidação Sinidu para priorizar |
| **S2ID** | Histórico oficial de desastres (SEDEC) |
| **CEMADEN** | Alertas e monitoramento — referência oficial de alerta |
| **DEM / LiDAR** | Modelo digital de terreno (relevo) |
| **HAND** | Altura acima da drenagem — suscetibilidade topográfica |
| **GloFAS** | Hazard global de inundação (referência JRC) |
| **COBRADE** | Classificação brasileira de desastres (planos) |
| **LOD1** | Edifício como bloco extrudado (gémeo simples) |
| **Triagem** | Priorizar e orientar — não dimensionar obra |

---

## 12. Abertura e encerramento modelo

### Abertura

> Bom dia. Vou apresentar o **Sinidu+Clima**, plataforma de inteligência territorial climática do MCID/CGMUR.  
> Em poucos minutos mostro o que o gestor vê hoje no piloto — e deixo claro o limite metodológico: apoio à decisão, não laudo de engenharia.

### Encerramento

> Recapitulando: diagnóstico com dados oficiais de entrada, simulação de cenários com selo explícito, leitura operacional de impactos e caminho para contingência e relatório.  
> Estamos à disposição para oficina hands-on no município ou aprofundamento técnico. Obrigada.

---

## 13. Contatos da equipe (preencher antes da reunião)

| Papel | Nome | Como acionar |
|-------|------|--------------|
| Apresentação | | |
| Suporte técnico na sala (stack/demo) | | |
| Respostas de metodologia / hidro | | |
| Respostas institucionais MCID | | |

---

*Atualizar este manual quando o roteiro de demo ou o piloto padrão mudar.*
