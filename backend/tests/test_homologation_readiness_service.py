"""Testes do checklist de homologação MCID."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.homologation_readiness_service import build_homologation_readiness

_INFRA_OK = {
    "osrm_meta": {"available": True, "region": "pe-se", "detail": "Ok"},
    "backup_meta": {"status": "ok", "detail": "sinidu_postgis_x.sql.gz · 2h"},
    "gotify_meta": {"configured": True, "reachable": True, "detail": "ok"},
    "ml_meta": {"ready_count": 10, "total": 10},
    "redis_meta": {"ok": True, "detail": "ping ok"},
    "scheduler_meta": {"running": True, "jobs": [{"id": "postgis_backup"}]},
}


def test_homologation_readiness_dev_mode(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "MULTI_TENANT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "OIDC_ENABLED", False)
    monkeypatch.setattr(config_module.settings, "AUTH_PASSWORD_LOGIN_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_JWT_SECRET", "x" * 40)
    monkeypatch.setattr(config_module.settings, "BOOT_PRIORITY_IBGE_CODES", ["2611606", "2800308"])

    db = MagicMock()
    with patch("app.services.dem_processor.is_processed", return_value=True):
        out = build_homologation_readiness(
            db,
            batch_coverage={
                "municipios_total": 62,
                "com_diagnostico": 62,
                "com_relatorio": 62,
                "diagnosticos_ok": True,
                "relatorios_ok": True,
            },
            ctm_summary={
                "total_alvo": 24,
                "importado_prefeitura": 8,
                "malha_operacional": 16,
                "lacuna_municipios": 0,
                "progress_label": "24/24 malha operacional (8 oficial)",
            },
            dem_summary={"boot_processed": 2, "boot_total": 2},
            **_INFRA_OK,
        )

    assert out["score_pct"] >= 70
    assert out["ready_for_demo"] is True
    assert out["ready_for_sso_test"] is False
    assert out["govbr_required"] is False
    assert any(i["id"] == "password_login_off" and i["status"] == "na" for i in out["items"])
    assert any(i["id"] == "ctm_malha" and i["status"] == "na" for i in out["items"])
    assert any(i["id"] == "jwt_secret" and i["status"] == "ok" for i in out["items"])
    assert any(i["id"] == "redis_cache" and i["status"] == "ok" for i in out["items"])
    assert any(i["id"] == "scheduler_running" and i["status"] == "ok" for i in out["items"])
    assert any(i["id"] == "ml_flood_models" and i["status"] == "ok" for i in out["items"])


def test_homologation_ready_for_sso_when_oidc_ok(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "MULTI_TENANT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "OIDC_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_PASSWORD_LOGIN_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_JWT_SECRET", "y" * 40)
    monkeypatch.setattr(config_module.settings, "OIDC_ISSUER_URL", "https://idp.example/realms/mcid")
    monkeypatch.setattr(config_module.settings, "OIDC_CLIENT_ID", "sinidu")
    monkeypatch.setattr(config_module.settings, "OIDC_REDIRECT_URI", "https://localhost/callback")
    monkeypatch.setattr(config_module.settings, "BOOT_PRIORITY_IBGE_CODES", ["2611606"])

    db = MagicMock()
    with patch("app.services.dem_processor.is_processed", return_value=True):
        out = build_homologation_readiness(
            db,
            oidc_meta={"configured": True, "reachable": True, "detail": "ok"},
            tls_meta={"status": "ok", "days_until_expiry": 90},
            batch_coverage={
                "municipios_total": 62,
                "com_diagnostico": 62,
                "com_relatorio": 62,
                "diagnosticos_ok": True,
                "relatorios_ok": True,
            },
            ctm_summary={
                "total_alvo": 24,
                "importado_prefeitura": 8,
                "malha_operacional": 16,
                "lacuna_municipios": 0,
                "progress_label": "24/24",
            },
            dem_summary={"boot_processed": 1, "boot_total": 1, "processados": 40, "prioritarios": 61},
            **_INFRA_OK,
        )

    assert out["ready_for_sso_test"] is True
    assert out["ready_for_demo"] is True
    assert out["ready_for_production"] is False  # senha ainda ligada
    assert out["score_pct"] >= 70
    dem = next(i for i in out["items"] if i["id"] == "dem_boot")
    assert "boot" in dem["detail"]


def test_homologation_ready_for_production(monkeypatch):
    import app.config as config_module

    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "MULTI_TENANT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "OIDC_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_PASSWORD_LOGIN_ENABLED", False)
    monkeypatch.setattr(config_module.settings, "AUTH_JWT_SECRET", "z" * 40)
    monkeypatch.setattr(config_module.settings, "OIDC_ISSUER_URL", "https://idp.example/realms/mcid")
    monkeypatch.setattr(config_module.settings, "OIDC_CLIENT_ID", "sinidu")
    monkeypatch.setattr(config_module.settings, "OIDC_REDIRECT_URI", "https://localhost/callback")
    monkeypatch.setattr(config_module.settings, "SIMULATION_PREWARM_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "DEM_PREWARM_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "BOOT_PRIORITY_IBGE_CODES", ["2611606"])

    db = MagicMock()
    with patch("app.services.homologation_readiness_service.boot_status") as boot_mock:
        boot_mock.errors = []
        out = build_homologation_readiness(
            db,
            oidc_meta={"configured": True, "reachable": True, "detail": "ok"},
            tls_meta={"status": "ok", "days_until_expiry": 90},
            batch_coverage={
                "municipios_total": 62,
                "com_diagnostico": 62,
                "com_relatorio": 62,
                "diagnosticos_ok": True,
                "relatorios_ok": True,
            },
            ctm_summary={
                "total_alvo": 24,
                "importado_prefeitura": 8,
                "malha_operacional": 16,
                "lacuna_municipios": 0,
                "progress_label": "24/24",
            },
            dem_summary={"boot_processed": 1, "boot_total": 1},
            osrm_meta={"available": False, "detail": "down", "setup_hint": "setup"},
            backup_meta={"status": "stale", "detail": "dump 72h"},
            gotify_meta={"configured": False, "reachable": False, "detail": "sem token"},
            ml_meta={"ready_count": 10, "total": 10},
            redis_meta={"ok": True, "detail": "ping"},
            scheduler_meta={"running": True, "jobs": [{"id": "cemaden"}]},
        )

    assert out["ready_for_sso_test"] is True
    # CTM fora do score do protótipo (na), mas ready_for_production ainda exige ctm_ok
    assert out["ready_for_production"] is True
    assert any(i["id"] == "password_login_off" and i["status"] == "ok" for i in out["items"])
    steps = " ".join(out["next_steps"])
    assert "OSRM" in steps or "backup" in steps.lower() or "GOTIFY" in steps


def test_jwt_secret_fail_in_prod_like(monkeypatch):
    import app.config as config_module

    monkeypatch.setenv("ENVIRONMENT", "homolog")
    monkeypatch.setattr(config_module.settings, "AUTH_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "MULTI_TENANT_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "OIDC_ENABLED", False)
    monkeypatch.setattr(config_module.settings, "AUTH_PASSWORD_LOGIN_ENABLED", True)
    monkeypatch.setattr(config_module.settings, "AUTH_JWT_SECRET", "sinidu-dev-secret-trocar-em-producao")
    monkeypatch.setattr(config_module.settings, "BOOT_PRIORITY_IBGE_CODES", ["2611606"])

    db = MagicMock()
    with patch("app.services.dem_processor.is_processed", return_value=True):
        out = build_homologation_readiness(
            db,
            batch_coverage={
                "municipios_total": 1,
                "com_diagnostico": 1,
                "com_relatorio": 1,
                "diagnosticos_ok": True,
                "relatorios_ok": True,
            },
            ctm_summary={"total_alvo": 24, "importado_prefeitura": 0, "malha_operacional": 0, "lacuna_municipios": 1, "progress_label": "0/24"},
            dem_summary={"boot_processed": 1, "boot_total": 1},
            **_INFRA_OK,
        )

    assert any(i["id"] == "jwt_secret" and i["status"] == "fail" for i in out["items"])
    assert out["ready_for_demo"] is False


def test_latest_backup_status(tmp_path):
    from app.services.postgis_backup import latest_backup_status

    empty = latest_backup_status(backup_dir=str(tmp_path))
    assert empty["status"] == "missing"

    dump = tmp_path / "sinidu_postgis_20260720_120000.sql.gz"
    dump.write_bytes(b"\x1f\x8b")
    fresh = latest_backup_status(backup_dir=str(tmp_path), max_age_hours=48)
    assert fresh["status"] == "ok"
    assert fresh["available"] is True
