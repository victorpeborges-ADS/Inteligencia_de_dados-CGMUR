"""LOD2-lite: mesh de telhado a partir do nDSM (LiDAR) — fase 18b.1.

Não é LOD2 arquitetônico (cumeeiras finas): o nDSM piloto do Recife tem ~17 m/px.
Gera TIN de telhado amostrado + paredes até o eaves, empacotado em GLB/tileset
no mesmo formato do LOD1 (`building_3dtiles_service`).
"""

from __future__ import annotations

import json
import logging
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import Point, box, shape
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio
from app.services.building_3dtiles_service import (
    DEFAULT_HEIGHT_M,
    _bbox_region,
    _extrude_polygon,
    _geom_polygons,
    _lonlat_to_local,
    _pack_glb,
    _ring_xy,
    tiles3d_muni_dir,
)
from app.services.ndsm_service import build_ndsm, ndsm_path

logger = logging.getLogger(__name__)

LOD2_VERSION = "18b.1"
MAX_BUILDINGS_LOD2 = 500
DEFAULT_BBOX_RECIFE = (-34.878, -8.068, -34.868, -8.058)  # centro / Recife Antigo
SAMPLE_STEP_M = 8.0
MIN_ROOF_RISE_M = 0.8


def lod2_dir(codigo_ibge: str) -> Path:
    d = tiles3d_muni_dir(codigo_ibge) / "lod2"
    d.mkdir(parents=True, exist_ok=True)
    return d


