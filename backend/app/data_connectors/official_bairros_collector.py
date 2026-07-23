"""Malha oficial de bairros e setores censitários — IBGE Censo 2022."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any

import requests
from geoalchemy2.shape import from_shape
from shapely.geometry import shape
from shapely.ops import unary_union
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.data_connectors.constants import TARGET_MUNICIPALITIES
from app.models import Bairro, Municipio, SetorCensitario

logger = logging.getLogger(__name__)

IBGE_MESH_BASE = (
    "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
    "malhas_de_setores_censitarios__divisoes_intramunicipais/censo_2022"
)
IBGE_BAIRROS_ZIP = IBGE_MESH_BASE + "/bairros/shp/UF/{uf}_bairros_CD2022.zip"
IBGE_SETORES_ZIP = IBGE_MESH_BASE + "/setores/shp/UF/{uf}_setores_CD2022.zip"

BAIRRO_NAME_KEYS = ("NM_BAIRRO", "nm_bairro", "nome", "name")
BAIRRO_CODE_KEYS = ("CD_BAIRRO", "cd_bairro")
SETOR_CODE_KEYS = ("CD_SETOR", "cd_setor")
DIST_NAME_KEYS = ("NM_DIST", "nm_dist")


def _cache_dir() -> Path:
    root = Path(os.getenv("IBGE_MESH_CACHE_DIR", "/data/ibge/censo_2022"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _uf_for_municipio(codigo_ibge: str, db: Session | None = None) -> str | None:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    for item in TARGET_MUNICIPALITIES:
        if item["codigo_ibge"] == code:
            return item["uf"]
    if db is not None:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
        if muni and muni.uf:
            return muni.uf
    return None


def ensure_municipio_geometry(db: Session, muni: Municipio) -> bool:
    """Atualiza municipios.geom quando placeholder ou bbox incorreto."""
    from app.services.municipio_loader import fetch_ibge_geometry

    current_area = float(db.scalar(func.ST_Area(muni.geom)) or 0)
    geom, fonte = fetch_ibge_geometry(muni.codigo_ibge)
    if fonte != "ibge_malhas_v3" or geom.is_empty:
        logger.warning("Geometria IBGE indisponível para %s (%s)", muni.codigo_ibge, fonte)
        return False

    needs_replace = (
        current_area <= 0
        or abs(current_area - 1.0) < 0.01
        or current_area >= 0.25
        or geom.area < current_area * 0.5
    )
    if needs_replace:
        muni.geom = from_shape(geom, srid=4326)
        db.commit()
        logger.info(
            "Geometria municipal corrigida %s (%.6f → %.6f deg²)",
            muni.codigo_ibge,
            current_area,
            geom.area,
        )
        return True
    return False


def _sync_municipio_boundary_from_setores(db: Session, muni: Municipio) -> None:
    """Alinha limite municipal à união dos setores censitários importados."""
    updated = db.execute(
        text(
            """
            UPDATE municipios SET geom = sub.u
            FROM (
                SELECT ST_Multi(ST_Union(geom)) AS u
                FROM setores_censitarios
                WHERE municipio_id = :mid
            ) sub
            WHERE municipios.id = :mid AND sub.u IS NOT NULL
            """
        ),
        {"mid": muni.id},
    )
    if updated.rowcount:
        db.commit()


def _geom_from_feature(feat: dict[str, Any]) -> Any | None:
    if not feat.get("geometry"):
        return None
    try:
        part = _as_multipolygon(shape(feat["geometry"]))
    except Exception:
        return None
    return None if part.is_empty else part


def _download_zip(url: str, dest: Path) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Baixando malha IBGE: %s", url)
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    tmp = dest.with_suffix(".part")
    with tmp.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                fh.write(chunk)
    tmp.replace(dest)
    return dest


def _extract_zip(zip_path: Path, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    shp_files = list(dest_dir.glob("*.shp"))
    if not shp_files:
        raise FileNotFoundError(f"Shapefile não encontrado em {zip_path}")
    return shp_files[0]


def _ogr_to_geojson(shp_path: Path, where: str | None = None) -> dict[str, Any]:
    fd, tmp_name = tempfile.mkstemp(suffix=".geojson")
    os.close(fd)
    out_path = Path(tmp_name)
    out_path.unlink(missing_ok=True)
    cmd = ["ogr2ogr", "-f", "GeoJSON", "-t_srs", "EPSG:4326", str(out_path), str(shp_path)]
    if where:
        cmd.extend(["-where", where])
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        if result.stderr:
            logger.debug("ogr2ogr: %s", result.stderr.strip())
        data = json.loads(out_path.read_text(encoding="utf-8"))
    except subprocess.CalledProcessError as exc:
        logger.error("ogr2ogr falhou: %s", (exc.stderr or exc.stdout or str(exc)).strip())
        raise
    finally:
        out_path.unlink(missing_ok=True)
    return data


def _prop(props: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = props.get(key)
        if value not in (None, "", " "):
            return str(value).strip()
    return None


def _as_multipolygon(geom):
    from app.data_connectors.territorial_mesh_collector import _as_multipolygon

    return _as_multipolygon(geom)


def fetch_ibge_bairros_geojson(codigo_ibge: str, uf: str) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    cache = _cache_dir()
    try:
        zip_path = _download_zip(IBGE_BAIRROS_ZIP.format(uf=uf), cache / f"{uf}_bairros_CD2022.zip")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            logger.warning("Malha de bairros IBGE indisponível para UF %s — usando agregação por setores", uf)
            return {"type": "FeatureCollection", "features": []}
        raise
    extract_dir = cache / f"{uf}_bairros_extract"
    shp = _extract_zip(zip_path, extract_dir)
    return _ogr_to_geojson(shp, where=f"CD_MUN = '{code}'")


def fetch_ibge_setores_geojson(codigo_ibge: str, uf: str) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    cache = _cache_dir()
    zip_path = _download_zip(IBGE_SETORES_ZIP.format(uf=uf), cache / f"{uf}_setores_CD2022.zip")
    extract_dir = cache / f"{uf}_setores_extract"
    shp = _extract_zip(zip_path, extract_dir)
    return _ogr_to_geojson(shp, where=f"CD_MUN = '{code}'")


def _dissolve_setores_to_bairros(setores_fc: dict[str, Any]) -> dict[str, Any]:
    """Agrega setores por NM_BAIRRO ou NM_DIST quando a malha de bairros IBGE está vazia."""
    groups: dict[str, list] = {}
    for feat in setores_fc.get("features") or []:
        if not feat.get("geometry"):
            continue
        props = feat.get("properties") or {}
        label = _prop(props, BAIRRO_NAME_KEYS) or _prop(props, DIST_NAME_KEYS)
        if not label:
            label = f"Setor {_prop(props, SETOR_CODE_KEYS) or 'indefinido'}"
        groups.setdefault(label, []).append(shape(feat["geometry"]))

    features: list[dict[str, Any]] = []
    for idx, (nome, geoms) in enumerate(sorted(groups.items()), start=1):
        merged = unary_union(geoms)
        if merged.is_empty:
            continue
        features.append(
            {
                "type": "Feature",
                "properties": {"NM_BAIRRO": nome, "CD_BAIRRO": f"agg-{idx:04d}"},
                "geometry": json.loads(json.dumps(merged.__geo_interface__)),
            }
        )
    return {"type": "FeatureCollection", "features": features}


def is_official_ibge_mesh(db: Session, muni: Municipio) -> bool:
    official_fonte = (
        db.query(Bairro)
        .filter(
            Bairro.municipio_id == muni.id,
            Bairro.fonte_malha.in_(("ibge_censo2022", "ibge_censo2022_setores", "prefeitura_oficial")),
        )
        .count()
    )
    try:
        official_n = int(official_fonte or 0)
    except (TypeError, ValueError):
        official_n = 0
    if official_n > 0:
        return True

    rows = db.query(Bairro.codigo_bairro, Bairro.nome).filter(Bairro.municipio_id == muni.id).all()
    if not rows:
        return False
    from app.data_connectors.territorial_mesh_collector import GENERIC_BAIRRO_NAMES

    names = {r.nome for r in rows}
    if names <= GENERIC_BAIRRO_NAMES:
        return False
    if len(rows) >= 15 and not names <= GENERIC_BAIRRO_NAMES:
        return True
    return any(r.codigo_bairro and r.codigo_bairro.isdigit() and len(r.codigo_bairro) >= 10 for r in rows)


def import_official_ibge_mesh(db: Session, muni: Municipio, *, force: bool = False) -> dict[str, Any]:
    """Importa bairros e setores censitários oficiais (IBGE Censo 2022)."""
    uf = _uf_for_municipio(muni.codigo_ibge, db) or muni.uf
    if not uf:
        return {"codigo_ibge": muni.codigo_ibge, "error": "UF não identificada.", "skipped": True}

    if not force and is_official_ibge_mesh(db, muni):
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
        setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).count()
        if bairros >= 8 or setores >= 50:
            return {
                "codigo_ibge": muni.codigo_ibge,
                "skipped": True,
                "bairros": bairros,
                "setores": setores,
                "source": "ibge_censo_2022",
            }

    ensure_municipio_geometry(db, muni)
    db.refresh(muni)

    setores_fc = fetch_ibge_setores_geojson(muni.codigo_ibge, uf)
    bairros_fc = fetch_ibge_bairros_geojson(muni.codigo_ibge, uf)
    bairro_features = bairros_fc.get("features") or []
    source_mode = "ibge_bairros"
    if not bairro_features:
        bairros_fc = _dissolve_setores_to_bairros(setores_fc)
        bairro_features = bairros_fc.get("features") or []
        source_mode = "ibge_setores_agregados"

    if not bairro_features:
        return {
            "codigo_ibge": muni.codigo_ibge,
            "error": "Malha IBGE indisponível para o município.",
            "skipped": True,
        }

    db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).delete(synchronize_session=False)
    db.query(Bairro).filter(Bairro.municipio_id == muni.id).delete(synchronize_session=False)
    db.flush()

    bairro_by_name: dict[str, Bairro] = {}
    bairros_created = 0

    for idx, feat in enumerate(bairro_features):
        props = feat.get("properties") or {}
        nome = _prop(props, BAIRRO_NAME_KEYS)
        if not nome:
            continue
        part = _geom_from_feature(feat)
        if part is None:
            continue
        codigo = _prop(props, BAIRRO_CODE_KEYS) or f"{muni.codigo_ibge}-{idx + 1:03d}"
        bairro = Bairro(
            municipio_id=muni.id,
            nome=nome,
            codigo_bairro=codigo[:15],
            geom=from_shape(part, srid=4326),
            fonte_malha="ibge_censo2022" if source_mode == "ibge_bairros" else "ibge_censo2022_setores",
        )
        db.add(bairro)
        db.flush()
        bairro_by_name[nome] = bairro
        bairros_created += 1

    if bairros_created == 0:
        db.rollback()
        return {"codigo_ibge": muni.codigo_ibge, "error": "Nenhum bairro válido após importação IBGE."}

    setores_created = 0
    setor_features = setores_fc.get("features") or []
    setor_rows: list[tuple[str, Any]] = []
    for feat in setor_features:
        props = feat.get("properties") or {}
        codigo_setor = _prop(props, SETOR_CODE_KEYS)
        if not codigo_setor:
            continue
        part = _geom_from_feature(feat)
        if part is None:
            continue
        setor_rows.append((codigo_setor[:15], part))

    total_area = sum(part.area for _, part in setor_rows) or 1.0
    for idx, (codigo_setor, part) in enumerate(setor_rows):
        pop_share = max(0.001, part.area / total_area)
        populacao = max(50, int((muni.populacao or 0) * pop_share))
        renda = 2200.0 + (idx % 7) * 150
        db.add(
            SetorCensitario(
                municipio_id=muni.id,
                codigo_setor=codigo_setor,
                populacao=populacao,
                renda_media=renda,
                geom=from_shape(part, srid=4326),
                fonte_renda="estimativa_sinidu_pendente_sidra",
            )
        )
        setores_created += 1

    if setores_created == 0:
        db.rollback()
        return {"codigo_ibge": muni.codigo_ibge, "error": "Nenhum setor censitário importado."}

    _sync_municipio_boundary_from_setores(db, muni)
    db.refresh(muni)
    from app.data_connectors.territorial_mesh_collector import _sync_infraestrutura

    infra_created = _sync_infraestrutura(db, muni)
    db.commit()

    try:
        from app.services.socioeconomic_engine import enrich_municipal_socioeconomics

        if setores_created <= 800:
            enrich_municipal_socioeconomics(db, muni)
            db.commit()
        else:
            logger.info(
                "Município %s com %d setores — enrich socio pulado (use socioeconomico_censo).",
                muni.codigo_ibge,
                setores_created,
            )
    except Exception as exc:
        logger.warning("Calibração socioeconômica pós-malha IBGE falhou %s: %s", muni.codigo_ibge, exc)

    return {
        "codigo_ibge": muni.codigo_ibge,
        "skipped": False,
        "bairros": bairros_created,
        "setores": setores_created,
        "infraestrutura": infra_created,
        "source": source_mode,
        "data_quality": "oficial_ibge",
        "mesh_version": 4,
    }


def sync_official_bairros_municipality(db: Session, codigo_ibge: str, *, force: bool = False) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "error": "Município não carregado no banco."}
    return import_official_ibge_mesh(db, muni, force=force)


def sync_official_bairros_batch(db: Session, *, limit: int = 6, force: bool = False) -> dict[str, Any]:
    from app.data_connectors.constants import TARGET_IBGE_CODES

    codes = TARGET_IBGE_CODES[:limit]
    processed: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for code in codes:
        try:
            result = sync_official_bairros_municipality(db, code, force=force)
            if result.get("error") and not result.get("skipped"):
                errors.append({"codigo_ibge": code, "error": result["error"]})
            else:
                processed.append(result)
        except Exception as exc:
            logger.exception("Malha IBGE falhou %s", code)
            errors.append({"codigo_ibge": code, "error": str(exc)})
    return {"requested": len(codes), "processed": len(processed), "errors": errors, "items": processed}
