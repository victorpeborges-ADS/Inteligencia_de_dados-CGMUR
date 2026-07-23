#!/usr/bin/env python3
"""Gera relatório DOCX de funcionalidades do Sinidu+Clima em docs/."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "RELATORIO_FUNCIONALIDADES_SINIDU_CLIMA.docx"


def _style_doc(doc: Document) -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    for level in range(1, 4):
        h = doc.styles[f"Heading {level}"]
        h.font.name = "Calibri"
        h.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)


def _add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def _add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, text in enumerate(headers):
        hdr[i].text = text
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.bold = True
    for ri, row in enumerate(rows):
        cells = table.rows[ri + 1].cells
        for ci, text in enumerate(row):
            cells[ci].text = text
    doc.add_paragraph()


def build() -> Document:
    doc = Document()
    _style_doc(doc)

    # Capa
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("Sinidu+Clima\n")
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = RGBColor(0x1E, 0x3A, 0x5F)
    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r2 = sub.add_run("Relatório de Funcionalidades e Roadmap de Evolução")
    r2.font.size = Pt(14)
    r2.italic = True
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    meta.add_run(f"\nVersão: julho/2026 · Gerado em {date.today().strftime('%d/%m/%Y')}\n")
    meta.add_run("Plataforma de inteligência territorial — MCID/CGMUR\n")
    doc.add_page_break()

    # 1. Sumário executivo
    doc.add_heading("1. Sumário executivo", level=1)
    doc.add_paragraph(
        "O Sinidu+Clima é uma plataforma web de inteligência territorial voltada ao diagnóstico climático, "
        "simulação de cenários, contingência e apoio à decisão municipal. O sistema integra fontes públicas "
        "(IBGE, SICONFI, CAPAG, MapBiomas, S2ID, CEMADEN, entre outras), calcula índices de vulnerabilidade "
        "e risco, e entrega mapas, relatórios PDF e assistente com inteligência artificial."
    )
    doc.add_paragraph(
        "O MVP cobre 61 municípios prioritários com onboarding sob demanda, piloto operacional em Recife (PE) "
        "e infraestrutura preparada para homologação institucional (autenticação, auditoria, multi-tenant, OIDC)."
    )

    # 2. Visão geral
    doc.add_heading("2. Visão geral e arquitetura", level=1)
    doc.add_heading("2.1 Stack tecnológica", level=2)
    _add_table(
        doc,
        ["Camada", "Tecnologia"],
        [
            ["Frontend", "Next.js 13, Tailwind, Leaflet (2D), MapLibre GL (3D), Recharts"],
            ["Backend", "FastAPI, SQLAlchemy, motores analíticos Python"],
            ["Banco de dados", "PostgreSQL + PostGIS + pgvector (RAG)"],
            ["Infraestrutura", "Docker Compose, Redis, Ollama (IA local), OSRM (opcional)"],
            ["CI/CD", "GitHub Actions — testes backend e build frontend"],
        ],
    )

    doc.add_heading("2.2 Módulos de interface (rotas)", level=2)
    _add_table(
        doc,
        ["Rota", "Módulo", "Finalidade"],
        [
            ["/painel", "Painel executivo", "KPIs, narrativa, recomendações, saúde fiscal, maturidade"],
            ["/municipios", "Municípios", "Onboarding territorial, validação e carga de malhas"],
            ["/simulacoes", "Simulações", "Chuva extrema, ilhas de calor, impermeabilização, vegetação"],
            ["/catalogo", "Catálogo de dados", "Maturidade informacional, lacunas, trâmite institucional"],
            ["/contingencia", "Contingência", "Planos COBRADE, rotas de evacuação, wizard operacional"],
            ["/monitor", "Monitoramento", "Alertas CEMADEN, clima urbano, timeline histórica"],
            ["/assistente", "Assistente IA", "Chat contextual municipal com RAG (Ollama/Gemini)"],
            ["/casos", "Casos de sucesso", "Busca semântica de experiências de outras cidades"],
            ["/auditoria", "Auditoria", "Trilha de ações (PDF, diagnóstico, comparação, onboarding)"],
            ["/sistema", "Sistema (admin)", "Saúde, jobs em background, sync ETL, pipeline 61 municípios"],
            ["/apresentacao/{ibge}", "Apresentação", "8 slides executivos para oficinas e reuniões"],
            ["/design-system", "Design system", "Tokens e componentes da interface institucional"],
        ],
    )

    # 3. Funcionalidades implementadas
    doc.add_heading("3. Funcionalidades implementadas", level=1)

    sections = [
        (
            "3.1 Integração e onboarding territorial",
            [
                "61 municípios prioritários cadastrados com metadados IBGE (nome, UF, prioridade).",
                "Onboarding automático: malha municipal, bairros/setores censitários, integrações IBGE/SICONFI/CAPAG/SNIS.",
                "Onboarding em lote (até 61) via painel Sistema ou API.",
                "Pipeline territorial: ETL → onboarding → MapBiomas → DEM → diagnósticos executivos.",
                "Jobs em background com polling na interface e notificação Gotify (opcional).",
                "Coletores: IBGE (população, área, PIB, série histórica, IDH), SICONFI, CAPAG, SNIS/SINISA, S2ID, MapBiomas, CEMADEN, fontes externas (AdaptaBrasil, GeoSGB, SIRENE, Brasil MAIS — proxy/derivado).",
                "SINGED Lab RS 2024: exposição oficial em áreas afetadas (6 municípios RS + 55 N/A).",
                "Malha viária OSRM multi-região com fallback geodésico quando malha indisponível.",
            ],
        ),
        (
            "3.2 Análise, índices e maturidade",
            [
                "IVC — Índice de Vulnerabilidade Climática por bairro/setor.",
                "IRI — Índice de Risco de Inundação territorial.",
                "Score Sinidu+Clima e classificação de prioridade (Crítica / Alta / Média).",
                "Score de maturidade informacional (0–100) com tiers Platina, Ouro, Prata, Bronze.",
                "Catálogo dinâmico de dados com status por fonte: Integrado, Estimado, Em integração, Ausente, N/A.",
                "Panorama nacional do catálogo para gestores (61 municípios).",
                "Ranking de lacunas prioritárias e painel de trâmite institucional (convênios MCID).",
                "Análise de impacto por fonte com explicação assistida por IA.",
                "Contexto socioeconômico: PIB total e série histórica, PIB per capita, IDH municipal, Atlas Econômico IPEA/RFB (UF).",
                "Vulnerabilidade multidimensional (VM) e camadas de saúde (CNES) e segurança (SINESP).",
            ],
        ),
        (
            "3.3 Mapa e visualização",
            [
                "Mapa 2D (Leaflet) com 15+ camadas temáticas agrupadas (base, clima, planejamento, saúde).",
                "Mapa 3D (MapLibre) com terreno, extrusão de manchas de alagamento e ilhas de calor.",
                "Modo Focus (tecla F): mapa expandido para apresentações.",
                "Inspeção por clique: profundidade da água (cm), cota do solo e cota da água (DEM SRTM 30 m ou LiDAR local).",
                "Legenda 3D com faixas de profundidade e overlays de simulação.",
                "Upload de DEM LiDAR local (piloto Recife) e processamento em lote.",
            ],
        ),
        (
            "3.4 Simulações e cenários",
            [
                "Chuva extrema (mm): mancha de alagamento modelada com cache Redis (24 h).",
                "Comparação de cenários (ex.: 80 mm vs 120 mm) com execução paralela.",
                "Jobs assíncronos com barra de progresso real na interface.",
                "Simulação de impermeabilização e perda de vegetação.",
                "Déficit de drenagem e plano de mitigação automático.",
                "Interpretação de resultados por IA (cache 6 h).",
                "Exportação GeoJSON e PDF de simulação.",
                "Próximos passos guiados pós-simulação (fluxo oficina).",
            ],
        ),
        (
            "3.5 Diagnóstico, relatórios e planos",
            [
                "Diagnóstico executivo municipal com narrativa IA e histórico versionado.",
                "Plano de ação municipal gerado a partir do diagnóstico.",
                "Relatório municipal PDF (rápido) e relatório completo (8+ páginas com gráficos).",
                "Exportação em lote: diagnósticos e PDFs para os 61 municípios.",
                "Export SEI: PDF + metadados + hash SHA-256 para trâmite institucional.",
                "Bloqueio de PDF formal se maturidade < Prata (com override admin).",
                "Comparação entre municípios: tabela, radar, veredicto IA, export PDF.",
            ],
        ),
        (
            "3.6 Contingência e monitoramento",
            [
                "Planos de contingência alinhados a COBRADE.",
                "Wizard de contingência com rotas de evacuação (OSRM ou fallback).",
                "Banner de status OSRM na interface.",
                "Monitor CEMADEN: alertas hidrológicos e de deslizamento.",
                "Clima urbano oficial/estimado: temperatura e urbanização (MapBiomas + INMET).",
                "Agente proativo com sugestões contextuais na interface.",
            ],
        ),
        (
            "3.7 Assistente IA e casos de sucesso",
            [
                "Assistente municipal com RAG (pgvector + embeddings Mistral/Ollama).",
                "Chat contextual com dados do município selecionado.",
                "Fallback Gemini quando Ollama indisponível ou sem memória.",
                "Casos de sucesso com busca semântica (experiências de outras cidades).",
                "Avaliação de retrieval RAG (dataset de perguntas-resposta).",
            ],
        ),
        (
            "3.8 Segurança, operação e governança",
            [
                "Autenticação JWT com perfis: admin, gestor_municipal, leitor.",
                "Multi-tenant por UF ou lista de municípios no token.",
                "OIDC / SSO (Keycloak, template gov.br).",
                "Auditoria de ações: quem gerou PDF, ativou contingência, comparou municípios.",
                "Health checks: /health, /health/ready, /health/db, /health/ollama.",
                "Observabilidade: logs JSON, métricas Prometheus (/metrics).",
                "Backup PostGIS agendado (pg_dump).",
                "Proxy nginx com TLS e rate limit (homologação/produção).",
                "Modo institucional: oculta rótulos internos/MVP em homolog/prod.",
            ],
        ),
    ]

    for heading, bullets in sections:
        doc.add_heading(heading, level=2)
        _add_bullets(doc, bullets)

    # 4. Fontes de dados
    doc.add_heading("4. Fontes de dados integradas", level=1)
    _add_table(
        doc,
        ["Fonte", "Conteúdo", "Status típico"],
        [
            ["IBGE Cidades / SIDRA", "População, área, densidade, PIB, IDH", "Integrado"],
            ["SICONFI / CAPAG", "RCL, dívida, pessoal % RCL, nota CAPAG", "Integrado"],
            ["MapBiomas", "Cobertura vegetal, impermeabilização, série anual", "Integrado / Estimado"],
            ["S2ID / SEDEC", "Histórico de desastres", "Integrado / Estimado"],
            ["CEMADEN", "Alertas em tempo quase real", "Integrado"],
            ["SNIS/SINISA", "Saneamento e drenagem", "Integrado / Estimado"],
            ["Atlas DH / Ipeadata", "IDH municipal (Censo 2010)", "Integrado"],
            ["IBGE SINGED Lab", "Exposição RS 2024 (CNEFE)", "Parcial (6 RS)"],
            ["Atlas Econômico IPEA", "Contexto UF (matrizes NF-e 2018)", "Referência estadual"],
            ["AdaptaBrasil / INPE", "Adaptação climática", "Proxy / Em integração"],
            ["GeoSGB / CPRM", "Geologia e susceptibilidade", "Lacuna — convênio"],
            ["Brasil MAIS / SIRENE / SINTER", "Monitoramento, emissões, cadastro", "Lacuna / Proxy"],
            ["CNES / DataSUS", "Estabelecimentos de saúde", "Derivado"],
            ["SINESP", "Segurança pública", "Estimado"],
        ],
    )

    # 5. O que ainda pode ser implementado
    doc.add_heading("5. Funcionalidades e melhorias ainda possíveis", level=1)
    doc.add_paragraph(
        "Itens abaixo não invalidam o MVP atual; representam evolução natural do produto "
        "conforme disponibilidade de infraestrutura, convênios e equipe."
    )

    doc.add_heading("5.1 Lacunas institucionais (dependem de convênio/credencial)", level=2)
    _add_table(
        doc,
        ["Prioridade", "Fonte", "Responsável", "Prazo estimado", "Impacto"],
        [
            ["1", "GeoSGB / CPRM", "MCID ↔ CPRM", "6 meses", "±8 pts maturidade"],
            ["2", "Brasil MAIS", "SNH / MCID", "2–3 meses", "±5 pts"],
            ["3", "SIRENE / MCTI", "MCID ↔ MCTI", "4 meses", "±4 pts"],
            ["4", "AdaptaBrasil / INPE", "INPE", "Contínuo", "±3 pts"],
            ["5", "SINTER / Receita", "Receita Federal", "A avaliar", "±2 pts"],
        ],
    )

    doc.add_heading("5.2 Evolução técnica priorizada", level=2)
    _add_bullets(
        doc,
        [
            "IDH Censo 2022 — atualizar quando Atlas DH publicar série pós-Censo 2022.",
            "SINGED Lab — importar CSV oficial para os 4 municípios RS pendentes e expandir se IBGE liberar API.",
            "Atlas Econômico — ingestão de multiplicadores MIP-IR/TRU por UF para narrativa de impacto econômico.",
            "OSRM nacional estável — malha viária real em todas as UFs dos 61 municípios (hoje: fallback ou região Nordeste).",
            "ML de alagamento — expandir modelos treinados além dos 5 municípios piloto.",
            "Renda domiciliar oficial — substituir estimativa espacial por PNAD/Censo setorial.",
            "Google Street View 3D — componente existe, fora do fluxo principal (custo de API).",
            "Integração Pro-Cidades — link informativo com IBGE pré-preenchido (sem duplicar parecer de mérito).",
        ],
    )

    doc.add_heading("5.3 Escala e operação em produção", level=2)
    _add_bullets(
        doc,
        [
            "Servidor dedicado com SLA, backup 24/7 e monitoramento centralizado.",
            "OIDC gov.br em produção (hoje: Keycloak local + template).",
            "Certificado TLS institucional MCID em ambiente definitivo.",
            "Equipe mínima recomendada: 2 desenvolvedores, 1 especialista em dados/GIS, 1 produto/negócio.",
            "Cobertura dos ~5.570 municípios com ETL contínuo e malha oficial em todas as UFs.",
            "IA em nuvem dedicada (reduzir dependência de Ollama local no Mac mini).",
            "Ampliar cobertura de testes automatizados (meta: 70% nos serviços críticos).",
        ],
    )

    doc.add_heading("5.4 Itens explicitamente fora de escopo do Sinidu", level=2)
    _add_bullets(
        doc,
        [
            "Parecer de mérito Pro-Cidades / FGTS — sistema dedicado em Pro-cidades/automacao/ (Streamlit).",
            "Substituição de sistemas legados municipais (SIG urbano, Defesa Civil local).",
            "Cadastro imobiliário endereço a endereço (CNEFE completo) — exceto produtos pontuais (SINGED Lab).",
        ],
    )

    # 6. Premissas e limitações atuais
    doc.add_heading("6. Premissas e limitações do MVP", level=1)
    _add_bullets(
        doc,
        [
            "Desenvolvimento conduzido por equipe reduzida (modelo MVP), com evolução incremental.",
            "Ambiente de desenvolvimento em estação local (Mac mini) com banco PostgreSQL em tier gratuito ou Docker.",
            "Algumas camadas territoriais são estimadas ou derivadas — sempre rotuladas na interface (Oficial / Estimado / Lacuna).",
            "Piloto mais maduro: Recife (PE) — LiDAR local, eventos S2ID curados, malha oficial IBGE.",
            "Simulações pluviais são modelos de apoio à decisão, não substituem estudos hidrológicos de engenharia.",
        ],
    )

    # 7. Conclusão
    doc.add_heading("7. Conclusão", level=1)
    doc.add_paragraph(
        "O Sinidu+Clima entrega hoje um conjunto amplo e funcional de capacidades para diagnóstico territorial, "
        "simulação de cenários climáticos, transparência de dados e suporte à decisão institucional. "
        "O núcleo técnico está validado; a expansão para escala nacional plena depende principalmente de "
        "reforço de equipe, infraestrutura de produção e conclusão dos trâmites de dados institucionais "
        "listados na seção 5."
    )

    doc.add_paragraph()
    p = doc.add_paragraph("Documentos relacionados:")
    _add_bullets(
        doc,
        [
            "ROADMAP.md — cronologia de fases e status detalhado",
            "documentacao/DOCUMENTACAO_TECNICA_COMPLETA.md — referência técnica",
            "CHECKLIST_DEMO_MCID.md — roteiro de demonstração",
            "docs/apresentacao-instituicional.html — apresentação em slides",
            "PLANO_LACUNAS_INSTITUCIONAIS.md — trâmite de fontes pendentes",
        ],
    )

    # Margens
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    return doc


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = build()
    doc.save(OUTPUT)
    print(f"Relatório gerado: {OUTPUT}")


if __name__ == "__main__":
    main()
