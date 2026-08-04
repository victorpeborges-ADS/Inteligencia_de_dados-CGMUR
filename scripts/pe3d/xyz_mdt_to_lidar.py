#!/usr/bin/env python3
"""Converte tiles MDT PE3D (.xyz UTM 25S) em GeoTIFF LiDAR WGS84 por município.

Entrada: /data/dem/pe3d_mdt/xyz/*.xyz  (ou --xyz-dir)
Saída:   /data/dem/local/{ibge}_lidar.tif

Uso:
  docker exec -w /app -e PYTHONPATH=/app sinidu_backend \\
    python /app/../scripts/pe3d/xyz_mdt_to_lidar.py
  # se scripts não montado:
  python scripts/pe3d/xyz_mdt_to_lidar.py --xyz-dir data/dem/pe3d_mdt/xyz
"""
from __future__ import annotations

import argparse
import json
import math
import ssl
import sys
import urllib.request
from pathlib import Path

import numpy as np

try:
    import rasterio
    from rasterio.transform import from_origin
    from pyproj import Transformer
except ImportError as exc:  # pragma: no cover
    print("Requer rasterio + pyproj:", exc, file=sys.stderr)
    raise SystemExit(1)

UTM = "EPSG:31985"  # SIRGAS 2000 / UTM 25S
WGS = "EPSG:4326"

# Bboxes WGS84 (IBGE + pad) — Camutanga e Ilha de Itamaracá
MUNIS = {
    "2603603": {
        "nome": "Camutanga",
        "west": -35.3526,
        "south": -7.4881,
        "east": -35.2271,
        "north": -7.3944,
    },
    "2607604": {
        "nome": "Ilha de Itamaracá",
        "west": -34.9002,
        "south": -7.8264,
        "east": -34.8132,
        "north": -7.6778,
    },
}


def _bbox_utm(west: float, south: float, east: float, north: float) -> tuple[float, float, float, float]:
    t = Transformer.from_crs(WGS, UTM, always_xy=True)
    x0, y0 = t.transform(west, south)
    x1, y1 = t.transform(east, north)
    # cantos extras para envelope correto
    corners = [
        t.transform(west, south),
        t.transform(west, north),
        t.transform(east, south),
        t.transform(east, north),
    ]
    xs = [c[0] for c in corners]
    ys = [c[1] for c in corners]
    return min(xs), min(ys), max(xs), max(ys)


def _tile_bounds(path: Path, sample_every: int = 50) -> tuple[float, float, float, float]:
    xmin = ymin = float("inf")
    xmax = ymax = float("-inf")
    with path.open() as fh:
        for i, line in enumerate(fh):
            if i % sample_every:
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            x, y = float(parts[0]), float(parts[1])
            xmin = min(xmin, x)
            xmax = max(xmax, x)
            ymin = min(ymin, y)
            ymax = max(ymax, y)
    return xmin, ymin, xmax, ymax


def _intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 < bx0 or bx1 < ax0 or ay1 < by0 or by1 < ay0)


