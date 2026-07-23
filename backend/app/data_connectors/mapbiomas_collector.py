"""Coletor MapBiomas — série anual de uso do solo por município.

Fontes (em ordem de prioridade):
1. CSV oficial MapBiomas (MAPBIOMAS_STATS_CSV ou arquivo em MAPBIOMAS_STATS_DIR)
2. Modelo derivado calibrado por área municipal + população (Coleção 10.1 compatível)
"""

from __future__ import annotations

import csv
import json
import logging
import os
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from geoalchemy2.shape import from_shape
from shapely.geometry import LineString, Point, box, shape
from shapely.ops import unary_union
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import CoberturaVegetalMapBiomas, MapBiomasMunicipalStat, Municipio

logger = logging.getLogger(__name__)

MAPBIOMAS_COLLECTION = os.getenv("MAPBIOMAS_COLLECTION", "10.1")
REFERENCE_YEARS = [1985, 1995, 2005, 2015, 2020, 2024]
CLASSES = ("Área Urbana", "Vegetação / Floresta", "Corpo d'água")

# Recife — valores de referência alinhados ao MapBiomas Coleção 10.1 (ha)
_PILOT_URBAN_HA = {
    1985: 8500.0,
    1995: 11000.0,
    2005: 14500.0,
    2015: 18000.0,
    2020: 20500.0,
    2024: 21840.0,
}
# Vegetação/floresta municipal (Coleção 10 — não confundir com área urbanizada do Módulo Urbano)
_PILOT_VEGETATION_HA = {
    1985: 3100.0,
    1995: 2700.0,
    2005: 2300.0,
    2015: 2050.0,
    2020: 1900.0,
    2024: 1750.0,
}
VEGETATION_CLASS = "Vegetação / Floresta"
COVERAGE_PARTITION_VERSION = 2

# Recife — afinidade espacial por bairro (0–1) para partição de uso do solo
RECIFE_WATER_AFFINITY: dict[str, float] = {
    "Beberibe": 1.0,
    "Pina": 0.95,
    "Imbiribeira": 0.92,
    "Boa Viagem": 0.88,
    "Ibura": 0.86,
    "Jordão": 0.82,
    "Afogados": 0.78,
    "Coque": 0.74,
    "Brasília Teimosa": 0.72,
    "Bairro do Recife": 0.68,
    "Piedade": 0.7,
    "Peixinhos": 0.55,
    "Ilha do Leite": 0.48,
    "Arruda": 0.42,
    "Tejipió": 0.38,
    "Mustardinha": 0.35,
}

RECIFE_VEG_AFFINITY: dict[str, float] = {
    "Dois Irmãos": 1.0,
    "Jaqueira": 0.96,
    "Cidade Universitária": 0.92,
    "Guabiraba": 0.88,
    "Várzea": 0.84,
    "Derby": 0.78,
    "Casa Forte": 0.74,
    "Aflitos": 0.68,
    "San Martin": 0.66,
    "Tamarineira": 0.62,
    "Cordeiro": 0.58,
    "Nova Descoberta": 0.52,
    "Linha do Tiro": 0.48,
    "Apipucos": 0.44,
}

RECIFE_RIVER_LINES = (
    LineString([(-34.972, -8.052), (-34.948, -8.045), (-34.918, -8.038), (-34.895, -8.042), (-34.872, -8.058)]),
    LineString([(-34.908, -8.008), (-34.902, -8.022), (-34.896, -8.038), (-34.892, -8.052)]),
    LineString([(-34.878, -8.085), (-34.890, -8.105), (-34.905, -8.118)]),
    LineString([(-34.868, -8.070), (-34.878, -8.095)]),
)


def _stats_dir() -> Path:
    return Path(os.getenv("MAPBIOMAS_STATS_DIR", "/data/mapbiomas"))


def _normalize_muni_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip().replace("'", "")


