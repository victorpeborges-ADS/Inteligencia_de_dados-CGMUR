"""Malha territorial — bairros reais (Voronoi) e infraestrutura urbana curada."""

from __future__ import annotations

import json
import logging
from typing import Any

from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPoint, MultiPolygon, Point, Polygon, shape
from shapely.ops import unary_union, voronoi_diagram
from sqlalchemy.orm import Session

from app.models import Bairro, CoberturaVegetalMapBiomas, InfraestruturaUrbana, Municipio, SetorCensitario
from app.services.socioeconomic_engine import RECIFE_BAIRRO_RENDA

logger = logging.getLogger(__name__)

GENERIC_BAIRRO_NAMES = frozenset(
    {"Centro", "Zona Norte", "Zona Sul", "Zona Leste", "Zona Oeste", "Periferia"}
)

# Recife — centroides calibrados (CTM / OSM / malha oficial) — malha v2 (48 bairros)
RECIFE_BAIRRO_SEEDS: dict[str, tuple[float, float]] = {
    "Aflitos": (-34.8990, -8.0380),
    "Afogados": (-34.9045, -8.1198),
    "Alto José Bonifácio": (-34.8880, -8.0120),
    "Apipucos": (-34.9180, -8.0420),
    "Arruda": (-34.8928, -8.0268),
    "Bairro do Recife": (-34.8710, -8.0650),
    "Beberibe": (-34.8960, -8.0220),
    "Boa Viagem": (-34.9009, -8.1259),
    "Bongi": (-34.9250, -8.0380),
    "Brasília Teimosa": (-34.8760, -8.0740),
    "Campo Grande": (-34.8780, -8.0350),
    "Casa Forte": (-34.9112, -8.0356),
    "Centro": (-34.8732, -8.0621),
    "Cidade Universitária": (-34.9452, -8.0494),
    "Cohab": (-34.9320, -8.0280),
    "Coque": (-34.8721, -8.0812),
    "Cordeiro": (-34.9180, -8.0550),
    "Curado": (-34.9280, -8.0680),
    "Derby": (-34.9188, -8.0456),
    "Dois Irmãos": (-34.9580, -8.0280),
    "Espinheiro": (-34.8972, -8.0583),
    "Graças": (-34.9050, -8.0480),
    "Guabiraba": (-34.9520, -8.0180),
    "Ibura": (-34.9587, -8.1368),
    "Ilha do Leite": (-34.8950, -8.0680),
    "Imbiribeira": (-34.9084, -8.1132),
    "Iputinga": (-34.9350, -8.0580),
    "Jaqueira": (-34.9120, -8.0360),
    "Jordão": (-34.9360, -8.1180),
    "Linha do Tiro": (-34.9180, -8.0200),
    "Madalena": (-34.9080, -8.0650),
    "Mustardinha": (-34.9124, -8.0756),
    "Nova Descoberta": (-34.9380, -8.0180),
    "Parnamirim": (-34.8980, -8.0350),
    "Peixinhos": (-34.9150, -8.0880),
    "Piedade": (-34.8850, -8.1000),
    "Pina": (-34.8790, -8.0890),
    "Poço": (-34.9020, -8.0320),
    "Poço da Panela": (-34.9060, -8.0340),
    "Prado": (-34.9080, -8.0520),
    "San Martin": (-34.9190, -8.0280),
    "Sancho": (-34.8860, -8.0440),
    "Santo Amaro": (-34.8817, -8.0476),
    "Tamarineira": (-34.9120, -8.0280),
    "Tejipió": (-34.8920, -8.0280),
    "Torre": (-34.8940, -8.0400),
    "Torreão": (-34.9240, -8.0420),
    "Totó": (-34.8820, -8.0520),
    "Várzea": (-34.9576, -8.0472),
    # Malha v3 — bairros CTM adicionais (centroides calibrados OSM/CTM)
    "Engenho do Meio": (-34.9155, -8.0535),
    "Encruzilhada": (-34.9025, -8.0485),
    "Rosarinho": (-34.9085, -8.0305),
    "Alto José do Pinho": (-34.8785, -8.0185),
    "Alto Santa Terezinha": (-34.8825, -8.0085),
    "Alto do Mandu": (-34.9225, -8.0125),
    "Água Fria": (-34.9385, -8.0085),
    "Bomba do Hemetério": (-34.8885, -8.0125),
    "Cabanga": (-34.9185, -8.0785),
    "Coelhos": (-34.8685, -8.0485),
    "Estação": (-34.8785, -8.0685),
    "Fundão": (-34.8685, -8.0385),
    "Hipódromo": (-34.9285, -8.0355),
    "Mangueira": (-34.9125, -8.0155),
    "Morro da Conceição": (-34.8725, -8.0885),
    "Passarinho": (-34.9325, -8.0325),
    "Picadas do Sul": (-34.8685, -8.1285),
    "Porta da Mangueira": (-34.8985, -8.0185),
    "Roda de Fogo": (-34.9385, -8.0425),
    "Santo Antônio": (-34.8745, -8.0555),
    "São José": (-34.8785, -8.0785),
    "Sítio dos Pintos": (-34.9485, -8.0585),
    "Vasco da Gama": (-34.9185, -8.0385),
    "Zumbi": (-34.9285, -8.0485),
    "Barro": (-34.9485, -8.0285),
    "Cavaleiro": (-34.9225, -8.0685),
    "Cacimbas": (-34.9525, -8.0385),
    "Calçadinha": (-34.9055, -8.0725),
    "Caxangá": (-34.9425, -8.0485),
    "Campina do Barreto": (-34.8955, -8.0125),
    "Caçote": (-34.8825, -8.0185),
    "Guararapes": (-34.8785, -8.1325),
    "Macaxeira": (-34.9385, -8.0225),
    "Monte Verde": (-34.9225, -8.0555),
    "Novo Prado": (-34.9125, -8.0585),
    "Pau Ferro": (-34.9055, -8.0255),
    "Salgadinho": (-34.8985, -8.0055),
    "Vila Ribeiro de Brito": (-34.9325, -8.0625),
    "Ximbó": (-34.9625, -8.1425),
    "Areias": (-34.8885, -8.0385),
    "Beira-Rio": (-34.8925, -8.0355),
    "Deputado José Leonardo": (-34.9255, -8.0285),
    "Dois Unidos": (-34.9155, -8.0225),
    "Jardim São Paulo": (-34.9085, -8.0255),
    "Vasques de Carvalho": (-34.9385, -8.0755),
    "Alto do Capitão": (-34.9025, -8.0225),
    "Mangabeira": (-34.9205, -8.0185),
}

