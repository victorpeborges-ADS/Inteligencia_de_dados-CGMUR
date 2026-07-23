#!/usr/bin/env python3
"""Avaliação operacional do Sinidu+Clima (Windows/macOS/Linux).

Verifica containers Docker, saúde da API, frontend e amostra municipal.
Gera relatório em scripts/avaliacao_ultimo_relatorio.txt

Uso:
  python scripts/avaliar_sistema.py
  python scripts/avaliar_sistema.py http://localhost:8000
"""
from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.getenv("SINIDU_PROJECT_DIR", Path(__file__).resolve().parent.parent))
_default_report = Path(__file__).resolve().parent / "avaliacao_ultimo_relatorio.txt"
REPORT_PATH = Path(os.getenv("AVALIACAO_REPORT_PATH", str(_default_report)))
BASE = (sys.argv[1] if len(sys.argv) > 1 else os.getenv("SINIDU_API_URL", "http://localhost:8000")).rstrip("/")
FRONTEND = os.getenv("FRONTEND_URL", "http://localhost:3000").rstrip("/")
SKIP_DOCKER = os.getenv("AVALIACAO_SKIP_DOCKER", "").strip().lower() in ("1", "true", "yes", "on")
SKIP_FRONTEND = os.getenv("AVALIACAO_SKIP_FRONTEND", "").strip().lower() in ("1", "true", "yes", "on")

CORE_CONTAINERS = ("sinidu_db", "sinidu_redis", "sinidu_backend", "sinidu_frontend")
SAMPLE_IBGE = [
    ("2611606", "Recife"),
    ("2800308", "Aracaju"),
    ("2927408", "Salvador"),
    ("3304557", "Rio de Janeiro"),
    ("3550308", "São Paulo"),
    ("5300108", "Brasília"),
]

lines: list[str] = []
failures = 0
warnings = 0


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def ok(msg: str) -> None:
    log(f"[OK]   {msg}")


def warn(msg: str) -> None:
    global warnings
    warnings += 1
    log(f"[WARN] {msg}")


def fail(msg: str) -> None:
    global failures
    failures += 1
    log(f"[FAIL] {msg}")


def info(msg: str) -> None:
    log(f"[INFO] {msg}")


