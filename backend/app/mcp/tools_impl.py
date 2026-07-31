"""Implementações read-only das tools MCP (20c.1) — testáveis sem SDK."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.mcp.auth_gate import McpAuthError, assert_read_only_tool, json_safe, resolve_mcp_user
from app.models import DiagnosticoExecutivo, Municipio, WeatherForecastCache
from app.security.auth import User
from app.security.municipio_access import assert_codigo_ibge_access, get_accessible_municipio, normalize_ibge


TOOL_NAMES = (
    "municipio_overview",
    "layers_catalog_summary",
    "diagnostic_latest",
    "monitoring_snapshot",
    "flood_model_status",
    "catalog_gaps",
    "live_alert",
)


def _session() -> Session:
    return SessionLocal()


def _with_access(
    codigo_ibge: str,
    *,
    token: str | None = None,
) -> tuple[Session, User, Municipio]:
    user = resolve_mcp_user(token=token)
    db = _session()
    try:
        code = normalize_ibge(codigo_ibge)
        assert_codigo_ibge_access(db, code, user=user)
        muni = get_accessible_municipio(db, code, user=user)
        return db, user, muni
    except Exception:
        db.close()
        raise


def run_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """Dispatcher único — usado pelo server FastMCP e pelos testes."""
    try:
        assert_read_only_tool(name)
    except McpAuthError as exc:
        return {"error": str(exc), "error_code": "forbidden_tool"}

    args = dict(arguments or {})
    token = args.pop("token", None)
    if name not in TOOL_NAMES:
        return {"error": f"Tool desconhecida: {name}", "error_code": "unknown_tool"}

    handlers = {
        "municipio_overview": municipio_overview,
        "layers_catalog_summary": layers_catalog_summary,
        "diagnostic_latest": diagnostic_latest,
        "monitoring_snapshot": monitoring_snapshot,
        "flood_model_status": flood_model_status,
        "catalog_gaps": catalog_gaps,
        "live_alert": live_alert,
    }
    try:
        return json_safe(handlers[name](token=token, **args))
    except McpAuthError as exc:
        return {"error": str(exc), "error_code": "auth_error"}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "error_code": "tool_error"}


def municipio_overview(*, codigo_ibge: str, token: str | None = None) -> dict[str, Any]:
    """Painel de risco unificado + perfil básico do município."""
    from app.services.risk_traffic_light_service import build_risk_panel

    db, user, muni = _with_access(codigo_ibge, token=token)
    try:
        panel = build_risk_panel(db, muni.codigo_ibge)
        return {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
            "populacao": muni.populacao,
            "risk_panel": panel,
            "actor": user.username,
            "read_only": True,
            "protocol": "20c1_mcp_overview",
        }
    finally:
        db.close()


def layers_catalog_summary(*, codigo_ibge: str, token: str | None = None) -> dict[str, Any]:
    """Resumo de cobertura/catálogo (sem sync territorial pesado)."""
    from app.services.catalog_coverage import coverage_for_code

    db, user, muni = _with_access(codigo_ibge, token=token)
    try:
        coverage = coverage_for_code(muni.codigo_ibge, db)
        return {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
            "coverage": coverage,
            "actor": user.username,
            "read_only": True,
            "protocol": "20c1_mcp_layers",
        }
    finally:
        db.close()


def diagnostic_latest(*, codigo_ibge: str, token: str | None = None) -> dict[str, Any]:
    """Último diagnóstico executivo persistido (não gera novo)."""
    from app.services.executive_diagnostic_engine import diagnostic_to_dict

    db, user, muni = _with_access(codigo_ibge, token=token)
    try:
        record = (
            db.query(DiagnosticoExecutivo)
            .filter(DiagnosticoExecutivo.codigo_ibge == muni.codigo_ibge)
            .order_by(DiagnosticoExecutivo.gerado_em.desc())
            .first()
        )
        if not record:
            return {
                "codigo_ibge": muni.codigo_ibge,
                "disponivel": False,
                "mensagem": "Nenhum diagnóstico gerado ainda. Use a UI do Sinidu para gerar.",
                "actor": user.username,
                "read_only": True,
            }
        payload = diagnostic_to_dict(record)
        payload["disponivel"] = True
        payload["actor"] = user.username
        payload["read_only"] = True
        payload["protocol"] = "20c1_mcp_diagnostic"
        return payload
    finally:
        db.close()


def monitoring_snapshot(*, codigo_ibge: str, token: str | None = None) -> dict[str, Any]:
    """Snapshot do Monitor: clima cache + selo de previsão + alerta vivo."""
    from app.services.forecast_source_seal import seal_from_weather_payload
    from app.services.live_alert_level import live_alert_snapshot

    db, user, muni = _with_access(codigo_ibge, token=token)
    try:
        weather = (
            db.query(WeatherForecastCache)
            .filter(WeatherForecastCache.codigo_ibge == muni.codigo_ibge)
            .order_by(WeatherForecastCache.fetched_at.desc())
            .first()
        )
        live = live_alert_snapshot(db, muni.codigo_ibge, hours=24)
        seal = None
        if weather:
            seal = seal_from_weather_payload(
                weather.raw_payload if isinstance(weather.raw_payload, dict) else None,
                precip_24h_mm=float(weather.precip_24h_mm)
                if weather.precip_24h_mm is not None
                else None,
            )
        return {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
            "precip_24h_mm": float(weather.precip_24h_mm) if weather and weather.precip_24h_mm is not None else None,
            "precip_72h_mm": float(weather.precip_72h_mm) if weather and weather.precip_72h_mm is not None else None,
            "risk_probability": float(weather.risk_probability)
            if weather and weather.risk_probability is not None
            else None,
            "selo_previsao": seal,
            "alerta_vivo": live,
            "weather_updated_at": weather.fetched_at.isoformat() if weather and weather.fetched_at else None,
            "actor": user.username,
            "read_only": True,
            "protocol": "20c1_mcp_monitoring",
        }
    finally:
        db.close()


def flood_model_status(
    *,
    codigo_ibge: str | None = None,
    token: str | None = None,
) -> dict[str, Any]:
    """Status dos modelos ML (piloto ou todos os alvos). Não treina/bootstrap."""
    from ml.constants import ML_TARGET_IBGE_CODES
    from ml.model_policy import load_model_meta, public_auc
    from ml.paths import model_path

    user = resolve_mcp_user(token=token)
    db = _session()
    try:
        codes = list(ML_TARGET_IBGE_CODES)
        if codigo_ibge:
            code = normalize_ibge(codigo_ibge)
            assert_codigo_ibge_access(db, code, user=user)
            codes = [code]

        models = []
        for codigo in codes:
            p = model_path(codigo)
            meta = load_model_meta(codigo) if p.exists() else {}
            kind = meta.get("model_kind") if meta else None
            if p.exists() and not kind:
                kind = "full"
            spatial = (
                meta.get("spatial_validation")
                or (meta.get("validation") or {}).get("spatial")
                or {}
            )
            models.append(
                {
                    "codigo_ibge": codigo,
                    "ready": p.exists(),
                    "production_ready": kind == "full",
                    "model_kind": kind,
                    "auc_roc_cv": public_auc(meta) if meta else None,
                    "spatial_hit_rate": spatial.get("hit_rate"),
                }
            )
        return {
            "ready_count": sum(1 for m in models if m["ready"]),
            "production_ready_count": sum(1 for m in models if m["production_ready"]),
            "total": len(models),
            "models": models,
            "note": (
                "Monitor operacional só usa model_kind=full. "
                "MCP não executa bootstrap/treino."
            ),
            "actor": user.username,
            "read_only": True,
            "protocol": "20c1_mcp_flood_status",
        }
    finally:
        db.close()


def catalog_gaps(*, codigo_ibge: str, token: str | None = None) -> dict[str, Any]:
    """Maturidade informacional + lacunas do catálogo."""
    from app.services.maturity_engine import compute_maturity

    db, user, muni = _with_access(codigo_ibge, token=token)
    try:
        maturity = compute_maturity(db, muni.codigo_ibge)
        return {
            "codigo_ibge": muni.codigo_ibge,
            "nome": muni.nome,
            "uf": muni.uf,
            "maturity": maturity,
            "actor": user.username,
            "read_only": True,
            "protocol": "20c1_mcp_catalog_gaps",
        }
    finally:
        db.close()


def live_alert(*, codigo_ibge: str, token: str | None = None) -> dict[str, Any]:
    """Nível de alerta vivo 24h (CEMADEN/monitoramento) — honestidade VERDE."""
    from app.services.live_alert_level import live_alert_snapshot

    db, user, muni = _with_access(codigo_ibge, token=token)
    try:
        snap = live_alert_snapshot(db, muni.codigo_ibge, hours=24)
        snap["actor"] = user.username
        snap["read_only"] = True
        snap["protocol"] = "20c1_mcp_live_alert"
        return snap
    finally:
        db.close()


def tool_result_text(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)
