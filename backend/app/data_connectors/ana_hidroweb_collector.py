"""Coletor ANA / HidroWeb (SNIRH) — stub com instrução de credencial (Fase 21b.2).

A API oficial exige cadastro e token Bearer.
Documentação: https://www.ana.gov.br/hidrowebservice
Cadastro / suporte: hidro@ana.gov.br

Variáveis de ambiente esperadas (quando credencial existir):
  ANA_HIDROWEB_TOKEN   — Bearer JWT
  ANA_HIDROWEB_BASE    — default https://www.ana.gov.br/hidrowebservice
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://www.ana.gov.br/hidrowebservice"
CREDENTIAL_HELP = (
    "API ANA HidroWeb exige cadastro. Solicite acesso em hidro@ana.gov.br, "
    "obtenha o Bearer token e defina ANA_HIDROWEB_TOKEN no ambiente. "
    "Sem credencial, a ingestão fluviométrica/pluviométrica ANA fica desligada."
)


def ana_credentials_configured() -> bool:
    token = (os.getenv("ANA_HIDROWEB_TOKEN") or "").strip()
    return bool(token)


def credential_status() -> dict[str, Any]:
    configured = ana_credentials_configured()
    return {
        "configured": configured,
        "base_url": (os.getenv("ANA_HIDROWEB_BASE") or DEFAULT_BASE).rstrip("/"),
        "env_var": "ANA_HIDROWEB_TOKEN",
        "help": None if configured else CREDENTIAL_HELP,
        "fase": "21b.2",
    }


def _auth_headers() -> dict[str, str]:
    token = (os.getenv("ANA_HIDROWEB_TOKEN") or "").strip()
    if not token:
        raise RuntimeError(CREDENTIAL_HELP)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "SiniduMVP/21b.2",
    }


def probe_api(timeout: float = 20.0) -> dict[str, Any]:
    """Testa autenticação com um endpoint leve (quando token existir)."""
    status = credential_status()
    if not status["configured"]:
        return {**status, "ok": False, "reason": "credencial_ausente"}

    base = status["base_url"]
    # Endpoint típico de inventário — pode variar; falha documentada não é crash.
    url = f"{base}/EstacoesTelemetricas/HidroInventarioEstacoesTelemetricas/v1"
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(url, headers=_auth_headers(), params={"codigoEstacao": "1"})
        return {
            **status,
            "ok": resp.status_code in (200, 204, 404),
            "http_status": resp.status_code,
            "probe_url": url,
            "detail": (resp.text or "")[:300],
        }
    except Exception as exc:
        logger.warning("ANA probe falhou: %s", exc)
        return {**status, "ok": False, "reason": str(exc), "probe_url": url}


def collect_pluvio_series_for_municipality(
    db: Session,
    codigo_ibge: str,
    *,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Placeholder de ingestão pluviométrica ANA → serie_pluviometrica_observada.

    dry_run=True (default) só reporta status até o contrato da API ser validado
    com token real.
    """
    code = str(codigo_ibge).zfill(7)[:7]
    status = credential_status()
    if not status["configured"]:
        return {
            "codigo_ibge": code,
            "ok": False,
            "ingested": 0,
            "reason": "credencial_ausente",
            **status,
        }

    if dry_run:
        probe = probe_api()
        return {
            "codigo_ibge": code,
            "ok": bool(probe.get("ok")),
            "ingested": 0,
            "dry_run": True,
            "nota": (
                "Credencial presente. Próximo passo: mapear estações no município, "
                "baixar série e upsert em serie_pluviometrica_observada (fonte=ana)."
            ),
            "probe": probe,
            **status,
        }

    # Implementação completa depende do contrato autenticado (inventário + telemetria).
    return {
        "codigo_ibge": code,
        "ok": False,
        "ingested": 0,
        "reason": "nao_implementado_sem_contrato_validado",
        "nota": "Use dry_run=True até validar endpoints com o token real.",
        **status,
    }
