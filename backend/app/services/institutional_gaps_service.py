"""Agregação nacional das lacunas institucionais (A.1–A.6)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_TARGET_CODES, ctm_registry_stats
from app.models import Bairro, Municipio, MunicipioSeed
from app.services.catalog_coverage import BASE_CATALOG
from app.services.catalog_source_registry import FONTE_REGISTRY
from app.services.data_catalog_engine import resolve_catalog_status

STATUS_BUCKETS = ("Integrado", "Estimado", "Em integracao", "Ausente", "Nao aplicavel")

INSTITUTIONAL_GAP_IDS: list[tuple[str, int]] = [
    ("geosgb", 1),
    ("brasil_mais", 2),
    ("sirene", 3),
    ("adapta_brasil", 4),
    ("sinter", 5),
]

CTM_OFFICIAL_MALHA = frozenset({"prefeitura_oficial", "geoportal_municipal"})

_BASE_NAMES = {item["id"]: item["nome"] for item in BASE_CATALOG}


def _empty_totals() -> dict[str, int]:
    return {status: 0 for status in STATUS_BUCKETS}


def _gap_nome(fonte_id: str) -> str:
    return _BASE_NAMES.get(fonte_id) or FONTE_REGISTRY.get(fonte_id, {}).get("descricao_curta", fonte_id)


def _summarize_catalog_gap(db: Session, codigos: list[str], fonte_id: str, rank: int) -> dict[str, Any]:
    meta = FONTE_REGISTRY.get(fonte_id, {})
    totals = _empty_totals()
    for code in codigos:
        status = resolve_catalog_status(db, code, fonte_id)
        if status in totals:
            totals[status] += 1

    total = len(codigos)
    integrado = totals["Integrado"]
    lacuna = totals["Ausente"] + totals["Em integracao"]
    proxy_ativo = integrado == 0 and totals["Estimado"] > 0

    return {
        "rank": rank,
        "fonte_id": fonte_id,
        "nome": _gap_nome(fonte_id),
        "total_municipios": total,
        "integrado_count": integrado,
        "integrado_pct": round((integrado / total) * 100) if total else 0,
        "lacuna_municipios": lacuna,
        "status_totals": totals,
        "etl_ready": bool(meta.get("integravel_etl")),
        "impacto_score_pts": meta.get("impacto_score_pts"),
        "dificuldade": meta.get("dificuldade"),
        "requisito": meta.get("requisito"),
        "proxy_ativo": proxy_ativo,
        "progress_label": f"{integrado}/{total} Integrado",
    }


def _summarize_ctm_gap(db: Session, codigos: list[str]) -> dict[str, Any]:
    scope = [code for code in CTM_TARGET_CODES if code in set(codigos)]
    totals = _empty_totals()
    ctm_cadastrada = 0
    malha_operacional = 0
    importado_prefeitura = 0

    for code in scope:
        if code in CTM_BY_CODE:
            ctm_cadastrada += 1

        muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
        if not muni:
            totals["Ausente"] += 1
            continue

        bcount = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
        seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
        malha_fonte = seed.malha_fonte if seed else None

        if malha_fonte in CTM_OFFICIAL_MALHA:
            importado_prefeitura += 1
            totals["Integrado"] += 1
        elif bcount >= 4:
            malha_operacional += 1
            totals["Estimado"] += 1
        elif code in CTM_BY_CODE:
            totals["Em integracao"] += 1
        else:
            totals["Ausente"] += 1

    total = len(scope)
    integrado = totals["Integrado"]
    lacuna = totals["Ausente"] + totals["Em integracao"]
    registry = ctm_registry_stats()

    return {
        "rank": 6,
        "fonte_id": "ctm_utb",
        "nome": "CTM / UTB municipal",
        "total_municipios": total,
        "integrado_count": integrado,
        "integrado_pct": round((integrado / total) * 100) if total else 0,
        "lacuna_municipios": lacuna,
        "status_totals": totals,
        "etl_ready": True,
        "impacto_score_pts": 2,
        "dificuldade": "Técnica + prefeitura",
        "requisito": "Malha poligonal oficial (CTM/UTB) ou geoportal municipal aberto",
        "proxy_ativo": integrado == 0 and totals["Estimado"] > 0,
        "progress_label": (
            f"{importado_prefeitura + malha_operacional}/{total} malha operacional "
            f"({importado_prefeitura} oficial)"
        ),
        "ctm_cadastrada_count": ctm_cadastrada,
        "ctm_sem_fonte_count": int(registry["sem_fonte"]),
        "ctm_por_kind": registry["por_kind"],
        "malha_operacional_count": malha_operacional,
        "importado_prefeitura_count": importado_prefeitura,
        "escopo_label": f"{total} municípios BAIXA/MÉDIA maturidade",
    }


def build_ctm_operational_summary(db: Session) -> dict[str, Any]:
    """Resumo compacto CTM para painel Sistema (pós-batch)."""
    gap = _summarize_ctm_gap(db, CTM_TARGET_CODES)
    registry = ctm_registry_stats()
    return {
        "total_alvo": gap["total_municipios"],
        "fontes_cadastradas": gap["ctm_cadastrada_count"],
        "sem_fonte": gap.get("ctm_sem_fonte_count", registry["sem_fonte"]),
        "importado_prefeitura": gap["importado_prefeitura_count"],
        "malha_operacional": gap["malha_operacional_count"],
        "lacuna_municipios": gap["lacuna_municipios"],
        "por_kind": gap.get("ctm_por_kind", registry["por_kind"]),
        "progress_label": gap["progress_label"],
        "escopo_label": gap["escopo_label"],
    }


def build_institutional_gaps_summary(db: Session, codigos: list[str]) -> dict[str, Any]:
    """Panorama nacional das lacunas A.1–A.6 para o conjunto de municípios informado."""
    ordered_codes = list(dict.fromkeys(codigos))
    gaps = [_summarize_catalog_gap(db, ordered_codes, fonte_id, rank) for fonte_id, rank in INSTITUTIONAL_GAP_IDS]
    gaps.append(_summarize_ctm_gap(db, ordered_codes))

    top_lacuna = max(gaps, key=lambda row: row["lacuna_municipios"])
    etl_ready_count = sum(1 for row in gaps if row.get("etl_ready"))

    return {
        "total_municipios": len(ordered_codes),
        "gaps": gaps,
        "meta_maturidade": {
            "baseline_pct": 77,
            "target_pct": 84,
            "label": "Meta nacional 77% → 84% (GeoSGB + Brasil MAIS)",
        },
        "etl_ready_fontes": etl_ready_count,
        "resumo": (
            f"{len(ordered_codes)} municípios — maior lacuna: {top_lacuna['nome']} "
            f"({top_lacuna['lacuna_municipios']} com Ausente/Em integração)."
        ),
    }
