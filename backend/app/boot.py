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
            with engine.connect() as conn:
                conn.execute(text(seed_sql.read_text(encoding="utf-8")))
                conn.commit()
            boot_status.seed_ok = True
            logger.info("Seed 61 municípios prioritários aplicado.")
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
        ensure_demo_municipalities(db)
        boot_status.demo_municipalities_ok = True
    except Exception as exc:
        boot_status.errors.append(f"demo_municipalities: {exc}")
        logger.warning("Demo municipalities falhou: %s", exc)
    finally:
        db.close()

    logger.info("Boot DB concluído (db_ready=%s).", boot_status.db_ready)


def _bootstrap_integrations() -> None:
    from app.data_connectors.orchestrator import IntegrationOrchestrator

    db = SessionLocal()
    try:
        summary = IntegrationOrchestrator(db).sync_all()
        logger.info("Integração inicial concluída: %s", summary)
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


def start_background_jobs() -> None:
    """Scheduler e sync inicial em threads — não bloqueiam o Uvicorn."""
    try:
        from app.data_connectors.scheduler import start_integration_scheduler

        start_integration_scheduler()
        boot_status.integration_scheduler = True
    except Exception as exc:
        boot_status.errors.append(f"scheduler: {exc}")
        logger.warning("Scheduler de integrações não iniciado: %s", exc)

    try:
        threading.Thread(target=_bootstrap_integrations, daemon=True, name="integration-bootstrap").start()
        boot_status.integration_bootstrap_started = True
    except Exception as exc:
        boot_status.errors.append(f"integration_thread: {exc}")
        logger.warning("Thread de integração não iniciada: %s", exc)

    try:
        threading.Thread(target=_bootstrap_flood_models, daemon=True, name="ml-flood-bootstrap").start()
    except Exception as exc:
        boot_status.errors.append(f"ml_thread: {exc}")
        logger.warning("Thread ML alagamento não iniciada: %s", exc)

    try:
        threading.Thread(target=_bootstrap_monitoring, daemon=True, name="monitoring-bootstrap").start()
    except Exception as exc:
        boot_status.errors.append(f"monitoring_thread: {exc}")
        logger.warning("Thread monitoramento não iniciada: %s", exc)


def _bootstrap_monitoring() -> None:
    """Sync inicial OpenMeteo + CEMADEN — piloto primeiro, depois rede."""
    from app.services.monitoring_sync import sync_monitoring_all_sync

    db = SessionLocal()
    try:
        pilot = settings.PILOT_IBGE_CODE
        summary_pilot = sync_monitoring_all_sync(db, codigos=[pilot])
        logger.info("Monitoramento piloto (%s): %s", pilot, summary_pilot)
        summary_all = sync_monitoring_all_sync(db)
        logger.info("Monitoramento rede completa: %s", summary_all)
    except Exception as exc:
        logger.warning("Bootstrap monitoramento indisponível: %s", exc)
        boot_status.errors.append(f"monitoring_bootstrap: {exc}")
    finally:
        db.close()
