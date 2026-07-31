#!/usr/bin/env python3
"""Validação de município piloto — malha, agente, simulação, apresentação."""
from __future__ import annotations

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

DEFAULT_IBGE = "2611606"
_AUTH_HEADERS: dict[str, str] = {}


def _ssl_context(base: str) -> ssl.SSLContext | None:
    if not base.lower().startswith("https"):
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _ensure_auth(base: str) -> None:
    global _AUTH_HEADERS
    if _AUTH_HEADERS:
        return
    token = os.getenv("HOMOLOG_TOKEN", "").strip()
    if not token:
        user = os.getenv("HOMOLOG_USER", os.getenv("AUTH_ADMIN_USER", "admin"))
        password = os.getenv("HOMOLOG_PASSWORD", os.getenv("AUTH_ADMIN_PASSWORD", "admin"))
        _, code, payload = call(
            base,
            "POST",
            "/api/v1/auth/login",
            {"username": user, "password": password},
            timeout=15,
            skip_auth=True,
        )
        if code == 200 and isinstance(payload, dict):
            token = str(payload.get("access_token") or "")
    if token:
        _AUTH_HEADERS = {"Authorization": f"Bearer {token}"}


def call(
    base: str,
    method: str,
    path: str,
    body: dict | None = None,
    timeout: int = 120,
    *,
    skip_auth: bool = False,
) -> tuple[float, int, dict | list | None]:
    url = f"{base.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    headers: dict[str, str] = {"Content-Type": "application/json"} if body else {}
    if not skip_auth:
        _ensure_auth(base)
        headers.update(_AUTH_HEADERS)
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context(base)) as resp:
            raw = resp.read().decode()
            elapsed = round(time.time() - t0, 2)
            return elapsed, resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        elapsed = round(time.time() - t0, 2)
        try:
            detail = json.loads(exc.read().decode())
        except Exception:
            detail = {"error": str(exc)}
        return elapsed, exc.code, detail


