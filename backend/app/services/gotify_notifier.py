"""Notificações push via Gotify (docker local)."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)

GOTIFY_URL = os.getenv("GOTIFY_URL", "http://gotify:80").rstrip("/")
GOTIFY_TOKEN = os.getenv("GOTIFY_TOKEN", "")
GOTIFY_PRIORITY = int(os.getenv("GOTIFY_PRIORITY", "8"))


def push_alert(
    title: str,
    message: str,
    *,
    priority: int | None = None,
    extras: dict | None = None,
) -> bool:
    """Envia notificação Gotify. Retorna True se enviado."""
    if not GOTIFY_TOKEN:
        return False

    payload = {
        "title": title[:250],
        "message": message[:5000],
        "priority": priority if priority is not None else GOTIFY_PRIORITY,
        "extras": extras or {},
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(
                f"{GOTIFY_URL}/message",
                params={"token": GOTIFY_TOKEN},
                json=payload,
            )
            if resp.status_code >= 400:
                logger.warning("Gotify HTTP %s: %s", resp.status_code, resp.text[:200])
                return False
            return True
    except Exception as exc:
        logger.warning("Gotify indisponível: %s", exc)
        return False


def push_risk_alert(municipio_nome: str, codigo_ibge: str, nivel: str, detail: str) -> bool:
    pri = 10 if nivel == "VERMELHO" else 8 if nivel == "LARANJA" else 5
    return push_alert(
        f"Sinidu+Clima · {nivel} · {municipio_nome}",
        f"IBGE {codigo_ibge}\n{detail}",
        priority=pri,
    )


def push_job_status(job_label: str, job_id: str, status: str, detail: str = "") -> bool:
    """Notifica conclusão ou falha de job administrativo."""
    ok = status == "completed"
    title = f"Sinidu+Clima · Job {'OK' if ok else 'FALHA'} · {job_label}"
    message = f"ID: {job_id}\nStatus: {status}"
    if detail:
        message += f"\n{detail[:4000]}"
    return push_alert(title, message, priority=5 if ok else 9)