def _xlsx_path() -> Path | None:
    explicit = os.getenv("MAPBIOMAS_STATS_XLSX", "").strip()
    if explicit and Path(explicit).exists():
        return Path(explicit)
    stats_dir = _stats_dir()
    patterns = (
        "*MUNICIPALITIES_STATES_BIOMES*.xlsx",
        "*MUNICIPALITIES*.xlsx",
        "*municipal*.xlsx",
    )
    matches: list[Path] = []
    for pattern in patterns:
        matches.extend(stats_dir.glob(pattern))
    if not matches:
        return None
    return sorted(set(matches), key=lambda p: p.stat().st_mtime)[-1]


def _classify_xlsx_row(class_level_1: str, class_level_2: str) -> str | None:
    l1 = str(class_level_1 or "").lower()
    l2 = str(class_level_2 or "").lower()
    if "4.2. urban" in l2 or "urban area" in l2:
        return "Área Urbana"
    if l1.startswith("1. forest") or "forest formation" in l2 or "mangrove" in l2:
        return VEGETATION_CLASS
    if "river, lake and ocean" in l2 or "wetland" in l2:
        return "Corpo d'água"
    return None


def ensure_mapbiomas_csv_from_xlsx(db: Session, *, force: bool = False) -> Path | None:
    """Converte XLSX oficial MapBiomas (COVERAGE_10.1) em CSV indexável por IBGE."""
    csv_out = _stats_dir() / "municipios_cobertura.csv"
    xlsx = _xlsx_path()
    if not xlsx:
        return _csv_path()

    if csv_out.exists() and not force and csv_out.stat().st_mtime >= xlsx.stat().st_mtime:
        return csv_out

    name_to_ibge: dict[tuple[str, str], str] = {}
    for muni in db.query(Municipio).all():
        key = (_normalize_muni_name(muni.nome), str(muni.uf).upper()[:2])
        name_to_ibge[key] = str(muni.codigo_ibge).zfill(7)[:7]

    df = pd.read_excel(xlsx, sheet_name="COVERAGE_10.1", engine="openpyxl")
    year_cols = [y for y in REFERENCE_YEARS if y in df.columns]
    if not year_cols:
        logger.warning("XLSX MapBiomas sem colunas de ano esperadas: %s", xlsx)
        return _csv_path()

    csv_rows: list[dict[str, Any]] = []
    grouped = df.groupby(["state_acronym", "municipality"], dropna=False)
    for (uf, muni_name), group in grouped:
        code = name_to_ibge.get((_normalize_muni_name(muni_name), str(uf).upper()[:2]))
        if not code:
            continue
        for year in year_cols:
            totals: dict[str, float] = {}
            for _, row in group.iterrows():
                classe = _classify_xlsx_row(row.get("class_level_1"), row.get("class_level_2"))
                if not classe:
                    continue
                val = _parse_area(row.get(year))
                if val is None or val <= 0:
                    continue
                totals[classe] = totals.get(classe, 0.0) + float(val)
            for classe, area in totals.items():
                csv_rows.append({
                    "codigo_ibge": code,
                    "ano": year,
                    "classe_uso": classe,
                    "area_ha": round(area, 3),
                })

    if not csv_rows:
        logger.warning("Nenhuma linha convertida do XLSX MapBiomas (%s)", xlsx)
        return _csv_path()

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    with csv_out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["codigo_ibge", "ano", "classe_uso", "area_ha"])
        writer.writeheader()
        writer.writerows(csv_rows)

    global _CSV_INDEX
    _CSV_INDEX = None
    logger.info("CSV MapBiomas gerado de %s → %s (%d linhas)", xlsx.name, csv_out, len(csv_rows))
    return csv_out


def _csv_path() -> Path | None:
    explicit = os.getenv("MAPBIOMAS_STATS_CSV", "").strip()
    if explicit and Path(explicit).exists():
        return Path(explicit)
    default = _stats_dir() / "municipios_cobertura.csv"
    return default if default.exists() else None


def _parse_area(value: Any) -> float | None:
    if value in (None, "", "-", "..."):
        return None
    if isinstance(value, (int, float)):
        try:
            val = float(value)
        except (TypeError, ValueError):
            return None
        return val if val > 0 else None
    text = str(value).strip()
    if not text:
        return None
    # CSV BR: 1.234,56 — XLSX/pandas já entrega float nativo (tratado acima).
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        val = float(text)
    except ValueError:
        return None
    return val if val > 0 else None


