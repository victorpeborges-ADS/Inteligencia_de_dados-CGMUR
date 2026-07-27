"""Inicialização resiliente do banco e jobs em background."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.db import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.seed_demo_municipalities import ensure_demo_municipalities

logger = logging.getLogger(__name__)

MIGRATIONS = (
    "003_rag_pgvector.sql",
    "004_municipios_expansion.sql",
    "005_contingency_monitoring.sql",
    "006_onboarding_engine.sql",
    "007_diagnosticos_executivos.sql",
    "008_planos_acao_municipais.sql",
    "009_municipios_saneamento.sql",
    "010_audit_log_sei.sql",
    "011_mapbiomas_stats.sql",
    "012_fontes_externas.sql",
    "013_rag_mistral_embeddings.sql",
    "014_municipio_data_honesty.sql",
    "015_diagnostic_narrativa_ia.sql",
    "016_casos_sucesso_semantic.sql",
    "017_singedlab_rs.sql",
    "018_pib_serie.sql",
    "019_censo_deficits.sql",
    "020_educacao_inep.sql",
    "021_territorios_especiais.sql",
    "022_municipio_geoportal.sql",
    "023_contingency_operacional.sql",
    "024_previsao_verificacao_archive.sql",
    "025_pluvio_eventos_observados.sql",
)


@dataclass
class BootStatus:
    db_extensions: bool = False
    migrations_applied: list[str] = field(default_factory=list)
    migrations_failed: list[str] = field(default_factory=list)
    seed_ok: bool = False
    tables_ok: bool = False
    demo_municipalities_ok: bool = False
    integration_scheduler: bool = False
    integration_bootstrap_started: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def db_ready(self) -> bool:
        return self.db_extensions and self.tables_ok

    def to_dict(self) -> dict:
        return {
            "db_ready": self.db_ready,
            "db_extensions": self.db_extensions,
            "migrations_applied": self.migrations_applied,
            "migrations_failed": self.migrations_failed,
            "seed_ok": self.seed_ok,
            "tables_ok": self.tables_ok,
            "demo_municipalities_ok": self.demo_municipalities_ok,
            "integration_scheduler": self.integration_scheduler,
            "integration_bootstrap_started": self.integration_bootstrap_started,
            "errors": self.errors,
        }


boot_status = BootStatus()

_DEFAULT_JWT_SECRET = "sinidu-dev-secret-trocar-em-producao"
_DEFAULT_PASSWORDS = frozenset({"admin", "gestor", "leitor"})


def validate_auth_secrets_for_environment() -> None:
    """Avisa (e em production+auth falha) se secret/senhas forem fracos (20a.2)."""
    import os

    env = (os.getenv("ENVIRONMENT") or "development").strip().lower()
    secret = settings.AUTH_JWT_SECRET or ""
    weak_secret = secret == _DEFAULT_JWT_SECRET or len(secret) < 32
    default_pw = any(
        (getattr(settings, name, "") or "") in _DEFAULT_PASSWORDS
        for name in ("AUTH_ADMIN_PASSWORD", "AUTH_GESTOR_PASSWORD", "AUTH_LEITOR_PASSWORD")
    )
    cors = settings.CORS_ORIGINS or []
    cors_star = "*" in cors

    if weak_secret:
        msg = "AUTH_JWT_SECRET default/curto — defina secret >=32 chars"
        logger.warning(msg)
        if msg not in boot_status.errors:
            boot_status.errors.append(msg)
        if env == "production" and settings.AUTH_ENABLED:
            raise RuntimeError(msg)
        if settings.AUTH_ENABLED and env != "production":
            logger.warning("AUTH_ENABLED=true com JWT fraco — inseguro em Dev Tunnel / LAN")

    if default_pw:
        msg = "Senha default (admin/gestor/leitor) — troque AUTH_*_PASSWORD"
        logger.warning(msg)
        if msg not in boot_status.errors:
            boot_status.errors.append(msg)
        if env == "production" and settings.AUTH_ENABLED:
            raise RuntimeError(msg)

    if cors_star:
        msg = "CORS_ORIGINS contém '*' — restrinja em homolog/produção"
        logger.warning(msg)
        if msg not in boot_status.errors:
            boot_status.errors.append(msg)
        if env == "production":
            raise RuntimeError(msg)

    if env == "production" and not settings.AUTH_ENABLED:
        msg = "ENVIRONMENT=production com AUTH_ENABLED=false — superfície pública aberta"
        logger.warning(msg)
        if msg not in boot_status.errors:
            boot_status.errors.append(msg)


def _run_sql_file(path: Path, label: str) -> bool:
    if not path.exists():
        return True
    logger.info("Aplicando %s...", label)
    try:
        with engine.connect() as conn:
            for stmt in path.read_text(encoding="utf-8").split(";"):
                cleaned = stmt.strip()
                if cleaned:
                    conn.execute(text(cleaned))
            conn.commit()
        logger.info("%s concluída.", label)
        return True
    except Exception as exc:
        logger.warning("%s falhou (continuando boot): %s", label, exc)
        boot_status.errors.append(f"{label}: {exc}")
        return False


def initialize_database() -> None:
    """Best-effort: falhas individuais não impedem a API de subir."""
    try:
        validate_auth_secrets_for_environment()
    except RuntimeError:
        raise
    except Exception as exc:
        boot_status.errors.append(f"auth_secrets: {exc}")

    migrations_dir = Path(__file__).resolve().parent.parent / "migrations"

    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        boot_status.db_extensions = True
    except Exception as exc:
        boot_status.errors.append(f"extensões: {exc}")
        logger.error("Falha ao habilitar extensões PostGIS/pgvector: %s", exc)
        return

    for filename in MIGRATIONS:
        ok = _run_sql_file(migrations_dir / filename, f"migration {filename}")
        if ok:
            boot_status.migrations_applied.append(filename)
        else:
            boot_status.migrations_failed.append(filename)

    seed_sql = Path(__file__).resolve().parent.parent / "seeds" / "municipios_seed_50.sql"
    if seed_sql.exists():
        try:
            raw = seed_sql.read_text(encoding="utf-8")
            # Remove comentários de linha e executa statement a statement (DELETE + INSERT)
            lines = []
            for line in raw.splitlines():
                stripped = line.strip()
                if stripped.startswith("--"):
                    continue
                lines.append(line)
            cleaned = "\n".join(lines)
            statements = [s.strip() for s in cleaned.split(";") if s.strip()]
            with engine.connect() as conn:
                for stmt in statements:
                    conn.execute(text(stmt))
                conn.commit()
            boot_status.seed_ok = True
            logger.info("Seed catálogo piloto (6 municípios) aplicado.")
        except Exception as exc:
            boot_status.errors.append(f"seed: {exc}")
            logger.warning("Seed municípios falhou (continuando boot): %s", exc)

    try:
        Base.metadata.create_all(bind=engine)
        boot_status.tables_ok = True
    except Exception as exc:
        boot_status.errors.append(f"create_all: {exc}")
        logger.error("Falha ao criar tabelas: %s", exc)
        return

    db = SessionLocal()
    try:
        if settings.SEED_DEMO_MUNICIPALITIES:
            ensure_demo_municipalities(db)
            boot_status.demo_municipalities_ok = True
        else:
            boot_status.demo_municipalities_ok = True
            logger.info(
                "Seed demo sintético desligado (SEED_DEMO_MUNICIPALITIES=false); "
                "prioridade de boot: %s",
                settings.BOOT_PRIORITY_IBGE_CODES,
            )
        from app.services.casos_sucesso_service import seed_casos_sucesso

        seed_casos_sucesso(db, force=False, embed=True)
    except Exception as exc:
        boot_status.errors.append(f"demo_municipalities: {exc}")
        logger.warning("Demo municipalities / casos seed falhou: %s", exc)
    finally:
        db.close()

    logger.info("Boot DB concluído (db_ready=%s).", boot_status.db_ready)


def _ensure_boot_priority_municipalities() -> None:
    """Garante malha territorial mínima dos municípios prioritários (Recife, Aracaju)."""
    from app.services.municipio_loader import ensure_municipality_loaded

    db = SessionLocal()
    try:
        for codigo in settings.BOOT_PRIORITY_IBGE_CODES:
            try:
                result = ensure_municipality_loaded(db, codigo)
                logger.info(
                    "Município prioritário pronto: %s (%s) loaded=%s",
                    result.get("nome") or codigo,
                    codigo,
                    result.get("loaded"),
                )
            except Exception as exc:
                logger.warning("Falha ao garantir município prioritário %s: %s", codigo, exc)
                boot_status.errors.append(f"boot_priority_{codigo}: {exc}")
    finally:
        db.close()


def _bootstrap_integrations() -> None:
    from app.data_connectors.orchestrator import IntegrationOrchestrator

    priority = settings.BOOT_PRIORITY_IBGE_CODES
    db = SessionLocal()
    try:
        summary = IntegrationOrchestrator(db).sync_all(codigos=priority)
        logger.info("Integração inicial (prioridade %s): %s", priority, summary)
    except Exception as exc:
        logger.warning("Integração inicial indisponível no boot: %s", exc)
        boot_status.errors.append(f"integration_bootstrap: {exc}")
    finally:
        db.close()


def _bootstrap_flood_models() -> None:
    from ml.bootstrap import ensure_flood_models

    db = SessionLocal()
    try:
        ensure_flood_models(db)
    except Exception as exc:
        logger.warning("Bootstrap ML alagamento falhou: %s", exc)
        boot_status.errors.append(f"ml_bootstrap: {exc}")
    finally:
        db.close()


def _run_boot_background_pipeline() -> None:
    """Malha prioritária primeiro; integrações/monitoramento depois, com atraso para não saturar o pool no boot."""
    import time

    # Deixa a API atender o mapa/painel antes do sync externo.
    time.sleep(8)
    _ensure_boot_priority_municipalities()
    if settings.DEM_PREWARM_ENABLED:
        _prewarm_priority_dem()
    if settings.SIMULATION_PREWARM_ENABLED:
        time.sleep(3)
        _prewarm_priority_simulations()
        _prewarm_priority_agent_bundles()
    # Sync de indicadores públicos pode esperar o scheduler semanal — no boot só malha.
    # Mantém monitoramento leve dos prioritários.
    time.sleep(2)
    _bootstrap_monitoring()
    _bootstrap_flood_models()


def _prewarm_priority_dem() -> None:
    from app.services.dem_prewarm import prewarm_boot_priority_dem

    try:
        outcomes = prewarm_boot_priority_dem()
        logger.info(
            "Pré-aquecimento DEM concluído para %s: %s",
            settings.BOOT_PRIORITY_IBGE_CODES,
            outcomes,
        )
    except Exception as exc:
        logger.warning("Pré-aquecimento DEM falhou: %s", exc)
        boot_status.errors.append(f"dem_prewarm: {exc}")


def _prewarm_priority_simulations() -> None:
    from app.services.simulation_prewarm import prewarm_boot_priority_municipalities

    try:
        prewarm_boot_priority_municipalities()
        logger.info(
            "Pré-aquecimento de simulação pluvial agendado para %s",
            settings.BOOT_PRIORITY_IBGE_CODES,
        )
    except Exception as exc:
        logger.warning("Pré-aquecimento de simulação falhou: %s", exc)
        boot_status.errors.append(f"simulation_prewarm: {exc}")


def _prewarm_priority_agent_bundles() -> None:
    from app.services.contextual_agent_prewarm import prewarm_boot_priority_agent_bundles

    try:
        prewarm_boot_priority_agent_bundles()
        logger.info(
            "Pré-aquecimento do agente contextual agendado para %s",
            settings.BOOT_PRIORITY_IBGE_CODES,
        )
    except Exception as exc:
        logger.warning("Pré-aquecimento do agente falhou: %s", exc)
        boot_status.errors.append(f"agent_prewarm: {exc}")


def start_background_jobs() -> None:
    """Scheduler e sync inicial em threads — não bloqueiam o Uvicorn."""
    try:
        from app.services.background_jobs import recover_stale_jobs

        recover_stale_jobs()
    except Exception as exc:
        logger.warning("Recuperação de jobs expirados falhou: %s", exc)

    try:
        from app.data_connectors.scheduler import start_integration_scheduler

        start_integration_scheduler()
        boot_status.integration_scheduler = True
    except Exception as exc:
        boot_status.errors.append(f"scheduler: {exc}")
        logger.warning("Scheduler de integrações não iniciado: %s", exc)

    try:
        threading.Thread(
            target=_run_boot_background_pipeline,
            daemon=True,
            name="boot-background-pipeline",
        ).start()
        boot_status.integration_bootstrap_started = True
    except Exception as exc:
        boot_status.errors.append(f"boot_pipeline_thread: {exc}")
        logger.warning("Pipeline de boot em background não iniciado: %s", exc)


def _bootstrap_monitoring() -> None:
    """Sync inicial OpenMeteo + CEMADEN — só municípios prioritários de boot."""
    from app.services.monitoring_sync import sync_monitoring_all_sync

    priority = settings.BOOT_PRIORITY_IBGE_CODES
    db = SessionLocal()
    try:
        summary = sync_monitoring_all_sync(db, codigos=priority)
        logger.info("Monitoramento prioritário (%s): %s", priority, summary)
    except Exception as exc:
        logger.warning("Bootstrap monitoramento indisponível: %s", exc)
        boot_status.errors.append(f"monitoring_bootstrap: {exc}")
    finally:
        db.close()