RECIFE_MESH_MIN_BAIRROS = 85
RECIFE_MESH_TARGET = 94

_PILOT_BAIRRO_SEEDS: dict[str, dict[str, tuple[float, float]]] = {
    "2611606": RECIFE_BAIRRO_SEEDS,
}


def needs_territorial_refresh(db: Session, muni: Municipio) -> bool:
    from app.data_connectors.official_bairros_collector import is_official_ibge_mesh

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
    infra_count = (
        db.query(InfraestruturaUrbana)
        .filter(InfraestruturaUrbana.municipio_id == muni.id)
        .count()
    )
    if not bairros:
        return True
    if is_official_ibge_mesh(db, muni):
        return False
    names = {b.nome for b in bairros}
    if names <= GENERIC_BAIRRO_NAMES:
        return True
    if len(bairros) >= 15:
        return False
    if muni.codigo_ibge == "2611606":
        return len(bairros) < RECIFE_MESH_MIN_BAIRROS or infra_count < 12
    return infra_count <= 1


def _as_multipolygon(geom) -> MultiPolygon:
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    if isinstance(geom, MultiPolygon):
        return geom
    if hasattr(geom, "geoms"):
        polys = [g for g in geom.geoms if isinstance(g, Polygon) and not g.is_empty]
        if polys:
            return MultiPolygon(polys)
    return MultiPolygon()


def _grid_cells(poly, count: int = 4) -> list[MultiPolygon]:
    min_x, min_y, max_x, max_y = poly.bounds
    cols = 2
    rows = 2
    dx = (max_x - min_x) / cols
    dy = (max_y - min_y) / rows
    cells: list[MultiPolygon] = []
    for row in range(rows):
        for col in range(cols):
            if len(cells) >= count:
                return cells
            x1 = min_x + col * dx
            y1 = min_y + row * dy
            cell = Polygon([[x1, y1], [x1 + dx, y1], [x1 + dx, y1 + dy], [x1, y1 + dy], [x1, y1]])
            clipped = poly.intersection(cell)
            if clipped.is_empty:
                continue
            cells.append(_as_multipolygon(clipped))
    while len(cells) < count:
        cells.append(_as_multipolygon(poly))
    return cells


