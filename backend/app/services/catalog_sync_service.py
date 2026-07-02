"""Sincronização e preview por fonte do catálogo — Step 5."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.services.catalog_coverage import coverage_for_code
from app.data_connectors.external_sources_collector import sync_external_sources_batch
from app.data_connectors.mapbiomas_collector import collect_mapbiomas_municipality
from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.data_connectors.s2id_collector import collect_s2id_municipality
from app.models import (
    AlertaCemaden,
    HistoricoDesastreS2ID,
    IntegrationRun,
    MapBiomasMunicipalStat,
    Municipio,
    MunicipioFonteExterna,
    MunicipioIbge,
    MunicipioSaneamento,
    MunicipioSeed,
)
from app.services.catalog_source_registry import FONTE_REGISTRY
from app.services.cemaden_monitor import sync_cemaden_alerts

logger = logging.getLogger(__name__)

EXTERNAL_FONTES = {"adapta_brasil", "geosgb", "sirene", "brasil_mais"}


def _last_integration(db: Session, source_key: str) -> datetime | None:
    row = (
        db.query(IntegrationRun)
        .filter(IntegrationRun.source == source_key, IntegrationRun.status == "OK")
        .order_by(IntegrationRun.last_success_at.desc())
        .first()
    )
    return row.last_success_at if row and row.last_success_at else None


def get_source_sync_meta(db: Session, codigo_ibge: str, fonte_id: str) -> dict[str, Any]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    meta = FONTE_REGISTRY.get(fonte_id, {})
    records = 0
    ultima_sync = None

    if fonte_id == "ibge_cidades":
        row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
        records = 1 if row and row.populacao else 0
        ultima_sync = row.atualizado_em if row else None
    elif fonte_id == "snis_sinisa":
        row = db.query(MunicipioSaneamento).filter(MunicipioSaneamento.codigo_ibge == codigo_ibge).first()
        records = 1 if row else 0
        ultima_sync = row.atualizado_em if row else None
    elif fonte_id == "s2id" and muni:
        records = db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == muni.id).count()
        ultima_sync = _last_integration(db, "s2id")
    elif fonte_id == "mapbiomas":
        records = db.query(MapBiomasMunicipalStat).filter(MapBiomasMunicipalStat.codigo_ibge == codigo_ibge).count()
        ultima_sync = _last_integration(db, "mapbiomas")
    elif fonte_id == "cemaden_georiscos" and muni:
        records = db.query(AlertaCemaden).filter(AlertaCemaden.municipio_id == muni.id).count()
        ultima_sync = _last_integration(db, "cemaden")
    elif fonte_id in EXTERNAL_FONTES:
        ext = db.query(MunicipioFonteExterna).filter(MunicipioFonteExterna.codigo_ibge == codigo_ibge).first()
        ultima_sync = ext.updated_at if ext else None
        records = 1 if ext else 0
    else:
        seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first()
        if seed and seed.integration_steps:
            step = seed.integration_steps.get(fonte_id)
            if isinstance(step, dict):
                ultima_sync = step.get("atualizado_em")
                records = step.get("registros", 0)

    if ultima_sync and isinstance(ultima_sync, str):
        try:
            ultima_sync = datetime.fromisoformat(ultima_sync.replace("Z", "+00:00"))
        except ValueError:
            ultima_sync = None

    return {
        "fonte_id": fonte_id,
        "ultima_sync": ultima_sync.isoformat() if isinstance(ultima_sync, datetime) else None,
        "registros": records,
        "requisito": meta.get("requisito"),
        "integravel_etl": meta.get("integravel_etl", False),
    }


def get_source_preview(db: Session, codigo_ibge: str, fonte_id: str, limit: int = 5) -> list[dict[str, Any]]:
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    rows: list[dict[str, Any]] = []

    if fonte_id == "s2id" and muni:
        events = (
            db.query(HistoricoDesastreS2ID)
            .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
            .order_by(HistoricoDesastreS2ID.data_ocorrencia.desc())
            .limit(limit)
            .all()
        )
        for ev in events:
            rows.append({
                "tipo": ev.tipo_desastre,
                "data": ev.data_ocorrencia.strftime("%d/%m/%Y") if ev.data_ocorrencia else "—",
                "afetados": ev.populacao_afetada,
                "danos": float(ev.danos_materiais or 0),
            })
    elif fonte_id == "mapbiomas":
        stats = (
            db.query(MapBiomasMunicipalStat)
            .filter(MapBiomasMunicipalStat.codigo_ibge == codigo_ibge)
            .order_by(MapBiomasMunicipalStat.ano.desc())
            .limit(limit)
            .all()
        )
        for st in stats:
            rows.append({
                "ano": st.ano,
                "vegetacao_pct": float(st.vegetacao_pct or 0),
                "urbano_pct": float(st.urbano_pct or 0),
                "qualidade": st.data_quality,
            })
    elif fonte_id == "cemaden_georiscos" and muni:
        alertas = (
            db.query(AlertaCemaden)
            .filter(AlertaCemaden.municipio_id == muni.id)
            .order_by(AlertaCemaden.data_alerta.desc())
            .limit(limit)
            .all()
        )
        for a in alertas:
            rows.append({
                "nivel": a.nivel_alerta,
                "data": a.data_alerta.strftime("%d/%m/%Y %H:%M") if a.data_alerta else "—",
                "descricao": (a.descricao or "")[:120],
            })
    elif fonte_id == "ibge_cidades":
        row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
        if row:
            rows.append({
                "populacao": row.populacao,
                "area_km2": float(row.area_km2 or 0),
                "idh": float(row.idh) if row.idh else None,
                "pib_per_capita": float(row.pib_per_capita) if row.pib_per_capita else None,
            })
    elif fonte_id == "snis_sinisa":
        row = db.query(MunicipioSaneamento).filter(MunicipioSaneamento.codigo_ibge == codigo_ibge).first()
        if row:
            rows.append({
                "cobertura_agua_pct": float(row.cobertura_agua_pct or 0) if row.cobertura_agua_pct else None,
                "cobertura_esgoto_pct": float(row.cobertura_esgoto_pct or 0) if row.cobertura_esgoto_pct else None,
                "indice_atendimento_esgoto_pct": float(row.indice_atendimento_esgoto_pct or 0) if row.indice_atendimento_esgoto_pct else None,
                "qualidade": row.data_quality,
            })
    elif fonte_id in EXTERNAL_FONTES:
        ext = db.query(MunicipioFonteExterna).filter(MunicipioFonteExterna.codigo_ibge == codigo_ibge).first()
        if ext:
            rows.append({
                "adapta_score": float(ext.adapta_score) if ext.adapta_score else None,
                "geosgb_score": float(ext.geosgb_score) if ext.geosgb_score else None,
                "sirene_tco2": float(ext.sirene_emissoes_tco2) if ext.sirene_emissoes_tco2 else None,
                "brasil_mais": float(ext.brasil_mais_indice) if ext.brasil_mais_indice else None,
                "sincronizado_em": ext.sincronizado_em.isoformat() if ext.sincronizado_em else None,
            })

    return rows


def refresh_catalog_source(db: Session, codigo_ibge: str, fonte_id: str, *, force: bool = False) -> dict[str, Any]:
    orch = IntegrationOrchestrator(db)
    result: dict[str, Any] = {"fonte_id": fonte_id, "codigo_ibge": codigo_ibge, "ok": False}

    try:
        if fonte_id == "ibge_cidades":
            result["ok"] = orch._sync_ibge(codigo_ibge)
        elif fonte_id == "snis_sinisa":
            result["ok"] = orch._sync_snis(codigo_ibge)
        elif fonte_id == "s2id":
            result.update(collect_s2id_municipality(db, codigo_ibge, force=force))
            result["ok"] = not result.get("skipped", False) or result.get("records", 0) > 0
        elif fonte_id == "mapbiomas":
            result.update(collect_mapbiomas_municipality(db, codigo_ibge, force=force))
            result["ok"] = "error" not in result
        elif fonte_id == "cemaden_georiscos":
            sync_cemaden_alerts(db)
            result["ok"] = True
        elif fonte_id in EXTERNAL_FONTES:
            ext = sync_external_sources_batch(db, [codigo_ibge])
            result["ok"] = ext.get("processed", 0) >= 1
            result["detail"] = ext
        else:
            result["reason"] = "Fonte sem ETL automático — requer ação institucional."
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.exception("Refresh fonte %s falhou", fonte_id)
        result["error"] = str(exc)

    result["meta"] = get_source_sync_meta(db, codigo_ibge, fonte_id)
    return result


def refresh_integrated_sources(
    db: Session,
    codigo_ibge: str,
    *,
    job_id: str | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    _, bases, _ = coverage_for_code(codigo_ibge, db)
    integradas = [
        b for b in bases
        if b["status"] == "Integrado" and FONTE_REGISTRY.get(b["id"], {}).get("integravel_etl", True)
    ]

    results: list[dict[str, Any]] = []
    total = len(integradas)

    for idx, base in enumerate(integradas):
        fonte_id = base["id"]
        entry = {"fonte_id": fonte_id, "nome": base["nome"], "status": "running"}
        if progress_callback:
            progress_callback({
                "progress": int((idx / max(total, 1)) * 100),
                "current": fonte_id,
                "sources": results + [entry],
                "done": idx,
                "total": total,
            })
        res = refresh_catalog_source(db, codigo_ibge, fonte_id, force=True)
        entry["status"] = "ok" if res.get("ok") else "failed"
        entry["detail"] = res.get("error") or res.get("reason") or "OK"
        results.append(entry)

    if progress_callback:
        progress_callback({"progress": 100, "sources": results, "done": total, "total": total})

    return {"codigo_ibge": codigo_ibge, "total": total, "sources": results, "job_id": job_id}