def validate_municipio(base: str, ibge: str, label: str | None = None) -> int:
    nome = label or ibge
    print(f"Validação {nome} ({ibge}) — {base}\n")
    fails = 0

    elapsed, code, layers = call(base, "GET", f"/api/v1/indicators/layers/meta?codigo_ibge={ibge}")
    malha = layers.get("malha_disponivel") if isinstance(layers, dict) else None
    bairros = (layers or {}).get("bairros", {}) if isinstance(layers, dict) else {}
    badge = bairros.get("qualidade_badge") or bairros.get("data_quality") or bairros.get("fonte")
    ok = code == 200 and malha is True
    print(f"[{'OK' if ok else 'FAIL'}] badges/malha ({elapsed}s) malha={malha} badge={badge}")
    fails += 0 if ok else 1

    call(base, "POST", f"/api/v1/assistant/municipal/{ibge}/prewarm", None, timeout=15)
    call(
        base,
        "POST",
        "/api/v1/simulations/extreme-rainfall/prewarm",
        {"codigo_ibge": ibge, "precipitacao_mm": 120},
        timeout=30,
    )
    elapsed, code, ctx = 0.0, 0, None
    for _ in range(45):
        time.sleep(2)
        elapsed, code, ctx = call(base, "GET", f"/api/v1/assistant/municipal/{ibge}/context", timeout=90)
        if code == 200 and elapsed < 10:
            break
    ok = code == 200 and isinstance(ctx, dict) and ctx.get("summary_text")
    tag = "OK" if ok and elapsed < 10 else ("WARN" if ok else "FAIL")
    print(f"[{tag}] agente contexto ({elapsed}s)")
    if tag == "FAIL":
        fails += 1

    elapsed2, code2, _ = call(base, "GET", f"/api/v1/assistant/municipal/{ibge}/context", timeout=15)
    ok2 = code2 == 200 and elapsed2 < 3
    print(f"[{'OK' if ok2 else 'WARN'}] agente contexto cache ({elapsed2}s)")

    elapsed, code, chat = call(
        base,
        "POST",
        "/api/v1/assistant/chat-contextual",
        {
            "municipio_codigo": ibge,
            "message": "O que significa o Score Sinidu?",
            "pagina_atual": "painel",
            "descricao_pagina": "Painel executivo",
            "stream": False,
        },
        timeout=45,
    )
    reply = (chat or {}).get("response") or (chat or {}).get("reply") or (chat or {}).get("content") or ""
    offline_demo = "modo demonstração" in reply.lower() or "mistral_api_key" in reply.lower()
    llm_unavailable = code == 500 and not reply
    ok = code == 200 and len(reply) > 40 and elapsed < 20
    warn = (
        (code == 200 and len(reply) > 40 and elapsed >= 20)
        or (code == 200 and offline_demo)
        or llm_unavailable
    )
    tag = "OK" if ok else ("WARN" if warn else "FAIL")
    detail = f"http={code}"
    if llm_unavailable:
        detail += " (LLM offline — rebuild backend ou MISTRAL_API_KEY)"
    print(f"[{tag}] agente resposta ({elapsed}s) chars={len(reply)} {detail}")
    if tag == "FAIL":
        fails += 1

    elapsed, code, job_start = call(
        base,
        "POST",
        "/api/v1/simulations/extreme-rainfall/async",
        {"codigo_ibge": ibge, "precipitacao_mm": 120},
        timeout=30,
    )
    job_id = (job_start or {}).get("job_id") if isinstance(job_start, dict) else None
    sim = None
    prog = None
    if job_id:
        for _ in range(40):
            time.sleep(2)
            _, _, prog = call(base, "GET", f"/api/v1/simulations/jobs/{job_id}", timeout=30)
            if isinstance(prog, dict) and prog.get("status") == "completed":
                sim = prog.get("result")
                break
            if isinstance(prog, dict) and prog.get("status") == "failed":
                break
    ok = isinstance(sim, dict) and (
        sim.get("affected_area_km2") is not None
        or sim.get("geometry", {}).get("features")
        or sim.get("features")
    )
    from_cache = (prog or {}).get("from_cache") if isinstance(prog, dict) else False
    area = sim.get("affected_area_km2") if isinstance(sim, dict) else None
    print(f"[{'OK' if ok else 'FAIL'}] simulação 120mm async cache={from_cache} area_km2={area}")
    fails += 0 if ok else 1

    if ok and isinstance(sim, dict):
        elapsed, code, interp = call(
            base,
            "POST",
            "/api/v1/simulations/interpret",
            {
                "municipio_codigo": ibge,
                "tipo_simulacao": "chuva",
                "parametro_atual": 120.0,
                "parametro_referencia": 80.0,
                "resultado_simulacao": sim,
                "use_ai": False,
            },
            timeout=90,
        )
        findings = (interp or {}).get("achados") or (interp or {}).get("findings") or []
        resumo = (interp or {}).get("resumo_executivo") or ""
        ok_i = code == 200 and (len(findings) > 0 or len(resumo) > 40)
        print(f"[{'OK' if ok_i else 'FAIL'}] interpretação simulação ({elapsed}s) findings={len(findings)}")
        fails += 0 if ok_i else 1

        elapsed, code, cmp = call(
            base,
            "POST",
            "/api/v1/simulations/extreme-rainfall/compare",
            {"codigo_ibge": ibge, "baseline_mm": 80, "scenario_mm": 120},
            timeout=120,
        )
        ok_c = code == 200 and isinstance(cmp, dict) and isinstance(cmp.get("delta"), dict)
        delta = (cmp or {}).get("delta") or {}
        print(f"[{'OK' if ok_c else 'FAIL'}] comparação 80→120mm delta_area_km2={delta.get('affected_area_km2')}")
        fails += 0 if ok_c else 1

    elapsed, code, pres = call(base, "GET", f"/api/v1/diagnostic/{ibge}/presentation", timeout=60)
    ok = code == 200 and isinstance(pres, dict) and pres.get("municipio")
    print(f"[{'OK' if ok else 'FAIL'}] apresentação ({elapsed}s)")
    fails += 0 if ok else 1

    elapsed, code, cat = call(base, "GET", f"/api/v1/data-catalog/coverage?codigo_ibge={ibge}")
    mat = (cat or {}).get("maturidade_percentual") if isinstance(cat, dict) else None
    ok = code == 200 and mat is not None
    print(f"[{'OK' if ok else 'FAIL'}] catálogo maturidade={mat}%")
    fails += 0 if ok else 1

    print(f"→ {nome}: {fails} falha(s)\n")
    return fails


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    ibge = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_IBGE
    return 1 if validate_municipio(base, ibge) else 0


if __name__ == "__main__":
    raise SystemExit(main())
