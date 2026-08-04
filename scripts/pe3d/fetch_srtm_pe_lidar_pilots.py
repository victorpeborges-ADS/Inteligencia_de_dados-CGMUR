#!/usr/bin/env python3
"""Baixa DEM SRTM (OpenTopography) para os pilotos PE LiDAR: Camutanga e Itamaracá.

Uso (API key já no ambiente ou no .env do compose):

  export OPENTOPOGRAPHY_API_KEY=...
  python3 scripts/pe3d/fetch_srtm_pe_lidar_pilots.py

Grava em data/dem/local/{ibge}.tif (SRTM interino).
Quando tiver MDT PE3D, substitua por data/dem/local/{ibge}_lidar.tif
(prioridade mais alta no dem_processor).
"""
from __future__ import annotations

import gzip
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = Path(os.getenv("LOCAL_DEM_DIR", ROOT / "data" / "dem" / "local"))
OPENTOPO = "https://portal.opentopography.org/API/globaldem"

PILOTS = {
    "2603603": "Camutanga",
    "2607604": "Ilha de Itamaracá",
}


def _get(url: str, timeout: float = 180) -> bytes:
    # Ambiente corporativo (proxy TLS) — usa contexto sem verify.
    ctx = ssl._create_unverified_context()  # noqa: S323
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "sinidu-pe3d/1.0", "Accept-Encoding": "identity"},
    )
    with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
        data = resp.read()
    if data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data


def _bbox(codigo_ibge: str) -> tuple[float, float, float, float]:
    url = (
        f"https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{codigo_ibge}"
        "?formato=application/vnd.geo+json&qualidade=minima"
    )
    geo = json.loads(_get(url, timeout=60).decode("utf-8"))
    coords: list[list[float]] = []

    def walk(obj: object) -> None:
        if isinstance(obj, (list, tuple)):
            if len(obj) == 2 and all(isinstance(x, (int, float)) for x in obj):
                coords.append([float(obj[0]), float(obj[1])])
            else:
                for item in obj:
                    walk(item)

    feats = geo.get("features") or [geo]
    for feat in feats:
        walk((feat.get("geometry") or {}).get("coordinates"))
    if not coords:
        raise RuntimeError(f"Sem coordenadas na malha IBGE {codigo_ibge}")
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    pad = 0.01
    return min(lons) - pad, min(lats) - pad, max(lons) + pad, max(lats) + pad


def fetch_one(codigo_ibge: str, nome: str, api_key: str) -> Path:
    west, south, east, north = _bbox(codigo_ibge)
    print(f"{codigo_ibge} {nome}: W{west:.4f} S{south:.4f} E{east:.4f} N{north:.4f}")
    params = (
        f"?demtype=SRTMGL1&south={south}&north={north}&west={west}&east={east}"
        f"&outputFormat=GTiff&API_Key={api_key}"
    )
    data = _get(OPENTOPO + params, timeout=180)
    if len(data) < 1000:
        raise RuntimeError(f"Resposta OpenTopo curta ({len(data)} bytes) para {codigo_ibge}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{codigo_ibge}.tif"
    dest.write_bytes(data)
    print(f"  → {dest} ({dest.stat().st_size:,} bytes)")
    return dest


def main() -> int:
    api_key = (os.getenv("OPENTOPOGRAPHY_API_KEY") or "").strip()
    if not api_key:
        print("Defina OPENTOPOGRAPHY_API_KEY no ambiente.", file=sys.stderr)
        return 1
    codes = sys.argv[1:] or list(PILOTS)
    for code in codes:
        nome = PILOTS.get(code, code)
        fetch_one(code, nome, api_key)
    print("OK. Depois: onboarding + POST /terrain/{ibge}/process?force=true")
    print("PE3D LiDAR (quando disponível): data/dem/local/{ibge}_lidar.tif")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
