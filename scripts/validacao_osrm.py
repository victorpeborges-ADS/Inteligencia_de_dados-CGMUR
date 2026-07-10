#!/usr/bin/env python3
"""Smoke test OSRM + rotas de contingência (Recife/Aracaju)."""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
RECIFE = "2611606"
ARACAJU = "2800308"

# Polígono simplificado no centro de Recife (Boa Viagem / Pina)
RISK_RECIFE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"nome": "Zona teste"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-34.895, -8.12],
                        [-34.885, -8.12],
                        [-34.885, -8.11],
                        [-34.895, -8.11],
                        [-34.895, -8.12],
                    ]
                ],
            },
        }
    ],
}


def get(path: str) -> tuple[int, dict | None]:
    with urllib.request.urlopen(f"{BASE.rstrip('/')}{path}", timeout=30) as resp:
        return resp.status, json.loads(resp.read().decode())


def post(path: str, body: dict) -> tuple[int, dict | None]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE.rstrip('/')}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.status, json.loads(resp.read().decode())


def main() -> int:
    fails = 0
    print(f"Validação OSRM — {BASE}\n")

    code, status = get("/api/v1/routing/status")
    ok = code == 200 and status and status.get("available")
    print(f"[{'OK' if ok else 'FAIL'}] routing/status available={status.get('available') if status else None} region={status.get('region') if status else None}")
    fails += 0 if ok else 1

    if status:
        ufs = status.get("covered_ufs") or []
        pe_se = "PE" in ufs and "SE" in ufs
        print(f"[{'OK' if pe_se else 'WARN'}] covered_ufs={','.join(ufs)}")

    code, plan = post(
        "/api/v1/contingency/generate-from-simulation",
        {
            "codigo_ibge": RECIFE,
            "cenario_tipo": "INUNDACAO",
            "risk_geojson": RISK_RECIFE,
            "buffer_m": 400,
        },
    )
    rotas = (plan or {}).get("rotas_fuga") or []
    osrm_routes = [r for r in rotas if (r.get("fonte_rota") or (r.get("geojson") or {}).get("properties", {}).get("fonte")) == "osrm"]
    ok = code == 200 and len(rotas) > 0 and len(osrm_routes) > 0
    print(f"[{'OK' if ok else 'FAIL'}] contingência Recife rotas={len(rotas)} osrm={len(osrm_routes)}")
    if rotas:
        g0 = rotas[0].get("geojson") or {}
        coords = (g0.get("geometry") or {}).get("coordinates") or []
        print(f"     1ª rota: aproximada={rotas[0].get('aproximada')} pontos={len(coords)}")
    fails += 0 if ok else 1

    print(f"\nResultado: {fails} falha(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
