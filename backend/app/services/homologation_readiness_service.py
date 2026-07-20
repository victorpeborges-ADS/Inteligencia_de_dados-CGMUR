"""Checklist automatizado de prontidão para homologação MCID (D.2)."""

from __future__ import annotations

import os
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.boot import boot_status
from app.config import settings
from app.security.oidc import check_oidc_connectivity, oidc_configured

ItemStatus = Literal["ok", "warn", "fail", "na"]

_DEFAULT_JWT_SECRET = "sinidu-dev-secret-trocar-em-producao"
_PROD_LIKE_ENVS = frozenset({"production", "homolog", "prod", "staging"})


def _item(
    item_id: str,
    label: str,
    status: ItemStatus,
    *,
    detail: str = "",
    group: str = "geral",
) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "status": status,
        "detail": detail,
        "group": group,
    }


def _score(items: list[dict[str, Any]]) -> int:
    scored = [i for i in items if i["status"] != "na"]
    if not scored:
        return 0
    weights = {"ok": 1.0, "warn": 0.5, "fail": 0.0}
    total = sum(weights[i["status"]] for i in scored)
    return round((total / len(scored)) * 100)


def _environment_name() -> str:
    return (os.getenv("ENVIRONMENT") or "development").strip().lower()


def _jwt_secret_status() -> tuple[ItemStatus, str]:
    secret = settings.AUTH_JWT_SECRET or ""
    weak = secret == _DEFAULT_JWT_SECRET or len(secret) < 32
    if not weak:
        return "ok", f"AUTH_JWT_SECRET com {len(secret)} chars"
    env = _environment_name()
    if env in _PROD_LIKE_ENVS:
        return "fail", "Secret default/curto — defina AUTH_JWT_SECRET (>=32) em homolog/produção"
    return "warn", "Secret de desenvolvimento — trocar antes de homolog/produção"


def _redis_status(redis_meta: dict[str, Any] | None = None) -> tuple[ItemStatus, str]:
    if redis_meta is not None:
        if redis_meta.get("ok") is True:
            return "ok", str(redis_meta.get("detail") or "ping ok")
        if redis_meta.get("na") is True:
            return "na", str(redis_meta.get("detail") or "Redis desligado")
        return "warn", str(redis_meta.get("detail") or "Redis indisponível")
    if not settings.JOB_STORE_REDIS:
        return "na", "JOB_STORE_REDIS=false"
    try:
        import redis

        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=1.5)
        client.ping()
        return "ok", "Redis ping ok"
    except Exception as exc:
        return "warn", f"Redis: {str(exc)[:100]}"


def _scheduler_item_status(scheduler_meta: dict[str, Any] | None = None) -> tuple[ItemStatus, str]:
    if scheduler_meta is None:
        from app.data_connectors.scheduler import scheduler_status

        scheduler_meta = scheduler_status()
    running = bool(scheduler_meta.get("running"))
    jobs = scheduler_meta.get("jobs") or []
    if running and jobs:
        return "ok", f"{len(jobs)} job(s) agendado(s)"
    if running:
        return "warn", "Scheduler up sem jobs"
    return "warn", "Scheduler parado (boot ainda em andamento?)"


