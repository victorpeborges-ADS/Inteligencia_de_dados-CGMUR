#!/usr/bin/env python3
"""
Relatório unificado: benchmark GeoReDUS × Sinidu+Clima e análise estratégica
para uso institucional (DAC).

Gera PDF em docs/RELATORIO_BENCHMARK_GEOREDUS_SINIDU.pdf

Uso:
  python3 scripts/gerar_relatorio_georedus_sinidu.py
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
OUT_DIR = ROOT / "docs"
COVER_IMAGE = ROOT / "docs" / "apresentacao-assets" / "sinidu-logo-relatorio.png"
OUTPUT = OUT_DIR / "RELATORIO_BENCHMARK_GEOREDUS_SINIDU.pdf"
TODAY = date.today().strftime("%d/%m/%Y")


def styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name="CoverTitle",
        parent=base["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f3b66"),
        fontSize=22,
        leading=27,
        spaceAfter=8,
    ))
    base.add(ParagraphStyle(
        name="CoverSub",
        parent=base["Normal"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#374151"),
        fontSize=11,
        leading=15,
        spaceAfter=12,
    ))
    base.add(ParagraphStyle(
        name="H1Custom",
        parent=base["Heading1"],
        textColor=colors.HexColor("#0f3b66"),
        fontSize=15,
        leading=19,
        spaceBefore=12,
        spaceAfter=6,
    ))
    base.add(ParagraphStyle(
        name="H2Custom",
        parent=base["Heading2"],
        textColor=colors.HexColor("#155e75"),
        fontSize=11,
        leading=14,
        spaceBefore=6,
        spaceAfter=3,
    ))
    base.add(ParagraphStyle(
        name="BodyCustom",
        parent=base["BodyText"],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
        spaceAfter=5,
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
        leftIndent=10,
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
    canvas.drawString(2 * cm, 1.1 * cm, "Sinidu+Clima — Benchmark GeoReDUS — Documento interno")
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
    story.append(Spacer(1, 0.18 * cm))


def build_story():
    s = styles()
    story: list = []

    # Capa
    story.append(Spacer(1, 1.2 * cm))
    if COVER_IMAGE.exists():
        story.append(Image(str(COVER_IMAGE), width=7 * cm, height=7 * cm))
        story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph("Sinidu+Clima e GeoReDUS", s["CoverTitle"]))
    story.append(Paragraph(
        "Análise comparativa e posicionamento estratégico",
        s["CoverSub"],
    ))
    story.append(Paragraph(
        f"DAC · {TODAY} · Documento interno",
        s["SmallCustom"],
    ))
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(
        "<i>Relatório de benchmarking técnico entre o Sinidu+Clima (plataforma em desenvolvimento "
        "na DAC) e o GeoReDUS (plataforma pública da ReDUS/FNP/CEM-USP), incluindo a avaliação "
        "da proposta de utilizar o GeoReDUS como base nacional do Sinidu.</i>",
        s["QuoteCustom"],
    ))
    story.append(PageBreak())

    # 1. Sumário executivo
    section(story, "1. Sumário executivo", [
        "O GeoReDUS e o Sinidu+Clima respondem a perguntas diferentes. O GeoReDUS é um geoportal "
        "nacional gratuito que permite visualizar e baixar indicadores urbanos georreferenciados "
        "em todos os 5.570 municípios brasileiros. O Sinidu+Clima é uma plataforma operacional "
        "da DAC, voltada a simulação de cenários climáticos, contingência, monitoramento, "
        "inteligência artificial e geração de relatórios formais, atualmente priorizando 61 municípios.",
        "<b>Conclusão central:</b> faz sentido integrar o GeoReDUS como <b>fonte nacional de dados "
        "e referência territorial</b>, mas <b>não</b> adotar o GeoReDUS no lugar do Sinidu como "
        "plataforma principal da DAC. "
        "A recomendação é uma <b>arquitetura híbrida</b>: GeoReDUS para consulta e diagnóstico "
        "em escala nacional; Sinidu para simulação, operação, decisão e governança institucional.",
    ], s)

    story.append(Paragraph("Resposta à pergunta central", s["H2Custom"]))
    section(story, "", [
        "<b>Pergunta:</b> faz sentido usar o GeoReDUS como <i>base de código-fonte</i> para "
        "implementar o Sinidu — isto é, pegar o código do GeoReDUS e nele construir o que o "
        "Sinidu já tem?",
        "<b>Resposta objetiva: não, não faz sentido — e, na prática, hoje nem é viável "
        "sem acordo formal com o fornecedor.</b>",
        "O código da aplicação GeoReDUS <b>não é público</b>. O que está aberto no GitHub "
        "(CEM-USP) são documentos de metodologia dos dados, não o software da plataforma. "
        "A aplicação web foi desenvolvida pelo Instituto ORI:ORO, roda em infraestrutura "
        "deles (Heroku + CDN) e não há repositório disponível para a DAC clonar ou adaptar.",
        "Mesmo que a DAC obtivesse acesso ao código via convênio, portar o Sinidu para "
        "dentro do GeoReDUS equivaleria a <b>reconstruir quase todo o Sinidu</b> em um "
        "produto de terceiro — com custo estimado superior a evoluir o repositório atual "
        "e integrar apenas os dados do GeoReDUS.",
    ], s)
    story.append(PageBreak())

    # 2. Contexto
    section(story, "2. Contexto da proposta", [
        "Foi oferecido à DAC utilizar o GeoReDUS como plataforma base para "
        "a criação do Sinidu em escala nacional. A proposta é politicamente atraente porque o "
        "GeoReDUS já cobre todo o território nacional, é gratuito, tem respaldo acadêmico "
        "(CEM-USP) e articulação com prefeitos (FNP), e dispõe de indicadores intramunicipais "
        "padronizados (Censo 2022, educação, saúde, temperatura de superfície por satélite, entre outros).",
        "Entretanto, o Sinidu já acumula investimento técnico significativo: 15 fases de "
        "desenvolvimento, integrações operacionais (CEMADEN, S2ID, MapBiomas), simulações, "
        "contingência COBRADE, assistente com IA, autenticação institucional e auditoria. "
        "A decisão não é apenas tecnológica — define o modelo de governança, controle e "
        "capacidade operacional da DAC no tema clima-território.",
        "É preciso distinguir três interpretações distintas da proposta, que costumam ser "
        "confundidas na conversa institucional:",
    ], s)
    tbl(story, [
        ["Interpretação", "O que significa", "Faz sentido?"],
        ["A — Usar o código-fonte do GeoReDUS como base", "Clonar/adaptar o software ORI:ORO e portar o Sinidu para dentro dele", "Não — código fechado; alto custo; perda de controle"],
        ["B — Usar os dados do GeoReDUS", "Consumir APIs/tiles ou referenciar indicadores nacionais", "Sim — complementa o Sinidu"],
        ["C — Substituir o Sinidu pelo GeoReDUS", "DAC adota só o geoportal, sem módulos operacionais", "Não — perde simulação, contingência, IA, PDF, auth"],
    ], [3.4 * cm, 5.8 * cm, 4.0 * cm], s)

    # 3. O que são
    section(story, "3. O que são as duas plataformas", [], s)
    tbl(story, [
        ["Aspecto", "GeoReDUS", "Sinidu+Clima"],
        ["Finalidade", "Catálogo e visualização de dados urbanos", "Inteligência territorial operacional"],
        ["Pergunta-chave", "O que existe no território?", "O que fazer, simular e reportar?"],
        ["Cobertura", "5.570 municípios", "61 prioritários (expansível)"],
        ["Acesso", "Público, sem login", "Autenticação JWT/OIDC gov.br"],
        ["Responsável", "ReDUS (CEM-USP, FNP, ORI:ORO, GIZ)", "DAC (desenvolvimento interno)"],
        ["Público", "Gestores, pesquisadores, cidadãos", "DAC, gestores técnicos, oficinas"],
    ], [3.0 * cm, 5.5 * cm, 5.9 * cm], s)

    # 4. Comparação técnica
    section(story, "4. Comparação técnica (síntese)", [
        "A tabela abaixo resume diferenças relevantes para decisão institucional. "
        "Termos técnicos são acompanhados de explicação em linguagem acessível entre parênteses.",
    ], s)

    story.append(Paragraph("4.1 Arquitetura e tecnologias", s["H2Custom"]))
    tbl(story, [
        ["Dimensão", "GeoReDUS", "Sinidu+Clima"],
        ["Interface web", "Next.js (framework moderno de páginas web)", "Next.js 13 + React"],
        ["Servidor de mapas", "MapLibre + tiles vetoriais/raster (Martin, mosaicjson)", "Leaflet 2D + MapLibre 3D"],
        ["API de dados", "PostgREST (306 endpoints públicos)", "FastAPI (~20 módulos REST próprios)"],
        ["Banco de dados", "PostgreSQL (inferido, não exposto)", "PostgreSQL 15 + PostGIS + pgvector"],
        ["Hospedagem", "Heroku + CDN CloudFront (nuvem gerenciada)", "Docker self-hosted (infra DAC)"],
        ["Inteligência artificial", "Planejada; não operacional na UI", "Assistente RAG + agente proativo"],
        ["Relatórios", "Exportação CSV de tabelas", "PDF municipal, export SEI, contingência"],
    ], [2.8 * cm, 5.6 * cm, 5.8 * cm], s)

    story.append(Paragraph("4.2 Segurança e governança", s["H2Custom"]))
    tbl(story, [
        ["Controle", "GeoReDUS", "Sinidu+Clima"],
        ["Autenticação", "Nenhuma — acesso aberto total", "JWT + OIDC gov.br/Keycloak"],
        ["Isolamento por município/UF", "Não aplicável", "Multi-tenant configurável"],
        ["Auditoria de ações", "Não", "Log de quem gera PDF, ativa contingência etc."],
        ["Limite de requisições", "Não observado", "Nginx: 30 req/s na API"],
        ["Dados sensíveis", "Inadequado (tudo público)", "Preparado para ambiente restrito"],
    ], [3.2 * cm, 5.2 * cm, 5.8 * cm], s)

    story.append(Paragraph("4.3 Operação e qualidade", s["H2Custom"]))
    tbl(story, [
        ["Aspecto", "GeoReDUS", "Sinidu+Clima"],
        ["Testes automatizados", "Não visível (produto de terceiro)", "56 suítes pytest + CI GitHub"],
        ["Monitoramento", "Logs Heroku", "Prometheus, health checks, backup PostGIS"],
        ["Performance de mapa", "Alta (CDN + tiles pré-processados)", "GeoJSON via API (mais pesado)"],
        ["Simulações", "Não possui", "Chuva, ilha de calor, vegetação, 3D"],
        ["Contingência", "Não possui", "COBRADE + rotas + PDF"],
    ], [3.0 * cm, 5.5 * cm, 5.9 * cm], s)
    story.append(PageBreak())

    # 5. Funcionalidades
    section(story, "5. Escopo funcional", [], s)
    tbl(story, [
        ["Capacidade", "GeoReDUS", "Sinidu"],
        ["Indicadores Censo/INEP/saúde no mapa", "Sim, granular", "Parcial (em expansão)"],
        ["Temperatura observada (satélite LST)", "Sim", "Não (simulação exploratória)"],
        ["Simulação de enchente/calor", "Não", "Sim"],
        ["Monitor CEMADEN tempo real", "Não", "Sim (WebSocket)"],
        ["Plano de contingência", "Não", "Sim"],
        ["Assistente com IA", "Planejado", "Sim"],
        ["Painel executivo + PDF institucional", "Não", "Sim"],
        ["Maturidade de dados municipal", "Não", "Sim (ranking 61 municípios)"],
        ["Busca global de indicadores", "Sim", "Previsto (Fase 16)"],
    ], [4.8 * cm, 2.6 * cm, 2.6 * cm], s)

    # 6. Usabilidade
    section(story, "6. Usabilidade e experiência do usuário", [
        "A usabilidade deve ser avaliada conforme o perfil do usuário, não de forma absoluta.",
    ], s)

    story.append(Paragraph("Pontos fortes do GeoReDUS", s["H2Custom"]))
    story.append(bullets([
        "Acesso imediato: seleciona o município e o mapa carrega, sem cadastro.",
        "Descoberta simples de dados: busca de indicadores, temas laterais, metadados por camada.",
        "Controles claros: camadas ativas, seletor de ano, comparação regional.",
        "Curva de aprendizado baixa para gestor sem treinamento técnico.",
    ], s["BodyCustom"]))

    story.append(Paragraph("Pontos fortes do Sinidu+Clima", s["H2Custom"]))
    story.append(bullets([
        "Fluxo operacional completo: diagnóstico → simulação → contingência → relatório PDF.",
        "Transparência de qualidade do dado (oficial, estimado, derivado, lacuna).",
        "Dez módulos especializados (painel, simulações, monitor, catálogo, auditoria…).",
        "Modo apresentação (Focus) e agente proativo para oficinas e demos institucionais.",
    ], s["BodyCustom"]))

    story.append(Paragraph("Limitações relativas", s["H2Custom"]))
    story.append(bullets([
        "<b>GeoReDUS:</b> não suporta operação de crise, simulação nem documentação formal institucional.",
        "<b>Sinidu:</b> curva de aprendizado maior; cobertura nacional de indicadores ainda incompleta.",
    ], s["BodyCustom"]))
    story.append(PageBreak())

    # 7. Convergências
    section(story, "7. Pontos de convergência (onde faz sentido alinhar)", [], s)
    story.append(bullets([
        "<b>Cobertura nacional:</b> o GeoReDUS resolve a lacuna de dados padronizados em 5.570 municípios; o Sinidu não precisa replicar esse catálogo inteiro.",
        "<b>Indicadores intramunicipais:</b> Censo 2022 por setor, educação INEP, LST observada, territórios tradicionais — o GeoReDUS já disponibiliza; o Sinidu pode consumir ou referenciar.",
        "<b>Stack de mapas moderna:</b> padrões do GeoReDUS (tiles vetoriais, raster por satélite) podem ser adotados no Sinidu sem trocar o backend operacional.",
        "<b>Narrativa política:</b> GeoReDUS (dados abertos, FNP) + Sinidu (operação DAC) formam mensagem complementar, não concorrente.",
        "<b>Municípios pequenos:</b> GeoReDUS atende quem não tem equipe GIS; Sinidu atende prioridades com operação climática intensa.",
    ], s["BodyCustom"]))

    # 8. Viabilidade de usar o código-fonte
    section(story, "8. Viabilidade técnica de usar o código-fonte do GeoReDUS", [
        "Esta seção responde diretamente ao cenário em que a DAC receberia ou obteria "
        "o código da aplicação GeoReDUS para nele reimplementar o Sinidu.",
    ], s)

    story.append(Paragraph("8.1 O que está (e não está) disponível publicamente", s["H2Custom"]))
    tbl(story, [
        ["Recurso", "Disponível?", "Observação"],
        ["Aplicação web GeoReDUS (frontend + backends)", "Não", "Produto ORI:ORO; sem repositório público"],
        ["API de metadados (PostgREST)", "Sim (leitura pública)", "306 endpoints; sem autenticação"],
        ["Tiles raster (LST, relevo…)", "Sim (via URLs públicas)", "Servidor mosaicjson em nuvem ORI:ORO"],
        ["Metodologia dos dados (CEM-USP/GitHub)", "Sim", "Documentação, não código da plataforma"],
        ["Código-fonte do Sinidu+Clima (DAC)", "Sim", "Repositório interno; 15 fases implementadas"],
    ], [4.2 * cm, 2.4 * cm, 7.6 * cm], s)

    story.append(Paragraph("8.2 O que teria de ser portado para o código GeoReDUS", s["H2Custom"]))
    story.append(bullets([
        "<b>Segurança:</b> JWT, OIDC gov.br, multi-tenant, auditoria, rate limit — inexistentes no GeoReDUS.",
        "<b>Operação:</b> simulação pluvial e de calor, terreno 3D, cache Redis, jobs em background.",
        "<b>Contingência:</b> wizard COBRADE, desenho no mapa, rotas OSRM, PDF de plano.",
        "<b>Monitor:</b> WebSocket CEMADEN, sync OpenMeteo, painel nacional de alertas.",
        "<b>IA:</b> RAG pgvector, assistente municipal, agente proativo, interpretação de simulações.",
        "<b>Documentação:</b> diagnóstico executivo, relatório PDF, export SEI, maturidade municipal.",
        "<b>Integrações:</b> 15+ collectors (IBGE, S2ID, MapBiomas, CAPAG, SINGEDLab…), orchestrator, onboarding 61 municípios.",
    ], s["BodyCustom"]))

    story.append(Paragraph("8.3 Estimativa de esforço (ordem de grandeza)", s["H2Custom"]))
    tbl(story, [
        ["Caminho", "Esforço relativo", "Resultado"],
        ["Evoluir Sinidu + integrar dados GeoReDUS (Fase 16)", "1× (referência)", "Preserva investimento; cobertura nacional via API"],
        ["Reescrever Sinidu dentro do código GeoReDUS", "2,5–4×", "Dependência ORI:ORO; reimplementar módulos operacionais"],
        ["Reconstruir catálogo nacional do zero no Sinidu", "3–5×", "Duplica o que GeoReDUS já faz; desnecessário"],
    ], [5.0 * cm, 3.2 * cm, 5.0 * cm], s)

    story.append(Paragraph(
        "<b>Conclusão desta seção:</b> a proposta de «usar o GeoReDUS como base de implementação "
        "do Sinidu» só seria tecnicamente coerente se a DAC tivesse acesso ao código-fonte "
        "<i>e</i> aceitasse reconstruir nele toda a camada operacional que o GeoReDUS não possui. "
        "Isso é mais caro e arriscado do que manter o Sinidu e consumir o GeoReDUS como fonte de dados.",
        s["BodyCustom"],
    ))
    story.append(PageBreak())

    # 9. Divergências
    section(story, "9. Pontos de divergência (onde não faz sentido substituir)", [], s)
    story.append(bullets([
        "<b>Propósito:</b> visualizar dados ≠ simular cenários, acionar contingência ou gerar parecer territorial.",
        "<b>Segurança:</b> a DAC precisa de login gov.br, isolamento por perfil e auditoria — inexistentes no GeoReDUS.",
        "<b>Controle e dependência:</b> GeoReDUS é produto de terceiro (ORI:ORO/ReDUS); Sinidu é código e roadmap da DAC.",
        "<b>Investimento já realizado:</b> 15 fases do Sinidu (simulação 3D, IA, integrações, homologação OIDC) seriam perdidas ou reconstruídas.",
        "<b>Modelo de persistência:</b> GeoReDUS serve dados pré-curados; Sinidu processa, simula, audita e evolui dados operacionais.",
        "<b>Ecossistema DAC:</b> Sinidu é inteligência territorial; Pro-Cidades (parecer FGTS) é sistema separado — GeoReDUS não encaixa nesse fluxo.",
    ], s["BodyCustom"]))
    story.append(PageBreak())

    # 10. Cenários
    section(story, "10. Cenários possíveis e recomendação", [], s)
    tbl(story, [
        ["Cenário", "Descrição", "Avaliação"],
        ["A — Sinidu vira fork do GeoReDUS", "Reescrever módulos operacionais sobre base de visualização", "Não recomendado"],
        ["B — GeoReDUS substitui só o mapa", "Iframe ou link externo para consulta", "Aceitável como etapa temporária"],
        ["C — Arquitetura híbrida", "GeoReDUS = dados nacionais; Sinidu = operação DAC", "Recomendado"],
        ["D — Parceria institucional", "Convênio DAC↔ReDUS: API estável, co-desenvolvimento", "Melhor narrativa política"],
    ], [2.4 * cm, 6.8 * cm, 5.0 * cm], s)

    section(story, "10.1 Arquitetura híbrida recomendada", [
        "Na arquitetura híbrida, o GeoReDUS permanece como camada nacional de dados abertos "
        "(camada 0). O Sinidu permanece como camada operacional da DAC (camada 1) para "
        "municípios prioritários e situações de crise. A integração técnica está planejada "
        "no roadmap interno como Fase 16, em quatro ondas progressivas:",
    ], s)
    story.append(bullets([
        "<b>Onda 16a (rápida):</b> link GeoReDUS no catálogo, busca de indicadores, distinção simulação vs. temperatura observada.",
        "<b>Onda 16b:</b> camada LST (satélite), ampliar Censo 2022, metadados por camada.",
        "<b>Onda 16c:</b> educação INEP no mapa, seletor de ano, visualização regional.",
        "<b>Onda 16d:</b> territórios especiais, SGB/ANADEM (com convênio CPRM), assistente citando GeoReDUS.",
    ], s["BodyCustom"]))

    # 11. Matriz decisão
    section(story, "11. Matriz de decisão", [], s)
    tbl(story, [
        ["Pergunta", "Só GeoReDUS", "Só Sinidu", "Híbrido"],
        ["Diagnóstico em qualquer município?", "Sim", "Não (61)", "Sim"],
        ["Simulação e contingência?", "Não", "Sim", "Sim"],
        ["PDF/SEI institucional?", "Não", "Sim", "Sim"],
        ["Login gov.br e auditoria?", "Não", "Sim", "Sim"],
        ["Custo de escala nacional de dados?", "Baixo", "Alto", "Médio"],
        ["Controle da DAC?", "Baixo", "Alto", "Alto na operação"],
    ], [4.5 * cm, 2.5 * cm, 2.5 * cm, 2.7 * cm], s)
    story.append(PageBreak())

    # 12. Riscos
    section(story, "12. Riscos de aceitar «base GeoReDUS» sem definir escopo", [], s)
    tbl(story, [
        ["Risco", "Impacto"],
        ["Dependência de fornecedor (ORI:ORO)", "Roadmap nacional fora do controle da DAC"],
        ["Perda de simulação e contingência", "Diferencial de demo e operação perdido"],
        ["Dados em API pública", "Inadequado para fluxos governamentais sensíveis"],
        ["Duplicação de esforço", "Reimplementar o que o Sinidu já possui"],
        ["Expectativa política mal calibrada", "Promessa de «Sinidu nacional em poucos meses» irreal"],
    ], [5.5 * cm, 8.7 * cm], s)

    # 13. Recomendações
    section(story, "13. Recomendações", [], s)
    story.append(bullets([
        "<b>Não recomendar</b> a proposta se ela significar usar o <i>código-fonte</i> do GeoReDUS como base do Sinidu — o código não é público e o esforço de portar os módulos operacionais supera evoluir o repositório atual.",
        "<b>Não recomendar</b> a proposta se ela significar substituir o Sinidu pelo GeoReDUS.",
        "<b>Recomendar</b> parceria em que o GeoReDUS funcione como infraestrutura nacional de dados e o Sinidu como camada operacional da DAC.",
        "<b>Negociar convênio</b> com ReDUS/ORI:ORO para acesso API estável, metadados e eventual federação de identidade.",
        "<b>Executar Fase 16</b> do roadmap Sinidu como plano de integração técnica (não de substituição).",
        "<b>Registrar</b> modelo em duas camadas: diagnóstico aberto (GeoReDUS) e decisão operacional (Sinidu).",
        "<b>Preservar</b> o investimento já realizado em simulação, IA, auditoria e homologação institucional.",
    ], s["BodyCustom"]))

    # 14. Conclusão
    section(story, "14. Conclusão", [
        "O GeoReDUS é uma ferramenta valiosa e complementar, especialmente para democratizar "
        "o acesso a indicadores urbanos em escala nacional. Não é, contudo, substituto do "
        "Sinidu+Clima como plataforma operacional da DAC.",
        "A estratégia mais segura e eficiente combina o melhor dos dois mundos: reutilizar "
        "os dados e padrões do GeoReDUS onde o Sinidu ainda tem lacunas, mantendo o núcleo "
        "operacional, a governança e o controle institucional na DAC. Essa abordagem reduz "
        "custo, acelera cobertura nacional de indicadores e preserva o diferencial do Sinidu "
        "em simulação, contingência, inteligência artificial e documentação formal.",
    ], s)

    story.append(Spacer(1, 0.6 * cm))
    story.append(Paragraph(
        f"Documento gerado automaticamente em {TODAY}. "
        "Fontes: análise técnica do repositório Sinidu+Clima (julho/2026), inspeção da plataforma "
        "GeoReDUS (redus.org.br/georedus) e roadmap interno (Fase 16). "
        "Referência web: https://www.redus.org.br/georedus",
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
        title="Benchmark GeoReDUS × Sinidu+Clima",
    )
    doc.build(build_story(), onFirstPage=footer, onLaterPages=footer)
    print(f"PDF gerado: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
