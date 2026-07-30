"""Camada de validação com manchas de inundação oficiais (20h.5).

Complementa o hit-rate pontual do S2ID (`simulation_confidence_service.py`)
com comparação **poligonal** contra estudos/manchas oficiais depositados
localmente (Defesa Civil, CPRM, plano diretor de drenagem etc.), quando
disponíveis. Não inventa cobertura: se não houver arquivo depositado para o
município, os métodos retornam `None`/`disponivel=False` de forma explícita.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from shapely.geometry import shape
from shapely.ops import unary_union
from shapely.validation import make_valid

DEFAULT_OFFICIAL_FLOOD_DIR = "/data/manchas_oficiais"


def _official_flood_dirs() -> list[Path]:
    """Diretórios candidatos para manchas oficiais, em ordem de prioridade.

    1. `OFFICIAL_FLOOD_DIR` (env) — ex.: volume `/data/manchas_oficiais` em produção.
    2. `backend/data/manchas_oficiais` — bind mount `./backend:/app` em dev/Docker.
    """
    dirs: list[Path] = []
    env_dir = os.environ.get("OFFICIAL_FLOOD_DIR")
    dirs.append(Path(env_dir) if env_dir else Path(DEFAULT_OFFICIAL_FLOOD_DIR))
    # services/ -> app/ -> backend/ -> backend/data/manchas_oficiais
    dirs.append(Path(__file__).resolve().parents[2] / "data" / "manchas_oficiais")
    # dedupe mantendo ordem
    seen: set[Path] = set()
    unique: list[Path] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def official_flood_map_path(codigo_ibge: str) -> Path | None:
    """Retorna o caminho do GeoJSON oficial para o município, se existir."""
    code = str(codigo_ibge or "").zfill(7)[:7]
    for base in _official_flood_dirs():
        candidate = base / f"{code}.geojson"
        if candidate.is_file():
            return candidate
    return None


def load_official_flood_geojson(codigo_ibge: str) -> dict[str, Any] | None:
    """Carrega o GeoJSON de mancha/estudo oficial de inundação do município.

    Retorna `None` (sem levantar exceção) quando o arquivo não existe ou é
    inválido — a ausência de mancha oficial é uma condição esperada, não erro.
    """
    path = official_flood_map_path(codigo_ibge)
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("type") not in ("FeatureCollection", "Feature"):
        return None
    return data


def _union_from_geojson(geojson: dict[str, Any] | None):
    if not geojson:
        return None
    feats = geojson.get("features") if geojson.get("type") == "FeatureCollection" else None
    if feats is not None:
        shapes = []
        for f in feats:
            geom = f.get("geometry")
            if not geom:
                continue
            try:
                g = shape(geom)
                if not g.is_valid:
                    g = make_valid(g)
                if not g.is_empty:
                    shapes.append(g)
            except Exception:
                continue
        if not shapes:
            return None
        return unary_union(shapes)
    geom = geojson.get("geometry") if geojson.get("type") == "Feature" else geojson
    try:
        g = shape(geom)
        if not g.is_valid:
            g = make_valid(g)
        return g if not g.is_empty else None
    except Exception:
        return None


def evaluate_against_official_polygons(
    sim_geojson: dict[str, Any] | None,
    official_geojson: dict[str, Any] | None,
) -> dict[str, Any]:
    """Compara a mancha simulada contra o polígono oficial (IoU + coberturas).

    Métricas retornadas:
    - `iou`: interseção sobre união (Jaccard poligonal).
    - `coverage_sim_in_official`: fração da área simulada dentro do polígono oficial.
    - `coverage_official_in_sim`: fração da área oficial coberta pela mancha simulada.
    """
    result: dict[str, Any] = {
        "disponivel": False,
        "iou": None,
        "coverage_sim_in_official": None,
        "coverage_official_in_sim": None,
        "narrativa": "Sem geometria oficial ou simulada suficiente para comparação poligonal.",
    }

    sim_union = _union_from_geojson(sim_geojson)
    official_union = _union_from_geojson(official_geojson)

    if sim_union is None or sim_union.is_empty:
        result["narrativa"] = "Mancha simulada vazia ou inválida — sem comparação poligonal possível."
        return result
    if official_union is None or official_union.is_empty:
        result["narrativa"] = "Sem mancha/estudo oficial depositado para este município."
        return result

    intersection = sim_union.intersection(official_union)
    union_geom = sim_union.union(official_union)

    area_sim = sim_union.area
    area_official = official_union.area
    area_inter = intersection.area
    area_union = union_geom.area

    iou = round(area_inter / area_union, 4) if area_union > 0 else 0.0
    coverage_sim_in_official = round(area_inter / area_sim, 4) if area_sim > 0 else 0.0
    coverage_official_in_sim = round(area_inter / area_official, 4) if area_official > 0 else 0.0

    if iou >= 0.5:
        narrativa = f"Boa concordância espacial com a mancha oficial (IoU {iou:.0%})."
    elif iou >= 0.2:
        narrativa = f"Concordância parcial com a mancha oficial (IoU {iou:.0%})."
    else:
        narrativa = f"Baixa concordância espacial com a mancha oficial (IoU {iou:.0%})."

    result.update(
        {
            "disponivel": True,
            "iou": iou,
            "coverage_sim_in_official": coverage_sim_in_official,
            "coverage_official_in_sim": coverage_official_in_sim,
            "narrativa": narrativa,
        }
    )
    # Nota: geometrias em graus (WGS84) — áreas absolutas em m² exigiriam reprojeção
    # métrica; expomos apenas razões (IoU/coberturas), que são invariantes à unidade.
    return result