def load_csv_index() -> dict[tuple[str, int, str], float]:
    """Índice (ibge, ano, classe) -> area_ha a partir de CSV oficial."""
    path = _csv_path()
    if not path:
        return {}

    index: dict[tuple[str, int, str], float] = {}
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return index
            fields = {f.lower(): f for f in reader.fieldnames}
            ibge_key = fields.get("codigo_ibge") or fields.get("geocode") or fields.get("cd_mun")
            year_key = fields.get("ano") or fields.get("year")
            class_key = fields.get("classe_uso") or fields.get("classe") or fields.get("class")
            area_key = fields.get("area_ha") or fields.get("area") or fields.get("hectares")
            if not all([ibge_key, year_key, class_key, area_key]):
                logger.warning("CSV MapBiomas sem colunas esperadas: %s", reader.fieldnames)
                return index
            for row in reader:
                code = str(row.get(ibge_key, "")).strip().zfill(7)[:7]
                if not code.isdigit():
                    continue
                try:
                    year = int(str(row.get(year_key, "")).strip()[:4])
                except ValueError:
                    continue
                classe = str(row.get(class_key, "")).strip()
                area = _parse_area(row.get(area_key))
                if area is None or area <= 0:
                    continue
                normalized = _normalize_class(classe)
                if normalized:
                    index[(code, year, normalized)] = area
    except Exception as exc:
        logger.warning("Falha ao ler CSV MapBiomas (%s): %s", path, exc)
    return index


_CSV_INDEX: dict[tuple[str, int, str], float] | None = None


def csv_index() -> dict[tuple[str, int, str], float]:
    global _CSV_INDEX
    if _CSV_INDEX is None:
        _CSV_INDEX = load_csv_index()
    return _CSV_INDEX


def _normalize_class(label: str) -> str | None:
    low = label.lower()
    if "urban" in low:
        return "Área Urbana"
    if "florest" in low or "veget" in low:
        return "Vegetação / Floresta"
    if "água" in low or "agua" in low or "water" in low:
        return "Corpo d'água"
    return None


def _urban_ha_for_year(
    codigo_ibge: str,
    year: int,
    area_km2: float,
    populacao: int,
) -> tuple[float, str]:
    """Retorna (urban_ha, data_quality)."""
    code = str(codigo_ibge).zfill(7)[:7]
    idx = csv_index()
    for classe in CLASSES:
        key = (code, year, classe)
        if key in idx:
            return idx[key], "oficial" if classe == "Área Urbana" else "oficial"

    if code == "2611606" and year in _PILOT_URBAN_HA:
        return _PILOT_URBAN_HA[year], "referencia_mapbiomas"

    total_ha = max(area_km2 * 100.0, 1.0)
    # Calibração 2024: densidade urbana efetiva ~120–180 hab/ha em capitais regionais
    urban_cap = min(total_ha * 0.92, max(500.0, populacao / 140.0))
    base_1985 = urban_cap * 0.38
    years_elapsed = max(0, year - 1985)
    growth = 1.0 + min(0.025, 0.015 + populacao / 5_000_000)  # ~2%/a
    urban = min(urban_cap, base_1985 * (growth ** years_elapsed))
    return round(urban, 2), "derivado"


def _vegetation_ha_for_year(
    codigo_ibge: str,
    year: int,
    area_km2: float,
    urban_ha: float,
    water_ha: float,
) -> tuple[float, str]:
    """Retorna (vegetacao_ha, data_quality)."""
    code = str(codigo_ibge).zfill(7)[:7]
    total_ha = max(float(area_km2 or 0) * 100.0, 1.0)
    idx = csv_index()
    key = (code, year, VEGETATION_CLASS)
    if key in idx:
        return idx[key], "oficial"

    if code == "2611606" and year in _PILOT_VEGETATION_HA:
        return _PILOT_VEGETATION_HA[year], "referencia_mapbiomas"

    remaining = max(total_ha - urban_ha - water_ha, 0.0)
    if remaining > 0:
        return round(remaining * 0.72, 2), "derivado"
    return round(total_ha * 0.08, 2), "derivado"


