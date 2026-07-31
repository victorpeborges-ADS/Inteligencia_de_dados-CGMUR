"""Export CityJSON / CityGML LOD1 das edificações — onda 17c.2.

Perfil mínimo interoperável (PLATEAU-like): Building + Solid LOD1 por footprint extrudado.
CityJSON 2.0 é o formato principal; CityGML 2.0 XML é gerado em paralelo para intercâmbio legado.
"""

from __future__ import annotations

import json
import logging
import math
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.dom import minidom

from shapely.geometry import MultiPolygon, Polygon, shape
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Edificacao, Municipio

logger = logging.getLogger(__name__)

CITYMODEL_VERSION = "17c.2"
DEFAULT_HEIGHT_M = 6.0
MAX_BUILDINGS_EXPORT = 5000
# Vertices inteiros CityJSON: lon/lat ~1e-7 ° (~1 cm), z em mm
SCALE = (1e-7, 1e-7, 0.001)


def citymodel_base_dir() -> Path:
    raw = getattr(settings, "CITYMODEL_DIR", None) or Path(settings.DEM_DIR).parent / "citymodels"
    path = Path(raw)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        path = Path(__file__).resolve().parents[1] / ".data" / "citymodels"
        path.mkdir(parents=True, exist_ok=True)
    return path


def citymodel_muni_dir(codigo_ibge: str) -> Path:
    code = str(codigo_ibge).zfill(7)[:7]
    d = citymodel_base_dir() / code
    d.mkdir(parents=True, exist_ok=True)
    return d


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


def _ring_lonlat(coords: list) -> list[tuple[float, float]]:
    pts = []
    for c in coords:
        if len(c) < 2:
            continue
        pts.append((float(c[0]), float(c[1])))
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _to_int_vertex(
    lon: float,
    lat: float,
    z: float,
    translate: tuple[float, float, float],
) -> list[int]:
    return [
        int(round((lon - translate[0]) / SCALE[0])),
        int(round((lat - translate[1]) / SCALE[1])),
        int(round((z - translate[2]) / SCALE[2])),
    ]


def _extrude_solid_boundaries(
    ring: list[tuple[float, float]],
    height_m: float,
    translate: tuple[float, float, float],
    vertices: list[list[int]],
) -> list[list[list[int]]] | None:
    """Adiciona vértices e retorna shell exterior (lista de surfaces) para Solid LOD1."""
    if len(ring) < 3:
        return None
    h = max(float(height_m), 1.0)
    base_idx: list[int] = []
    top_idx: list[int] = []
    for lon, lat in ring:
        base_idx.append(len(vertices))
        vertices.append(_to_int_vertex(lon, lat, 0.0, translate))
        top_idx.append(len(vertices))
        vertices.append(_to_int_vertex(lon, lat, h, translate))

    n = len(ring)
    # CityJSON: superfície = [anel exterior]; shell = [surfaces]; Solid = [shell]
    # Solo (sentido horário visto de cima → normal para baixo)
    ground = [list(reversed(base_idx))]
    roof = [list(top_idx)]
    walls = []
    for i in range(n):
        j = (i + 1) % n
        # parede: base_i → base_j → top_j → top_i
        walls.append([[base_idx[i], base_idx[j], top_idx[j], top_idx[i]]])

    surfaces = [ground, roof, *walls]
    return surfaces


def status_citymodel(codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    d = citymodel_muni_dir(code)
    cityjson = d / "model.city.json"
    citygml = d / "model.gml"
    meta_path = d / "meta.json"
    meta: dict[str, Any] = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}
    return {
        "codigo_ibge": code,
        "disponivel": cityjson.exists(),
        "cityjson_path": str(cityjson) if cityjson.exists() else None,
        "cityjson_url": f"/static/citymodels/{code}/model.city.json" if cityjson.exists() else None,
        "citygml_path": str(citygml) if citygml.exists() else None,
        "citygml_url": f"/static/citymodels/{code}/model.gml" if citygml.exists() else None,
        "meta": meta,
    }