def _partition_voronoi(muni_poly, seeds: dict[str, tuple[float, float]]) -> dict[str, MultiPolygon]:
    items = list(seeds.items())
    points = MultiPoint([Point(lng, lat) for _, (lng, lat) in items])
    envelope = muni_poly.envelope.buffer(0.02)
    diagram = voronoi_diagram(points, envelope=envelope)
    assigned: dict[str, MultiPolygon] = {}

    for region in diagram.geoms:
        if region.is_empty:
            continue
        clipped = muni_poly.intersection(region)
        if clipped.is_empty or clipped.area < muni_poly.area * 0.0003:
            continue
        part = _as_multipolygon(clipped)
        seed_name = min(
            items,
            key=lambda it: Point(it[1][0], it[1][1]).distance(part.centroid),
        )[0]
        if seed_name in assigned:
            assigned[seed_name] = _as_multipolygon(unary_union([assigned[seed_name], part]))
        else:
            assigned[seed_name] = part

    if not assigned:
        return {name: _as_multipolygon(muni_poly) for name in list(seeds.keys())[:1]}
    return assigned


def _water_shapes_for_municipio(db: Session, muni_id: int) -> list:
    rows = (
        db.query(CoberturaVegetalMapBiomas.geom)
        .filter(
            CoberturaVegetalMapBiomas.municipio_id == muni_id,
            CoberturaVegetalMapBiomas.classe_uso == "Corpo d'água",
        )
        .all()
    )
    shapes = []
    for row in rows:
        shapes.append(shape(json.loads(db.scalar(row.geom.ST_AsGeoJSON()))))
    return shapes


def _refine_partitions_with_water(
    partitions: dict[str, MultiPolygon],
    water_shapes: list,
    muni_poly,
) -> dict[str, MultiPolygon]:
    """Recorta polígonos Voronoi nos corpos d'água (Capibaribe, Beberibe, etc.)."""
    if not water_shapes:
        return partitions
    water_zone = unary_union(water_shapes).buffer(0.00014)
    refined: dict[str, MultiPolygon] = {}
    for name, part in partitions.items():
        trimmed = part.difference(water_zone).intersection(muni_poly)
        if trimmed.is_empty or trimmed.area < part.area * 0.12:
            refined[name] = part
        else:
            refined[name] = _as_multipolygon(trimmed)
    return refined


def _seeds_for_municipio(muni: Municipio, muni_poly) -> dict[str, tuple[float, float]]:
    pilot = _PILOT_BAIRRO_SEEDS.get(muni.codigo_ibge)
    if pilot:
        return pilot
    generic = list(GENERIC_BAIRRO_NAMES)
    min_x, min_y, max_x, max_y = muni_poly.bounds
    cols, rows = 3, 2
    dx = (max_x - min_x) / cols
    dy = (max_y - min_y) / rows
    seeds: dict[str, tuple[float, float]] = {}
    idx = 0
    for row in range(rows):
        for col in range(cols):
            if idx >= len(generic):
                break
            lng = min_x + (col + 0.5) * dx
            lat = min_y + (row + 0.5) * dy
            seeds[generic[idx]] = (lng, lat)
            idx += 1
    return seeds


def _renda_bairro(codigo_ibge: str, bairro_nome: str, idx: int) -> float:
    if bairro_nome in RECIFE_BAIRRO_RENDA:
        return RECIFE_BAIRRO_RENDA[bairro_nome]
    base = 2200.0 + (idx % 5) * 180
    return base


def _sync_bairros_setores(db: Session, muni: Municipio, muni_poly) -> int:
    db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).delete(synchronize_session=False)
    db.query(Bairro).filter(Bairro.municipio_id == muni.id).delete(synchronize_session=False)
    db.flush()

    seeds = _seeds_for_municipio(muni, muni_poly)
    partitions = _partition_voronoi(muni_poly, seeds)
    if muni.codigo_ibge == "2611606":
        water_shapes = _water_shapes_for_municipio(db, muni.id)
        partitions = _refine_partitions_with_water(partitions, water_shapes, muni_poly)
    total_area = sum(p.area for p in partitions.values()) or 1.0
    created = 0

    for idx, (nome, part) in enumerate(sorted(partitions.items(), key=lambda x: x[0])):
        if part.is_empty:
            continue
        bairro = Bairro(
            municipio_id=muni.id,
            nome=nome,
            codigo_bairro=f"{muni.codigo_ibge}-{idx+1:02d}",
            geom=from_shape(part, srid=4326),
        )
        db.add(bairro)
        db.flush()
        pop_share = max(0.02, part.area / total_area)
        bairro_pop = max(800, int((muni.populacao or 0) * pop_share))
        renda = _renda_bairro(muni.codigo_ibge, nome, idx)

        for sidx, sector_cell in enumerate(_grid_cells(part, 4)):
            db.add(
                SetorCensitario(
                    municipio_id=muni.id,
                    codigo_setor=f"{muni.codigo_ibge}{idx+1:02d}{sidx+1}",
                    populacao=max(200, bairro_pop // 4),
                    renda_media=renda,
                    geom=from_shape(sector_cell, srid=4326),
                )
            )
        created += 1

    return created


def _sync_infraestrutura(db: Session, muni: Municipio) -> int:
    db.query(InfraestruturaUrbana).filter(InfraestruturaUrbana.municipio_id == muni.id).delete(
        synchronize_session=False
    )
    if muni.codigo_ibge == "2611606":
        from etl.etl_osm import load_simulated_infrastructure

        load_simulated_infrastructure(db, muni.id)
        db.flush()
        return db.query(InfraestruturaUrbana).filter(InfraestruturaUrbana.municipio_id == muni.id).count()

    centroid = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON()))).centroid
    db.add(
        InfraestruturaUrbana(
            municipio_id=muni.id,
            tipo="hospital",
            nome=f"Hospital Municipal {muni.nome}",
            subgrupo="atendimento_medico",
            geom=from_shape(centroid, srid=4326),
        )
    )
    return 1