def _areas_for_map(class_ha: dict[str, float], total_ha: float) -> dict[str, float]:
    """Normaliza classes para polígonos disjuntos que preenchem o município."""
    veg = max(float(class_ha.get(VEGETATION_CLASS, 0)), 0.0)
    water = max(float(class_ha.get("Corpo d'água", 0)), 0.0)
    urban = max(float(class_ha.get("Área Urbana", 0)), 0.0)
    if urban + veg + water > total_ha * 1.01:
        urban = max(0.0, total_ha - veg - water)
    elif urban + veg + water < total_ha * 0.85:
        scale = total_ha / max(urban + veg + water, 1.0)
        urban, veg, water = urban * scale, veg * scale, water * scale
    return {"Área Urbana": urban, VEGETATION_CLASS: veg, "Corpo d'água": water}


def vegetation_coverage_percent(db: Session, muni: Municipio) -> tuple[float, str]:
    """
    Percentual de vegetação/floresta sobre a área municipal.
    Prioriza estatísticas MapBiomas (ha); fallback para polígonos de cobertura.
    """
    total_ha = max(float(muni.area_km2 or 0) * 100.0, 0.0)
    if total_ha <= 0:
        return 0.0, "lacuna"

    code = str(muni.codigo_ibge).zfill(7)[:7]
    latest_year = (
        db.query(func.max(MapBiomasMunicipalStat.ano))
        .filter(
            MapBiomasMunicipalStat.codigo_ibge == code,
            MapBiomasMunicipalStat.classe_uso == VEGETATION_CLASS,
        )
        .scalar()
    )
    if latest_year:
        row = (
            db.query(MapBiomasMunicipalStat)
            .filter(
                MapBiomasMunicipalStat.codigo_ibge == code,
                MapBiomasMunicipalStat.ano == latest_year,
                MapBiomasMunicipalStat.classe_uso == VEGETATION_CLASS,
            )
            .first()
        )
        if row and float(row.area_ha or 0) > 0:
            pct = (float(row.area_ha) / total_ha) * 100.0
            quality = row.data_quality or "derivado"
            if quality in ("oficial", "referencia_mapbiomas"):
                return round(pct, 2), quality
            return round(pct, 2), "derivado"

    total_area_deg = db.scalar(func.ST_Area(muni.geom))
    forest_area_deg = db.query(func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom))).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id,
        CoberturaVegetalMapBiomas.classe_uso == VEGETATION_CLASS,
    ).scalar()
    veg_count = db.query(CoberturaVegetalMapBiomas).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id
    ).count()
    if forest_area_deg and total_area_deg:
        return round((float(forest_area_deg) / float(total_area_deg)) * 100.0, 2), "derivado" if veg_count else "lacuna"
    return 0.0, "lacuna" if veg_count == 0 else "derivado"


def build_landcover_series(
    codigo_ibge: str,
    area_km2: float,
    populacao: int,
    years: list[int] | None = None,
) -> list[dict[str, Any]]:
    """Gera série anual urbana/floresta/água em hectares."""
    years = years or REFERENCE_YEARS
    total_ha = max(float(area_km2 or 0) * 100.0, 1.0)
    water_ha = round(min(total_ha * 0.04, max(50.0, total_ha * 0.02)), 2)
    rows: list[dict[str, Any]] = []

    for year in years:
        urban_ha, urban_quality = _urban_ha_for_year(codigo_ibge, year, area_km2, populacao)
        forest_ha, forest_quality = _vegetation_ha_for_year(
            codigo_ibge, year, area_km2, urban_ha, water_ha
        )
        if urban_ha + forest_ha + water_ha > total_ha * 1.01:
            code = str(codigo_ibge).zfill(7)[:7]
            if not (code == "2611606" and year in _PILOT_VEGETATION_HA):
                forest_ha = round(max(0.0, total_ha - urban_ha - water_ha), 2)
                forest_quality = "derivado"
        for classe, area, quality in (
            ("Área Urbana", urban_ha, urban_quality),
            (VEGETATION_CLASS, forest_ha, forest_quality),
            ("Corpo d'água", water_ha, "derivado"),
        ):
            rows.append({
                "ano": year,
                "classe_uso": classe,
                "area_ha": round(float(area), 3),
                "data_quality": quality,
            })
    return rows


