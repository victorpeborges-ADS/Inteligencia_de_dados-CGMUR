#!/usr/bin/env python3
"""Smoke test de homologação — health, OIDC, overview e amostra municipal."""
from __future__ import annotations

import json
import os
import ssl
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"

SAMPLE_IBGE = [
    "2611606",  # Recife (piloto boot)
    "2800308",  # Aracaju (piloto boot)
    "3550308",  # São Paulo
    "2927408",  # Salvador
    "1302603",  # Manaus
    "4314902",  # Porto Alegre
]


def _ssl_context() -> ssl.SSLContext | None:
    if not BASE.lower().startswith("https"):
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _request(
    method: str,
    path: str,
    *,
    body: dict | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict | list | None]:
    url = f"{BASE.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req_headers = {"Content-Type": "application/json"} if body is not None else {}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_context()) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode())
        except Exception:
            detail = {"error": str(exc)}
        return exc.code, detail


def get(path: str, *, headers: dict[str, str] | None = None) -> tuple[int, dict | list | None]:
    return _request("GET", path, headers=headers)


def login_admin() -> str | None:
    user = os.getenv("HOMOLOG_USER", os.getenv("AUTH_ADMIN_USER", "admin"))
    password = os.getenv("HOMOLOG_PASSWORD", os.getenv("AUTH_ADMIN_PASSWORD", "admin"))
    code, payload = _request("POST", "/api/v1/auth/login", body={"username": user, "password": password})
    if code != 200 or not isinstance(payload, dict):
        return None
    token = payload.get("access_token")
    return str(token) if token else None


def resolve_auth_headers() -> dict[str, str]:
    token = os.getenv("HOMOLOG_TOKEN", "").strip()
    if not token:
        token = login_admin() or ""
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def check_oidc_health() -> bool:
    code, payload = get("/health/oidc")
    if code != 200 or not isinstance(payload, dict):
        print(f"[FAIL] health/oidc HTTP {code}")
        return False
    status = payload.get("status")
    if status == "ok":
        print("[OK] health/oidc IdP acessível")
        return True
    if status == "disabled":
        print("[INFO] health/oidc OIDC desligado")
        return True
    print(f"[FAIL] health/oidc status={status}")
    return False


def main() -> int:
    print(f"Smoke test Sinidu+Clima — {BASE}\n")
    failures = 0

    ok, health = get("/health/ready")
    print(f"[{'OK' if ok == 200 else 'FAIL'}] health/ready {health}")
    if ok != 200:
        return 1

    if BASE.lower().startswith("https"):
        if not check_oidc_health():
            failures += 1

    auth_headers = resolve_auth_headers()
    if auth_headers:
        print("[OK] autenticação admin (JWT)")
    else:
        print("[WARN] sem JWT — endpoints protegidos podem falhar")

    ok, overview = get("/api/v1/system/overview", headers=auth_headers or None)
    if ok == 200 and isinstance(overview, dict):
        ob = overview.get("onboarding", {})
        dem = overview.get("dem", {})
        hom = overview.get("homologation", {})
        print(
            f"[OK] overview onboarding={ob.get('concluidos')} "
            f"dem={dem.get('processados')}/{dem.get('prioritarios', 61)} "
            f"homolog={hom.get('score_pct', '?')}% "
            f"demo={hom.get('ready_for_demo')} "
            f"sso={hom.get('ready_for_sso_test')}"
        )
        if hom.get("govbr_required") is True:
            print("[FAIL] homologação: govbr_required deveria ser false no protótipo")
            failures += 1
        score = hom.get("score_pct")
        if isinstance(score, (int, float)) and score < 55:
            print(f"[WARN] homologação: score baixo ({score}%)")
        if hom and hom.get("ready_for_demo") is False:
            print("[WARN] homologação: ready_for_demo=false — ver painel Sistema")
        if hom and not hom.get("ready_for_sso_test") and overview.get("auth", {}).get("oidc_enabled"):
            print("[WARN] homologação: SSO ainda não marcado como testável")
    elif ok == 401 and not auth_headers:
        print("[FAIL] overview HTTP 401 — defina HOMOLOG_USER/HOMOLOG_PASSWORD")
        failures += 1
    else:
        print(f"[WARN] overview HTTP {ok}")
        failures += 1

    sample_failures = 0
    for ibge in SAMPLE_IBGE:
        checks: list[str] = []
        code, layers = get(f"/api/v1/indicators/layers/meta?codigo_ibge={ibge}", headers=auth_headers or None)
        if code == 200 and isinstance(layers, dict):
            bairros = layers.get("bairros", {})
            checks.append(f"bairros={bairros.get('count', '?')}")
        else:
            sample_failures += 1
            print(f"[FAIL] {ibge} layers/meta HTTP {code}")
            continue

        code, diag = get(f"/api/v1/analytics/diagnostic?codigo_ibge={ibge}", headers=auth_headers or None)
        if code == 200:
            checks.append("diagnostico=sim")
        else:
            checks.append(f"diagnostico=nao({code})")
            sample_failures += 1

        code, terrain = get(f"/api/v1/terrain/{ibge}/config", headers=auth_headers or None)
        if code == 200 and isinstance(terrain, dict):
            checks.append(f"dem={str(terrain.get('dem_source', '?'))[:24]}")
        else:
            checks.append("dem=ausente")
            sample_failures += 1

        print(f"[{'OK' if 'diagnostico=sim' in checks else 'WARN'}] {ibge}: {', '.join(checks)}")

    code, routing = get("/api/v1/routing/status", headers=auth_headers or None)
    osrm = routing.get("available") if isinstance(routing, dict) else False
    print(f"[{'OK' if osrm else 'INFO'}] OSRM {'online' if osrm else 'fallback Haversine'}")

    failures += sample_failures
    print(f"\nConcluído — {failures} falha(s) em amostra de {len(SAMPLE_IBGE)} municípios.")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