def rasterize_muni(
    codigo: str,
    meta: dict,
    xyz_files: list[Path],
    out_path: Path,
    resolution_m: float = 2.0,
) -> dict:
    ux0, uy0, ux1, uy1 = _bbox_utm(meta["west"], meta["south"], meta["east"], meta["north"])
    # pad 50 m
    ux0 -= 50
    uy0 -= 50
    ux1 += 50
    uy1 += 50
    cols = int(math.ceil((ux1 - ux0) / resolution_m))
    rows = int(math.ceil((uy1 - uy0) / resolution_m))
    print(f"{codigo} {meta['nome']}: grid {cols}x{rows} @ {resolution_m}m UTM")

    sum_z = np.zeros((rows, cols), dtype=np.float64)
    count = np.zeros((rows, cols), dtype=np.uint32)
    n_pts = 0

    for path in xyz_files:
        tb = _tile_bounds(path)
        if not _intersects(tb, (ux0, uy0, ux1, uy1)):
            print(f"  skip {path.name}")
            continue
        print(f"  read {path.name}")
        with path.open() as fh:
            for line in fh:
                parts = line.split()
                if len(parts) < 3:
                    continue
                x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
                if x < ux0 or x >= ux1 or y < uy0 or y >= uy1:
                    continue
                c = int((x - ux0) / resolution_m)
                r = int((uy1 - y) / resolution_m)  # north-up
                if 0 <= r < rows and 0 <= c < cols:
                    sum_z[r, c] += z
                    count[r, c] += 1
                    n_pts += 1

    if n_pts == 0:
        raise RuntimeError(f"Nenhum ponto XYZ dentro de {codigo} — tiles cobrem este município?")

    elev = np.full((rows, cols), np.nan, dtype=np.float32)
    mask = count > 0
    elev[mask] = (sum_z[mask] / count[mask]).astype(np.float32)
    # preenche buracos pequenos com média local
    filled = elev.copy()
    nan_idx = np.argwhere(~mask)
    for r, c in nan_idx:
        r0, r1 = max(0, r - 2), min(rows, r + 3)
        c0, c1 = max(0, c - 2), min(cols, c + 3)
        win = elev[r0:r1, c0:c1]
        vals = win[np.isfinite(win)]
        if vals.size:
            filled[r, c] = float(vals.mean())

    # Reamostra para WGS84 via transformação de grade (cantos)
    t_to_wgs = Transformer.from_crs(UTM, WGS, always_xy=True)
    # Escreve GeoTIFF UTM temporário e warp com rasterio.warp
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    transform_utm = from_origin(ux0, uy1, resolution_m, resolution_m)
    tmp = out_path.with_suffix(".utm.tif")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(
        tmp,
        "w",
        driver="GTiff",
        height=rows,
        width=cols,
        count=1,
        dtype="float32",
        crs=UTM,
        transform=transform_utm,
        nodata=-9999.0,
        compress="lzw",
    ) as dst:
        write = np.where(np.isfinite(filled), filled, -9999.0).astype(np.float32)
        dst.write(write, 1)

    with rasterio.open(tmp) as src:
        dst_transform, dst_width, dst_height = calculate_default_transform(
            src.crs, WGS, src.width, src.height, *src.bounds, resolution=None
        )
        # limita resolução ~1–2 m em graus (~2/111320)
        kwargs = src.meta.copy()
        kwargs.update(
            {
                "crs": WGS,
                "transform": dst_transform,
                "width": dst_width,
                "height": dst_height,
                "nodata": -9999.0,
                "compress": "lzw",
            }
        )
        with rasterio.open(out_path, "w", **kwargs) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=WGS,
                resampling=Resampling.bilinear,
                src_nodata=-9999.0,
                dst_nodata=-9999.0,
            )
    tmp.unlink(missing_ok=True)

    west, south = t_to_wgs.transform(ux0, uy0)
    east, north = t_to_wgs.transform(ux1, uy1)
    info = {
        "codigo_ibge": codigo,
        "nome": meta["nome"],
        "points": n_pts,
        "cells_filled": int(mask.sum()),
        "out": str(out_path),
        "size_bytes": out_path.stat().st_size,
        "bbox_wgs84": [west, south, east, north],
        "resolution_m": resolution_m,
        "source": "PE3D MDT XYZ → GeoTIFF",
    }
    print(json.dumps(info, ensure_ascii=False))
    return info


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xyz-dir", default="/data/dem/pe3d_mdt/xyz")
    ap.add_argument("--out-dir", default="/data/dem/local")
    ap.add_argument("--resolution", type=float, default=2.0)
    ap.add_argument("--ibge", nargs="*", default=list(MUNIS))
    args = ap.parse_args()

    xyz_dir = Path(args.xyz_dir)
    files = sorted(xyz_dir.glob("*.xyz"))
    if not files:
        print(f"Sem .xyz em {xyz_dir}", file=sys.stderr)
        return 1
    print(f"{len(files)} tiles em {xyz_dir}")

    out_dir = Path(args.out_dir)
    for code in args.ibge:
        meta = MUNIS[code]
        out = out_dir / f"{code}_lidar.tif"
        rasterize_muni(code, meta, files, out, resolution_m=args.resolution)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