def build_homologation_readiness(
    db: Session,
    *,
    oidc_meta: dict[str, Any] | None = None,
    tls_meta: dict[str, Any] | None = None,
    batch_coverage: dict[str, Any] | None = None,
    ctm_summary: dict[str, Any] | None = None,
    dem_summary: dict[str, Any] | None = None,
    osrm_meta: dict[str, Any] | None = None,
    backup_meta: dict[str, Any] | None = None,
    gotify_meta: dict[str, Any] | None = None,
    ml_meta: dict[str, Any] | None = None,
    redis_meta: dict[str, Any] | None = None,
    scheduler_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Consolida itens do CHECKLIST_OIDC_GOVBR + passos operacionais do RESUMO."""
    from app.services.batch_export_service import batch_coverage_summary
    from app.services.dem_processor import is_processed
    from app.services.gotify_notifier import gotify_status
    from app.services.institutional_gaps_service import build_ctm_operational_summary
    from app.services.osrm_router import osrm_status
    from app.services.postgis_backup import latest_backup_status
    from ml.constants import ML_TARGET_IBGE_CODES
    from ml.paths import model_path

    oidc_meta = oidc_meta or {}
    tls_meta = tls_meta or {}
    batch_coverage = batch_coverage or batch_coverage_summary(db)
    ctm_summary = ctm_summary or build_ctm_operational_summary(db)
    dem_summary = dem_summary or {}
    osrm_meta = osrm_meta if osrm_meta is not None else osrm_status()
    backup_meta = backup_meta if backup_meta is not None else latest_backup_status()
    gotify_meta = gotify_meta if gotify_meta is not None else gotify_status()
    if ml_meta is None:
        ready = sum(1 for code in ML_TARGET_IBGE_CODES if model_path(code).exists())
        ml_meta = {"ready_count": ready, "total": len(ML_TARGET_IBGE_CODES)}
    else:
        ml_meta = ml_meta

    items: list[dict[str, Any]] = []

    items.append(
        _item(
            "auth_jwt",
            "Autenticação JWT ativa",
            "ok" if settings.AUTH_ENABLED else "warn",
            detail="AUTH_ENABLED=true exigido em homologação/produção",
            group="auth",
        )
    )
    jwt_status, jwt_detail = _jwt_secret_status()
    items.append(
        _item(
            "jwt_secret",
            "AUTH_JWT_SECRET seguro",
            jwt_status,
            detail=jwt_detail,
            group="auth",
        )
    )
    items.append(
        _item(
            "multi_tenant",
            "Multi-tenant habilitado",
            "ok" if settings.MULTI_TENANT_ENABLED else "warn",
            detail="MULTI_TENANT_ENABLED=true para gestores por UF/município",
            group="auth",
        )
    )

    if settings.OIDC_ENABLED:
        if oidc_configured():
            reachable = oidc_meta.get("reachable")
            if reachable is True:
                oidc_status: ItemStatus = "ok"
                oidc_detail = oidc_meta.get("detail") or "IdP acessível"
            elif reachable is False:
                oidc_status = "fail"
                oidc_detail = oidc_meta.get("detail") or "IdP inacessível"
            else:
                oidc_ok, oidc_detail, _extra = check_oidc_connectivity()
                oidc_status = "ok" if oidc_ok else "fail"
            items.append(
                _item(
                    "oidc_config",
                    "OIDC configurado",
                    "ok",
                    detail=f"Issuer: {settings.OIDC_ISSUER_URL}",
                    group="auth",
                )
            )
            items.append(
                _item(
                    "oidc_reachable",
                    "IdP OIDC acessível",
                    oidc_status,
                    detail=str(oidc_detail),
                    group="auth",
                )
            )
        else:
            items.append(
                _item(
                    "oidc_config",
                    "OIDC configurado",
                    "fail",
                    detail="OIDC_ENABLED=true mas faltam issuer/client/redirect",
                    group="auth",
                )
            )
    else:
        items.append(
            _item(
                "oidc_config",
                "OIDC / Keycloak",
                "na",
                detail="OIDC_ENABLED=false — protótipo com senha (gov.br fora de escopo)",
                group="auth",
            )
        )

    if settings.AUTH_ENABLED and settings.AUTH_PASSWORD_LOGIN_ENABLED and not settings.OIDC_ENABLED:
        items.append(
            _item(
                "password_login_off",
                "Login por senha (protótipo)",
                "na",
                detail="Aceito no protótipo — gov.br/OIDC fora de escopo",
                group="auth",
            )
        )
    elif settings.AUTH_PASSWORD_LOGIN_ENABLED and settings.AUTH_ENABLED:
        items.append(
            _item(
                "password_login_off",
                "Login por senha desligado",
                "warn",
                detail="Com OIDC ativo, AUTH_PASSWORD_LOGIN_ENABLED=false é recomendado",
                group="auth",
            )
        )
    elif settings.AUTH_ENABLED:
        items.append(
            _item(
                "password_login_off",
                "Login por senha desligado",
                "ok",
                detail="Somente SSO/OIDC",
                group="auth",
            )
        )

    tls_status = tls_meta.get("status", "unavailable")
    if tls_status == "ok":
        days = tls_meta.get("days_until_expiry")
        tls_item: ItemStatus = "ok" if days is None or days >= 14 else "warn"
        items.append(
            _item(
                "tls_cert",
                "Certificado TLS válido",
                tls_item,
                detail=f"Expira em {days} dias" if days is not None else "OK",
                group="infra",
            )
        )
    elif tls_status == "warning":
        items.append(
            _item(
                "tls_cert",
                "Certificado TLS válido",
                "warn",
                detail=tls_meta.get("detail") or "Expira em breve",
                group="infra",
            )
        )
    elif tls_status == "unavailable":
        items.append(
            _item(
                "tls_cert",
                "Certificado TLS",
                "na",
                detail="TLS no balanceador ou não inspecionado neste host",
                group="infra",
            )
        )
    else:
        items.append(
            _item(
                "tls_cert",
                "Certificado TLS válido",
                "fail",
                detail=tls_meta.get("detail") or tls_status,
                group="infra",
            )
        )

    diag_ok = batch_coverage.get("diagnosticos_ok", False)
    pdf_ok = batch_coverage.get("relatorios_ok", False)
    total = batch_coverage.get("municipios_total", 0)
    items.append(
        _item(
            "diagnosticos_batch",
            "Diagnósticos executivos",
            "ok" if diag_ok else "fail",
            detail=f"{batch_coverage.get('com_diagnostico', 0)}/{total}",
            group="dados",
        )
    )
    items.append(
        _item(
            "pdfs_batch",
            "Relatórios PDF municipais",
            "ok" if pdf_ok else "fail",
            detail=f"{batch_coverage.get('com_relatorio', 0)}/{total}",
            group="dados",
        )
    )

    ctm_total = ctm_summary.get("total_alvo", 24)
    ctm_malha = (ctm_summary.get("importado_prefeitura", 0) or 0) + (
        ctm_summary.get("malha_operacional", 0) or 0
    )
    ctm_ok = ctm_summary.get("lacuna_municipios", 1) == 0 and ctm_malha >= ctm_total
    # A.6 CTM oficial bloqueado — não puxa score do protótipo
    items.append(
        _item(
            "ctm_malha",
            "Malha CTM operacional (24 alvos)",
            "na",
            detail=(
                f"{ctm_summary.get('progress_label', '')} · "
                "fora do gate do protótipo (depende de REST/convênio A.6)"
            ).strip(" ·"),
            group="dados",
        )
    )

    boot_codes = settings.BOOT_PRIORITY_IBGE_CODES
    if dem_summary.get("boot_processed") is not None:
        dem_ready = int(dem_summary["boot_processed"])
        dem_total = int(dem_summary.get("boot_total") or len(boot_codes))
    else:
        dem_ready = sum(1 for code in boot_codes if is_processed(code))
        dem_total = len(boot_codes)
    dem_item_status: ItemStatus = (
        "ok" if dem_total and dem_ready >= dem_total else ("warn" if dem_ready else "fail")
    )
    dem_detail = dem_summary.get("boot_detail") or f"{dem_ready}/{dem_total} processados"
    if dem_summary.get("processados") is not None and dem_summary.get("prioritarios") is not None:
        dem_detail = (
            f"{dem_ready}/{dem_total} boot · "
            f"{dem_summary['processados']}/{dem_summary['prioritarios']} prioritários"
        )
    items.append(
        _item(
            "dem_boot",
            "DEM dos municípios de boot",
            dem_item_status,
            detail=str(dem_detail),
            group="performance",
        )
    )
    items.append(
        _item(
            "sim_prewarm",
            "Prewarm simulação + DEM",
            "ok" if settings.SIMULATION_PREWARM_ENABLED and settings.DEM_PREWARM_ENABLED else "warn",
            detail=(
                f"SIM={settings.SIMULATION_PREWARM_ENABLED} "
                f"DEM={settings.DEM_PREWARM_ENABLED}"
            ),
            group="performance",
        )
    )

    ml_ready = int(ml_meta.get("ready_count") or 0)
    ml_total = int(ml_meta.get("total") or len(ML_TARGET_IBGE_CODES))
    ml_status: ItemStatus = (
        "ok" if ml_total and ml_ready >= ml_total else ("warn" if ml_ready else "fail")
    )
    items.append(
        _item(
            "ml_flood_models",
            "Modelos ML alagamento",
            ml_status,
            detail=f"{ml_ready}/{ml_total} artefatos prontos",
            group="performance",
        )
    )

    osrm_ok = bool(osrm_meta.get("available"))
    items.append(
        _item(
            "osrm_routing",
            "OSRM malha viária",
            "ok" if osrm_ok else "warn",
            detail=(
                f"região {osrm_meta.get('region')} · {osrm_meta.get('detail')}"
                if osrm_ok
                else (osrm_meta.get("setup_hint") or osrm_meta.get("detail") or "fallback geométrico")
            ),
            group="infra",
        )
    )

    backup_status = str(backup_meta.get("status") or "missing")
    if backup_status == "ok":
        backup_item: ItemStatus = "ok"
    elif backup_status == "stale":
        backup_item = "warn"
    else:
        backup_item = "warn"
    items.append(
        _item(
            "postgis_backup",
            "Backup PostGIS recente",
            backup_item,
            detail=str(backup_meta.get("detail") or "sem dump"),
            group="infra",
        )
    )

    gotify_configured = bool(gotify_meta.get("configured"))
    gotify_reachable = bool(gotify_meta.get("reachable"))
    if gotify_configured and gotify_reachable:
        gotify_item: ItemStatus = "ok"
        gotify_detail = str(gotify_meta.get("detail") or "ok")
    elif gotify_configured:
        gotify_item = "warn"
        gotify_detail = str(gotify_meta.get("detail") or "token ok, health falhou")
    else:
        gotify_item = "warn"
        gotify_detail = "GOTIFY_TOKEN ausente — alertas push desligados"
    items.append(
        _item(
            "gotify_notify",
            "Gotify (alertas push)",
            gotify_item,
            detail=gotify_detail,
            group="infra",
        )
    )

    redis_status, redis_detail = _redis_status(redis_meta)
    items.append(
        _item(
            "redis_cache",
            "Redis (jobs/cache)",
            redis_status,
            detail=redis_detail,
            group="infra",
        )
    )

    sched_status, sched_detail = _scheduler_item_status(scheduler_meta)
    items.append(
        _item(
            "scheduler_running",
            "Scheduler de integrações",
            sched_status,
            detail=sched_detail,
            group="infra",
        )
    )

    boot_errors = boot_status.errors or []
    items.append(
        _item(
            "boot_clean",
            "Boot sem erros críticos",
            "ok" if not boot_errors else "warn",
            detail=f"{len(boot_errors)} aviso(s)" if boot_errors else "OK",
            group="infra",
        )
    )

    score = _score(items)
    auth_items = [i for i in items if i["group"] == "auth" and i["status"] != "na"]
    ready_sso = (
        settings.AUTH_ENABLED
        and settings.MULTI_TENANT_ENABLED
        and settings.OIDC_ENABLED
        and oidc_configured()
        and any(i["id"] == "oidc_reachable" and i["status"] == "ok" for i in items)
    )
    password_off_ok = any(
        i["id"] == "password_login_off" and i["status"] == "ok" for i in items
    ) or (
        settings.AUTH_ENABLED and not settings.AUTH_PASSWORD_LOGIN_ENABLED
    )
    # Demo/protótipo: JWT + multi-tenant + batch + DEM; sem OIDC/CTM/gov.br
    ready_demo = (
        settings.AUTH_ENABLED
        and settings.MULTI_TENANT_ENABLED
        and diag_ok
        and pdf_ok
        and dem_item_status == "ok"
        and jwt_status != "fail"
        and all(
            i["status"] != "fail"
            for i in items
            if i["id"] in {"auth_jwt", "diagnosticos_batch", "pdfs_batch", "jwt_secret"}
        )
    )
    # Produção institucional: SSO + senha off + dados (+ CTM quando houver convênio)
    ready_prod = (
        ready_sso
        and password_off_ok
        and not settings.AUTH_PASSWORD_LOGIN_ENABLED
        and diag_ok
        and pdf_ok
        and ctm_ok
        and dem_item_status == "ok"
        and jwt_status == "ok"
        and all(
            i["status"] in {"ok", "na", "warn"}
            for i in items
            if i["group"] == "infra"
            and i["id"] in {"osrm_routing", "gotify_notify", "postgis_backup", "redis_cache", "scheduler_running"}
        )
        and all(
            i["status"] in {"ok", "na"}
            for i in items
            if i["group"] == "infra" and i["id"] in {"tls_cert", "boot_clean"}
        )
        and all(i["status"] == "ok" for i in auth_items if i["id"] not in {"password_login_off"})
        and password_off_ok
    )

    pending = [
        i["label"] for i in items if i["status"] in {"fail", "warn"} and i["status"] != "na"
    ]
    next_steps: list[str] = []
    if jwt_status != "ok":
        next_steps.append("Definir AUTH_JWT_SECRET forte (>=32 chars, não usar default)")
    if not settings.AUTH_ENABLED or not settings.MULTI_TENANT_ENABLED:
        next_steps.append("Ativar AUTH_ENABLED e MULTI_TENANT_ENABLED no .env")
    if not diag_ok or not pdf_ok:
        next_steps.append("Painel Sistema → Gerar PDFs/diagnósticos pendentes")
    if dem_item_status != "ok":
        next_steps.append("Processar DEM dos municípios de boot (painel Sistema → DEM batch)")
    if ml_status != "ok":
        next_steps.append("Painel Sistema → Bootstrap ML alagamento")
    if settings.OIDC_ENABLED and not ready_sso:
        next_steps.append("Validar IdP: ./scripts/validacao_oidc_govbr.sh https://localhost")
    if settings.OIDC_ENABLED and settings.AUTH_PASSWORD_LOGIN_ENABLED:
        next_steps.append("Produção: AUTH_PASSWORD_LOGIN_ENABLED=false")
    if not osrm_ok:
        next_steps.append("Ativar OSRM: scripts/osrm-enable.sh (ou validacao_osrm.py)")
    if backup_status != "ok":
        next_steps.append("Gerar backup PostGIS (scheduler 02:30 ou job manual)")
    if not gotify_configured:
        next_steps.append("Configurar GOTIFY_TOKEN para alertas push")
    if redis_status == "warn":
        next_steps.append("Verificar REDIS_URL / serviço redis")
    if not next_steps and ready_demo:
        next_steps.append(
            "Protótipo pronto para demo (ready_for_demo). gov.br OAuth2 fora de escopo."
        )
    elif not next_steps and ready_sso:
        next_steps.append("SSO Keycloak testável — gov.br real não é requisito deste protótipo")

    return {
        "score_pct": score,
        "ready_for_demo": ready_demo,
        "ready_for_sso_test": ready_sso,
        "ready_for_production": ready_prod,
        "govbr_required": False,
        "pending_count": len(pending),
        "items": items,
        "next_steps": next_steps[:5],
        "checklist_doc": "CHECKLIST_OIDC_GOVBR.md",
        "note": (
            "Gate de demo: JWT+multi-tenant+diagnósticos+PDF+DEM. "
            "gov.br REAL adiado — Keycloak local ou senha bastam no protótipo"
        ),
    }
