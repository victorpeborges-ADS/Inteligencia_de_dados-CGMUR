#!/usr/bin/env python3
"""Atualiza cache GeoJSON das UTB de Campinas (DIDC exporta_shp id=91)."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import geopandas as gpd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.data_connectors.ctm_registry import CAMPINAS_UTB_GEOJSON

DIDC_EXPORT = "https://informacao-didc.campinas.sp.gov.br/exporta_shp.php?id=91"
BASE_URL = "https://informacao-didc.campinas.sp.gov.br/"


def _download_shapefile(tmpdir: Path) -> Path:
    resp = requests.get(DIDC_EXPORT, timeout=120)
    resp.raise_for_status()
    links = re.findall(r'href="(/pmapper/tmp/ms_tmp/[^"]+\.(?:shp|dbf|prj|shx))"', resp.text, re.I)
    if not links:
        raise RuntimeError("Página DIDC não retornou links de shapefile.")

    for rel in links:
        url = urljoin(BASE_URL, rel)
        ext = Path(rel).suffix
        out = tmpdir / f"utb{ext}"
        file_resp = requests.get(url, timeout=120)
        file_resp.raise_for_status()
        out.write_bytes(file_resp.content)

    shp = tmpdir / "utb.shp"
    if not shp.is_file():
        raise RuntimeError("Arquivo .shp não foi baixado.")
    return shp


def main() -> int:
    tmpdir = Path("/tmp/campinas_utb_refresh")
    tmpdir.mkdir(parents=True, exist_ok=True)

    shp = _download_shapefile(tmpdir)
    gdf = gpd.read_file(shp, encoding="iso-8859-1")
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(4326)

    out = Path(__file__).resolve().parents[1] / CAMPINAS_UTB_GEOJSON
    out.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_file(out, driver="GeoJSON")

    print(f"OK — {len(gdf)} feições → {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
