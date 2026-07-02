"""Health, liveness e readiness probes."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.boot import boot_status
from app.config import settings
from app.db import engine
from app.observability.metrics import render_prometheus
from app.security.oidc import check_oidc_connectivity, oidc_configured
from rag.config import AI_CHAT_PROVIDER, MISTRAL_API_KEY
from rag.providers.registry import default_chat_provider_id

router = APIRouter()

TLS_FULLCHAIN = os.getenv("TLS_FULLCHAIN", "/etc/nginx/certs/fullchain.pem")


def _check_db() -> tuple[bool, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _ollama_base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")


def _check_ollama() -> tuple[bool, str, dict[str, Any]]:
    base = _ollama_base_url()
    details: dict[str, Any] = {"url": base, "running_models": [], "memory_pressure": False}
    try:
        with httpx.Client(timeout=3.0) as client:
            tags = client.get(f"{base}/api/tags")
            if tags.status_code != 200:
                return False, f"HTTP {tags.status_code}", details

            ps = client.get(f"{base}/api/ps")
            if ps.status_code == 200:
                models = ps.json().get("models") or []
                details["running_models"] = [
                    {
                        "name": m.get("name"),
                        "size_vram_gb": round((m.get("size_vram") or 0) / 1e9, 2),
                    }
                    for m in models
                ]
                total_vram = sum(m.get("size_vram") or 0 for m in models)
                details["total_vram_gb"] = round(total_vram / 1e9, 2)
                details["memory_pressure"] = total_vram > 10e9

            return True, "ok", details
    except Exception as exc:
        return False, str(exc), details


def _ai_fallback_status() -> dict[str, Any]:
    mistral_ok = bool(MISTRAL_API_KEY.strip())
    return {
        "mistral_configured": mistral_ok,
        "chat_provider_env": AI_CHAT_PROVIDER,
        "default_provider": default_chat_provider_id(),
        "embed_provider": "mistral",
        "ai_available": mistral_ok,
    }


@router.get("/metrics")
def prometheus_metrics():
    """Métricas no formato Prometheus text exposition."""
    return Response(content=render_prometheus(), media_type="text/plain; version=0.0.4; charset=utf-8")


@router.get("/health")
def health_overview():
    db_ok, db_msg = _check_db()
    ollama_ok, ollama_msg, ollama_details = _check_ollama()
    return {
        "status": "healthy" if db_ok else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": settings.PROJECT_NAME,
        "auth_enabled": settings.AUTH_ENABLED,
        "checks": {
            "database": {"ok": db_ok, "detail": db_msg},
            "ollama": {"ok": ollama_ok, "detail": ollama_msg, **ollama_details},
            "ai_fallback": _ai_fallback_status(),
        },
        "boot": boot_status.to_dict(),
    }


@router.get("/health/live")
def liveness():
    """Processo vivo — sempre 200 se Uvicorn responde."""
    return {"status": "alive"}


@router.get("/health/ready")
def readiness(response: Response):
    """Pronto para tráfego — exige DB."""
    db_ok, db_msg = _check_db()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "database": db_msg}
    return {"status": "ready", "db_ready": boot_status.db_ready}


@router.get("/health/db")
def health_db(response: Response):
    db_ok, db_msg = _check_db()
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"ok": db_ok, "detail": db_msg}


@router.get("/health/ollama")
def health_ollama(response: Response):
    ok, msg, details = _check_ollama()
    payload = {
        "ok": ok,
        "detail": msg,
        "memory_pressure": details.get("memory_pressure", False),
        "running_models": details.get("running_models", []),
        "total_vram_gb": details.get("total_vram_gb"),
        "gemini_fallback": bool(GEMINI_API_KEY.strip()),
        "url": details.get("url"),
    }
    if not ok and not GEMINI_API_KEY.strip():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif details.get("memory_pressure"):
        response.status_code = status.HTTP_200_OK
        payload["warning"] = "Ollama com alta pressão de memória — fallback Gemini recomendado."
    return payload


@router.get("/health/oidc")
def health_oidc(response: Response):
    """Readiness do IdP OIDC — útil em homologação Keycloak/gov.br."""
    if not oidc_configured():
        return {"status": "disabled", "configured": False}

    ok, detail, meta = check_oidc_connectivity()
    payload = {"status": "ok" if ok else "error", "configured": True, "detail": detail, **meta}
    if not ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return payload


def _inspect_tls_cert(path: str) -> dict[str, Any]:
    import subprocess

    if not os.path.isfile(path):
        return {"status": "unavailable", "detail": "Certificado não montado no container", "path": path}

    try:
        proc = subprocess.run(
            ["openssl", "x509", "-in", path, "-noout", "-subject", "-issuer", "-enddate"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except FileNotFoundError:
        return {"status": "unknown", "detail": "openssl indisponível no container"}
    except subprocess.CalledProcessError as exc:
        return {"status": "error", "detail": exc.stderr.strip() or "certificado inválido"}

    meta: dict[str, Any] = {"status": "ok", "path": path}
    for line in proc.stdout.splitlines():
        if line.startswith("subject="):
            meta["subject"] = line.split("=", 1)[1]
            if "Sinidu Clima Homolog" in meta["subject"]:
                meta["homolog_self_signed"] = True
        elif line.startswith("issuer="):
            meta["issuer"] = line.split("=", 1)[1]
        elif line.startswith("notAfter="):
            meta["not_after"] = line.split("=", 1)[1]
            try:
                from datetime import datetime as dt

                expiry = dt.strptime(meta["not_after"], "%b %d %H:%M:%S %Y %Z")
                days_left = (expiry.replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)).days
                meta["days_until_expiry"] = days_left
                if days_left < 14:
                    meta["status"] = "warning"
                    meta["warning"] = "Certificado expira em menos de 14 dias"
            except ValueError:
                pass
    return meta


@router.get("/health/tls")
def health_tls(response: Response):
    """Validade do certificado TLS montado (produção MCID)."""
    payload = _inspect_tls_cert(TLS_FULLCHAIN)
    if payload.get("status") == "unavailable":
        return {"status": "disabled", "configured": False, **payload}
    if payload.get("status") == "error":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    elif payload.get("status") == "warning":
        response.status_code = status.HTTP_200_OK
    return {"configured": True, **payload}
