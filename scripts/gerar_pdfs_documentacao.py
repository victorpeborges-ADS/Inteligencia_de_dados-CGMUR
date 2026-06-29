from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
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


def styles():
    base = getSampleStyleSheet()
    base.add(ParagraphStyle(
        name="CoverTitle",
        parent=base["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f3b66"),
        fontSize=26,
        leading=31,
        spaceAfter=12,
    ))
    base.add(ParagraphStyle(
        name="CoverSub",
        parent=base["Normal"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#374151"),
        fontSize=12,
        leading=17,
        spaceAfter=18,
    ))
    base.add(ParagraphStyle(
        name="H1Custom",
        parent=base["Heading1"],
        textColor=colors.HexColor("#0f3b66"),
        fontSize=18,
        leading=22,
        spaceBefore=12,
        spaceAfter=8,
    ))
    base.add(ParagraphStyle(
        name="H2Custom",
        parent=base["Heading2"],
        textColor=colors.HexColor("#155e75"),
        fontSize=13,
        leading=16,
        spaceBefore=8,
        spaceAfter=5,
    ))
    base.add(ParagraphStyle(
        name="BodyCustom",
        parent=base["BodyText"],
        fontSize=10,
        leading=14,
        spaceAfter=7,
    ))
    base.add(ParagraphStyle(
        name="SmallCustom",
        parent=base["BodyText"],
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#4b5563"),
    ))
    return base


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(2 * cm, 1.2 * cm, "Sinidu+Clima - documentação interna")
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {doc.page}")
    canvas.restoreState()


def bullets(items, style):
    return ListFlowable(
        [ListItem(Paragraph(item, style), leftIndent=10) for item in items],
        bulletType="bullet",
        start="circle",
        leftIndent=16,
        bulletFontSize=6,
    )


def cover(title, subtitle, style):
    story = [Spacer(1, 1.1 * cm)]
    if LOGO.exists():
        story.append(Image(str(LOGO), width=4.0 * cm, height=4.0 * cm))
        story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(title, style["CoverTitle"]))
    story.append(Paragraph(subtitle, style["CoverSub"]))
    story.append(Paragraph("Versão INTERNA de referência - gerada em 23/06/2026", style["SmallCustom"]))
    story.append(PageBreak())
    return story


def section(story, title, paragraphs, style):
    story.append(Paragraph(title, style["H1Custom"]))
    for text in paragraphs:
        story.append(Paragraph(text, style["BodyCustom"]))