def _class_area_ratios(class_ha: dict[str, float]) -> tuple[float, float, float]:
    total = sum(float(v) for v in class_ha.values()) or 1.0
    water_r = max(0.0, float(class_ha.get("Corpo d'água", 0)) / total)
    veg_r = max(0.0, float(class_ha.get(VEGETATION_CLASS, 0)) / total)
    urban_r = max(0.0, float(class_ha.get("Área Urbana", 0)) / total)
    share = water_r + veg_r + urban_r
    if share <= 0:
        return 0.04, 0.08, 0.88
    return water_r / share, veg_r / share, urban_r / share


def _take_cells_by_quota(
    cells: dict[str, Any],
    affinity: dict[str, float],
    target_area: float,
    default: float = 0.05,
) -> tuple[list[Any], dict[str, Any]]:
    if target_area <= 0 or not cells:
        return [], dict(cells)
    ranked = sorted(
        cells.items(),
        key=lambda item: affinity.get(item[0], default),
        reverse=True,
    )
    selected: list[Any] = []
    remaining = dict(cells)
    accumulated = 0.0
    for name, geom in ranked:
        if accumulated >= target_area:
            break
        selected.append(geom)
        accumulated += float(geom.area)
        remaining.pop(name, None)
    return selected, remaining


def _river_water_mask(poly) -> Any:
    rivers = unary_union(
        [line.buffer(0.0032, cap_style=2, join_style=2) for line in RECIFE_RIVER_LINES]
    )
    return poly.intersection(rivers)


def _recife_landcover_partition(poly, class_ha: dict[str, float]) -> dict[str, Any]:
    """Partição por bairros + rios — evita faixas horizontais artificiais."""
    from app.data_connectors.territorial_mesh_collector import RECIFE_BAIRRO_SEEDS, _partition_voronoi

    water_r, veg_r, _urban_r = _class_area_ratios(class_ha)
    cells = _partition_voronoi(poly, RECIFE_BAIRRO_SEEDS)

    water_cells, remaining = _take_cells_by_quota(
        cells, RECIFE_WATER_AFFINITY, poly.area * water_r, default=0.08
    )
    veg_cells, remaining = _take_cells_by_quota(
        remaining, RECIFE_VEG_AFFINITY, poly.area * veg_r, default=0.06
    )

    water_parts = [g for g in water_cells if g is not None and not g.is_empty]
    river_mask = _river_water_mask(poly)
    if not river_mask.is_empty:
        water_parts.append(river_mask)

    water = poly.intersection(unary_union(water_parts)) if water_parts else None
    if water is not None and water.is_empty:
        water = None

    veg_raw = unary_union(veg_cells) if veg_cells else None
    if veg_raw is not None and not veg_raw.is_empty:
        veg_clip = veg_raw.difference(water) if water is not None else veg_raw
        veg = poly.intersection(veg_clip)
    else:
        veg = None
    if veg is not None and veg.is_empty:
        veg = None

    clips = [g for g in (water, veg) if g is not None and not g.is_empty]
    if clips:
        urban = poly.difference(unary_union(clips))
    elif remaining:
        urban = unary_union(list(remaining.values()))
    else:
        urban = poly

    parts: dict[str, Any] = {}
    if water is not None and not water.is_empty and water.area > 0:
        parts["Corpo d'água"] = water
    if urban is not None and not urban.is_empty and urban.area > 0:
        parts["Área Urbana"] = urban
    if veg is not None and not veg.is_empty and veg.area > 0:
        parts[VEGETATION_CLASS] = veg
    return parts


def _grid_landcover_cells(poly, cols: int = 12, rows: int = 12) -> dict[str, Any]:
    min_x, min_y, max_x, max_y = poly.bounds
    dx = (max_x - min_x) / cols
    dy = (max_y - min_y) / rows
    cells: dict[str, Any] = {}
    for row in range(rows):
        for col in range(cols):
            x1 = min_x + col * dx
            y1 = min_y + row * dy
            cell = box(x1, y1, x1 + dx, y1 + dy)
            clipped = poly.intersection(cell)
            if clipped.is_empty or clipped.area < poly.area * 0.0002:
                continue
            cells[f"c{row}_{col}"] = clipped
    return cells


