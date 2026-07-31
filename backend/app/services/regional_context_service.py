"""Contexto regional municipal — mesorregião e região imediata (RM proxy) via IBGE."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.data_connectors.base import fetch_json
from app.models import Municipio, MunicipioIbge, MunicipioSeed
from app.services.municipio_audit_service import audit_municipio

logger = logging.getLogger(__name__)

IBGE_LOCALIDADES = "https://servicodados.ibge.gov.br/api/v1/localidades"


def _fetch_municipio_localidade(codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    cache_key = f"ibge:localidades:municipio:{code}"
    try:
        payload = fetch_json(
            f"{IBGE_LOCALIDADES}/municipios/{code}",
            cache_key=cache_key,
            cache_ttl=86400 * 30,
        )
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        logger.warning("IBGE localidades falhou %s: %s", code, exc)
        return {}


def _fetch_municipios_por_nivel(path: str) -> list[dict[str, Any]]:
    cache_key = f"ibge:localidades:{path}"
    try:
        payload = fetch_json(
            f"{IBGE_LOCALIDADES}/{path}",
            cache_key=cache_key,
            cache_ttl=86400 * 30,
        )
        return payload if isinstance(payload, list) else []
    except Exception as exc:
        logger.warning("IBGE localidades lista falhou %s: %s", path, exc)
        return []


def _region_block(localidade: dict[str, Any]) -> dict[str, Any] | None:
    micro = localidade.get("microrregiao") or {}
    meso = micro.get("mesorregiao") or {}
    if meso.get("id"):
        uf = (meso.get("UF") or {}).get("sigla")
        return {
            "id": int(meso["id"]),
            "nome": meso.get("nome"),
            "tipo": "mesorregiao",
            "uf": uf,
        }
    return None


def _immediate_region_block(localidade: dict[str, Any]) -> dict[str, Any] | None:
    rgi = localidade.get("regiao-imediata") or localidade.get("regiao_imediata") or {}
    if rgi.get("id"):
        uf = (rgi.get("UF") or {}).get("sigla")
        return {
            "id": int(rgi["id"]),
            "nome": rgi.get("nome"),
            "tipo": "regiao_imediata",
            "uf": uf,
        }
    return None


def _peer_codigos_ibge(localidade: dict[str, Any], escopo: str) -> list[str]:
    if escopo == "mesorregiao":
        meso = _region_block(localidade)
        if not meso:
            return []
        rows = _fetch_municipios_por_nivel(f"mesorregioes/{meso['id']}/municipios")
    else:
        rgi = _immediate_region_block(localidade)
        if not rgi:
            return []
        rows = _fetch_municipios_por_nivel(f"regioes-imediatas/{rgi['id']}/municipios")
    return [str(row["id"]).zfill(7)[:7] for row in rows if row.get("id")]


def _referencia_comparacao(db: Session, muni: Municipio) -> dict[str, Any] | None:
    peer = (
        db.query(MunicipioSeed)
        .filter(
            MunicipioSeed.codigo_ibge != muni.codigo_ibge,
            MunicipioSeed.uf == muni.uf,
        )
        .order_by(MunicipioSeed.nome.asc())
        .first()
    )
    if not peer:
        peer_row = (
            db.query(Municipio)
            .filter(Municipio.uf == muni.uf, Municipio.codigo_ibge != muni.codigo_ibge)
            .order_by(Municipio.nome.asc())
            .first()
        )
        if not peer_row:
            return None
        return {
            "codigo_ibge": peer_row.codigo_ibge,
            "nome": peer_row.nome,
            "motivo": "Referência na mesma UF (CompareModal)",
        }
    return {
        "codigo_ibge": peer.codigo_ibge,
        "nome": peer.nome,
        "motivo": "Referência na mesma UF (CompareModal)",
    }


def _municipio_metrics(db: Session, codigo_ibge: str) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if not muni:
        return {"codigo_ibge": codigo_ibge, "disponivel": False}
    audit = audit_municipio(db, muni, persist=False)
    ibge = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first()
    return {
        "codigo_ibge": codigo_ibge,
        "nome": muni.nome,
        "disponivel": True,
        "populacao": ibge.populacao if ibge else muni.populacao,
        "score_sinidu": float(seed.score_sinidu) if seed and seed.score_sinidu is not None else audit.get("score_sinidu"),
        "maturity_score": float(seed.maturity_score) if seed and seed.maturity_score is not None else None,
        "confiabilidade": audit.get("confiabilidade_geral"),
    }


def _aggregate_metrics(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    available = [m for m in metrics if m.get("disponivel")]
    if not available:
        return {"municipios_com_dados": 0}
    scores = [float(m["score_sinidu"]) for m in available if m.get("score_sinidu") is not None]
    pops = [int(m["populacao"]) for m in available if m.get("populacao")]
    maturities = [float(m["maturity_score"]) for m in available if m.get("maturity_score") is not None]
    return {
        "municipios_com_dados": len(available),
        "score_sinidu_medio": round(sum(scores) / len(scores), 1) if scores else None,
        "populacao_total": sum(pops) if pops else None,
        "maturity_score_medio": round(sum(maturities) / len(maturities), 1) if maturities else None,
    }


def _regional_geojson(
    db: Session,
    codigo_ibge: str,
    peer_codigos: list[str],
    referencia: dict[str, Any] | None,
) -> dict[str, Any]:
    ref_code = referencia.get("codigo_ibge") if referencia else None
    targets = [c for c in peer_codigos if c != codigo_ibge]
    if not targets:
        return {"type": "FeatureCollection", "features": []}

    rows = (
        db.query(
            Municipio.codigo_ibge,
            Municipio.nome,
            Municipio.uf,
            func.ST_AsGeoJSON(Municipio.geom).label("geojson"),
        )
        .filter(Municipio.codigo_ibge.in_(targets), Municipio.geom.isnot(None))
        .all()
    )

    features: list[dict[str, Any]] = []
    for row in rows:
        if not row.geojson:
            continue
        role = "referencia_comparacao" if row.codigo_ibge == ref_code else "municipio_regional"
        features.append({
            "type": "Feature",
            "geometry": json.loads(row.geojson),
            "properties": {
                "codigo_ibge": row.codigo_ibge,
                "nome": row.nome,
                "uf": row.uf,
                "feature_kind": role,
                "fonte_referencia": "IBGE / limites municipais Sinidu+Clima",
                "qualidade_dado": "Oficial",
            },
        })
    return {"type": "FeatureCollection", "features": features}


def build_regional_overlay(
    db: Session,
    muni: Municipio,
    *,
    escopo: str = "regiao_imediata",
) -> dict[str, Any]:
    escopo_norm = escopo if escopo in {"regiao_imediata", "mesorregiao"} else "regiao_imediata"
    localidade = _fetch_municipio_localidade(muni.codigo_ibge)
    mesorregiao = _region_block(localidade)
    regiao_imediata = _immediate_region_block(localidade)

    peer_codigos = _peer_codigos_ibge(localidade, escopo_norm)
    referencia = _referencia_comparacao(db, muni)

    loaded_peers = [
        c for c in peer_codigos
        if c != muni.codigo_ibge
        and db.query(Municipio.id).filter(Municipio.codigo_ibge == c).first()
    ]
    peer_metrics = [_municipio_metrics(db, code) for code in loaded_peers[:12]]
    municipio_metrics = _municipio_metrics(db, muni.codigo_ibge)

    geojson = _regional_geojson(db, muni.codigo_ibge, peer_codigos, referencia)

    return {
        "codigo_ibge": muni.codigo_ibge,
        "municipio_nome": muni.nome,
        "uf": muni.uf,
        "escopo": escopo_norm,
        "mesorregiao": mesorregiao,
        "regiao_imediata": regiao_imediata,
        "total_municipios_escopo": len(peer_codigos),
        "municipios_carregados_mapa": len(geojson.get("features") or []),
        "referencia_comparacao": referencia,
        "indicadores": {
            "municipio": municipio_metrics,
            "regional": _aggregate_metrics(peer_metrics),
        },
        "geojson": geojson,
        "nota": (
            "Região imediata IBGE como proxy de RM. Municípios tracejados são pares com malha "
            "carregada no Sinidu; use CompareModal para análise detalhada."
        ),
    }
