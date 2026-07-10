"""Cobertura e maturidade do catálogo — lógica compartilhada (sem dependência da API)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.data_connectors.snis_sinisa_collector import snis_status_label
from app.models import Municipio, MunicipioSaneamento, MunicipioSeed
from app.services.catalog_source_registry import STATUS_SCORE
from app.services.data_catalog_engine import resolve_catalog_status

BASE_CATALOG = [
    {"id": "ibge_cidades", "nome": "Cidades@ / IBGE", "grupo": "Dados urbanos e socioeconomicos", "camada": "municipio"},
    {"id": "snis_sinisa", "nome": "SNIS/SINISA", "grupo": "Saneamento", "camada": "saneamento_drenagem"},
    {"id": "s2id", "nome": "S2ID / SEDEC", "grupo": "Desastres", "camada": "desastres"},
    {"id": "mapbiomas", "nome": "MapBiomas", "grupo": "Clima e uso do solo", "camada": "cobertura"},
    {"id": "cemaden_georiscos", "nome": "CEMADEN / GeoRiscos", "grupo": "Risco e alertas", "camada": "alertas"},
    {"id": "adapta_brasil", "nome": "AdaptaBrasil / INPE", "grupo": "Adaptacao climatica", "camada": "adaptacao_climatica"},
    {"id": "geosgb", "nome": "GeoSGB / CPRM", "grupo": "Geologia", "camada": "vulnerabilidade"},
    {"id": "sinter", "nome": "SINTER / Receita Federal", "grupo": "Cadastro territorial", "camada": "socioeconomico"},
    {"id": "munic", "nome": "MUNIC / IBGE", "grupo": "Capacidade institucional", "camada": "prioridade_planejamento"},
    {"id": "sirene", "nome": "SIRENE / MCTI", "grupo": "Emissoes", "camada": None},
    {"id": "inde", "nome": "INDE", "grupo": "Infraestrutura de dados espaciais", "camada": "municipio"},
    {"id": "brasil_mais", "nome": "Brasil MAIS", "grupo": "Monitoramento territorial", "camada": None},
    {"id": "inep_censo_escolar", "nome": "INEP Censo Escolar", "grupo": "Educação", "camada": "educacao"},
    {"id": "incra_quilombos", "nome": "INCRA Quilombos", "grupo": "Territórios especiais", "camada": "territorios_especiais"},
    {"id": "funai_ti", "nome": "FUNAI Terras Indígenas", "grupo": "Territórios especiais", "camada": "territorios_especiais"},
    {"id": "ibge_aglomerados", "nome": "IBGE Aglomerados Subnormais", "grupo": "Territórios especiais", "camada": "territorios_especiais"},
    {"id": "ibge_singedlab_rs", "nome": "IBGE SINGED Lab (RS 2024)", "grupo": "Exposição oficial", "camada": "desastres"},
]

MUNICIPALITY_STATUS = {
    "2611606": {
        "ibge_cidades": "Integrado",
        "s2id": "Integrado",
        "mapbiomas": "Integrado",
        "cemaden_georiscos": "Integrado",
        "adapta_brasil": "Estimado",
        "geosgb": "Em integracao",
        "sinter": "Estimado",
        "munic": "Em integracao",
        "sirene": "Ausente",
        "inde": "Integrado",
        "brasil_mais": "Em integracao",
    },
    "2927408": {
        "ibge_cidades": "Integrado",
        "s2id": "Integrado",
        "mapbiomas": "Integrado",
        "cemaden_georiscos": "Estimado",
        "adapta_brasil": "Estimado",
        "geosgb": "Em integracao",
        "sinter": "Estimado",
        "munic": "Em integracao",
        "sirene": "Ausente",
        "inde": "Integrado",
        "brasil_mais": "Em integracao",
    },
    "4314902": {
        "ibge_cidades": "Integrado",
        "s2id": "Integrado",
        "mapbiomas": "Integrado",
        "cemaden_georiscos": "Estimado",
        "adapta_brasil": "Em integracao",
        "geosgb": "Estimado",
        "sinter": "Estimado",
        "munic": "Em integracao",
        "sirene": "Ausente",
        "inde": "Integrado",
        "brasil_mais": "Em integracao",
    },
    "2507507": {
        "ibge_cidades": "Integrado",
        "s2id": "Estimado",
        "mapbiomas": "Integrado",
        "cemaden_georiscos": "Estimado",
        "adapta_brasil": "Em integracao",
        "geosgb": "Em integracao",
        "sinter": "Estimado",
        "munic": "Em integracao",
        "sirene": "Ausente",
        "inde": "Integrado",
        "brasil_mais": "Ausente",
    },
    "1400233": {
        "ibge_cidades": "Integrado",
        "s2id": "Estimado",
        "mapbiomas": "Estimado",
        "cemaden_georiscos": "Em integracao",
        "adapta_brasil": "Em integracao",
        "geosgb": "Ausente",
        "sinter": "Estimado",
        "munic": "Ausente",
        "sirene": "Ausente",
        "inde": "Estimado",
        "brasil_mais": "Ausente",
    },
    "5201108": {
        "ibge_cidades": "Integrado",
        "s2id": "Integrado",
        "mapbiomas": "Integrado",
        "cemaden_georiscos": "Estimado",
        "adapta_brasil": "Em integracao",
        "geosgb": "Em integracao",
        "sinter": "Estimado",
        "munic": "Em integracao",
        "sirene": "Ausente",
        "inde": "Integrado",
        "brasil_mais": "Em integracao",
    },
    "4113700": {
        "ibge_cidades": "Integrado",
        "s2id": "Integrado",
        "mapbiomas": "Integrado",
        "cemaden_georiscos": "Estimado",
        "adapta_brasil": "Em integracao",
        "geosgb": "Estimado",
        "sinter": "Estimado",
        "munic": "Em integracao",
        "sirene": "Ausente",
        "inde": "Integrado",
        "brasil_mais": "Em integracao",
    },
}


def _snis_status(db: Session, codigo_ibge: str) -> str:
    row = db.query(MunicipioSaneamento).filter(MunicipioSaneamento.codigo_ibge == codigo_ibge).first()
    if row:
        return snis_status_label(row.data_quality)
    return "Ausente"


def recommendation_for_status(status: str, nome: str):
    if status == "Nao aplicavel":
        return f"{nome} é produto pontual do RS — não se aplica a este município."
    if status == "Integrado":
        return f"Manter rotina de atualizacao para {nome}."
    if status == "Estimado":
        return f"Substituir estimativa por carga oficial de {nome}."
    if status == "Em integracao":
        return f"Priorizar conector e validacao institucional de {nome}."
    return f"Mapear responsavel e iniciar acordo de compartilhamento para {nome}."


def coverage_for_code(codigo_ibge: str, db: Session | None = None):
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first() if db else None
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first() if db else None

    bases = []
    weighted_score = 0.0
    for item in BASE_CATALOG:
        if db is not None:
            status = resolve_catalog_status(db, codigo_ibge, item["id"], muni=muni, seed=seed)
        else:
            status = MUNICIPALITY_STATUS.get(codigo_ibge, {}).get(item["id"], "Ausente")
        score = STATUS_SCORE.get(status, 0.0)
        weighted_score += score
        bases.append({
            **item,
            "status": status,
            "score": score,
            "recomendacao": recommendation_for_status(status, item["nome"]),
        })

    maturidade = round((weighted_score / len(BASE_CATALOG)) * 100)
    gaps = [item for item in bases if item["status"] in ("Ausente", "Em integracao")]
    return maturidade, bases, gaps