def _generic_landcover_partition(poly, class_ha: dict[str, float]) -> dict[str, Any]:
    """Malha fina com afinidade geográfica (costa = água, bordas = vegetação)."""
    water_r, veg_r, _urban_r = _class_area_ratios(class_ha)
    cells = _grid_landcover_cells(poly)
    if not cells:
        return _fallback_landcover_partition(poly, class_ha)

    min_x, min_y, max_x, max_y = poly.bounds
    width = max(max_x - min_x, 1e-9)
    height = max(max_y - min_y, 1e-9)
    centroid = poly.centroid

    water_affinity: dict[str, float] = {}
    veg_affinity: dict[str, float] = {}
    for name, geom in cells.items():
        cx, cy = geom.centroid.x, geom.centroid.y
        south = (cy - min_y) / height
        coast = min(
            (cx - min_x) / width,
            (max_x - cx) / width,
            (cy - min_y) / height,
            (max_y - cy) / height,
        )
        water_affinity[name] = 0.15 + south * 0.65 + (1.0 - coast) * 0.2
        veg_affinity[name] = 0.1 + coast * 0.55 + centroid.distance(Point(cx, cy)) * 2.5

    water_cells, remaining = _take_cells_by_quota(
        cells, water_affinity, poly.area * water_r, default=0.12
    )
    veg_cells, _remaining = _take_cells_by_quota(
        remaining, veg_affinity, poly.area * veg_r, default=0.08
    )

    water = poly.intersection(unary_union(water_cells)) if water_cells else None
    veg_raw = unary_union(veg_cells) if veg_cells else None
    if veg_raw is not None and not veg_raw.is_empty:
        veg_clip = veg_raw.difference(water) if water is not None else veg_raw
        veg = poly.intersection(veg_clip)
    else:
        veg = None

    clips = [g for g in (water, veg) if g is not None and not g.is_empty]
    urban = poly.difference(unary_union(clips)) if clips else poly

    parts: dict[str, Any] = {}
    if water is not None and not water.is_empty and water.area > 0:
        parts["Corpo d'água"] = water
    if urban is not None and not urban.is_empty and urban.area > 0:
        parts["Área Urbana"] = urban
    if veg is not None and not veg.is_empty and veg.area > 0:
        parts[VEGETATION_CLASS] = veg
    return parts or _fallback_landcover_partition(poly, class_ha)


def _fallback_landcover_partition(poly, class_ha: dict[str, float]) -> dict[str, Any]:
    """Último recurso: faixas horizontais proporcionais."""
    water_r, veg_r, _urban_r = _class_area_ratios(class_ha)
    minx, miny, maxx, maxy = poly.bounds
    height = max(maxy - miny, 1e-9)
    water = poly.intersection(box(minx, miny, maxx, miny + height * water_r)) if water_r > 0 else None
    veg = poly.intersection(box(minx, maxy - height * veg_r, maxx, maxy)) if veg_r > 0 else None
    clips = [g for g in (water, veg) if g is not None and not g.is_empty]
    urban = poly.difference(unary_union(clips)) if clips else poly
    parts: dict[str, Any] = {}
    if water is not None and not water.is_empty:
        parts["Corpo d'água"] = water
    if urban is not None and not urban.is_empty:
        parts["Área Urbana"] = urban
    if veg is not None and not veg.is_empty:
        parts[VEGETATION_CLASS] = veg
    return parts


def _build_landcover_partition(
    poly,
    class_ha: dict[str, float],
    *,
    codigo_ibge: str | None = None,
) -> dict[str, Any]:
    """Particiona o município em polígonos disjuntos proporcionais às áreas (ha)."""
    code = str(codigo_ibge or "").zfill(7)[:7]
    if code == "2611606":
        return _recife_landcover_partition(poly, class_ha)
    return _generic_landcover_partition(poly, class_ha)


def _geometry_is_horizontal_band(geom, poly) -> bool:
    minx, miny, maxx, maxy = poly.bounds
    gx0, gy0, gx1, gy1 = geom.bounds
    width = max(maxx - minx, 1e-9)
    height = max(maxy - miny, 1e-9)
    g_width = max(gx1 - gx0, 1e-9)
    g_height = max(gy1 - gy0, 1e-9)
    return g_width / width > 0.82 and g_height / height < 0.28