def table(story, rows, col_widths, style):
    data = [[Paragraph(str(cell), style["SmallCustom"]) for cell in row] for row in rows]
    tbl = Table(data, colWidths=col_widths, hAlign="LEFT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 0.25 * cm))


def build_pdf(filename, story):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_DIR / filename),
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title=filename,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def technical_doc():
    s = styles()
    story = cover(
        "Sinidu+Clima - Documentação Técnica INTERNA",
        "Arquitetura, tecnologias, APIs, dados, modelos analíticos e limites do sistema",
        s,
    )

    section(story, "1. Visão Geral", [
        "O Sinidu+Clima é uma versão interna de inteligência territorial para apoiar diagnóstico urbano, leitura de risco climático, simulação de eventos extremos e priorização de ações de adaptação municipal.",
        "A aplicação combina mapa interativo, painel executivo, simulações, catálogo de dados, comparação entre municípios, radar de lacunas informacionais, assistente textual e geração de planos de ação sugeridos para cenários climáticos e urbanos.",
    ], s)

    story.append(Paragraph("Principais capacidades implementadas", s["H2Custom"]))
    story.append(bullets([
        "Seleção de municípios demonstrativos: Recife, Caroebe, Salvador, Porto Alegre e João Pessoa.",
        "Sobreposição de camadas geoespaciais no mapa: bairros, limite municipal, vulnerabilidade, inundação, cobertura, alertas, desastres, infraestrutura, saneamento/drenagem, adaptação, prioridade de planejamento e lacunas de dados.",
        "Dashboard executivo com população, área, densidade, renda estimada, danos materiais, cobertura vegetal, alertas e maturidade dos dados.",
        "Simulação de chuva extrema, impermeabilização/asfalto, perda de vegetação e déficit de drenagem.",
        "Plano de ação sugerido após qualquer simulação, com severidade, ações proporcionais, evidências, municípios análogos, fontes oficiais e lacunas.",
        "Modo comparação entre municípios e explicabilidade do Score Sinidu+Clima.",
    ], s["BodyCustom"]))

    section(story, "2. Arquitetura", [
        "A solução roda em Docker Compose com três serviços principais: banco PostGIS, backend FastAPI e frontend Next.js.",
        "O frontend consome APIs REST do backend. O backend usa SQLAlchemy/GeoAlchemy2 para consultar dados relacionais e geoespaciais no PostgreSQL/PostGIS. A camada analítica usa Shapely para operações geométricas e regras explícitas para os índices e simulações.",
    ], s)
    table(story, [
        ["Camada", "Tecnologia", "Função"],
        ["Frontend", "Next.js 13, React 18, TypeScript, Tailwind CSS", "Interface, painéis, mapa, simulações e relatórios visuais."],
        ["Mapa", "Leaflet e React-Leaflet", "Renderização de camadas GeoJSON e popups."],
        ["Gráficos", "Recharts", "Indicadores e séries no dashboard."],
        ["Backend", "Python, FastAPI, Uvicorn, Pydantic", "APIs REST, validação de payloads e orquestração das análises."],
        ["Dados", "PostgreSQL 15 + PostGIS 3.4", "Armazenamento relacional e geoespacial."],
        ["ORM/GIS", "SQLAlchemy, GeoAlchemy2, Shapely", "Consultas, interseções, buffers e cálculos territoriais."],
        ["Infraestrutura", "Docker Compose", "Execução local reprodutível em containers."],
    ], [3.1 * cm, 5.0 * cm, 7.1 * cm], s)

    section(story, "3. Linguagens e Bibliotecas", [
        "Backend em Python com FastAPI, SQLAlchemy, GeoAlchemy2, Pydantic, Requests/HTTPX, Pandas, NumPy, Shapely e PyProj.",
        "Frontend em TypeScript/React com Next.js, Tailwind CSS, Leaflet, React-Leaflet, Recharts, lucide-react e utilitários de classe CSS.",
    ], s)

    section(story, "4. APIs Internas Implementadas", [
        "As APIs internas seguem o prefixo /api/v1 e entregam JSON ou GeoJSON para a interface.",
    ], s)
    table(story, [
        ["Grupo", "Endpoint/uso", "Descrição"],
        ["Indicators", "/indicators/executive, /indicators/layers/{layer}, /indicators/municipalities", "Indicadores executivos, camadas GeoJSON e lista de municípios."],
        ["Analytics", "/analytics/indices, /analytics/diagnostic, /analytics/compare, /analytics/sentinel-stac", "Índices de risco, diagnóstico de oficina, comparação municipal e metadados Sentinel."],
        ["Simulations", "/simulations/waterproofing, /vegetation-loss, /extreme-rainfall, /drainage-deficit", "Cenários de impermeabilização, perda de vegetação, chuva extrema e déficit de drenagem."],
        ["Plano de ação", "/simulations/mitigation-plan e /simulations/extreme-rainfall/mitigation-plan", "Plano de ação sugerido proporcional ao cenário simulado."],
        ["Data Catalog", "/data-catalog/coverage", "Maturidade informacional e lacunas de integração."],
        ["Assistant", "/assistant/chat, /assistant/cases/search", "Assistente textual e busca de casos no banco local."],
    ], [3.0 * cm, 5.4 * cm, 6.8 * cm], s)

    section(story, "5. Fontes, APIs Públicas e Bases Referenciadas", [
        "A versão interna combina dados demonstrativos carregados no banco com integrações e referências a fontes oficiais. Onde uma fonte não está integrada de forma verificável, o sistema indica lacuna em vez de inventar dado.",
    ], s)
    story.append(bullets([
        "Element 84 Earth Search STAC API: consulta pública para metadados Sentinel-2 L2A, com fallback demonstrativo se a rede falhar.",
        "IBGE/Cidades e malhas: referência para município, população, área, densidade e contexto territorial.",
        "S2ID/SEDEC: referência para histórico de desastres e danos materiais.",
        "CEMADEN/GeoRiscos: referência para alertas e leitura de risco.",
        "MapBiomas: referência para cobertura vegetal, área urbana e corpos d'água.",
        "SNIS/SINISA: referência para saneamento e drenagem, ainda representada como dado derivado/estimado na versão interna.",
        "AdaptaBrasil/INPE, GeoSGB/CPRM, SINTER, MUNIC/IBGE, INDE, Brasil MAIS e SIRENE: aparecem no radar de integração/lacunas para orientar priorização de conectores.",
        "Planos Diretores: fontes oficiais por município consultadas no plano de ação sugerido quando há URL oficial e texto legível.",
    ], s["BodyCustom"]))

    section(story, "6. Modelos Analíticos e Regras", [
        "Os índices da versão interna são determinísticos e transparentes. Não há modelo preditivo de machine learning treinado nesta versão.",
        "O índice de vulnerabilidade climática cruza exposição, sensibilidade e capacidade adaptativa. O índice de inundação cruza histórico S2ID, impermeabilização e proximidade de corpos d'água. O Score Sinidu+Clima combina 45% vulnerabilidade, 35% inundação e 20% déficit de adaptação.",
        "As simulações usam buffers, interseções geoespaciais e fatores proporcionais ao parâmetro informado. A mancha de chuva extrema, asfalto, vegetação e drenagem é uma estimativa territorial para planejamento, não uma modelagem hidrodinâmica, hidráulica, microclimática ou de engenharia oficial.",
    ], s)

    section(story, "7. Plano de Ação Sugerido", [
        "O plano de ação sugerido é acionado após a simulação de chuva, asfalto, vegetação ou drenagem. O backend recalcula o cenário para o município selecionado e retorna severidade, ações técnicas padrão, evidências do histórico municipal, municípios análogos, fontes oficiais e lacunas.",
        "O coeficiente de similaridade entre municípios usa variáveis disponíveis: população, densidade, renda média, cobertura vegetal, histórico de desastres, danos, região e perfil climático operacional. Só são retornados análogos acima do limiar mínimo configurado.",
        "Casos análogos ficam vazios quando não há solução e resultado verificáveis por fonte oficial. Restrições do Plano Diretor só aparecem quando extraídas de página oficial legível.",
    ], s)

    section(story, "8. LLM, IA e Assistente", [
        "No runtime atual do produto não há chamada a LLM externo. O Assistente Sinidu+Clima é uma camada determinística baseada em regras de intenção, consultas ao PostGIS e busca textual simples sobre casos de sucesso.",
        "A busca de casos usa tokenização em português e pontuação de relevância semelhante a TF-IDF simples; não usa embeddings, RAG vetorial ou modelo generativo nesta versão.",
        "O desenvolvimento desta versão interna foi apoiado por agente no Cursor usando GPT-5.5, mas isso não é uma dependência da aplicação executada pelo usuário. Futuras versões podem conectar Ollama, OpenAI, Anthropic ou outro provedor, desde que haja política de fonte, auditoria e rastreabilidade.",
    ], s)

    section(story, "9. Limitações e Cuidados", [
        "Parte dos dados é demonstrativa/estimada. A interface sinaliza qualidade do dado como Oficial, Estimado ou Derivado Sinidu+Clima.",
        "Relatórios não substituem laudos de engenharia, modelagem hidrológica/hidrodinâmica oficial, parecer jurídico nem validação técnica municipal.",
        "Quando não há fonte oficial, caso análogo verificável ou Plano Diretor legível, o sistema deixa o campo vazio e explica a lacuna.",
    ], s)

    build_pdf("Sinidu_Clima_Documentacao_Tecnica.pdf", story)


