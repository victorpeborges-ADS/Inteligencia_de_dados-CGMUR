#!/usr/bin/env python3
"""Smoke test OSRM + rotas de contingência (Recife/Aracaju)."""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
RECIFE = "2611606"

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

_AUTH_HEADERS: dict[str, str] = {}


def _ssl_context() -> ssl.SSLContext | None:
    if not BASE.lower().startswith("https"):
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _ensure_auth() -> None:
    global _AUTH_HEADERS
    if _AUTH_HEADERS:
        return
    token = os.getenv("HOMOLOG_TOKEN", "").strip()
    if not token:
        user = os.getenv("HOMOLOG_USER", os.getenv("AUTH_ADMIN_USER", "admin"))
        password = os.getenv("HOMOLOG_PASSWORD", os.getenv("AUTH_ADMIN_PASSWORD", "admin"))
        code, payload = _request(
            "POST",
            "/api/v1/auth/login",
            {"username": user, "password": password},
            skip_auth=True,
        )
        if code == 200 and isinstance(payload, dict):
            token = str(payload.get("access_token") or "")
    if token:
        _AUTH_HEADERS = {"Authorization": f"Bearer {token}"}


def _request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    skip_auth: bool = False,
    timeout: int = 120,
) -> tuple[int, dict | list | None]:
    url = f"{BASE.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    headers: dict[str, str] = {"Content-Type": "application/json"} if body else {}
    if not skip_auth:
        _ensure_auth()
        headers.update(_AUTH_HEADERS)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode())
        except Exception:
            detail = {"error": str(exc)}
        return exc.code, detail


def get(path: str) -> tuple[int, dict | None]:
    code, payload = _request("GET", path, timeout=30)
    return code, payload if isinstance(payload, dict) else None


def post(path: str, body: dict) -> tuple[int, dict | None]:
    code, payload = _request("POST", path, body, timeout=120)
    return code, payload if isinstance(payload, dict) else None


def main() -> int:
    fails = 0
    print(f"Validação OSRM — {BASE}\n")

    code, status = get("/api/v1/routing/status")
    ok = code == 200 and status and status.get("available")
    print(
        f"[{'OK' if ok else 'FAIL'}] routing/status available={status.get('available') if status else None} "
        f"region={status.get('region') if status else None}"
    )
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
    osrm_routes = [
        r
        for r in rotas
        if (r.get("fonte_rota") or (r.get("geojson") or {}).get("properties", {}).get("fonte")) == "osrm"
    ]
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