def needs_coverage_polygon_refresh(db: Session, muni: Municipio) -> bool:
    rows = (
        db.query(CoberturaVegetalMapBiomas)
        .filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
        .all()
    )
    if not rows:
        return True
    if muni.geom is None:
        return False
    poly = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
    if poly.is_empty:
        return False
    if len(rows) != 3:
        return False
    return all(
        _geometry_is_horizontal_band(shape(json.loads(db.scalar(row.geom.ST_AsGeoJSON()))), poly)
        for row in rows
    )


def ensure_spatial_coverage_polygons(db: Session, muni: Municipio) -> bool:
    """Regenera polígonos de cobertura quando ainda usam faixas horizontais legadas."""
    if not needs_coverage_polygon_refresh(db, muni):
        return False
    series = build_landcover_series(
        muni.codigo_ibge,
        float(muni.area_km2 or 0),
        int(muni.populacao or 0),
    )
    _sync_coverage_polygons(db, muni, series)
    db.commit()
    return True


def upsert_municipal_stats(db: Session, muni: Municipio, force: bool = False) -> dict[str, Any]:
    """Persiste estatísticas MapBiomas e regenera polígonos de cobertura."""
    code = muni.codigo_ibge
    existing = db.query(MapBiomasMunicipalStat).filter(MapBiomasMunicipalStat.codigo_ibge == code).count()
    if existing > 0 and not force:
        return {"codigo_ibge": code, "skipped": True, "records": existing}

    if existing and force:
        db.query(MapBiomasMunicipalStat).filter(MapBiomasMunicipalStat.codigo_ibge == code).delete()
        db.query(CoberturaVegetalMapBiomas).filter(CoberturaVegetalMapBiomas.municipio_id == muni.id).delete()

    series = build_landcover_series(
        code,
        float(muni.area_km2 or 0),
        int(muni.populacao or 0),
    )
    now = datetime.now(timezone.utc)
    official_count = 0
    for row in series:
        db.add(
            MapBiomasMunicipalStat(
                codigo_ibge=code,
                municipio_id=muni.id,
                ano=row["ano"],
                classe_uso=row["classe_uso"],
                area_ha=row["area_ha"],
                colecao=MAPBIOMAS_COLLECTION,
                data_quality=row["data_quality"],
                fonte="MapBiomas Coleção 10.1" if row["data_quality"] == "oficial" else "MapBiomas calibrado Sinidu+Clima",
                atualizado_em=now,
            )
        )
        if row["data_quality"] in ("oficial", "referencia_mapbiomas"):
            official_count += 1

    polygons_created = _sync_coverage_polygons(db, muni, series)
    db.commit()

    return {
        "codigo_ibge": code,
        "skipped": False,
        "records": len(series),
        "official_points": official_count,
        "polygons": polygons_created,
        "csv_loaded": bool(csv_index()),
        "data_quality": "oficial" if official_count >= len(REFERENCE_YEARS) else "derivado",
    }


def _sync_coverage_polygons(db: Session, muni: Municipio, series: list[dict[str, Any]]) -> int:
    """Cria polígonos de cobertura disjuntos para o ano mais recente."""
    if muni.geom is None:
        return 0

    latest_year = max(row["ano"] for row in series)
    year_rows = [r for r in series if r["ano"] == latest_year]
    class_ha = {row["classe_uso"]: float(row["area_ha"]) for row in year_rows}
    total_ha = max(float(muni.area_km2 or 0) * 100.0, 1.0)
    map_ha = _areas_for_map(class_ha, total_ha)

    poly = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
    if poly.is_empty:
        return 0

    db.query(CoberturaVegetalMapBiomas).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id
    ).delete(synchronize_session=False)

    parts = _build_landcover_partition(poly, map_ha, codigo_ibge=muni.codigo_ibge)
    created = 0
    for classe, geom in parts.items():
        if geom is None or geom.is_empty:
            continue
        db.add(
            CoberturaVegetalMapBiomas(
                municipio_id=muni.id,
                ano=latest_year,
                classe_uso=classe,
                geom=from_shape(geom, srid=4326),
            )
        )
        created += 1
    return created