def status_lod2(codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    d = lod2_dir(code)
    tileset = d / "tileset.json"
    glb = d / "content.glb"
    meta_path = d / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    footprints = d / "footprints.geojson"
    return {
        "codigo_ibge": code,
        "disponivel": (tileset.exists() and glb.exists()) or footprints.exists(),
        "lod": "LOD2",
        "tileset_path": str(tileset) if tileset.exists() else None,
        "tileset_url": f"/static/3dtiles/{code}/lod2/tileset.json" if tileset.exists() else None,
        "content_url": f"/static/3dtiles/{code}/lod2/content.glb" if glb.exists() else None,
        "footprints_url": (
            f"/static/3dtiles/{code}/lod2/footprints.geojson" if footprints.exists() else None
        ),
        "api_tileset_url": f"/api/v1/buildings/{code}/3dtiles/lod2/tileset.json",
        "api_content_url": f"/api/v1/buildings/{code}/3dtiles/lod2/content.glb",
        "api_footprints_url": f"/api/v1/buildings/{code}/3dtiles/lod2/footprints.geojson",
        "meta": meta,
    }


def _open_ndsm_sampler(codigo_ibge: str):
    """Retorna (sample_fn(lon,lat)->float|None, meta) ou (None, info)."""
    code = str(codigo_ibge).zfill(7)[:7]
    path = ndsm_path(code)
    if not path.exists():
        info = build_ndsm(code, force=False)
        if info.get("status") not in {"ok", "cached"}:
            return None, info
    try:
        import rasterio
    except ImportError:
        return None, {"status": "sem_rasterio"}

    src = rasterio.open(path)

    def sample(lon: float, lat: float) -> float | None:
        try:
            vals = list(src.sample([(lon, lat)]))
            if not vals:
                return None
            v = float(vals[0][0])
            if not math.isfinite(v) or v < 0 or v > 200:
                return None
            return v
        except Exception:
            return None

    return (sample, src), {"status": "ok", "path": str(path)}


def _sample_points_in_poly(poly, step_m: float = SAMPLE_STEP_M) -> list[tuple[float, float]]:
    """Gera pontos lon/lat no interior + vértices do anel."""
    minx, miny, maxx, maxy = poly.bounds
    lat0 = (miny + maxy) / 2.0
    dlon = step_m / (111_320.0 * max(0.2, math.cos(math.radians(lat0))))
    dlat = step_m / 110_540.0
    pts: list[tuple[float, float]] = []
    for lon, lat in poly.exterior.coords:
        pts.append((float(lon), float(lat)))
    c = poly.centroid
    pts.append((float(c.x), float(c.y)))
    x = minx
    while x <= maxx + 1e-12:
        y = miny
        while y <= maxy + 1e-12:
            p = Point(x, y)
            if poly.contains(p) or poly.touches(p):
                pts.append((float(x), float(y)))
            y += dlat
        x += dlon
    # dedup aproximado
    seen: set[tuple[float, float]] = set()
    out: list[tuple[float, float]] = []
    for lon, lat in pts:
        key = (round(lon, 6), round(lat, 6))
        if key in seen:
            continue
        seen.add(key)
        out.append((lon, lat))
    return out


def _lod2_mesh_from_samples(
    ring_xy: list[tuple[float, float]],
    samples_local: list[tuple[float, float, float]],
    fallback_h: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Paredes até eaves + telhado em tip (pico) a partir das amostras nDSM."""
    if len(ring_xy) < 3:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0,), dtype=np.uint32)

    if not samples_local:
        return _extrude_polygon(ring_xy, fallback_h)

    heights = np.array([h for _, _, h in samples_local], dtype=np.float64)
    eaves = float(np.percentile(heights, 20))
    eaves = max(2.0, min(eaves, float(np.max(heights))))
    peak_i = int(np.argmax(heights))
    px, py, ph = samples_local[peak_i]
    ph = max(float(ph), eaves + MIN_ROOF_RISE_M)

    # Se variação for desprezível → LOD1
    if float(np.max(heights) - np.min(heights)) < 0.4:
        return _extrude_polygon(ring_xy, max(fallback_h, eaves, ph))

    n = len(ring_xy)
    bottom = np.array([[x, 0.0, -y] for x, y in ring_xy], dtype=np.float32)
    eaves_ring = np.array([[x, eaves, -y] for x, y in ring_xy], dtype=np.float32)
    peak = np.array([[px, ph, -py]], dtype=np.float32)
    verts = np.vstack([bottom, eaves_ring, peak])
    peak_idx = 2 * n

    indices: list[int] = []
    # piso
    for a, b, c in ((0, i, i + 1) for i in range(1, n - 1)):
        indices.extend([a, c, b])
    # paredes
    for i in range(n):
        j = (i + 1) % n
        indices.extend([i, j, n + j, i, n + j, n + i])
    # telhado: fan eaves → pico
    for i in range(n):
        j = (i + 1) % n
        indices.extend([n + i, n + j, peak_idx])

    return verts, np.asarray(indices, dtype=np.uint32)


def build_lod2_for_bbox(
    db: Session,
    codigo_ibge: str,
    *,
    west: float | None = None,
    south: float | None = None,
    east: float | None = None,
    north: float | None = None,
    limit: int = 400,
    force: bool = False,
    ensure_buildings: bool = True,
) -> dict[str, Any]:
    """Gera LOD2-lite (GLB + tileset) para edificações no bbox."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    if None in (west, south, east, north):
        west, south, east, north = DEFAULT_BBOX_RECIFE if code == "2611606" else (
            None,
            None,
            None,
            None,
        )
        if west is None and muni.geom is not None:
            try:
                from sqlalchemy import func

                env = db.execute(
                    text(
                        "SELECT ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g) FROM ("
                        "SELECT ST_Envelope(ST_Transform(ST_Centroid(geom)::geometry, 4326)) AS g "
                        "FROM municipios WHERE id = :id) t"
                    ),
                    {"id": muni.id},
                ).first()
            except Exception:
                env = None
            if env and all(v is not None for v in env):
                cx = (float(env[0]) + float(env[2])) / 2
                cy = (float(env[1]) + float(env[3])) / 2
                west, south, east, north = cx - 0.005, cy - 0.005, cx + 0.005, cy + 0.005
            else:
                raise ValueError("Informe west/south/east/north para o bbox LOD2")
        elif west is None:
            raise ValueError("Informe west/south/east/north para o bbox LOD2")

    assert west is not None and south is not None and east is not None and north is not None
    if east <= west or north <= south:
        raise ValueError("Bbox inválido")

    out_dir = lod2_dir(code)
    tileset_path = out_dir / "tileset.json"
    glb_path = out_dir / "content.glb"
    meta_path = out_dir / "meta.json"

    footprints_path = out_dir / "footprints.geojson"
    if (
        tileset_path.exists()
        and glb_path.exists()
        and footprints_path.exists()
        and not force
    ):
        st = status_lod2(code)
        st["status"] = "cached"
        return st

    n = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if n == 0 and ensure_buildings:
        from app.data_connectors.building_footprints_collector import collect_buildings_municipality

        collect_buildings_municipality(db, code, force=False)

    # Edificações que intersectam o bbox (WGS84)
    sql = text(
        """
        SELECT e.id
        FROM edificacoes e
        WHERE e.municipio_id = :mid
          AND e.geom IS NOT NULL
          AND ST_Intersects(
            e.geom,
            ST_MakeEnvelope(:west, :south, :east, :north, 4326)
          )
        LIMIT :lim
        """
    )
    ids = [r[0] for r in db.execute(
        sql,
        {
            "mid": muni.id,
            "west": west,
            "south": south,
            "east": east,
            "north": north,
            "lim": max(1, min(int(limit), MAX_BUILDINGS_LOD2)),
        },
    ).fetchall()]

    rows = (
        db.query(Edificacao).filter(Edificacao.id.in_(ids)).all()
        if ids
        else []
    )

    sampler_pack, ndsm_info = _open_ndsm_sampler(code)
    sample_fn = None
    src_handle = None
    if sampler_pack:
        sample_fn, src_handle = sampler_pack

    lon0 = (west + east) / 2.0
    lat0 = (south + north) / 2.0

    all_verts: list[np.ndarray] = []
    all_idx: list[np.ndarray] = []
    v_offset = 0
    lons: list[float] = []
    lats: list[float] = []
    max_h = DEFAULT_HEIGHT_M
    exported = 0
    lod2_count = 0
    lod1_fallback = 0
    footprint_features: list[dict[str, Any]] = []

    try:
        for row in rows:
            try:
                gjson = db.scalar(row.geom.ST_AsGeoJSON())
                if not gjson:
                    continue
                g = shape(json.loads(gjson))
            except Exception:
                continue
            polys = _geom_polygons(g)
            if not polys:
                continue
            fallback = float(row.altura_m or DEFAULT_HEIGHT_M)
            max_h = max(max_h, fallback)
            feat_h = fallback
            feat_mode = "lod1_fallback"

            for poly in polys:
                # clip leve ao bbox de interesse
                try:
                    poly = poly.intersection(box(west, south, east, north))
                except Exception:
                    pass
                if poly.is_empty:
                    continue
                for part in _geom_polygons(poly):
                    ring = list(part.exterior.coords)
                    for c in ring:
                        lons.append(float(c[0]))
                        lats.append(float(c[1]))
                    xy = _ring_xy(ring, lon0, lat0)
                    samples_local: list[tuple[float, float, float]] = []
                    if sample_fn:
                        for lon, lat in _sample_points_in_poly(part):
                            h = sample_fn(lon, lat)
                            if h is None:
                                continue
                            lx, ly = _lonlat_to_local(lon, lat, lon0, lat0)
                            samples_local.append((lx, ly, float(h)))
                    verts, idx = _lod2_mesh_from_samples(xy, samples_local, fallback)
                    if verts.size == 0:
                        continue
                    h_mesh = float(verts[:, 1].max())
                    feat_h = max(feat_h, h_mesh)
                    if samples_local:
                        hs = [h for _, _, h in samples_local]
                        if max(hs) - min(hs) >= 0.4:
                            lod2_count += 1
                            feat_mode = "lod2_tin"
                        else:
                            lod1_fallback += 1
                    else:
                        lod1_fallback += 1
                    max_h = max(max_h, h_mesh)
                    all_verts.append(verts)
                    all_idx.append(idx + v_offset)
                    v_offset += verts.shape[0]
                    try:
                        footprint_features.append({
                            "type": "Feature",
                            "geometry": json.loads(json.dumps(part.__geo_interface__)),
                            "properties": {
                                "altura_m": round(feat_h, 2),
                                "modo": feat_mode,
                                "fonte": "ndsm_lod2",
                                "id": row.id,
                            },
                        })
                    except Exception:
                        pass
            exported += 1
    finally:
        if src_handle is not None:
            src_handle.close()

    if not all_verts:
        meta = {
            "codigo_ibge": code,
            "status": "vazio",
            "edificios": 0,
            "bbox": [west, south, east, north],
            "ndsm": ndsm_info,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "versao": LOD2_VERSION,
            "aviso": "Nenhuma edificação no bbox — colete footprints OSM ou amplie a área.",
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        region = _bbox_region([west, east], [south, north], DEFAULT_HEIGHT_M)
        tileset = {
            "asset": {"version": "1.0", "tilesetVersion": LOD2_VERSION, "gltfUpAxis": "Y"},
            "geometricError": 500,
            "root": {"boundingVolume": {"region": region}, "geometricError": 0, "refine": "ADD"},
        }
        tileset_path.write_text(json.dumps(tileset, indent=2), encoding="utf-8")
        return {**status_lod2(code), **meta}

    vertices = np.vstack(all_verts).astype(np.float32)
    indices = np.concatenate(all_idx).astype(np.uint32)
    glb = _pack_glb(vertices, indices)
    # Remarca generator no GLB via rewrite leve do meta externo (packer usa TILES_VERSION)
    glb_path.write_bytes(glb)

    footprints_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": footprint_features,
                "properties": {
                    "codigo_ibge": code,
                    "lod": "LOD2",
                    "center_lonlat": [lon0, lat0],
                    "bbox": [west, south, east, north],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    region = _bbox_region(lons, lats, max_h)
    xs, zs = vertices[:, 0], vertices[:, 2]
    diag = float(np.hypot(xs.max() - xs.min(), zs.max() - zs.min())) if len(xs) else 500.0

    tileset = {
        "asset": {
            "version": "1.0",
            "tilesetVersion": LOD2_VERSION,
            "gltfUpAxis": "Y",
            "generator": "Sinidu+Clima building_lod2_mesh_service",
        },
        "properties": {
            "codigo_ibge": code,
            "lod": "LOD2",
            "fonte": "nDSM LiDAR + footprints OSM",
            "qualidade": "lod2_lite_ndsm_coarse",
        },
        "geometricError": max(diag, 200.0),
        "root": {
            "boundingVolume": {"region": region},
            "geometricError": 0,
            "refine": "ADD",
            "content": {"uri": "content.glb"},
        },
    }
    tileset_path.write_text(json.dumps(tileset, indent=2), encoding="utf-8")

    meta = {
        "codigo_ibge": code,
        "status": "ok",
        "lod": "LOD2",
        "edificios": exported,
        "com_telhado_tin": lod2_count,
        "fallback_lod1": lod1_fallback,
        "vertices": int(vertices.shape[0]),
        "triangles": int(indices.size // 3),
        "glb_bytes": len(glb),
        "center_lonlat": [lon0, lat0],
        "bbox": [west, south, east, north],
        "max_altura_m": max_h,
        "ndsm": ndsm_info,
        "aviso": (
            "LOD2-lite: telhado TIN amostrado no nDSM (~17 m/px). "
            "Não representa cumeeiras arquitetônicas."
        ),
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "versao": LOD2_VERSION,
        "formato": "3D Tiles 1.0 + glTF 2.0 (GLB)",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        "LOD2 %s: %s edifícios (%s TIN), %s bytes",
        code,
        exported,
        lod2_count,
        len(glb),
    )
    return {**status_lod2(code), **meta}