def _ssl_context() -> ssl.SSLContext | None:
    if not BASE.lower().startswith("https"):
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_get(url: str, *, headers: dict[str, str] | None = None, timeout: float = 20) -> tuple[int, object | None]:
    req_headers = dict(headers or {})
    req = urllib.request.Request(url, method="GET", headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else None
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            detail = {"error": str(exc)}
        return exc.code, detail
    except Exception as exc:
        return 0, {"error": str(exc)}


def http_post_json(url: str, body: dict, *, headers: dict[str, str] | None = None, timeout: float = 20) -> tuple[int, object | None]:
    data = json.dumps(body).encode("utf-8")
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, data=data, method="POST", headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(raw) if raw else None
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            detail = {"error": str(exc)}
        return exc.code, detail
    except Exception as exc:
        return 0, {"error": str(exc)}


def run_cmd(args: list[str], *, timeout: float = 30) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except FileNotFoundError:
        return 127, "comando nao encontrado"
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as exc:
        return 1, str(exc)


def check_docker() -> None:
    log("--- Docker ---")
    code, out = run_cmd(["docker", "info"])
    if code != 0:
        fail("Docker nao responde (Docker Desktop instalado e iniciado?)")
        info(out.splitlines()[-1] if out else "sem saida")
        return
    ok("Docker Engine acessivel")

    code, out = run_cmd(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"])
    if code != 0:
        fail("Nao foi possivel listar containers")
        return

    status_map: dict[str, str] = {}
    for line in out.splitlines():
        if "\t" in line:
            name, st = line.split("\t", 1)
            status_map[name.strip()] = st.strip()

    for name in CORE_CONTAINERS:
        st = status_map.get(name)
        if not st:
            fail(f"Container ausente: {name}")
        elif "Up" in st or "running" in st.lower():
            if "(healthy)" in st or "healthy" in st.lower():
                ok(f"{name}: {st}")
            else:
                ok(f"{name}: {st}")
        else:
            fail(f"{name}: {st}")

    extras = sorted(set(status_map) - set(CORE_CONTAINERS))
    if extras:
        info("Outros containers: " + ", ".join(extras[:12]))


def login_admin() -> str | None:
    user = os.getenv("HOMOLOG_USER", os.getenv("AUTH_ADMIN_USER", "admin"))
    password = os.getenv("HOMOLOG_PASSWORD", os.getenv("AUTH_ADMIN_PASSWORD", "admin"))
    code, payload = http_post_json(f"{BASE}/api/v1/auth/login", {"username": user, "password": password})
    if code == 200 and isinstance(payload, dict) and payload.get("access_token"):
        return str(payload["access_token"])
    return None


def check_api() -> dict[str, str]:
    log("")
    log("--- API / saude ---")
    auth: dict[str, str] = {}

    code, live = http_get(f"{BASE}/health/live")
    if code == 200:
        ok("health/live")
    else:
        fail(f"health/live HTTP {code} — {live}")

    code, ready = http_get(f"{BASE}/health/ready")
    if code == 200:
        ok(f"health/ready — {ready if isinstance(ready, dict) else 'ok'}")
    else:
        fail(f"health/ready HTTP {code} — sistema nao esta pronto")

    token = os.getenv("HOMOLOG_TOKEN", "").strip() or (login_admin() or "")
    if token:
        auth = {"Authorization": f"Bearer {token}"}
        ok("autenticacao admin (JWT)")
    else:
        warn("sem JWT — endpoints protegidos podem falhar (AUTH off ou credenciais invalidas)")

    code, overview = http_get(f"{BASE}/api/v1/system/overview", headers=auth or None)
    if code == 200 and isinstance(overview, dict):
        ob = overview.get("onboarding", {}) or {}
        dem = overview.get("dem", {}) or {}
        hom = overview.get("homologation", {}) or {}
        ok(
            "system/overview "
            f"onboarding={ob.get('concluidos')} "
            f"dem={dem.get('processados')}/{dem.get('prioritarios', '?')} "
            f"homolog={hom.get('score_pct', '?')}% "
            f"demo={hom.get('ready_for_demo')}"
        )
        score = hom.get("score_pct")
        if isinstance(score, (int, float)) and score < 55:
            warn(f"score de homologacao baixo ({score}%)")
        if hom.get("ready_for_demo") is False:
            warn("ready_for_demo=false — ver painel Sistema")
    elif code == 401:
        fail("system/overview HTTP 401 — autentique com HOMOLOG_USER/HOMOLOG_PASSWORD")
    else:
        fail(f"system/overview HTTP {code}")

    return auth


def check_frontend() -> None:
    log("")
    log("--- Frontend ---")
    code, _ = http_get(FRONTEND, timeout=8)
    if code == 200:
        ok(f"interface respondendo em {FRONTEND}")
    else:
        fail(f"interface offline em {FRONTEND} (HTTP {code})")


def check_municipal_sample(auth: dict[str, str]) -> None:
    log("")
    log("--- Amostra dos 6 municipios-piloto ---")
    for ibge, nome in SAMPLE_IBGE:
        checks: list[str] = []
        code, layers = http_get(
            f"{BASE}/api/v1/indicators/layers/meta?codigo_ibge={ibge}",
            headers=auth or None,
        )
        if code == 200 and isinstance(layers, dict):
            bairros = layers.get("bairros", {}) or {}
            checks.append(f"bairros={bairros.get('count', '?')}")
        else:
            fail(f"{nome} ({ibge}): layers/meta HTTP {code}")
            continue

        code, diag = http_get(
            f"{BASE}/api/v1/analytics/diagnostic?codigo_ibge={ibge}",
            headers=auth or None,
        )
        if code == 200:
            checks.append("diagnostico=sim")
        else:
            checks.append(f"diagnostico=nao({code})")
            warn(f"{nome} ({ibge}): diagnostico HTTP {code}")

        code, terrain = http_get(f"{BASE}/api/v1/terrain/{ibge}/config", headers=auth or None)
        if code == 200 and isinstance(terrain, dict):
            checks.append(f"dem={str(terrain.get('dem_source', '?'))[:24]}")
        else:
            checks.append("dem=ausente")
            warn(f"{nome} ({ibge}): DEM/config ausente")

        if "diagnostico=sim" in checks:
            ok(f"{nome} ({ibge}): {', '.join(checks)}")
        else:
            warn(f"{nome} ({ibge}): {', '.join(checks)}")


def check_routing(auth: dict[str, str]) -> None:
    log("")
    log("--- Roteamento / opcionais ---")
    code, routing = http_get(f"{BASE}/api/v1/routing/status", headers=auth or None)
    if code == 200 and isinstance(routing, dict) and routing.get("available"):
        ok("OSRM online")
    else:
        info("OSRM indisponivel — fallback Haversine (ok para demo)")


def write_report() -> None:
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
    header = [
        "SINIDU+Clima — Relatorio de avaliacao do sistema",
        f"Gerado em: {stamp}",
        f"API: {BASE}",
        f"Frontend: {FRONTEND}",
        f"Projeto: {ROOT}",
        "",
    ]
    footer = [
        "",
        f"Resumo: {failures} falha(s), {warnings} aviso(s).",
        "Criterio: 0 falhas = sistema operacionalmente saudavel para demo.",
    ]
    REPORT_PATH.write_text("\n".join(header + lines + footer) + "\n", encoding="utf-8")


def main() -> int:
    log("========================================")
    log(" SINIDU+Clima — avaliacao do sistema")
    log("========================================")
    log(f"API:       {BASE}")
    log(f"Frontend:  {FRONTEND}")
    log(f"Projeto:   {ROOT}")
    log("")

    if SKIP_DOCKER:
        info("Checagem Docker pulada (AVALIACAO_SKIP_DOCKER=1)")
    else:
        check_docker()
    auth = check_api()
    if SKIP_FRONTEND:
        info("Checagem frontend pulada (AVALIACAO_SKIP_FRONTEND=1)")
    else:
        check_frontend()
    check_municipal_sample(auth)
    check_routing(auth)

    log("")
    log("========================================")
    if failures == 0:
        log(f" RESULTADO: APROVADO  ({warnings} aviso(s))")
    else:
        log(f" RESULTADO: REPROVADO — {failures} falha(s), {warnings} aviso(s)")
    log("========================================")

    write_report()
    log("")
    log(f"Relatorio salvo em: {REPORT_PATH}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
