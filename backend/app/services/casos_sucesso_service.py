"""Casos de sucesso municipais — seed, embeddings Mistral e busca semântica pgvector."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import CasoSucesso, Municipio
from rag.config import EMBEDDING_DIM
from rag.embeddings import embed_text, embed_texts

logger = logging.getLogger(__name__)

REGIAO_POR_UF: dict[str, str] = {
    "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

POP_FAIXAS: dict[str, tuple[int, int]] = {
    "pequeno": (0, 100_000),
    "medio": (100_000, 500_000),
    "grande": (500_000, 1_000_000),
    "metropole": (1_000_000, 50_000_000),
}

SEED_CASES: list[dict[str, Any]] = [
    {
        "titulo": "Piscinões de detenção pluvial — PAC Drenagem",
        "municipio_nome": "Guarulhos", "municipio_uf": "SP", "populacao_aprox": 1_345_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Alagamentos recorrentes em avenidas de fundo de vale e bairros densos durante temporais de verão, com perdas materiais e interrupção do transporte.",
        "solucao_implementada": "Construção de piscinões de detenção e microbacias de retenção integradas ao PAC Seleções Drenagem Urbana, com obras de macro e microdrenagem e limpeza de córregos.",
        "resultado_mensuravel": "Redução reportada de até 60% nos pontos críticos de alagamento nas áreas intervenidas; melhoria do escoamento em dias de chuva intensa.",
        "custo_estimado_reais": 8_000_000, "programa_financiador": "PAC Seleções — Drenagem Urbana",
        "ano_implementacao": 2019,
        "fonte_referencia": "https://www.gov.br/cidades/pt-br/assuntos/pac-selecoes/drenagem-urbana",
        "tags": ["drenagem", "piscinão", "alagamento", "PAC"],
    },
    {
        "titulo": "Contenção de encostas pós-desastre 2022",
        "municipio_nome": "Petrópolis", "municipio_uf": "RJ", "populacao_aprox": 305_000,
        "tipo_intervencao": "encosta",
        "problema_original": "Deslizamentos catastróficos em encostas urbanas após precipitação extrema em fevereiro de 2022, com centenas de óbitos e desabrigados.",
        "solucao_implementada": "Programa emergencial de obras de estabilização (solo grampeado, drenagem superficial, muretas de contenção) e reassentamento em áreas seguras, coordenado pelo Governo do Estado e MDR.",
        "resultado_mensuravel": "Estabilização de dezenas de encostas críticas; redução de evacuações recorrentes nos bairros priorizados; reassentamento de famílias em risco iminente.",
        "custo_estimado_reais": 120_000_000, "programa_financiador": "MDR / Governo RJ — reconstrução pós-2022",
        "ano_implementacao": 2022,
        "fonte_referencia": "https://www.gov.br/mdr/pt-br/assuntos/defesa-civil-desastres/desastres/petropolis-rj-2022",
        "tags": ["encosta", "deslizamento", "contenção", "reassentamento"],
    },
    {
        "titulo": "Parques lineares e bacias inundáveis urbanas",
        "municipio_nome": "Curitiba", "municipio_uf": "PR", "populacao_aprox": 1_945_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Inundações na bacia do Rio Barigui e áreas centrais de baixa declividade com aumento de impermeabilização.",
        "solucao_implementada": "Parques inundáveis (Barigui, Tingui) como bacias de retenção temporária, jardins de chuva e corredores verdes integrados ao planejamento urbano.",
        "resultado_mensuravel": "Controle eficaz de cheias no centro; recarga de aquíferos locais; valorização do entorno com áreas verdes de lazer.",
        "custo_estimado_reais": 45_000_000, "programa_financiador": "Municipal / PNUD — urbanismo sustentável",
        "ano_implementacao": 2015,
        "fonte_referencia": "https://www.curitiba.pr.gov.br/conteudo/parques-lineares/123",
        "tags": ["parque inundável", "Barigui", "drenagem verde"],
    },
    {
        "titulo": "Parceria nos Morros — estabilização comunitária",
        "municipio_nome": "Recife", "municipio_uf": "PE", "populacao_aprox": 1_653_000,
        "tipo_intervencao": "encosta",
        "problema_original": "Deslizamentos em morros habitados de alta densidade durante chuvas de inverno no litoral metropolitano.",
        "solucao_implementada": "Programa Parceria nos Morros: município fornece materiais e assessoria; moradores executam mutirões de estabilização, canaletas e geogrelhas.",
        "resultado_mensuravel": "Mais de 1.500 encostas estabilizadas; redução de ~80% nos incidentes fatais nas áreas cobertas; baixo custo por m².",
        "custo_estimado_reais": 12_000_000, "programa_financiador": "Prefeitura do Recife / Defesa Civil",
        "ano_implementacao": 2010,
        "fonte_referencia": "https://www.recife.pe.gov.br/programa-parceria-nos-morros",
        "tags": ["encosta", "mutirão", "comunitário"],
    },
    {
        "titulo": "Regularização fundiária em áreas de risco",
        "municipio_nome": "Recife", "municipio_uf": "PE", "populacao_aprox": 1_653_000,
        "tipo_intervencao": "habitacao",
        "problema_original": "Ocupações irregulares em áreas de risco de inundação e encosta, dificultando investimento em infraestrutura e evacuação.",
        "solucao_implementada": "Programa de regularização fundiária urbana (REURB) integrado a obras de drenagem e reassentamento voluntário em conjuntos habitacionais.",
        "resultado_mensuravel": "Titulação de milhares de lotes; redução de conflitos fundiários; viabilização de obras de drenagem em áreas antes informais.",
        "custo_estimado_reais": 25_000_000, "programa_financiador": "MCID — REURB / Fundo Nacional de Habitação",
        "ano_implementacao": 2018,
        "fonte_referencia": "https://www.gov.br/cidades/pt-br/assuntos/habitacao/reurb",
        "tags": ["REURB", "habitação", "regularização"],
    },
    {
        "titulo": "Piscinões subterrâneos com telemetria",
        "municipio_nome": "Belo Horizonte", "municipio_uf": "MG", "populacao_aprox": 2_530_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Inundações relâmpago em avenidas de fundo de vale (Av. Vilarinho) por temporais concentrados.",
        "solucao_implementada": "Bacias de detenção subterrâneas (piscinões) com comportas automatizadas e monitoramento por telemetria integrado à Defesa Civil.",
        "resultado_mensuravel": "Retenção de milhões de litros de escoamento superficial; redução de enchentes repentinas nas avenidas críticas.",
        "custo_estimado_reais": 35_000_000, "programa_financiador": "PBH / BNDES — infraestrutura urbana",
        "ano_implementacao": 2016,
        "fonte_referencia": "https://prefeitura.pbh.gov.br/noticias/piscinao-subterraneo-vilarinho",
        "tags": ["piscinão", "telemetria", "inundação relâmpago"],
    },
    {
        "titulo": "Plano Diretor Climático municipal",
        "municipio_nome": "Fortaleza", "municipio_uf": "CE", "populacao_aprox": 2_703_000,
        "tipo_intervencao": "planejamento_climatico",
        "problema_original": "Aumento de eventos extremos (secas, chuvas intensas) sem integração climática ao planejamento urbano.",
        "solucao_implementada": "Plano Diretor Climático de Fortaleza (PDCF), alinhado ao Plano Clima, com metas de adaptação, drenagem sustentável e redução de ilhas de calor.",
        "resultado_mensuravel": "Marco legal municipal para obras resilientes; priorização de bairros costeiros e áreas de alagamento crônico.",
        "custo_estimado_reais": 3_000_000, "programa_financiador": "Prefeitura / ICLEI / PNUD",
        "ano_implementacao": 2021,
        "fonte_referencia": "https://www.fortaleza.ce.gov.br/noticias/plano-diretor-climatico",
        "tags": ["plano climático", "adaptação", "PDDU"],
    },
    {
        "titulo": "Macrodrenagem e desassoreamento de igarapés",
        "municipio_nome": "Belém", "municipio_uf": "PA", "populacao_aprox": 1_499_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Alagamentos crônicos em bairros ribeirinhos e centros com igarapés assoreados e marés altas combinadas a chuvas.",
        "solucao_implementada": "Obras de macrodrenagem, desassoreamento de igarapés (Tucunduba, Guamá) e sistemas de bombeamento em pontos críticos.",
        "resultado_mensuravel": "Melhoria do escoamento em áreas historicamente alagadas; redução de tempo de inundação em eventos de chuva moderada.",
        "custo_estimado_reais": 55_000_000, "programa_financiador": "PAC / Governo PA",
        "ano_implementacao": 2014,
        "fonte_referencia": "https://www.gov.br/cidades/pt-br/assuntos/pac-selecoes/drenagem-urbana",
        "tags": ["macrodrenagem", "igarapé", "Amazônia"],
    },
    {
        "titulo": "Prevenção de deslizamentos em encostas costeiras",
        "municipio_nome": "Angra dos Reis", "municipio_uf": "RJ", "populacao_aprox": 207_000,
        "tipo_intervencao": "encosta",
        "problema_original": "Deslizamentos em encostas de Mata Atlântica ocupadas irregularmente, agravados por chuvas de verão.",
        "solucao_implementada": "Mapeamento de risco geológico, obras de contenção, drenagem em encostas e plano de evacuação com sirenes e rotas seguras.",
        "resultado_mensuravel": "Redução de ocorrências graves em áreas estabilizadas; evacuação preventiva estruturada em eventos de alto risco.",
        "custo_estimado_reais": 18_000_000, "programa_financiador": "Defesa Civil RJ / MDR",
        "ano_implementacao": 2017,
        "fonte_referencia": "https://www.gov.br/mdr/pt-br/assuntos/defesa-civil-desastres",
        "tags": ["encosta", "Mata Atlântica", "evacuação"],
    },
    {
        "titulo": "Contenção de encostas argilosas",
        "municipio_nome": "Salvador", "municipio_uf": "BA", "populacao_aprox": 2_900_000,
        "tipo_intervencao": "encosta",
        "problema_original": "Deslizamentos em encostas argilosas durante chuvas intensas e prolongadas na orla e periferia.",
        "solucao_implementada": "Obras de contenção com solo grampeado, cortinas atirantadas, concreto projetado e macrodrenagem integrada.",
        "resultado_mensuravel": "Mais de 100 encostas de alto risco mitigadas; eliminação de evacuações emergenciais sistemáticas em bairros priorizados.",
        "custo_estimado_reais": 90_000_000, "programa_financiador": "Governo BA / MDR — encostas",
        "ano_implementacao": 2013,
        "fonte_referencia": "https://www.salvador.ba.gov.br/obras/contencao-encostas",
        "tags": ["encosta", "contenção", "Salvador"],
    },
    {
        "titulo": "Corredor verde Parque Capibaribe",
        "municipio_nome": "Recife", "municipio_uf": "PE", "populacao_aprox": 1_653_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Ilha de calor urbana e degradação ambiental nas margens do Rio Capibaribe em área impermeabilizada.",
        "solucao_implementada": "Parque Capibaribe: corredor verde linear com ciclovias, arborização nativa e APPs nas margens do rio.",
        "resultado_mensuravel": "Redução local de até 2°C na temperatura superficial; espaços públicos resilientes à inundação.",
        "custo_estimado_reais": 40_000_000, "programa_financiador": "Prefeitura / Fundo Clima",
        "ano_implementacao": 2012,
        "fonte_referencia": "https://www.recife.pe.gov.br/parque-capibaribe",
        "tags": ["corredor verde", "Capibaribe", "adaptação"],
    },
    {
        "titulo": "Macrodrenagem e polder urbano",
        "municipio_nome": "Porto Alegre", "municipio_uf": "RS", "populacao_aprox": 1_488_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Inundações na bacia do Arroio Dilúvio e áreas centrais por chuvas extremas e deficiência de drenagem.",
        "solucao_implementada": "Obras de macrodrenagem, diques e sistemas de bombeamento; integração com plano de contingência de cheias.",
        "resultado_mensuravel": "Redução de áreas inundadas em eventos recorrentes; melhoria do tempo de resposta da Defesa Civil.",
        "custo_estimado_reais": 70_000_000, "programa_financiador": "PAC / Prefeitura POA",
        "ano_implementacao": 2018,
        "fonte_referencia": "https://www2.portoalegre.rs.gov.br/cgmur/default.php?p_secao=131",
        "tags": ["macrodrenagem", "cheia", "Sul"],
    },
    {
        "titulo": "Canais pluviais e bacias de contenção",
        "municipio_nome": "Teresina", "municipio_uf": "PI", "populacao_aprox": 866_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Alagamentos em grotas urbanas e avenidas por chuvas concentradas no semiárido úmido.",
        "solucao_implementada": "Ampliação de canais pluviais, bacias de detenção e dragagem de rios urbanos (Poti, Piauí).",
        "resultado_mensuravel": "Melhoria do escoamento em pontos críticos da zona leste; redução de danos em comércios de rua.",
        "custo_estimado_reais": 22_000_000, "programa_financiador": "PAC Drenagem / Governo PI",
        "ano_implementacao": 2016,
        "fonte_referencia": "https://www.gov.br/cidades/pt-br/assuntos/pac-selecoes/drenagem-urbana",
        "tags": ["canal pluvial", "semiárido", "drenagem"],
    },
    {
        "titulo": "Programa de encostas — Niterói",
        "municipio_nome": "Niterói", "municipio_uf": "RJ", "populacao_aprox": 515_000,
        "tipo_intervencao": "encosta",
        "problema_original": "Risco geológico elevado em encostas da Região Oceânica após desastres históricos (2010).",
        "solucao_implementada": "Programa municipal de encostas com obras geotécnicas, monitoramento e reassentamento em conjuntos do Minha Casa Minha Vida.",
        "resultado_mensuravel": "Estabilização de encostas críticas; redução de óbitos por deslizamento na Região Oceânica.",
        "custo_estimado_reais": 50_000_000, "programa_financiador": "MCID / MDR — encostas RJ",
        "ano_implementacao": 2011,
        "fonte_referencia": "https://www.niteroi.rj.gov.br/programa-de-encostas/",
        "tags": ["encosta", "Niterói", "reassentamento"],
    },
    {
        "titulo": "Habitação em encosta — Aglomerado da Serra",
        "municipio_nome": "Belo Horizonte", "municipio_uf": "MG", "populacao_aprox": 2_530_000,
        "tipo_intervencao": "habitacao",
        "problema_original": "Ocupações precárias em encostas do Aglomerado da Serra com alto risco de deslizamento.",
        "solucao_implementada": "Programa Vila Viva: urbanização integrada com contenção de encostas, pavimentação, drenagem e reassentamento.",
        "resultado_mensuravel": "Milhares de domicílios urbanizados; redução de risco geológico em áreas priorizadas.",
        "custo_estimado_reais": 200_000_000, "programa_financiador": "PBH / MCID — habitação",
        "ano_implementacao": 2009,
        "fonte_referencia": "https://prefeitura.pbh.gov.br/vilaviva",
        "tags": ["habitação", "encosta", "Vila Viva"],
    },
    {
        "titulo": "Jardins de chuva e pavimento permeável",
        "municipio_nome": "Campinas", "municipio_uf": "SP", "populacao_aprox": 1_214_000,
        "tipo_intervencao": "drenagem",
        "problema_original": "Enchentes localizadas em bairros com alta impermeabilização e rede pluvial subdimensionada.",
        "solucao_implementada": "Jardins de chuva, pavimento permeável em praças e bacias de retenção lineares em corredores viários.",
        "resultado_mensuravel": "Redução de pontos de alagamento em microbacias pilotos; aumento de infiltração local.",
        "custo_estimado_reais": 6_500_000, "programa_financiador": "Municipal / Fundo Clima",
        "ano_implementacao": 2020,
        "fonte_referencia": "https://www.campinas.sp.gov.br/servicos/meio-ambiente/drenagem-sustentavel",
        "tags": ["jardim de chuva", "SUDS", "permeável"],
    },
    {
        "titulo": "Contenção de encostas — Maceió",
        "municipio_nome": "Maceió", "municipio_uf": "AL", "populacao_aprox": 1_025_000,
        "tipo_intervencao": "encosta",
        "problema_original": "Deslizamentos em encostas de tabuleiros costeiros com ocupação vertical densa.",
        "solucao_implementada": "Obras de estabilização geotécnica, drenagem profunda e mapeamento de risco com evacuação preventiva.",
        "resultado_mensuravel": "Mitigação de encostas de alto risco; integração com sistema de alerta da Defesa Civil.",
        "custo_estimado_reais": 28_000_000, "programa_financiador": "Governo AL / MDR",
        "ano_implementacao": 2015,
        "fonte_referencia": "https://www.gov.br/mdr/pt-br/assuntos/defesa-civil-desastres",
        "tags": ["encosta", "tabuleiro", "Nordeste"],
    },
]


def regiao_from_uf(uf: str) -> str:
    return REGIAO_POR_UF.get((uf or "").upper(), "Brasil")


def embedding_source_text(case: dict[str, Any] | CasoSucesso) -> str:
    if isinstance(case, CasoSucesso):
        return " ".join(
            filter(
                None,
                [
                    case.titulo,
                    case.problema_original or case.problema,
                    case.solucao_implementada or case.solucao,
                    case.tipo_intervencao,
                    case.municipio_nome or case.municipio,
                ],
            )
        )
    return " ".join(
        filter(
            None,
            [
                case.get("titulo"),
                case.get("problema_original"),
                case.get("solucao_implementada"),
                case.get("tipo_intervencao"),
                case.get("municipio_nome"),
            ],
        )
    )


def _case_to_dict(row: CasoSucesso, *, similarity: float | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "uuid": str(row.uuid) if row.uuid else None,
        "titulo": row.titulo or f"{row.municipio_nome} — {row.tipo_intervencao or 'caso'}",
        "municipio_nome": row.municipio_nome or row.municipio,
        "municipio_uf": row.municipio_uf or row.uf,
        "municipio": row.municipio_nome or row.municipio,
        "uf": row.municipio_uf or row.uf,
        "populacao_aprox": row.populacao_aprox,
        "regiao": row.regiao,
        "tipo_intervencao": row.tipo_intervencao,
        "problema_original": row.problema_original or row.problema,
        "solucao_implementada": row.solucao_implementada or row.solucao,
        "resultado_mensuravel": row.resultado_mensuravel or row.resultado,
        "problema": row.problema_original or row.problema,
        "solucao": row.solucao_implementada or row.solucao,
        "resultado": row.resultado_mensuravel or row.resultado,
        "custo_estimado_reais": row.custo_estimado_reais,
        "programa_financiador": row.programa_financiador,
        "ano_implementacao": row.ano_implementacao,
        "fonte_referencia": row.fonte_referencia,
        "tags": row.tags or [],
        "imagem_url": row.imagem_url,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "relevance_score": round(similarity, 4) if similarity is not None else None,
        "similarity": round(similarity, 4) if similarity is not None else None,
    }


def _store_embedding(db: Session, case_id: int, vector: list[float]) -> None:
    if len(vector) != EMBEDDING_DIM:
        raise ValueError(f"Embedding deve ter {EMBEDDING_DIM} dimensões.")
    vec_literal = "[" + ",".join(str(float(x)) for x in vector) + "]"
    db.execute(
        text("UPDATE casos_sucesso SET embedding = CAST(:vec AS vector) WHERE id = :id"),
        {"vec": vec_literal, "id": case_id},
    )


def seed_casos_sucesso(db: Session, *, force: bool = False, embed: bool = True) -> dict[str, Any]:
    count = db.query(CasoSucesso).count()
    if count >= len(SEED_CASES) and not force:
        if embed:
            _ensure_embeddings(db)
        return {"seeded": 0, "total": count, "skipped": True}

    db.query(CasoSucesso).delete()
    db.commit()

    created: list[CasoSucesso] = []
    for raw in SEED_CASES:
        uf = raw["municipio_uf"]
        obj = CasoSucesso(
            titulo=raw["titulo"],
            municipio_nome=raw["municipio_nome"],
            municipio_uf=uf,
            municipio=raw["municipio_nome"],
            uf=uf,
            populacao_aprox=raw.get("populacao_aprox"),
            regiao=regiao_from_uf(uf),
            tipo_intervencao=raw.get("tipo_intervencao"),
            problema_original=raw["problema_original"],
            solucao_implementada=raw["solucao_implementada"],
            resultado_mensuravel=raw.get("resultado_mensuravel"),
            problema=raw["problema_original"],
            solucao=raw["solucao_implementada"],
            resultado=raw.get("resultado_mensuravel"),
            custo_estimado_reais=raw.get("custo_estimado_reais"),
            programa_financiador=raw.get("programa_financiador"),
            ano_implementacao=raw.get("ano_implementacao"),
            fonte_referencia=raw.get("fonte_referencia"),
            tags=raw.get("tags"),
        )
        db.add(obj)
        created.append(obj)
    db.commit()
    for obj in created:
        db.refresh(obj)

    embedded = 0
    if embed:
        embedded = _ensure_embeddings(db)
    return {"seeded": len(created), "total": db.query(CasoSucesso).count(), "embedded": embedded}


def _ensure_embeddings(db: Session) -> int:
    rows = db.query(CasoSucesso).all()
    pending = []
    for row in rows:
        has_emb = db.execute(
            text("SELECT embedding IS NOT NULL AS ok FROM casos_sucesso WHERE id = :id"),
            {"id": row.id},
        ).scalar()
        if not has_emb:
            pending.append(row)
    if not pending:
        return 0

    texts = [embedding_source_text(r) for r in pending]
    try:
        vectors = embed_texts(texts)
    except Exception as exc:
        logger.warning("Embeddings Mistral indisponíveis para casos: %s", exc)
        return 0

    for row, vec in zip(pending, vectors):
        _store_embedding(db, row.id, vec)
    db.commit()
    return len(pending)


def _build_search_query(
    query: str,
    municipio: Municipio | None = None,
) -> str:
    parts = [query.strip()]
    if municipio:
        regiao = regiao_from_uf(municipio.uf)
        parts.append(
            f"município similar população {municipio.populacao} região {regiao} {municipio.nome} {municipio.uf}"
        )
    return " ".join(parts)


def _keyword_fallback(db: Session, query: str, top_k: int, **filters) -> list[dict[str, Any]]:
    from app.services.semantic_search import SuccessCaseSearchService

    rows = SuccessCaseSearchService.search(db, query, limit=top_k * 3)
    out: list[dict[str, Any]] = []
    for item in rows:
        row = db.query(CasoSucesso).filter(CasoSucesso.id == item["id"]).first()
        if not row:
            continue
        sim = float(item.get("relevance_score") or 0) / 100.0
        d = _case_to_dict(row, similarity=sim)
        if _passes_filters(d, **filters):
            out.append(d)
        if len(out) >= top_k:
            break
    return out


def _passes_filters(
    case: dict[str, Any],
    *,
    regiao: str | None = None,
    tipo_intervencao: str | None = None,
    faixa_populacao: str | None = None,
) -> bool:
    if regiao and (case.get("regiao") or "").lower() != regiao.lower():
        return False
    if tipo_intervencao and tipo_intervencao.lower() not in (case.get("tipo_intervencao") or "").lower():
        return False
    if faixa_populacao:
        bounds = POP_FAIXAS.get(faixa_populacao.lower())
        if bounds:
            pop = case.get("populacao_aprox") or 0
            lo, hi = bounds
            if not (lo <= pop < hi):
                return False
    return True


def search_casos(
    db: Session,
    *,
    query: str,
    municipio_codigo: str | None = None,
    top_k: int = 5,
    regiao: str | None = None,
    tipo_intervencao: str | None = None,
    faixa_populacao: str | None = None,
) -> list[dict[str, Any]]:
    top_k = max(1, min(top_k, 20))
    muni: Municipio | None = None
    if municipio_codigo:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == municipio_codigo).first()
        if muni and not regiao:
            regiao = regiao_from_uf(muni.uf)

    search_text = _build_search_query(query, muni)
    filters = {
        "regiao": regiao,
        "tipo_intervencao": tipo_intervencao,
        "faixa_populacao": faixa_populacao,
    }

    try:
        query_vec = embed_text(search_text)
    except Exception as exc:
        logger.warning("Busca vetorial indisponível, fallback TF-IDF: %s", exc)
        return _keyword_fallback(db, query, top_k, **filters)

    vec_literal = "[" + ",".join(str(float(x)) for x in query_vec) + "]"
    where_clauses = ["embedding IS NOT NULL"]
    params: dict[str, Any] = {"vec": vec_literal, "top_k": top_k * 4}

    if regiao:
        where_clauses.append("LOWER(regiao) = LOWER(:regiao)")
        params["regiao"] = regiao
    if tipo_intervencao:
        where_clauses.append("LOWER(tipo_intervencao) LIKE LOWER(:tipo)")
        params["tipo"] = f"%{tipo_intervencao}%"
    if faixa_populacao and faixa_populacao.lower() in POP_FAIXAS:
        lo, hi = POP_FAIXAS[faixa_populacao.lower()]
        where_clauses.append("populacao_aprox >= :pop_lo AND populacao_aprox < :pop_hi")
        params["pop_lo"] = lo
        params["pop_hi"] = hi

    sql = f"""
        SELECT id, 1 - (embedding <=> CAST(:vec AS vector)) AS similarity
        FROM casos_sucesso
        WHERE {' AND '.join(where_clauses)}
        ORDER BY embedding <=> CAST(:vec AS vector)
        LIMIT :top_k
    """
    rows = db.execute(text(sql), params).mappings().all()
    if not rows:
        return _keyword_fallback(db, query, top_k, **filters)

    out: list[dict[str, Any]] = []
    for row in rows:
        case = db.query(CasoSucesso).filter(CasoSucesso.id == row["id"]).first()
        if case:
            out.append(_case_to_dict(case, similarity=float(row["similarity"] or 0)))
    return out[:top_k]


def get_caso(db: Session, case_id: int) -> dict[str, Any] | None:
    row = db.query(CasoSucesso).filter(CasoSucesso.id == case_id).first()
    return _case_to_dict(row) if row else None


def list_filter_options(db: Session) -> dict[str, list[str]]:
    regioes = [r[0] for r in db.query(CasoSucesso.regiao).distinct().all() if r[0]]
    tipos = [r[0] for r in db.query(CasoSucesso.tipo_intervencao).distinct().all() if r[0]]
    programas = [r[0] for r in db.query(CasoSucesso.programa_financiador).distinct().all() if r[0]]
    return {
        "regioes": sorted(regioes),
        "tipos_intervencao": sorted(tipos),
        "programas_financiadores": sorted(programas),
        "faixas_populacao": list(POP_FAIXAS.keys()),
    }


def format_caso_referencia(caso: dict[str, Any]) -> str:
    custo = caso.get("custo_estimado_reais")
    custo_txt = f"R$ {custo / 1_000_000:.1f}M" if custo and custo >= 1_000_000 else (
        f"R$ {custo:,}".replace(",", ".") if custo else "custo não informado"
    )
    prog = caso.get("programa_financiador") or "programa municipal"
    ano = caso.get("ano_implementacao") or "?"
    res = caso.get("resultado_mensuravel") or caso.get("resultado") or ""
    return (
        f"{caso.get('municipio_nome')}/{caso.get('municipio_uf')} implementou solução similar em {ano} "
        f"via {prog} ({custo_txt}). Resultado: {res[:120]}{'…' if len(res) > 120 else ''}"
    )


def enrich_action_with_cases(
    db: Session,
    action: dict[str, Any],
    municipio: Municipio,
    *,
    top_k: int = 2,
) -> dict[str, Any]:
    tipo = action.get("titulo") or action.get("descricao") or "adaptação urbana"
    contexto = action.get("justificativa") or action.get("fonte") or ""
    regiao = regiao_from_uf(municipio.uf)
    query = (
        f"{tipo} em município de {municipio.populacao or 'N/A'} habitantes "
        f"na região {regiao} com {contexto}"
    )
    casos = search_casos(db, query=query, municipio_codigo=municipio.codigo_ibge, top_k=top_k)
    enriched = dict(action)
    enriched["casos_referencia"] = [
        {**c, "referencia_texto": format_caso_referencia(c)} for c in casos
    ]
    return enriched


def enrich_all_actions(db: Session, actions: list[dict], municipio: Municipio) -> list[dict]:
    return [enrich_action_with_cases(db, a, municipio) for a in actions]


def _scale_factor(orig_pop: int | None, target_pop: int | None) -> float:
    if not orig_pop or not target_pop or orig_pop <= 0:
        return 1.0
    return max(0.15, min(2.5, target_pop / orig_pop))


def adapt_case_for_municipio(
    db: Session,
    case_id: int,
    codigo_ibge: str,
) -> dict[str, Any]:
    caso = db.query(CasoSucesso).filter(CasoSucesso.id == case_id).first()
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not caso or not muni:
        raise ValueError("Caso ou município não encontrado.")

    case_dict = _case_to_dict(caso)
    orig_pop = caso.populacao_aprox or 500_000
    target_pop = muni.populacao or 100_000
    scale = _scale_factor(orig_pop, target_pop)
    custo_orig = caso.custo_estimado_reais or 5_000_000
    custo_est = int(custo_orig * scale)

    prompt = (
        f"Adapte esta solução urbana para outro município.\n\n"
        f"CASO ORIGINAL: {caso.municipio_nome}/{caso.municipio_uf} ({orig_pop:,} hab)\n"
        f"Título: {caso.titulo}\n"
        f"Problema: {caso.problema_original}\n"
        f"Solução: {caso.solucao_implementada}\n"
        f"Resultado: {caso.resultado_mensuravel}\n\n"
        f"MUNICÍPIO ALVO: {muni.nome}/{muni.uf} ({target_pop:,} hab, região {regiao_from_uf(muni.uf)})\n"
        f"Custo original: R$ {custo_orig/1_000_000:.1f}M\n\n"
        f"Compare os dois municípios e adapte a solução em 3-4 frases: escala, número de intervenções "
        f"estimado e custo aproximado R$ {custo_est/1_000_000:.1f}M."
    )

    try:
        from rag.providers.registry import resolve_chat_provider_with_fallback

        provider = resolve_chat_provider_with_fallback(None)
        if provider.is_available():
            text_out = provider.chat(
                [{"role": "user", "content": prompt}],
                model=provider.info().default_model,
                temperature=0.3,
                max_tokens=400,
            )
            provider_name = provider.info().label.lower()
        else:
            raise RuntimeError("Provedor IA indisponível")
    except Exception as exc:
        logger.warning("Adaptação IA indisponível: %s", exc)
        n_units = max(1, int(scale * 3))
        vol = max(500, int(2000 * scale))
        text_out = (
            f"**{caso.municipio_nome}** tem {orig_pop:,} hab e é "
            f"{'maior' if orig_pop > target_pop else 'menor'} que **{muni.nome}** ({target_pop:,} hab). "
            f"O mesmo conceito de {caso.tipo_intervencao or 'intervenção'} funciona em escala "
            f"{'menor' if scale < 1 else 'similar'}. Para {muni.nome}, estimo **{n_units}** intervenções "
            f"de ~{vol:,} m³/unidade, custo aproximado **R$ {custo_est/1_000_000:.1f}M**."
        )
        provider_name = "deterministic"

    return {
        "caso": case_dict,
        "municipio": {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
            "populacao": muni.populacao,
            "regiao": regiao_from_uf(muni.uf),
        },
        "adaptacao_ia": text_out.strip(),
        "custo_estimado_adaptado_reais": custo_est,
        "ai_provider": provider_name,
        "pergunta_sugerida": f"Como adaptar esta solução para {muni.nome}/{muni.uf}?",
    }
