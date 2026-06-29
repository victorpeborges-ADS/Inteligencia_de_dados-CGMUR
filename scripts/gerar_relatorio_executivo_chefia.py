#!/usr/bin/env python3
"""
Relatório executivo completo Sinidu+Clima — uso institucional (chefia MCID).

Gera PDF em documentacao/Sinidu_Clima_Relatorio_Executivo_Chefia.pdf

Uso:
  python3 scripts/gerar_relatorio_executivo_chefia.py
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "documentacao"
LOGO = ROOT / "frontend" / "public" / "logo-sinidu-clima.png"
OUTPUT = OUT_DIR / "Sinidu_Clima_Relatorio_Executivo_Chefia.pdf"
TODAY = date.today().strftime("%d/%m/%Y")


def styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name="CoverTitle",
        parent=base["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f3b66"),
        fontSize=24,
        leading=29,
        spaceAfter=10,
    ))
    base.add(ParagraphStyle(
        name="CoverSub",
        parent=base["Normal"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#374151"),
        fontSize=12,
        leading=16,
        spaceAfter=14,
    ))
    base.add(ParagraphStyle(
        name="H1Custom",
        parent=base["Heading1"],
        textColor=colors.HexColor("#0f3b66"),
        fontSize=16,
        leading=20,
        spaceBefore=14,
        spaceAfter=8,
    ))
    base.add(ParagraphStyle(
        name="H2Custom",
        parent=base["Heading2"],
        textColor=colors.HexColor("#155e75"),
        fontSize=12,
        leading=15,
        spaceBefore=8,
        spaceAfter=4,
    ))
    base.add(ParagraphStyle(
        name="BodyCustom",
        parent=base["BodyText"],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    ))
    base.add(ParagraphStyle(
        name="SmallCustom",
        parent=base["BodyText"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#4b5563"),
    ))
    base.add(ParagraphStyle(
        name="QuoteCustom",
        parent=base["BodyText"],
        fontSize=10,
        leading=14,
        leftIndent=12,
        textColor=colors.HexColor("#1e3a5f"),
        backColor=colors.HexColor("#eff6ff"),
        borderPadding=8,
        spaceAfter=8,
    ))
    return base


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(2 * cm, 1.1 * cm, "Sinidu+Clima — Relatório Executivo — Uso interno MCID")
    canvas.drawRightString(A4[0] - 2 * cm, 1.1 * cm, f"Página {doc.page}")
    canvas.restoreState()


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=8) for item in items],
        bulletType="bullet",
        start="•",
        leftIndent=14,
        bulletFontSize=7,
    )


def section(story, title, paragraphs, style):
    story.append(Paragraph(title, style["H1Custom"]))
    for text in paragraphs:
        story.append(Paragraph(text, style["BodyCustom"]))


def tbl(story, rows, col_widths, style):
    data = [[Paragraph(str(cell), style["SmallCustom"]) for cell in row] for row in rows]
    t = Table(data, colWidths=col_widths, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.2 * cm))


def build_story():
    s = styles()
    story: list = []

    # —— Capa ——
    story.append(Spacer(1, 1.2 * cm))
    if LOGO.exists():
        story.append(Image(str(LOGO), width=3.8 * cm, height=3.8 * cm))
        story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Sinidu+Clima", s["CoverTitle"]))
    story.append(Paragraph(
        "Plataforma Nacional de Inteligência Territorial",
        s["CoverSub"],
    ))
    story.append(Paragraph(
        "Relatório Executivo Completo",
        s["CoverSub"],
    ))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        "Apresentação técnica e funcional para decisão institucional<br/>"
        f"Ministério das Cidades · {TODAY}",
        s["SmallCustom"],
    ))
    story.append(Spacer(1, 1.5 * cm))
    story.append(Paragraph(
        "<i>Este documento descreve o que a plataforma faz hoje, como foi construída, "
        "suas limitações explícitas e o horizonte de evolução. Destina-se à chefia "
        "e às áreas técnicas que avaliam adoção, escala ou integração ao ecossistema MCID.</i>",
        s["QuoteCustom"],
    ))
    story.append(PageBreak())

    # —— 1. Sumário executivo ——
    section(story, "1. Sumário executivo", [
        "O Sinidu+Clima é um protótipo operacional de inteligência territorial voltado ao apoio "
        "à gestão municipal de riscos climáticos, adaptação urbana e priorização de investimentos. "
        "Consolida mapas, indicadores, simulações, monitoramento, contingência e assistente com IA "
        "em uma única interface web, com backend geoespacial e integrações a fontes públicas.",
        "O sistema já permite onboardar 61 municípios prioritários, calcular índices de "
        "vulnerabilidade e inundação, simular cenários extremos, gerar diagnósticos e relatórios PDF, "
        "operar planos de contingência alinhados ao COBRADE e acompanhar alertas CEMADEN e clima "
        "em tempo quase real.",
        "Trata-se de um MVP interno maduro para demonstração e pilotos — não de um produto "
        "nacional em produção. Simulações e modelos preditivos são proxies territoriais para "
        "planejamento; não substituem estudos hidrológicos, laudos geotécnicos ou alertas oficiais.",
    ], s)

    story.append(Paragraph("Principais entregas já disponíveis", s["H2Custom"]))
    story.append(bullets([
        "Painel executivo com KPIs, maturidade de dados e score territorial.",
        "Mapa 2D (16 camadas) e terreno 3D com DEM SRTM.",
        "Quatro simulações + análise preditiva ML (5 municípios) + interpretação por IA.",
        "Monitor operacional (CEMADEN + OpenMeteo + WebSocket).",
        "Contingência COBRADE com rotas OSRM e exportação PDF.",
        "Assistente municipal com RAG local (Ollama) e provedores cloud opcionais.",
        "Relatórios PDF municipais e documentação técnica versionada.",
    ], s["BodyCustom"]))
    story.append(PageBreak())

    # —— 2. Problema e objetivo ——
    section(story, "2. Problema institucional e objetivo", [
        "Municípios brasileiros enfrentam dados fragmentados sobre clima, desastres, fiscal, "
        "território e programas federais. Decisões urgentes (chuvas extremas, alagamentos, "
        "contingência) exigem cruzamento rápido de informações que hoje está disperso entre "
        "planilhas, sistemas setoriais e conhecimento tácito.",
        "O Sinidu+Clima responde a essa lacuna ao oferecer uma \"sala de situação territorial\": "
        "visualizar risco por bairro, testar cenários, documentar lacunas de dados, sugerir ações "
        "proporcionais e gerar entregáveis formais (PDF) para gestores e equipes técnicas.",
    ], s)

    # —— 3. Funcionalidades ——
    section(story, "3. Funcionalidades da plataforma", [
        "A interface está organizada em sete módulos principais, sincronizados pelo município "
        "selecionado no header global.",
    ], s)
    tbl(story, [
        ["Módulo", "O que faz", "Valor para o gestor"],
        ["Painel", "KPIs IBGE/fiscal, score Sinidu+Clima, maturidade, diagnóstico, plano de ação, PDF", "Visão executiva única do território"],
        ["Municípios", "Onboarding: malha IBGE, CAPAG, SICONFI, bairros", "Entrada de novos municípios na base"],
        ["Simulações", "Chuva extrema (DEM+IRI), asfalto, vegetação, drenagem, ML preditivo", "Antecipar impactos e priorizar bairros"],
        ["Monitor", "CEMADEN, precipitação prevista, mapa nacional, timeline, contingência", "Operação diária e alerta"],
        ["Contingência", "Planos COBRADE, zonas no mapa, rotas, PDF", "Resposta a eventos extremos"],
        ["Assistente", "Chat IA com contexto municipal + corpus normativo (RAG)", "Tirar dúvidas com citação de fontes"],
        ["Casos", "Busca de experiências e boas práticas", "Aprendizado entre municípios"],
    ], [2.8 * cm, 6.2 * cm, 5.4 * cm], s)

    story.append(Paragraph("Fluxo operacional recomendado", s["H2Custom"]))
    story.append(bullets([
        "Integrar município (Onboarding) → Painel e diagnóstico automático.",
        "Plano de ação territorial vinculado a programas federais (Pro-Cidades, Fundo Clima, PAC…).",
        "Simular cenários → plano de mitigação → plano de contingência se necessário.",
        "Monitorar alertas → ativar contingência → exportar PDF para equipes de campo.",
        "Assistente para dúvidas normativas e técnicas com rastreabilidade.",
    ], s["BodyCustom"]))
    story.append(PageBreak())

    # —— 4. O que PODE fazer ——
    section(story, "4. O que o sistema pode fazer (capacidades confirmadas)", [], s)
    story.append(bullets([
        "<b>Análise territorial integrada:</b> cruzar bairros, setores censitários, MapBiomas, S2ID, CEMADEN, CAPAG e IBGE em mapas e rankings.",
        "<b>Índices transparentes:</b> IVC (vulnerabilidade climática), IRI (risco de inundação) e score multidimensional — regras documentadas, não caixa-preta.",
        "<b>Simulações exploratórias:</b> manchas de impacto por chuva (DEM SRTM 30 m, faixas de profundidade, declividade), impermeabilização, ilha de calor e déficit de drenagem.",
        "<b>Predição estatística:</b> Random Forest de alagamento para Recife, Salvador, Porto Alegre, João Pessoa e Londrina (precipitação + terreno + histórico).",
        "<b>Interpretação assistida:</b> análise pós-simulação via LLM (Ollama local ou API cloud) com fallback determinístico.",
        "<b>Monitoramento:</b> sincronização periódica CEMADEN e OpenMeteo; alertas WebSocket; push Gotify (opcional).",
        "<b>Contingência:</b> templates COBRADE, desenho de zonas, rotas de evacuação (OSRM em PE; fallback geodésico).",
        "<b>Documentação:</b> diagnóstico executivo (7 seções), plano de ação, relatório municipal PDF (WeasyPrint).",
        "<b>Transparência de lacunas:</b> maturidade municipal (Bronze→Platina), catálogo de cobertura, campos vazios quando não há fonte verificável.",
        "<b>Escalabilidade técnica base:</b> 61 municípios no seed; arquitetura containerizada; ~55 endpoints REST documentados.",
    ], s["BodyCustom"]))
    story.append(Spacer(1, 0.3 * cm))

    # —— 5. O que NÃO pode fazer ——
    section(story, "5. O que o sistema não pode fazer (limites explícitos)", [
        "É fundamental que a chefia e os municípios conheçam estes limites antes de qualquer "
        "uso externo ou vinculação a decisões irreversíveis.",
    ], s)
    story.append(bullets([
        "<b>Não substitui</b> modelagem hidrodinâmica (HEC-RAS, SWMM), laudo geotécnico, ART/RRT de engenheiro, parecer jurídico ou alerta oficial CEMADEN/Defesa Civil.",
        "<b>Não garante</b> precisão cadastral de bairros em municípios sem malha local detalhada (usa grade genérica ou IBGE quando necessário).",
        "<b>Não é produto nacional em produção:</b> frontend ainda em modo desenvolvimento; autenticação JWT existe mas está desligada por padrão no ambiente local.",
        "<b>Integrações parciais:</b> SNIS/SINISA e algumas bases aparecem como derivadas; OSRM viário completo só para Pernambuco; DEM SRTM depende de chave OpenTopography em escala.",
        "<b>ML preditivo limitado:</b> 5 municípios; modelos baseline sintéticos até retreino com OpenMeteo+S2ID; probabilidades são apoio estatístico, não previsão meteorológica.",
        "<b>Assistente IA:</b> pode alucinar se contexto insuficiente; exige revisão humana; corpus RAG ainda pequeno (7 textos normativos + PDFs internos).",
        "<b>Sem multi-tenant institucional:</b> isolamento por perfil/órgão, auditoria completa e SSO gov.br ainda no roadmap.",
        "<b>Sem homologação SEI:</b> exportação PDF não gera protocolo nem hash institucional automático.",
    ], s["BodyCustom"]))
    story.append(PageBreak())

    # —— 6. Arquitetura e tecnologias ——
    section(story, "6. Arquitetura técnica e uso das tecnologias", [
        "A solução segue arquitetura em camadas, executada via Docker Compose em ambiente de "
        "desenvolvimento/piloto. Todos os componentes são open source ou APIs públicas, "
        "permitindo implantação on-premises (importante para dados sensíveis).",
    ], s)

    story.append(Paragraph("6.1 Visão de componentes", s["H2Custom"]))
    tbl(story, [
        ["Camada", "Tecnologia", "Papel"],
        ["Frontend", "Next.js 13, React 18, TypeScript, Tailwind", "Interface única, mapas, painéis"],
        ["Mapas 2D", "Leaflet + GeoJSON", "Camadas temáticas e simulações"],
        ["Mapas 3D", "MapLibre GL + tiles DEM Terrarium", "Terreno, declividade, escoamento"],
        ["Backend", "Python 3.10, FastAPI, Uvicorn", "APIs REST, WebSocket, orquestração"],
        ["Banco", "PostgreSQL 15 + PostGIS + pgvector", "Dados geoespaciais e embeddings RAG"],
        ["Geoprocessamento", "Shapely, rasterio, GDAL", "Interseções, buffers, DEM, manchas"],
        ["ML", "scikit-learn, pandas", "Predição de alagamento por município"],
        ["IA / RAG", "Ollama (local), LangChain, pgvector", "Assistente e busca semântica"],
        ["PDF", "WeasyPrint, Jinja2, ReportLab", "Relatórios formais"],
        ["Jobs", "APScheduler", "Sync CEMADEN (30 min), clima (55 min), integrações"],
        ["Infra", "Docker Compose, Redis, OSRM, Gotify", "Cache, rotas, notificações push"],
    ], [2.6 * cm, 4.8 * cm, 6.0 * cm], s)

    story.append(Paragraph("6.2 Como cada tecnologia é usada na prática", s["H2Custom"]))
    story.append(bullets([
        "<b>PostGIS:</b> armazena limites municipais, bairros, desastres S2ID, alertas CEMADEN, cobertura MapBiomas; consultas ST_Intersects alimentam IVC/IRI.",
        "<b>DEM SRTM (30 m):</b> processado offline por município; gera curvas de nível, manchas pluviais simuladas e terreno 3D.",
        "<b>OpenMeteo / INMET:</b> precipitação prevista e dados climáticos oficiais no painel e monitor.",
        "<b>Ollama (LLM local):</b> chat do assistente e embeddings RAG sem enviar dados para cloud — adequado a ambiente restrito.",
        "<b>Provedores cloud (opcional):</b> Gemini, OpenAI, Anthropic etc. para fallback quando Ollama indisponível.",
        "<b>WebSocket:</b> push de alertas ao frontend sem polling constante.",
        "<b>OSRM:</b> rotas de evacuação em planos de contingência (malha viária PE).",
    ], s["BodyCustom"]))
    story.append(PageBreak())

    # —— 7. Fontes de dados ——
    section(story, "7. Fontes de dados e integrações", [], s)
    tbl(story, [
        ["Fonte", "Uso no sistema", "Status típico"],
        ["IBGE", "População, malhas, contexto territorial", "Integrado via onboarding"],
        ["SICONFI / CAPAG", "Fiscal, nota CAPAG, endividamento", "Coletor com parser adaptativo"],
        ["S2ID / CEMADEN", "Desastres e alertas", "Sync periódico + seed demo"],
        ["MapBiomas", "Vegetação, urbano, corpos d'água", "Camadas e índices"],
        ["OpenMeteo", "Precipitação prevista", "Monitor e ML"],
        ["INMET", "Clima urbano oficial", "Painel executivo"],
        ["OpenTopography", "DEM SRTM", "Simulações e 3D (requer API key)"],
        ["Sentinel STAC", "Imagens satélite recentes", "Metadados + fallback demo"],
        ["Corpus MCID/normativo", "RAG assistente", "7 textos + PDFs internos"],
    ], [3.2 * cm, 5.5 * cm, 5.7 * cm], s)

    story.append(Paragraph(
        "O sistema distingue qualidade do dado (Oficial, Estimado, Derivado Sinidu+Clima) e "
        "pontua maturidade municipal (0–100). Municípios sem onboarding completo exibem lacunas "
        "explicitamente — não inventam indicadores.",
        s["BodyCustom"],
    ))
    story.append(PageBreak())

    # —— 8. Maturidade atual ——
    section(story, "8. Estado de maturidade do produto (junho/2026)", [], s)
    tbl(story, [
        ["Dimensão", "Estimativa", "Observação"],
        ["Infraestrutura Docker", "88%", "8 serviços orquestrados; health checks implementados"],
        ["API e backend", "85%", "~55 endpoints; boot resiliente"],
        ["Integrações externas", "72%", "CAPAG/SICONFI sensíveis a mudanças de layout"],
        ["Análise e índices", "78%", "Regras determinísticas; simulações enriquecidas com DEM"],
        ["IA e RAG", "70%", "Ollama local; corpus a expandir"],
        ["Visualização 2D/3D", "75%", "MapLibre 3D operacional"],
        ["Contingência e alerta", "80%", "COBRADE + WebSocket + Gotify opcional"],
        ["Segurança / auth", "55%", "JWT implementado; desligado em dev; SSO gov.br pendente"],
        ["Testes automatizados", "45%", "pytest em módulos críticos; CI básico"],
        ["Produção nacional", "45%", "Dockerfile prod; falta proxy TLS e multi-tenant"],
    ], [3.5 * cm, 2.2 * cm, 8.7 * cm], s)

    # —— 9. Evolução ——
    section(story, "9. Horizonte de evolução — até onde podemos ir", [
        "O roadmap está priorizado em quatro fases. Abaixo, síntese para decisão de investimento.",
    ], s)

    story.append(Paragraph("Fase 1 — Desbloqueadores (concluída)", s["H2Custom"]))
    story.append(bullets([
        "Autenticação JWT, CORS restrito, health checks, boot resiliente, CI smoke, docker-compose prod.",
    ], s["BodyCustom"]))

    story.append(Paragraph("Fase 2 — Credibilidade territorial (próximos 3–6 meses)", s["H2Custom"]))
    story.append(bullets([
        "OSRM multi-região ou serviço nacional de rotas.",
        "Badges de qualidade em cada KPI do painel.",
        "Bloquear PDF formal se maturidade &lt; Prata (com override admin).",
        "ETL S2ID + MapBiomas automático no onboarding.",
        "Integração real SNIS/SINISA para drenagem.",
    ], s["BodyCustom"]))

    story.append(Paragraph("Fase 3 — Qualidade e escala (6–12 meses)", s["H2Custom"]))
    story.append(bullets([
        "CI/CD com cobertura mínima 60% nos serviços críticos.",
        "Refator frontend em rotas modulares; estado global.",
        "ML de alagamento expandido a todos os 61 municípios ou mensagem clara de degradação.",
        "Observabilidade (logs JSON, Prometheus), backup PostGIS agendado.",
        "Avaliação RAG com conjunto de perguntas-resposta esperadas.",
    ], s["BodyCustom"]))

    story.append(Paragraph("Fase 4 — Produto MCID institucional (12–24 meses)", s["H2Custom"]))
    story.append(bullets([
        "Módulo Pro-Cidades: parecer de mérito automatizado (IN MCID 18/2025).",
        "Export SEI com metadados e hash.",
        "Multi-tenant e OIDC gov.br / Keycloak.",
        "Reverse proxy, TLS, rate limiting, auditoria de ações.",
    ], s["BodyCustom"]))
    story.append(PageBreak())

    # —— 10. Recomendações ——
    section(story, "10. Recomendações para a chefia", [], s)
    story.append(bullets([
        "<b>Posicionamento:</b> apresentar como \"laboratório operacional de inteligência territorial\" — não como sistema nacional já homologado.",
        "<b>Pilotos:</b> iniciar com 3–5 municípios com onboarding completo (Recife + capitais do seed) e equipe técnica municipal envolvida.",
        "<b>Comunicação externa:</b> sempre acompanhar entregáveis PDF com disclaimer de proxy/simulação e lista de lacunas.",
        "<b>Investimento prioritário:</b> Fase 2 (credibilidade de dados) antes de escala nacional; integrações SNIS e OSRM multi-UF.",
        "<b>Infraestrutura:</b> servidor com ≥32 GB RAM se IA local (Ollama); ou política de uso exclusivo de APIs cloud aprovadas.",
        "<b>Governança:</b> definir perfis (admin MCID, gestor municipal, leitor) e auditoria antes de exposição externa.",
        "<b>Sinergia Pro-Cidades:</b> Fase 4 alinha diretamente ao programa — candidato natural a ferramenta de apoio a pareceres de mérito.",
    ], s["BodyCustom"]))

    section(story, "11. Conclusão", [
        "O Sinidu+Clima demonstra viabilidade técnica e valor institucional de integrar mapa, "
        "dados públicos, simulação, IA e documentação em um fluxo único para gestão municipal "
        "de riscos climáticos. O núcleo está funcional; os gaps principais são credibilidade "
        "cadastral em escala, homologação de segurança e integrações setoriais ainda derivadas.",
        "Recomenda-se autorizar continuidade do piloto com foco na Fase 2 do roadmap, avaliação "
        "por municípios parceiros e definição de critérios objetivos para promoção a ferramenta "
        "institucional do MCID (incluindo eventual módulo Pro-Cidades).",
    ], s)

    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(
        f"Documento gerado automaticamente a partir do repositório Sinidu+Clima em {TODAY}. "
        "Versão de referência: junho/2026. Contato técnico: equipe de desenvolvimento interno MCID.",
        s["SmallCustom"],
    ))
    return story


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Sinidu+Clima — Relatório Executivo",
    )
    doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    print(f"PDF gerado: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
