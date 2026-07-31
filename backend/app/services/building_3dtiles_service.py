"""Export 3D Tiles (LOD1) das edificações — onda 17c.1.

Pipeline próprio (sem py3dtiles): extrusão de footprints → glTF/GLB + tileset.json 1.0.
Coordenadas locais ENU (metros) centradas no município; boundingVolume.region em WGS84.
"""

from __future__ import annotations

import json
import logging
import math
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from shapely.geometry import MultiPolygon, Polygon, shape
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Edificacao, Municipio

logger = logging.getLogger(__name__)

TILES_VERSION = "17c.1"
DEFAULT_HEIGHT_M = 6.0
MAX_BUILDINGS_EXPORT = 5000


def tiles3d_base_dir() -> Path:
    raw = getattr(settings, "TILES3D_DIR", None) or Path(settings.DEM_DIR).parent / "3dtiles"
    path = Path(raw)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = Path(__file__).resolve().parents[1] / ".data" / "3dtiles"
        path.mkdir(parents=True, exist_ok=True)
    return path


def tiles3d_muni_dir(codigo_ibge: str) -> Path:
    code = str(codigo_ibge).zfill(7)[:7]
    d = tiles3d_base_dir() / code
    d.mkdir(parents=True, exist_ok=True)
    return d


def _lonlat_to_local(lon: float, lat: float, lon0: float, lat0: float) -> tuple[float, float]:
    """ENU aproximado (metros): x=leste, y=norte."""
    x = (lon - lon0) * 111_320.0 * math.cos(math.radians(lat0))
    y = (lat - lat0) * 110_540.0
    return x, y


def _ring_xy(coords: list, lon0: float, lat0: float) -> list[tuple[float, float]]:
    pts = []
    for c in coords:
        if len(c) < 2:
            continue
        pts.append(_lonlat_to_local(float(c[0]), float(c[1]), lon0, lat0))
    # remove closing duplicate
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _fan_tris(n: int) -> list[tuple[int, int, int]]:
    if n < 3:
        return []
    return [(0, i, i + 1) for i in range(1, n - 1)]


