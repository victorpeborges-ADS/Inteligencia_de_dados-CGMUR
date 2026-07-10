"""Importação automática de malha CTM (geoportais municipais)."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from typing import Any
import requests
from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import make_valid
from sqlalchemy.orm import Session

from app.data_connectors.ctm_registry import CTM_BY_CODE, CTM_RESEARCH_NOTES, CTM_SOURCES, CTM_TARGET_CODES, CtmSource
from app.data_connectors.territorial_mesh_collector import _as_multipolygon, _feature_bairro_name
from app.models import Bairro, Municipio, MunicipioSeed, SetorCensitario

logger = logging.getLogger(__name__)

_ARCGIS_PAGE = 1000


def _prop(props: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        val = props.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return None


def _arcgis_rings_to_geojson(esri_fc: dict[str, Any]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for feat in esri_fc.get("features") or []:
        geom = feat.get("geometry") or {}
        attrs = feat.get("attributes") or {}
        if "rings" not in geom:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": attrs,
                "geometry": {"type": "Polygon", "coordinates": geom["rings"]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def _normalize_geojson(raw: dict[str, Any]) -> dict[str, Any]:
    """Converte resposta ArcGIS JSON em FeatureCollection RFC7946."""
    if raw.get("type") == "FeatureCollection":
        return raw
    if "features" in raw and raw["features"]:
        first = raw["features"][0]
        geom = first.get("geometry") or {}
        if "x" in geom:
            return {"type": "FeatureCollection", "features": []}
        if "rings" in geom:
            return _arcgis_rings_to_geojson(raw)
    return {"type": "FeatureCollection", "features": []}


def fetch_arcgis_geojson(source: CtmSource) -> dict[str, Any]:
    """Baixa FeatureCollection via ArcGIS REST (paginado)."""
    all_features: list[dict[str, Any]] = []
    offset = 0
    url = source.url if "?" not in source.url else source.url.split("?")[0]

    while True:
        params = {
            "where": source.where,
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "resultOffset": str(offset),
            "resultRecordCount": str(_ARCGIS_PAGE),
            "f": "json",
        }
        resp = requests.get(url, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        if data.get("error"):
            raise RuntimeError(data["error"])

        fc = _arcgis_rings_to_geojson(data) if data.get("features") else {"features": []}
        batch = fc.get("features") or []
        if not batch:
            break
        all_features.extend(batch)
        if len(batch) < _ARCGIS_PAGE and not data.get("exceededTransferLimit"):
            break
        offset += len(batch)
        if offset > 5000:
            break

    return {"type": "FeatureCollection", "features": all_features}


def fetch_geojson_url(url: str) -> dict[str, Any]:
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if data.get("type") != "FeatureCollection":
        raise RuntimeError("URL não retornou FeatureCollection GeoJSON.")
    return data


def fetch_geoserver_wfs_geojson(source: CtmSource) -> dict[str, Any]:
    """Baixa FeatureCollection via GeoServer WFS 2.0 (outputFormat GeoJSON, EPSG:4326)."""
    type_name = (source.where or "").strip()
    if not type_name or type_name == "1=1":
        raise ValueError("typeName da camada GeoServer é obrigatório (campo where/type_name).")

    base = source.url.strip().rstrip("/")
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": type_name,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
    }
    resp = requests.get(base, params=params, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    if data.get("type") != "FeatureCollection":
        raise RuntimeError("GeoServer WFS não retornou FeatureCollection GeoJSON.")
    return data


def _safe_shape(feat: dict[str, Any]) -> Any | None:
    try:
        geom = shape(feat["geometry"])
    except Exception:
        return None
    if not geom.is_valid:
        try:
            geom = make_valid(geom)
        except Exception:
            return None
    return geom if not geom.is_empty else None


def _merge_geoms(geoms: list) -> Any:
    if len(geoms) == 1:
        return geoms[0]
    try:
        return unary_union(geoms)
    except Exception:
        return max(geoms, key=lambda g: g.area)


def dissolve_by_name(
    geojson: dict[str, Any],
    name_fields: tuple[str, ...],
) -> dict[str, Any]:
    """Unifica polígonos com o mesmo nome (ex.: Goiânia — vários lotes por bairro)."""
    groups: dict[str, list] = defaultdict(list)
    for feat in geojson.get("features") or []:
        if not feat.get("geometry"):
            continue
        props = feat.get("properties") or {}
        nome = _prop(props, name_fields) or _feature_bairro_name(props)
        if not nome or nome.lower() in {"null", "none", "indefinido"}:
            continue
        try:
            part_geom = _safe_shape(feat)
            if part_geom is None:
                continue
            groups[nome].append(part_geom)
        except Exception:
            continue

    out_features: list[dict[str, Any]] = []
    for idx, (nome, geoms) in enumerate(sorted(groups.items()), start=1):
        merged = _merge_geoms(geoms)
        if merged.is_empty:
            continue
        part = _as_multipolygon(merged)
        if part.is_empty:
            continue
        out_features.append(
            {
                "type": "Feature",
                "properties": {"nome": nome, "NM_BAIRRO": nome, "CD_BAIRRO": f"ctm-{idx:04d}"},
                "geometry": json.loads(json.dumps(part.__geo_interface__)),
            }
        )
    return {"type": "FeatureCollection", "features": out_features}


def fetch_ctm_geojson(source: CtmSource) -> dict[str, Any]:
    if source.kind == "arcgis":
        raw = fetch_arcgis_geojson(source)
    elif source.kind == "geojson_url":
        raw = fetch_geojson_url(source.url)
    elif source.kind == "geoserver_wfs":
        raw = fetch_geoserver_wfs_geojson(source)
    else:
        raise ValueError(f"Tipo de fonte não suportado: {source.kind}")

    dissolved = dissolve_by_name(raw, source.name_fields)
    if len(dissolved.get("features") or []) < 4:
        return dissolved
    return dissolved


def probe_ctm_source(source: CtmSource) -> dict[str, Any]:
    """Testa conectividade e conta feições sem gravar no banco."""
    try:
        fc = fetch_ctm_geojson(source)
        count = len(fc.get("features") or [])
        return {
            "codigo_ibge": source.codigo_ibge,
            "nome": source.nome,
            "uf": source.uf,
            "status": "disponivel" if count >= 4 else "insuficiente",
            "feicoes": count,
            "fonte": source.kind,
            "nota": source.nota,
            "url": source.url.split("/query")[0] if source.kind == "arcgis" else source.url,
        }
    except Exception as exc:
        return {
            "codigo_ibge": source.codigo_ibge,
            "nome": source.nome,
            "uf": source.uf,
            "status": "erro",
            "feicoes": 0,
            "erro": str(exc)[:200],
            "nota": source.nota,
        }


def catalog_ctm_targets() -> list[dict[str, Any]]:
    """Inventário: fonte CTM cadastrada vs. dependência de setores IBGE."""
    from app.data_connectors.constants import TARGET_MUNICIPALITIES

    rows: list[dict[str, Any]] = []
    for code in CTM_TARGET_CODES:
        source = CTM_BY_CODE.get(code)
        meta = next((m for m in TARGET_MUNICIPALITIES if m["codigo_ibge"] == code), {})
        if source:
            row = probe_ctm_source(source)
            if row.get("status") == "erro" and source.prioridade >= 3:
                row["status"] = "intermitente"
            rows.append(row)
        else:
            rows.append(
                {
                    "codigo_ibge": code,
                    "nome": meta.get("nome", code),
                    "uf": meta.get("uf", ""),
                    "status": "sem_ctm_cadastrada",
                    "feicoes": 0,
                    "nota": CTM_RESEARCH_NOTES.get(
                        code,
                        "Malha IBGE setores (camada bairros) até obter CTM municipal",
                    ),
                }
            )
    return rows


def import_ctm_mesh(
    db: Session,
    muni: Municipio,
    geojson: dict[str, Any],
    *,
    source_label: str = "prefeitura_oficial",
) -> dict[str, Any]:
    """
    Importa polígonos CTM como bairros, preservando setores censitários IBGE existentes.
    """
    features = geojson.get("features") or []
    if len(features) < 4:
        return {
            "codigo_ibge": muni.codigo_ibge,
            "error": f"Poucas feições CTM ({len(features)}) — importação abortada.",
            "skipped": True,
        }

    muni_poly = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
    setores_antes = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).count()

    db.query(Bairro).filter(Bairro.municipio_id == muni.id).delete(synchronize_session=False)
    db.expire_all()
    db.flush()

    created = 0
    total_area = muni_poly.area or 1.0
    for idx, feat in enumerate(features):
        if not isinstance(feat, dict) or not feat.get("geometry"):
            continue
        props = feat.get("properties") or {}
        nome = _feature_bairro_name(props) or _prop(props, ("nome", "NM_BAIRRO", "nm_bai", "ra_nome"))
        if not nome:
            continue
        try:
            geom = _safe_shape(feat)
        except Exception:
            geom = None
        if geom is None:
            continue
        clipped = muni_poly.intersection(geom)
        if clipped.is_empty or clipped.area < total_area * 0.00005:
            continue
        part = _as_multipolygon(clipped)
        if part.is_empty:
            continue

        codigo = (
            _prop(props, ("CD_BAIRRO", "id", "ra_codigo", "codigo_bairro"))
            or f"{muni.codigo_ibge}-ctm-{idx + 1:03d}"
        )
        db.add(
            Bairro(
                municipio_id=muni.id,
                nome=nome,
                codigo_bairro=str(codigo)[:15],
                geom=from_shape(part, srid=4326),
                fonte_malha=source_label,
            )
        )
        created += 1

    if created < 4:
        db.rollback()
        return {
            "codigo_ibge": muni.codigo_ibge,
            "error": f"Apenas {created} bairros válidos após recorte municipal.",
            "skipped": True,
        }

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
    if seed:
        seed.malha_fonte = source_label

    db.commit()
    codigo = muni.codigo_ibge

    try:
        from app.services.socioeconomic_engine import enrich_municipal_socioeconomics
        from app.services.malha_ibge_service import _aggregate_bairro_socio

        if setores_antes >= 4 and setores_antes <= 800:
            _aggregate_bairro_socio(db, muni)
            db.commit()
            db.expire_all()
            enrich_municipal_socioeconomics(db, muni)
            db.commit()
        elif setores_antes > 800:
            logger.info(
                "Município %s com %d setores — agregação socio CTM simplificada.",
                codigo,
                setores_antes,
            )
    except Exception as exc:
        db.rollback()
        logger.warning("Enriquecimento pós-CTM falhou %s: %s", codigo, exc)

    return {
        "codigo_ibge": codigo,
        "bairros": created,
        "setores_preservados": setores_antes,
        "source": "ctm_geoportal",
        "malha_fonte": source_label,
        "skipped": False,
    }


def collect_ctm_municipality(db: Session, codigo_ibge: str, *, force: bool = False) -> dict[str, Any]:
    """Baixa CTM do registry e importa para o município."""
    code = str(codigo_ibge).strip().zfill(7)[:7]
    source = CTM_BY_CODE.get(code)
    if not source:
        return {
            "codigo_ibge": code,
            "error": "Sem fonte CTM cadastrada para este município.",
            "skipped": True,
        }

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "error": "Município não encontrado no PostGIS.", "skipped": True}

    bcount = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
    if not force and bcount >= 30:
        return {
            "codigo_ibge": code,
            "skipped": True,
            "bairros": bcount,
            "motivo": "Malha densa existente — use force=True para sobrescrever.",
        }

    try:
        fc = fetch_ctm_geojson(source)
    except Exception as exc:
        return {"codigo_ibge": code, "error": f"Falha ao baixar CTM: {exc}", "skipped": True}

    result = import_ctm_mesh(db, muni, fc, source_label="prefeitura_oficial")
    result["fonte_registry"] = source.nota
    return result


def collect_ctm_batch(db: Session, *, codigos: list[str] | None = None, force: bool = False) -> dict[str, Any]:
    targets = codigos or [c for c in CTM_TARGET_CODES if c in CTM_BY_CODE]
    ok, err, skip = 0, 0, 0
    details: list[dict[str, Any]] = []
    for code in targets:
        res = collect_ctm_municipality(db, code, force=force)
        details.append(res)
        if res.get("skipped") and not res.get("error"):
            skip += 1
        elif res.get("error"):
            err += 1
        else:
            ok += 1
    return {"ok": ok, "erro": err, "pulados": skip, "detalhes": details}
