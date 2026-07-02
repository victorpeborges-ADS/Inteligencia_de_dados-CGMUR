#!/usr/bin/env python3
"""Finaliza homologação MCID — onboarding restante, DEM piloto, CTM, diagnósticos, PDFs."""
from __future__ import annotations

import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"


def post(path: str) -> dict:
    req = urllib.request.Request(f"{BASE.rstrip('/')}{path}", method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{BASE.rstrip('/')}{path}", timeout=30) as resp:
        return json.loads(resp.read().decode())


def wait_job(job_id: str, *, label: str, timeout_s: int = 3600) -> dict:
    print(f"Aguardando {label} ({job_id})…")
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        job = get(f"/api/v1/system/jobs/{job_id}")
        status = job.get("status")
        if status in ("completed", "failed"):
            print(f"  → {status}")
            if job.get("error"):
                print(f"  erro: {job['error'][:200]}")
            return job
        time.sleep(15)
    raise TimeoutError(f"Job {job_id} não concluiu em {timeout_s}s")


def main() -> int:
    overview = get("/api/v1/system/overview")
    ob = overview.get("onboarding", {})
    print(f"Onboarding atual: {ob}")

    for status in ("em_progresso", "parcial"):
        count = ob.get("by_status", {}).get(status, 0)
        if count:
            r = post(f"/api/v1/system/jobs/onboarding-batch?limit=61&status={status}&force=true")
            wait_job(r["job_id"], label=f"onboarding {status}")

    print("Reprocessando DEM Recife (refino piloto)…")
    req = urllib.request.Request(
        f"{BASE.rstrip('/')}/api/v1/terrain/2611606/process?force=true",
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        terrain = json.loads(resp.read().decode())
    cfg = terrain.get("config", {})
    print(f"  Recife DEM: {cfg.get('dem_source')} res={cfg.get('dem_resolution_m')}m")

    print("Sync malha territorial Recife…")
    req = urllib.request.Request(
        f"{BASE.rstrip('/')}/api/v1/integrations/territorial/sync/2611606?force=true",
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        print(" ", json.loads(resp.read().decode()).get("bairros_count", "?"), "bairros")

    r = post("/api/v1/system/jobs/diagnostics-batch?limit=61")
    diag_job = wait_job(r["job_id"], label="diagnósticos")

    r = post("/api/v1/system/jobs/reports-batch?limit=61&force=true")
    pdf_job = wait_job(r["job_id"], label="PDFs", timeout_s=7200)

    overview = get("/api/v1/system/overview")
    print("\n=== Resultado final ===")
    print("Onboarding:", overview.get("onboarding"))
    print("DEM:", overview.get("dem", {}).get("processados"), "/61")
    if diag_job.get("result"):
        print("Diagnósticos:", diag_job["result"].get("processed"), "erros", len(diag_job["result"].get("errors", [])))
    if pdf_job.get("result"):
        print("PDFs:", pdf_job["result"].get("processed"), "bloqueados", pdf_job["result"].get("blocked_maturidade"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