def _extrude_polygon(
    ring_xy: list[tuple[float, float]],
    height_m: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Retorna vertices (N,3) Y-up e indices uint32 triangulares."""
    if len(ring_xy) < 3:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0,), dtype=np.uint32)

    n = len(ring_xy)
    h = max(float(height_m), 1.0)
    # base z=0, topo z=h — glTF Y-up: (x, height, -y) para manter leste/norte
    bottom = np.array([[x, 0.0, -y] for x, y in ring_xy], dtype=np.float32)
    top = np.array([[x, h, -y] for x, y in ring_xy], dtype=np.float32)
    verts = np.vstack([bottom, top])

    indices: list[int] = []
    # piso (normal para baixo — invertido)
    for a, b, c in _fan_tris(n):
        indices.extend([a, c, b])
    # teto
    for a, b, c in _fan_tris(n):
        indices.extend([n + a, n + b, n + c])
    # paredes
    for i in range(n):
        j = (i + 1) % n
        # quad i,j,j+n,i+n
        indices.extend([i, j, n + j, i, n + j, n + i])

    return verts, np.asarray(indices, dtype=np.uint32)


def _pack_glb(vertices: np.ndarray, indices: np.ndarray) -> bytes:
    """glTF 2.0 binary (GLB) mínimo — POSITION + INDICES."""
    if vertices.size == 0 or indices.size == 0:
        # cubo unitário placeholder
        vertices = np.array(
            [
                [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                [0, 0, -1], [1, 0, -1], [1, 1, -1], [0, 1, -1],
            ],
            dtype=np.float32,
        )
        indices = np.array(
            [0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1,
             1, 5, 6, 1, 6, 2, 2, 6, 7, 2, 7, 3, 3, 7, 4, 3, 4, 0],
            dtype=np.uint32,
        )

    v_bytes = vertices.astype(np.float32).tobytes()
    # align indices to 4 bytes
    pad_v = (4 - (len(v_bytes) % 4)) % 4
    v_bytes_padded = v_bytes + (b"\x00" * pad_v)
    i_bytes = indices.astype(np.uint32).tobytes()

    bin_blob = v_bytes_padded + i_bytes
    v_count = int(vertices.shape[0])
    i_count = int(indices.size)
    v_min = vertices.min(axis=0).tolist()
    v_max = vertices.max(axis=0).tolist()
    byte_offset_idx = len(v_bytes_padded)

    gltf = {
        "asset": {"version": "2.0", "generator": f"Sinidu+Clima {TILES_VERSION}"},
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{
            "primitives": [{
                "attributes": {"POSITION": 0},
                "indices": 1,
                "mode": 4,
            }],
        }],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": v_count,
                "type": "VEC3",
                "max": v_max,
                "min": v_min,
            },
            {
                "bufferView": 1,
                "componentType": 5125,
                "count": i_count,
                "type": "SCALAR",
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": len(v_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": byte_offset_idx, "byteLength": len(i_bytes), "target": 34963},
        ],
        "buffers": [{"byteLength": len(bin_blob)}],
    }
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_pad = (4 - (len(json_bytes) % 4)) % 4
    json_bytes += b" " * json_pad

    # GLB: header + JSON chunk + BIN chunk
    chunks = b""
    chunks += struct.pack("<I", len(json_bytes))
    chunks += struct.pack("<I", 0x4E4F534A)  # JSON
    chunks += json_bytes
    chunks += struct.pack("<I", len(bin_blob))
    chunks += struct.pack("<I", 0x004E4942)  # BIN
    chunks += bin_blob

    total_len = 12 + len(chunks)
    header = struct.pack("<4sII", b"glTF", 2, total_len)
    return header + chunks


def _bbox_region(lons: list[float], lats: list[float], max_h: float) -> list[float]:
    """boundingVolume.region: [west, south, east, north, minHeight, maxHeight] em radianos/metros."""
    if not lons or not lats:
        return [0, 0, 0, 0, 0, max_h]
    west, east = min(lons), max(lons)
    south, north = min(lats), max(lats)
    return [
        math.radians(west),
        math.radians(south),
        math.radians(east),
        math.radians(north),
        0.0,
        float(max_h),
    ]


def _geom_polygons(g) -> list[Polygon]:
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return [p for p in g.geoms if isinstance(p, Polygon) and not p.is_empty]
    try:
        if g.geom_type == "Polygon":
            return [g]
        if g.geom_type == "MultiPolygon":
            return [p for p in g.geoms if not p.is_empty]
    except Exception:
        pass
    return []


def status_3dtiles(codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    d = tiles3d_muni_dir(code)
    tileset = d / "tileset.json"
    meta_path = d / "meta.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {
        "codigo_ibge": code,
        "disponivel": tileset.exists(),
        "tileset_path": str(tileset) if tileset.exists() else None,
        "tileset_url": f"/static/3dtiles/{code}/tileset.json" if tileset.exists() else None,
        "content_url": f"/static/3dtiles/{code}/content.glb" if (d / "content.glb").exists() else None,
        "meta": meta,
    }


def build_3dtiles_for_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
    limit: int = MAX_BUILDINGS_EXPORT,
    ensure_buildings: bool = True,
) -> dict[str, Any]:
    """Gera tileset.json + content.glb (LOD1) para o município."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    out_dir = tiles3d_muni_dir(code)
    tileset_path = out_dir / "tileset.json"
    glb_path = out_dir / "content.glb"
    meta_path = out_dir / "meta.json"

    if tileset_path.exists() and glb_path.exists() and not force:
        st = status_3dtiles(code)
        st["status"] = "cached"
        return st

    n = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if n == 0 and ensure_buildings:
        from app.data_connectors.building_footprints_collector import collect_buildings_municipality

        collect_buildings_municipality(db, code, force=False)
        n = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()

    rows = (
        db.query(Edificacao)
        .filter(Edificacao.municipio_id == muni.id, Edificacao.geom.isnot(None))
        .limit(max(1, min(int(limit), MAX_BUILDINGS_EXPORT)))
        .all()
    )

    # Centro: centróide do município ou média dos footprints
    lon0, lat0 = -34.8811, -8.0539  # Recife fallback
    try:
        from sqlalchemy import func

        if muni.geom is not None:
            cj = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(muni.geom)))
            if cj:
                c = shape(json.loads(cj))
                lon0, lat0 = float(c.x), float(c.y)
    except Exception:
        pass

    all_verts: list[np.ndarray] = []
    all_idx: list[np.ndarray] = []
    v_offset = 0
    lons: list[float] = []
    lats: list[float] = []
    max_h = DEFAULT_HEIGHT_M
    exported = 0
    by_fonte: dict[str, int] = {}

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
        altura = float(row.altura_m or DEFAULT_HEIGHT_M)
        max_h = max(max_h, altura)
        fonte = row.fonte_altura or "heuristic"
        by_fonte[fonte] = by_fonte.get(fonte, 0) + 1

        for poly in polys:
            ring = list(poly.exterior.coords)
            for c in ring:
                lons.append(float(c[0]))
                lats.append(float(c[1]))
            xy = _ring_xy(ring, lon0, lat0)
            verts, idx = _extrude_polygon(xy, altura)
            if verts.size == 0:
                continue
            all_verts.append(verts)
            all_idx.append(idx + v_offset)
            v_offset += verts.shape[0]
        exported += 1

    if not all_verts:
        # tileset vazio válido
        region = _bbox_region([lon0 - 0.01, lon0 + 0.01], [lat0 - 0.01, lat0 + 0.01], DEFAULT_HEIGHT_M)
        tileset = {
            "asset": {"version": "1.0", "tilesetVersion": TILES_VERSION, "gltfUpAxis": "Y"},
            "geometricError": 5000,
            "root": {
                "boundingVolume": {"region": region},
                "geometricError": 0,
                "refine": "ADD",
            },
        }
        tileset_path.write_text(json.dumps(tileset, indent=2), encoding="utf-8")
        meta = {
            "codigo_ibge": code,
            "status": "vazio",
            "edificios": 0,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
            "versao": TILES_VERSION,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return {**status_3dtiles(code), "status": "vazio", "edificios": 0}

    vertices = np.vstack(all_verts).astype(np.float32)
    indices = np.concatenate(all_idx).astype(np.uint32)
    glb = _pack_glb(vertices, indices)
    glb_path.write_bytes(glb)

    region = _bbox_region(lons, lats, max_h)
    # geometricError ~ diagonal da bbox em metros
    xs = vertices[:, 0]
    zs = vertices[:, 2]
    diag = float(np.hypot(xs.max() - xs.min(), zs.max() - zs.min())) if len(xs) else 1000.0

    tileset = {
        "asset": {
            "version": "1.0",
            "tilesetVersion": TILES_VERSION,
            "gltfUpAxis": "Y",
            "generator": "Sinidu+Clima building_3dtiles_service",
        },
        "properties": {
            "codigo_ibge": code,
            "lod": "LOD1",
            "fonte": "OSM / nDSM / heurística",
        },
        "geometricError": max(diag, 500.0),
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
        "edificios": exported,
        "vertices": int(vertices.shape[0]),
        "triangles": int(indices.size // 3),
        "glb_bytes": len(glb),
        "center_lonlat": [lon0, lat0],
        "max_altura_m": max_h,
        "por_fonte_altura": by_fonte,
        "limit": limit,
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "versao": TILES_VERSION,
        "formato": "3D Tiles 1.0 + glTF 2.0 (GLB)",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("3D Tiles %s: %s edifícios, %s bytes", code, exported, len(glb))
    return {**status_3dtiles(code), **meta}
