#!/usr/bin/env python3
"""Smoke test de homologação — camadas, diagnóstico, DEM e simulação."""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

SAMPLE_IBGE = [
    "2611606",  # Recife (piloto)
    "3550308",  # São Paulo
    "2927408",  # Salvador
    "1302603",  # Manaus
    "4314902",  # Porto Alegre
]


def get(path: str) -> tuple[int, dict | list | None]:
    url = f"{BASE.rstrip('/')}{path}"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode())
        except Exception:
            detail = {"error": str(exc)}
        return exc.code, detail


def main() -> int:
    print(f"Smoke test Sinidu+Clima — {BASE}\n")
    ok, health = get("/health/ready")
    print(f"[{'OK' if ok == 200 else 'FAIL'}] health/ready {health}")
    if ok != 200:
        return 1

    ok, overview = get("/api/v1/system/overview")
    if ok == 200 and isinstance(overview, dict):
        ob = overview.get("onboarding", {})
        dem = overview.get("dem", {})
        print(
            f"[OK] overview onboarding={ob.get('concluidos')}/{ob.get('concluidos', 0) + ob.get('pendentes', 0) + sum(ob.get('by_status', {}).values()) - ob.get('concluidos', 0)} "
            f"dem={dem.get('processados')}/61"
        )
    else:
        print(f"[WARN] overview HTTP {ok}")

    failures = 0
    for ibge in SAMPLE_IBGE:
        checks: list[str] = []
        code, layers = get(f"/api/v1/indicators/layers/meta?codigo_ibge={ibge}")
        if code == 200 and isinstance(layers, dict):
            bairros = layers.get("bairros", {})
            checks.append(f"bairros={bairros.get('count', '?')}")
        else:
            failures += 1
            print(f"[FAIL] {ibge} layers/meta HTTP {code}")
            continue

        code, diag = get(f"/api/v1/analytics/diagnostic?codigo_ibge={ibge}")
        if code == 200:
            checks.append("diagnostico=sim")
        else:
            checks.append(f"diagnostico=nao({code})")
            failures += 1

        code, terrain = get(f"/api/v1/terrain/{ibge}/config")
        if code == 200 and isinstance(terrain, dict):
            checks.append(f"dem={terrain.get('dem_source', '?')[:24]}")
        else:
            checks.append("dem=ausente")
            failures += 1

        print(f"[{'OK' if 'diagnostico=sim' in checks else 'WARN'}] {ibge}: {', '.join(checks)}")

    code, routing = get("/api/v1/routing/status")
    osrm = routing.get("available") if isinstance(routing, dict) else False
    print(f"[{'OK' if osrm else 'INFO'}] OSRM {'online' if osrm else 'fallback Haversine'}")

    print(f"\nConcluído — {failures} falha(s) em amostra de {len(SAMPLE_IBGE)} municípios.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