def simple_doc():
    s = styles()
    story = cover(
        "Sinidu+Clima - Explicação Simplificada",
        "O que foi feito no sistema, em linguagem direta para pessoas fora da área de tecnologia",
        s,
    )

    section(story, "1. O que é o Sinidu+Clima?", [
        "O Sinidu+Clima é uma plataforma demonstrativa para ajudar municípios a entenderem riscos urbanos e climáticos. Ela reúne mapa, indicadores, simulações e relatórios para apoiar decisões públicas.",
        "A ideia central é transformar dados espalhados em uma leitura simples: onde há mais risco, quais áreas podem ser atingidas por chuva forte, que dados ainda faltam e quais ações podem ser priorizadas.",
    ], s)

    section(story, "2. O que aparece na tela?", [
        "O sistema tem um painel executivo, um mapa interativo, simulações, assistente textual e casos de sucesso. O usuário escolhe um município e pode ligar várias camadas ao mesmo tempo para cruzar informações.",
    ], s)
    story.append(bullets([
        "Painel executivo: mostra população, área, densidade, renda estimada, desastres, alertas e maturidade dos dados.",
        "Mapa: mostra bairros, riscos, áreas afetadas, alertas, desastres e lacunas de dados.",
        "Simulações: permite testar chuva forte, aumento de asfalto/impermeabilização, perda de vegetação e déficit de drenagem.",
        "Plano de ação sugerido: sugere ações proporcionais ao tamanho do cenário simulado.",
        "Comparação: compara municípios para apoiar prioridades.",
    ], s["BodyCustom"]))

    section(story, "3. Quais municípios estão na versão interna?", [
        "A primeira versão trabalha com Recife, Caroebe, Salvador, Porto Alegre e João Pessoa. Esses municípios foram usados para demonstrar diferentes realidades urbanas, climáticas e institucionais.",
    ], s)

    section(story, "4. De onde vêm os dados?", [
        "O sistema usa dados carregados no banco e referências a bases públicas. Quando uma base ainda não está integrada, isso aparece como lacuna. Quando o dado é aproximado, aparece como Estimado.",
    ], s)
    story.append(bullets([
        "IBGE: população, território e dados socioeconômicos.",
        "S2ID: histórico de desastres.",
        "CEMADEN e GeoRiscos: alertas e risco.",
        "MapBiomas: vegetação, área urbana e corpos d'água.",
        "SNIS/SINISA: saneamento e drenagem.",
        "Sentinel-2/STAC: imagens de satélite recentes quando disponíveis.",
        "Planos Diretores municipais: regras urbanísticas e limites legais quando há fonte oficial legível.",
    ], s["BodyCustom"]))

    section(story, "5. O que significa a qualidade do dado?", [
        "O sistema não trata todos os dados como se tivessem o mesmo nível de confiança. Por isso, cada camada pode aparecer com um selo.",
    ], s)
    table(story, [
        ["Selo", "Significado"],
        ["Oficial", "Dado vindo de fonte pública ou institucional reconhecida."],
        ["Estimado", "Dado aproximado usado para demonstração ou enquanto a base oficial não entra."],
        ["Derivado Sinidu+Clima", "Resultado calculado pelo sistema a partir de outras informações."],
    ], [4.2 * cm, 11.0 * cm], s)

    section(story, "6. Como funcionam as simulações?", [
        "O usuário pode testar quatro situações: chuva forte, aumento de asfalto, perda de vegetação e déficit de drenagem. Em cada caso, o sistema cruza o valor informado com mapa, bairros, população e camadas de risco disponíveis.",
        "O resultado é uma mancha provável de área atingida. Ela serve para planejamento e conversa técnica, mas não substitui estudos oficiais de engenharia, hidrologia, hidráulica ou microclima.",
    ], s)

    section(story, "7. O que é o plano de ação sugerido?", [
        "Depois de simular um cenário, o usuário pode gerar um plano sugerido. Esse plano mostra a gravidade do evento, ações imediatas, ações de curto prazo e medidas estruturais.",
        "O plano também tenta olhar o passado do próprio município e municípios parecidos. Se não houver caso confiável ou fonte oficial, o relatório deixa o campo vazio e explica que não há evidência suficiente.",
    ], s)

    section(story, "8. O sistema usa inteligência artificial?", [
        "A versão atual tem um assistente textual, mas ele não usa um grande modelo de linguagem rodando dentro do sistema. Ele responde por regras, consultas ao banco e busca simples em textos de casos cadastrados.",
        "O desenvolvimento da versão interna foi apoiado por um agente de programação no Cursor com GPT-5.5. Isso ajudou a construir o sistema, mas não significa que o usuário final esteja usando GPT dentro da aplicação.",
    ], s)

    section(story, "9. O que o sistema não deve prometer?", [
        "O Sinidu+Clima não substitui equipe técnica, Defesa Civil, engenharia, jurídico municipal ou modelagem oficial. Ele organiza dados, mostra riscos e ajuda a formular perguntas melhores.",
        "Quando faltar dado, o sistema deve dizer que falta dado. Essa é uma parte importante da proposta: mostrar não só o que se sabe, mas também o que ainda precisa ser integrado.",
    ], s)

    section(story, "10. Em uma frase", [
        "O Sinidu+Clima é uma ferramenta para enxergar riscos urbanos e climáticos de forma integrada, ajudando o município a decidir melhor, com transparência sobre fontes, limitações e lacunas.",
    ], s)

    build_pdf("Sinidu_Clima_Explicacao_Simplificada.pdf", story)


if __name__ == "__main__":
    technical_doc()
    simple_doc()
    print(OUT_DIR / "Sinidu_Clima_Documentacao_Tecnica.pdf")
    print(OUT_DIR / "Sinidu_Clima_Explicacao_Simplificada.pdf")