def _build_citygml_xml(
    buildings: list[dict[str, Any]],
    *,
    codigo_ibge: str,
    nome: str,
) -> str:
    """CityGML 2.0 mínimo — Building com lod1Solid (gml:Solid)."""
    ns = {
        "gml": "http://www.opengis.net/gml/3.2",
        "core": "http://www.opengis.net/citygml/2.0",
        "bldg": "http://www.opengis.net/citygml/building/2.0",
        "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    }
    for prefix, uri in ns.items():
        ET.register_namespace(prefix if prefix != "core" else "", uri)
        if prefix == "core":
            ET.register_namespace("core", uri)

    root = ET.Element(
        "{http://www.opengis.net/citygml/2.0}CityModel",
        {
            "{http://www.w3.org/2001/XMLSchema-instance}schemaLocation": (
                "http://www.opengis.net/citygml/2.0 "
                "http://schemas.opengis.net/citygml/2.0/cityGMLBase.xsd "
                "http://www.opengis.net/citygml/building/2.0 "
                "http://schemas.opengis.net/citygml/building/2.0/building.xsd"
            ),
        },
    )
    name_el = ET.SubElement(root, "{http://www.opengis.net/gml/3.2}name")
    name_el.text = f"Sinidu+Clima LOD1 · {nome} ({codigo_ibge})"

    for b in buildings:
        member = ET.SubElement(root, "{http://www.opengis.net/citygml/2.0}cityObjectMember")
        bldg = ET.SubElement(
            member,
            "{http://www.opengis.net/citygml/building/2.0}Building",
            {"{http://www.opengis.net/gml/3.2}id": b["gml_id"]},
        )
        h_el = ET.SubElement(
            bldg,
            "{http://www.opengis.net/citygml/building/2.0}measuredHeight",
            {"uom": "m"},
        )
        h_el.text = f"{b['height_m']:.2f}"
        if b.get("nome"):
            fn = ET.SubElement(bldg, "{http://www.opengis.net/citygml/building/2.0}function")
            fn.text = str(b.get("uso") or "unknown")
            nm = ET.SubElement(bldg, "{http://www.opengis.net/gml/3.2}name")
            nm.text = str(b["nome"])[:200]

        lod1 = ET.SubElement(bldg, "{http://www.opengis.net/citygml/building/2.0}lod1Solid")
        solid = ET.SubElement(lod1, "{http://www.opengis.net/gml/3.2}Solid")
        exterior = ET.SubElement(solid, "{http://www.opengis.net/gml/3.2}exterior")
        composite = ET.SubElement(exterior, "{http://www.opengis.net/gml/3.2}CompositeSurface")

        for ring3d in b["gml_surfaces"]:
            sm = ET.SubElement(composite, "{http://www.opengis.net/gml/3.2}surfaceMember")
            poly = ET.SubElement(sm, "{http://www.opengis.net/gml/3.2}Polygon")
            ext = ET.SubElement(poly, "{http://www.opengis.net/gml/3.2}exterior")
            ring = ET.SubElement(ext, "{http://www.opengis.net/gml/3.2}LinearRing")
            pos = ET.SubElement(ring, "{http://www.opengis.net/gml/3.2}posList", {"srsDimension": "3"})
            # fechar anel
            coords = list(ring3d)
            if coords and coords[0] != coords[-1]:
                coords = coords + [coords[0]]
            pos.text = " ".join(f"{x:.8f} {y:.8f} {z:.3f}" for x, y, z in coords)

    rough = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
    return pretty.decode("utf-8")


def build_citymodel_for_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
    limit: int = MAX_BUILDINGS_EXPORT,
    ensure_buildings: bool = True,
    formats: tuple[str, ...] = ("cityjson", "citygml"),
) -> dict[str, Any]:
    """Gera model.city.json (+ model.gml opcional) LOD1."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        raise ValueError(f"Município {code} não encontrado")

    out_dir = citymodel_muni_dir(code)
    cityjson_path = out_dir / "model.city.json"
    citygml_path = out_dir / "model.gml"
    meta_path = out_dir / "meta.json"

    if cityjson_path.exists() and not force:
        st = status_citymodel(code)
        st["status"] = "cached"
        return st

    n = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if n == 0 and ensure_buildings:
        from app.data_connectors.building_footprints_collector import collect_buildings_municipality

        collect_buildings_municipality(db, code, force=False)

    rows = (
        db.query(Edificacao)
        .filter(Edificacao.municipio_id == muni.id, Edificacao.geom.isnot(None))
        .limit(max(1, min(int(limit), MAX_BUILDINGS_EXPORT)))
        .all()
    )

    lon0, lat0 = -34.8811, -8.0539
    try:
        if muni.geom is not None:
            cj = db.scalar(func.ST_AsGeoJSON(func.ST_Centroid(muni.geom)))
            if cj:
                c = shape(json.loads(cj))
                lon0, lat0 = float(c.x), float(c.y)
    except Exception:
        pass

    translate = (lon0, lat0, 0.0)
    vertices: list[list[int]] = []
    city_objects: dict[str, Any] = {}
    gml_buildings: list[dict[str, Any]] = []
    exported = 0
    by_fonte: dict[str, int] = {}
    extent = [math.inf, math.inf, 0.0, -math.inf, -math.inf, 0.0]

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
        fonte = row.fonte_altura or "heuristic"
        by_fonte[fonte] = by_fonte.get(fonte, 0) + 1
        obj_id = f"B_{row.id}" if row.id else f"B_{exported}"
        # MultiPolygon → várias solids no mesmo Building (CompositeSolid) ou 1ª parte
        solids = []
        gml_surfaces: list[list[tuple[float, float, float]]] = []

        for poly in polys:
            ring = _ring_lonlat(list(poly.exterior.coords))
            if len(ring) < 3:
                continue
            for lon, lat in ring:
                extent[0] = min(extent[0], lon)
                extent[1] = min(extent[1], lat)
                extent[3] = max(extent[3], lon)
                extent[4] = max(extent[4], lat)
            extent[5] = max(extent[5], altura)

            surfaces = _extrude_solid_boundaries(ring, altura, translate, vertices)
            if not surfaces:
                continue
            solids.append({
                "type": "Solid",
                "lod": "1",
                "boundaries": [surfaces],
            })
            # CityGML surfaces em coordenadas reais
            h = max(altura, 1.0)
            n = len(ring)
            gml_surfaces.append([(lon, lat, 0.0) for lon, lat in reversed(ring)])
            gml_surfaces.append([(lon, lat, h) for lon, lat in ring])
            for i in range(n):
                j = (i + 1) % n
                lon_i, lat_i = ring[i]
                lon_j, lat_j = ring[j]
                gml_surfaces.append([
                    (lon_i, lat_i, 0.0),
                    (lon_j, lat_j, 0.0),
                    (lon_j, lat_j, h),
                    (lon_i, lat_i, h),
                ])

        if not solids:
            continue

        attrs = {
            "measuredHeight": round(altura, 2),
            "storeysAboveGround": int(row.pavimentos or max(1, round(altura / 3))),
            "codigo_ibge": code,
            "fonte_altura": fonte,
            "qualidade": row.qualidade or "Derivado",
            "osm_id": row.osm_id,
            "uso": row.uso,
            "nome": row.nome,
        }
        from app.services.building_quality_service import resolve_building_seal

        seal = resolve_building_seal(fonte, qualidade=row.qualidade)
        attrs["selo_3d"] = seal["selo_3d"]
        attrs["selo_label"] = seal["selo_label"]
        attrs["confianca"] = seal["confianca"]
        attrs["qualidade"] = seal["qualidade"]
        attrs = {k: v for k, v in attrs.items() if v is not None}

        city_objects[obj_id] = {
            "type": "Building",
            "attributes": attrs,
            "geometry": solids,
        }
        gml_buildings.append({
            "gml_id": obj_id,
            "nome": row.nome,
            "uso": row.uso,
            "height_m": altura,
            "gml_surfaces": gml_surfaces,
        })
        exported += 1

    if not math.isfinite(extent[0]):
        extent = [lon0 - 0.01, lat0 - 0.01, 0.0, lon0 + 0.01, lat0 + 0.01, DEFAULT_HEIGHT_M]

    cityjson_doc = {
        "type": "CityJSON",
        "version": "2.0",
        "transform": {
            "scale": list(SCALE),
            "translate": list(translate),
        },
        "metadata": {
            "referenceSystem": "https://www.opengis.net/def/crs/EPSG/0/4326",
            "title": f"Sinidu+Clima LOD1 — {muni.nome} ({code})",
            "geographicalExtent": extent,
            "presentLoDs": ["1"],
            "presentCityObjects": ["Building"],
            "datasetPointOfContact": {
                "contactName": "Sinidu+Clima / MCID-CGMUR",
                "emailAddress": "",
                "website": "",
            },
            "citymodelVersion": CITYMODEL_VERSION,
        },
        "CityObjects": city_objects,
        "vertices": vertices,
    }

    if "cityjson" in formats:
        cityjson_path.write_text(
            json.dumps(cityjson_doc, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )

    if "citygml" in formats:
        xml_text = _build_citygml_xml(
            gml_buildings,
            codigo_ibge=code,
            nome=muni.nome or code,
        )
        citygml_path.write_text(xml_text, encoding="utf-8")

    meta = {
        "codigo_ibge": code,
        "status": "ok" if exported else "vazio",
        "edificios": exported,
        "vertices": len(vertices),
        "formatos": [f for f in formats],
        "cityjson_bytes": cityjson_path.stat().st_size if cityjson_path.exists() else 0,
        "citygml_bytes": citygml_path.stat().st_size if citygml_path.exists() else 0,
        "por_fonte_altura": by_fonte,
        "limit": limit,
        "lod": "1",
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "versao": CITYMODEL_VERSION,
        "especificacao": "CityJSON 2.0 + CityGML 2.0 Building LOD1",
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("CityJSON/CityGML %s: %s edifícios", code, exported)
    return {**status_citymodel(code), **meta}
