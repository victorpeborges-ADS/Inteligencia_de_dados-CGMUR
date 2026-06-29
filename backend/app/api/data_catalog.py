from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Municipio, MunicipioSaneamento, MunicipioSeed
from app.data_connectors.snis_sinisa_collector import snis_status_label
from app.security.municipio_access import filter_seed_query, get_accessible_municipio
from app.security.auth import User, require_role, Role
from app.services.audit_service import resolve_actor
from app.services.data_catalog_engine import resolve_catalog_status
from app.config import settings

router = APIRouter()

STATUS_SCORE = {
    "Integrado": 1.0,
    "Estimado": 0.6,
    "Em integracao": 0.35,
    "Ausente": 0.0,
}

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


def coverage_for_code(codigo_ibge: str, db: Session | None = None):
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first() if db else None
    from app.models import MunicipioSeed

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


def recommendation_for_status(status: str, nome: str):
    if status == "Integrado":
        return f"Manter rotina de atualizacao para {nome}."
    if status == "Estimado":
        return f"Substituir estimativa por carga oficial de {nome}."
    if status == "Em integracao":
        return f"Priorizar conector e validacao institucional de {nome}."
    return f"Mapear responsavel e iniciar acordo de compartilhamento para {nome}."


@router.get("/coverage")
def get_data_coverage(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    maturidade, bases, gaps = coverage_for_code(muni.codigo_ibge, db)
    return {
        "municipio": {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
        },
        "maturidade_percentual": maturidade,
        "classificacao": "Alta" if maturidade >= 75 else ("Media" if maturidade >= 50 else "Baixa"),
        "bases": bases,
        "lacunas_prioritarias": gaps[:5],
        "resumo": f"{muni.nome} possui {maturidade}% de maturidade informacional no radar Sinidu+Clima.",
    }


@router.get("/national")
def get_national_data_coverage(
    request: Request,
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(Role.GESTOR)),
):
    """Panorama agregado do catálogo nos municípios prioritários (respeita multi-tenant)."""
    actor = resolve_actor(request)
    query = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge.in_(settings.TARGET_IBGE_CODES))
    query = filter_seed_query(query, actor)
    seeds = query.order_by(MunicipioSeed.prioridade.asc()).all()

    if not seeds:
        raise HTTPException(status_code=404, detail="Nenhum município prioritário no escopo do perfil.")

    base_totals: dict[str, dict[str, int]] = {}
    municipio_rows = []
    gap_counter: dict[str, int] = {}

    for seed in seeds:
        maturidade, bases, gaps = coverage_for_code(seed.codigo_ibge, db)
        municipio_rows.append({
            "codigo_ibge": seed.codigo_ibge,
            "nome": seed.nome,
            "uf": seed.uf,
            "maturidade_percentual": maturidade,
            "onboarding_status": seed.onboarding_status,
            "lacunas_count": len(gaps),
        })
        for item in bases:
            bucket = base_totals.setdefault(item["id"], {"nome": item["nome"], "Integrado": 0, "Estimado": 0, "Em integracao": 0, "Ausente": 0})
            status = item["status"]
            if status in bucket:
                bucket[status] += 1
        for gap in gaps:
            gap_counter[gap["id"]] = gap_counter.get(gap["id"], 0) + 1

    total = len(seeds)
    media_maturidade = round(sum(row["maturidade_percentual"] for row in municipio_rows) / total)
    bases_summary = []
    for base_id, counts in base_totals.items():
        integrado_pct = round((counts["Integrado"] / total) * 100)
        bases_summary.append({
            "id": base_id,
            "nome": counts["nome"],
            "integrado_pct": integrado_pct,
            "totals": {k: v for k, v in counts.items() if k != "nome"},
        })
    bases_summary.sort(key=lambda row: row["integrado_pct"])

    top_gaps = sorted(
        [{"id": k, "nome": base_totals[k]["nome"], "municipios": v} for k, v in gap_counter.items()],
        key=lambda row: row["municipios"],
        reverse=True,
    )[:8]

    return {
        "total_municipios": total,
        "media_maturidade_percentual": media_maturidade,
        "classificacao": "Alta" if media_maturidade >= 75 else ("Media" if media_maturidade >= 50 else "Baixa"),
        "bases": bases_summary,
        "lacunas_frequentes": top_gaps,
        "municipios": sorted(municipio_rows, key=lambda row: row["maturidade_percentual"]),
        "resumo": f"Panorama de {total} municípios prioritários — maturidade média {media_maturidade}%.",
    }
