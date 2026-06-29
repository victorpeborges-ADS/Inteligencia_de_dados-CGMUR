"""Sincronização de fontes externas estendidas (AdaptaBrasil, GeoSGB, SIRENE, Brasil MAIS).

Deriva indicadores a partir de dados já carregados no PostGIS quando APIs institucionais
não estão disponíveis, com `data_quality` explícito (estimado / referencia_derivada).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import (
    CoberturaVegetalMapBiomas,
    MapBiomasMunicipalStat,
    Municipio,
    MunicipioFonteExterna,
    MunicipioIbge,
)

# Fatores de emissão simplificados (tCO2/ habitante/ano) — proxy SIRENE até inventário oficial
_EMISSAO_PER_CAPITA_TCO2 = 1.8


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _quality_label(score: float | None, *, min_integrado: float = 0.65) -> str:
    if score is None:
        return "ausente"
    if score >= min_integrado:
        return "referencia_derivada"
    if score >= 0.35:
        return "estimado"
    return "lacuna"


def _adapta_indicators(db: Session, muni: Municipio | None, codigo_ibge: str) -> dict[str, Any]:
    stats = (
        db.query(MapBiomasMunicipalStat)
        .filter(MapBiomasMunicipalStat.codigo_ibge == codigo_ibge)
        .order_by(MapBiomasMunicipalStat.ano.desc())
        .limit(5)
        .all()
    )
    vegetacao_pct = None
    if stats:
        vegetacao_pct = float(stats[0].vegetacao_pct or stats[0].floresta_pct or 0)
    elif muni:
        cob = (
            db.query(CoberturaVegetalMapBiomas)
            .filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
            .order_by(CoberturaVegetalMapBiomas.ano.desc())
            .first()
        )
        if cob:
            vegetacao_pct = float(cob.percentual_vegetacao or 0)

    if vegetacao_pct is None:
        return {"score": None, "indicadores": {}, "quality": "ausente"}

    # Score adaptação: cobertura vegetal + estabilidade da série MapBiomas
    stability = 1.0
    if len(stats) >= 2:
        vals = [float(s.vegetacao_pct or s.floresta_pct or 0) for s in stats[:3]]
        if vals:
            spread = max(vals) - min(vals)
            stability = max(0.0, 1.0 - spread / 100.0)

    score = min(1.0, (vegetacao_pct / 100.0) * 0.6 + stability * 0.4)
    return {
        "score": round(score, 4),
        "indicadores": {
            "vegetacao_pct": vegetacao_pct,
            "estabilidade_serie": round(stability, 3),
            "fonte_referencia": "MapBiomas + proxy AdaptaBrasil",
        },
        "quality": _quality_label(score),
    }


def _geosgb_indicators(db: Session, muni: Municipio | None) -> dict[str, Any]:
    if not muni:
        return {"score": None, "indicadores": {}, "quality": "ausente"}

    try:
        from app.services.analytical_engine import AnalyticalEngine

        ivc_rows = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id) or []
        iri_rows = AnalyticalEngine.calculate_flood_risk(db, muni.id) or []
        ivc_vals = [float(r.get("indice_vulnerabilidade", 0)) for r in ivc_rows if r.get("indice_vulnerabilidade") is not None]
        iri_vals = [float(r.get("indice_risco_inundacao", 0)) for r in iri_rows if r.get("indice_risco_inundacao") is not None]
        ivc = sum(ivc_vals) / len(ivc_vals) if ivc_vals else 0.0
        iri = sum(iri_vals) / len(iri_vals) if iri_vals else 0.0
    except Exception:
        ivc, iri = 0.0, 0.0

    if iri <= 0 and ivc <= 0:
        return {"score": None, "indicadores": {}, "quality": "ausente"}

    # Susceptibilidade geológica proxy: combina IRI + IVC (CPRM/GeoSGB pendente)
    score = min(1.0, iri * 0.55 + ivc * 0.45)
    return {
        "score": round(score, 4),
        "indicadores": {
            "iri_proxy": round(iri, 4),
            "ivc_proxy": round(ivc, 4),
            "fonte_referencia": "Sinidu+Clima derivado (GeoSGB/CPRM em integração)",
        },
        "quality": "estimado" if score >= 0.35 else "lacuna",
    }


def _sirene_indicators(db: Session, codigo_ibge: str, muni: Municipio | None) -> dict[str, Any]:
    ibge = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
    pop = (ibge.populacao if ibge else None) or (muni.populacao if muni else None)
    if not pop or pop <= 0:
        return {"score": None, "indicadores": {}, "quality": "ausente", "emissoes_tco2": None}

    emissoes = round(pop * _EMISSAO_PER_CAPITA_TCO2, 2)
    area = float(muni.area_km2 if muni and muni.area_km2 else (ibge.area_km2 if ibge else 0) or 1)
    densidade = pop / max(area, 0.1)
    score = min(1.0, densidade / 8000.0)  # normalização urbana

    return {
        "score": round(score, 4),
        "emissoes_tco2": emissoes,
        "indicadores": {
            "populacao": pop,
            "densidade_hab_km2": round(densidade, 1),
            "metodo": "proxy per capita SIRENE",
        },
        "quality": "estimado",
    }


def _brasil_mais_indicators(db: Session, codigo_ibge: str) -> dict[str, Any]:
    stats = (
        db.query(MapBiomasMunicipalStat)
        .filter(MapBiomasMunicipalStat.codigo_ibge == codigo_ibge)
        .order_by(MapBiomasMunicipalStat.ano.asc())
        .all()
    )
    if len(stats) < 2:
        return {"score": None, "indicadores": {}, "quality": "ausente"}

    first = stats[0]
    last = stats[-1]
    v0 = float(first.vegetacao_pct or first.floresta_pct or 0)
    v1 = float(last.vegetacao_pct or last.floresta_pct or 0)
    delta = v1 - v0
    imperv_delta = float(last.area_impermeavel_pct or 0) - float(first.area_impermeavel_pct or 0)

    # Índice monitoramento territorial: perda vegetação + impermeabilização
    stress = max(0.0, (-delta / 100.0) * 0.6 + (imperv_delta / 100.0) * 0.4)
    score = min(1.0, stress + 0.15)

    return {
        "score": round(score, 4),
        "indicadores": {
            "delta_vegetacao_pct": round(delta, 2),
            "delta_impermeavel_pct": round(imperv_delta, 2),
            "periodo_anos": f"{first.ano}-{last.ano}",
            "fonte_referencia": "MapBiomas série municipal (proxy Brasil MAIS)",
        },
        "quality": "referencia_derivada" if len(stats) >= 4 else "estimado",
    }


def collect_external_sources(db: Session, codigo_ibge: str) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    adapta = _adapta_indicators(db, muni, codigo_ibge)
    geosgb = _geosgb_indicators(db, muni)
    sirene = _sirene_indicators(db, codigo_ibge, muni)
    brasil_mais = _brasil_mais_indicators(db, codigo_ibge)

    row = db.query(MunicipioFonteExterna).filter(MunicipioFonteExterna.codigo_ibge == codigo_ibge).first()
    if not row:
        row = MunicipioFonteExterna(codigo_ibge=codigo_ibge)
        db.add(row)

    row.municipio_id = muni.id if muni else None
    row.adapta_score = adapta.get("score")
    row.adapta_indicadores = adapta.get("indicadores") or {}
    row.adapta_data_quality = adapta.get("quality", "ausente")
    row.geosgb_score = geosgb.get("score")
    row.geosgb_indicadores = geosgb.get("indicadores") or {}
    row.geosgb_data_quality = geosgb.get("quality", "ausente")
    row.sirene_emissoes_tco2 = sirene.get("emissoes_tco2")
    row.sirene_indicadores = sirene.get("indicadores") or {}
    row.sirene_data_quality = sirene.get("quality", "ausente")
    row.brasil_mais_indice = brasil_mais.get("score")
    row.brasil_mais_indicadores = brasil_mais.get("indicadores") or {}
    row.brasil_mais_data_quality = brasil_mais.get("quality", "ausente")
    row.fonte_metodo = "derivado_sinidu"
    row.sincronizado_em = _utcnow()
    row.updated_at = _utcnow()

    db.flush()
    return {
        "codigo_ibge": codigo_ibge,
        "adapta_brasil": adapta,
        "geosgb": geosgb,
        "sirene": sirene,
        "brasil_mais": brasil_mais,
    }


def sync_external_sources_batch(db: Session, codigos: list[str] | None = None) -> dict[str, Any]:
    from app.data_connectors.constants import TARGET_IBGE_CODES

    targets = codigos or TARGET_IBGE_CODES
    processed = 0
    errors: list[dict[str, str]] = []
    for codigo in targets:
        try:
            collect_external_sources(db, codigo)
            processed += 1
        except Exception as exc:
            errors.append({"codigo_ibge": codigo, "error": str(exc)})
    db.commit()
    return {"requested": len(targets), "processed": processed, "errors": errors}


def catalog_status_from_quality(quality: str | None) -> str:
    q = (quality or "ausente").lower()
    if q in ("oficial", "referencia_mapbiomas", "referencia_derivada"):
        return "Integrado"
    if q in ("estimado", "derivado"):
        return "Estimado"
    if q in ("lacuna", "em integracao", "parcial"):
        return "Em integracao"
    return "Ausente"