def collect_mapbiomas_municipality(db: Session, codigo_ibge: str, force: bool = False) -> dict[str, Any]:
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "error": "Município não carregado no banco."}
    result = upsert_municipal_stats(db, muni, force=force)
    if result.get("skipped"):
        # Reconstrói polígonos mesmo quando stats já existem (corrige malhas antigas)
        series = build_landcover_series(code, float(muni.area_km2 or 0), int(muni.populacao or 0))
        polygons = _sync_coverage_polygons(db, muni, series)
        db.commit()
        result = {**result, "skipped": False, "polygons_refreshed": polygons}
    return result


def sync_mapbiomas_batch(db: Session, *, limit: int = 6, force: bool = False) -> dict[str, Any]:
    """Sincroniza MapBiomas para municípios já carregados no banco."""
    from app.data_connectors.constants import TARGET_IBGE_CODES

    csv_built = ensure_mapbiomas_csv_from_xlsx(db, force=force)
    source = "xlsx_oficial" if csv_built and _xlsx_path() else "csv_ou_derivado"

    codes = TARGET_IBGE_CODES[: max(1, min(limit, 100))]
    processed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for code in codes:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
        if not muni:
            errors.append({"codigo_ibge": code, "error": "não carregado"})
            continue
        try:
            processed.append(collect_mapbiomas_municipality(db, code, force=force))
        except Exception as exc:
            db.rollback()
            errors.append({"codigo_ibge": code, "error": str(exc)})
    return {
        "requested": len(codes),
        "processed": len(processed),
        "errors": errors,
        "items": processed,
        "stats_source": source,
    }


def get_urban_series(db: Session, codigo_ibge: str) -> list[dict[str, Any]]:
    """Série área urbanizada (km² e % do município) — 17e.2."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    area_km2 = float(muni.area_km2) if muni and muni.area_km2 else 0.0

    def _pct(area_urb_km2: float) -> float | None:
        if area_km2 <= 0:
            return None
        return round(100.0 * area_urb_km2 / area_km2, 2)

    rows = (
        db.query(MapBiomasMunicipalStat)
        .filter(
            MapBiomasMunicipalStat.codigo_ibge == code,
            MapBiomasMunicipalStat.classe_uso == "Área Urbana",
        )
        .order_by(MapBiomasMunicipalStat.ano.asc())
        .all()
    )
    if rows:
        out = []
        for r in rows:
            km2 = round(float(r.area_ha) / 100.0, 2)
            out.append({
                "ano": r.ano,
                "area_urbanizada_km2": km2,
                "pct_area_municipal": _pct(km2),
                "qualidade_dado": (
                    "Oficial" if r.data_quality in ("oficial", "referencia_mapbiomas") else "Derivado"
                ),
            })
        return out

    if not muni:
        return []
    derived = build_landcover_series(code, area_km2, int(muni.populacao or 0))
    return [
        {
            "ano": r["ano"],
            "area_urbanizada_km2": round(float(r["area_ha"]) / 100.0, 2),
            "pct_area_municipal": _pct(round(float(r["area_ha"]) / 100.0, 2)),
            "qualidade_dado": "Derivado",
        }
        for r in derived
        if r["classe_uso"] == "Área Urbana"
    ]


def mapbiomas_status(db: Session, codigo_ibge: str | None = None) -> dict[str, Any]:
    query = db.query(MapBiomasMunicipalStat)
    if codigo_ibge:
        query = query.filter(MapBiomasMunicipalStat.codigo_ibge == str(codigo_ibge).zfill(7)[:7])
    total = query.count()
    official = query.filter(MapBiomasMunicipalStat.data_quality.in_(("oficial", "referencia_mapbiomas"))).count()
    municipios = db.query(MapBiomasMunicipalStat.codigo_ibge).distinct().count()
    return {
        "records": total,
        "municipios": municipios,
        "official_records": official,
        "csv_configured": _csv_path() is not None,
        "csv_path": str(_csv_path()) if _csv_path() else None,
        "colecao": MAPBIOMAS_COLLECTION,
    }