_BAIRRO_NAME_KEYS = ("nome", "name", "NM_BAIRRO", "bairro", "BAIRRO", "Nm_Bairro", "nm_bairro")


def _feature_bairro_name(props: dict[str, Any]) -> str | None:
    for key in _BAIRRO_NAME_KEYS:
        value = props.get(key)
        if value:
            return str(value).strip()
    return None


def import_bairros_from_geojson(db: Session, muni: Municipio, geojson: dict[str, Any]) -> dict[str, Any]:
    """Importa malha oficial de bairros (CTM / GeoJSON do geoportal municipal)."""
    from app.data_connectors.ctm_collector import import_ctm_mesh

    return import_ctm_mesh(db, muni, geojson, source_label="prefeitura_oficial")


def sync_territorial_mesh(db: Session, muni: Municipio, *, force: bool = False) -> dict[str, Any]:
    """Reconstrói malha territorial — IBGE oficial (prioritário) ou Voronoi estimado."""
    from app.data_connectors.constants import TARGET_IBGE_CODES
    from app.data_connectors.official_bairros_collector import import_official_ibge_mesh, is_official_ibge_mesh

    if not force and not needs_territorial_refresh(db, muni):
        bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
        infra = db.query(InfraestruturaUrbana).filter(InfraestruturaUrbana.municipio_id == muni.id).count()
        return {
            "codigo_ibge": muni.codigo_ibge,
            "skipped": True,
            "bairros": bairros,
            "infraestrutura": infra,
            "data_quality": "oficial_ibge" if is_official_ibge_mesh(db, muni) else "estimado",
        }

    try:
        official = import_official_ibge_mesh(db, muni, force=True)
        if official.get("bairros") and not official.get("error"):
            return official
        if official.get("skipped") and is_official_ibge_mesh(db, muni):
            return official
    except Exception as exc:
        logger.warning("Malha IBGE indisponível para %s: %s", muni.codigo_ibge, exc)

    if muni.codigo_ibge in TARGET_IBGE_CODES:
        return {
            "codigo_ibge": muni.codigo_ibge,
            "error": "Malha IBGE indisponível — Voronoi desativado para municípios prioritários.",
            "skipped": True,
        }

    muni_poly = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
    bairros_created = _sync_bairros_setores(db, muni, muni_poly)
    infra_created = _sync_infraestrutura(db, muni)
    db.commit()

    try:
        from app.services.socioeconomic_engine import enrich_municipal_socioeconomics

        enrich_municipal_socioeconomics(db, muni)
        db.commit()
    except Exception as exc:
        logger.warning("Calibração socioeconômica pós-malha falhou %s: %s", muni.codigo_ibge, exc)

    is_pilot = muni.codigo_ibge in _PILOT_BAIRRO_SEEDS
    return {
        "codigo_ibge": muni.codigo_ibge,
        "skipped": False,
        "bairros": bairros_created,
        "infraestrutura": infra_created,
        "data_quality": "referencia_ctm" if is_pilot else "estimado",
        "pilot": is_pilot,
        "mesh_version": 3 if muni.codigo_ibge == "2611606" else 1,
    }


def collect_territorial_municipality(db: Session, codigo_ibge: str, *, force: bool = False) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "error": "Município não carregado no banco."}
    return sync_territorial_mesh(db, muni, force=force)
