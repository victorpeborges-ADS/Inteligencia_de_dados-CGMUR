#!/usr/bin/env python3
"""Validação Recife (Step 1) — agente, simulação, apresentação, badges."""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
IBGE = "2611606"


def call(method: str, path: str, body: dict | None = None, timeout: int = 120) -> tuple[float, int, dict | list | None]:
    url = f"{BASE.rstrip('/')}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"} if body else {})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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


def main() -> int:
    print(f"Validação Recife {IBGE} — {BASE}\n")
    fails = 0

    elapsed, code, layers = call("GET", f"/api/v1/indicators/layers/meta?codigo_ibge={IBGE}")
    malha = layers.get("malha_disponivel") if isinstance(layers, dict) else None
    bairros = (layers or {}).get("bairros", {}) if isinstance(layers, dict) else {}
    badge = bairros.get("qualidade_badge") or bairros.get("data_quality") or bairros.get("fonte")
    ok = code == 200 and malha is True
    print(f"[{'OK' if ok else 'FAIL'}] badges/malha ({elapsed}s) malha={malha} badge={badge}")
    fails += 0 if ok else 1

    call("POST", f"/api/v1/assistant/municipal/{IBGE}/prewarm", None, timeout=15)
    call("POST", "/api/v1/simulations/extreme-rainfall/prewarm", {"codigo_ibge": IBGE, "precipitacao_mm": 120}, timeout=30)
    for _ in range(45):
        time.sleep(2)
        elapsed, code, ctx = call("GET", f"/api/v1/assistant/municipal/{IBGE}/context", timeout=90)
        if code == 200 and elapsed < 10:
            break
    ok = code == 200 and isinstance(ctx, dict) and ctx.get("summary_text")
    tag = "OK" if ok and elapsed < 10 else ("WARN" if ok else "FAIL")
    print(f"[{tag}] agente contexto ({elapsed}s) cached={'summary' in str((ctx or {}).keys())}")
    if tag == "FAIL":
        fails += 1

    elapsed2, code2, ctx2 = call("GET", f"/api/v1/assistant/municipal/{IBGE}/context", timeout=15)
    ok2 = code2 == 200 and elapsed2 < 3
    print(f"[{'OK' if ok2 else 'WARN'}] agente contexto cache ({elapsed2}s)")

    elapsed, code, chat = call(
        "POST",
        "/api/v1/assistant/chat-contextual",
        {
            "municipio_codigo": IBGE,
            "message": "O que significa o Score Sinidu?",
            "pagina_atual": "painel",
            "descricao_pagina": "Painel executivo",
            "stream": False,
        },
        timeout=45,
    )
    reply = (chat or {}).get("response") or (chat or {}).get("reply") or (chat or {}).get("content") or ""
    ok = code == 200 and len(reply) > 40 and elapsed < 20
    warn = code == 200 and len(reply) > 40 and elapsed >= 20
    tag = "OK" if ok else ("WARN" if warn else "FAIL")
    print(f"[{tag}] agente resposta ({elapsed}s) chars={len(reply)}")
    if tag == "FAIL":
        fails += 1

    elapsed, code, job_start = call(
        "POST",
        "/api/v1/simulations/extreme-rainfall/async",
        {"codigo_ibge": IBGE, "precipitacao_mm": 120},
        timeout=30,
    )
    job_id = (job_start or {}).get("job_id") if isinstance(job_start, dict) else None
    sim = None
    prog = None
    if job_id:
        for _ in range(40):
            time.sleep(2)
            _, _, prog = call("GET", f"/api/v1/simulations/jobs/{job_id}", timeout=30)
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
    print(f"[{'OK' if ok else 'FAIL'}] simulação 120mm async ({elapsed}s start) cache={from_cache} area_km2={area}")
    fails += 0 if ok else 1

    if ok and isinstance(sim, dict):
        elapsed, code, interp = call(
            "POST",
            "/api/v1/simulations/interpret",
            {
                "municipio_codigo": IBGE,
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
            "POST",
            "/api/v1/simulations/extreme-rainfall/compare",
            {"codigo_ibge": IBGE, "baseline_mm": 80, "scenario_mm": 120},
            timeout=120,
        )
        ok_c = code == 200 and isinstance(cmp, dict) and isinstance(cmp.get("delta"), dict)
        delta = (cmp or {}).get("delta") or {}
        print(f"[{'OK' if ok_c else 'FAIL'}] comparação 80→120mm ({elapsed}s) delta_area_km2={delta.get('affected_area_km2')}")
        fails += 0 if ok_c else 1

    elapsed, code, pres = call("GET", f"/api/v1/diagnostic/{IBGE}/presentation", timeout=60)
    ok = code == 200 and isinstance(pres, dict) and pres.get("municipio")
    print(f"[{'OK' if ok else 'FAIL'}] apresentação ({elapsed}s) keys={list((pres or {}).keys())[:6]}")
    fails += 0 if ok else 1

    elapsed, code, cat = call("GET", f"/api/v1/data-catalog/coverage?codigo_ibge={IBGE}")
    mat = (cat or {}).get("maturidade_percentual") if isinstance(cat, dict) else None
    ok = code == 200 and mat is not None
    print(f"[{'OK' if ok else 'FAIL'}] catálogo ({elapsed}s) maturidade={mat}%")
    fails += 0 if ok else 1

    print(f"\nResultado: {fails} falha(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
