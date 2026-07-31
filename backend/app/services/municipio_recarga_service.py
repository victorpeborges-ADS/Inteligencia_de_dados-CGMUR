"""Pipeline sequencial de recarga com dados reais por município."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.s2id_collector import ensure_s2id_loaded
from app.data_connectors.sinesp_collector import ensure_sinesp_loaded
from app.data_connectors.inep_educacao_collector import sync_educacao_municipio
from app.data_connectors.territorios_especiais_collector import sync_territorios_municipio
from app.models import Municipio, MunicipioSeed
from app.services.cemaden_monitor import sync_cemaden_alerts
from app.services.malha_ibge_service import baixar_malha_bairros_ibge, enriquecer_socioeconomico_censo
from app.services.municipio_audit_service import audit_municipio
from app.services.municipio_loader import compute_initial_score
from app.services.recarga_progress_store import init_recarga, load_recarga_status, update_recarga

logger = logging.getLogger(__name__)

ETAPAS = ("malha_ibge", "socioeconomico_censo", "s2id", "cemaden", "seguranca_sinesp", "educacao_inep", "territorios_especiais")
_locks: dict[str, threading.Lock] = {}


def _get_lock(codigo_ibge: str) -> threading.Lock:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    if code not in _locks:
        _locks[code] = threading.Lock()
    return _locks[code]


def get_recarga_status(codigo_ibge: str) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    stored = load_recarga_status(code)
    if stored:
        return stored
    return {
        "codigo_ibge": code,
        "status": "idle",
        "progresso_pct": 0,
        "etapa_atual": None,
        "fontes": [],
        "etapas_concluidas": [],
    }


async def _run_etapa(
    db: Session,
    muni: Municipio,
    etapa: str,
) -> dict[str, Any]:
    if etapa == "malha_ibge":
        return await baixar_malha_bairros_ibge(muni.codigo_ibge, db)
    if etapa == "socioeconomico_censo":
        return await enriquecer_socioeconomico_censo(muni.codigo_ibge, db)
    if etapa == "s2id":
        result = ensure_s2id_loaded(db, muni)
        return result or {"codigo_ibge": muni.codigo_ibge, "skipped": True}
    if etapa == "cemaden":
        return sync_cemaden_alerts(db)
    if etapa == "seguranca_sinesp":
        result = ensure_sinesp_loaded(db, muni)
        return result or {"codigo_ibge": muni.codigo_ibge, "skipped": True}
    if etapa == "educacao_inep":
        return sync_educacao_municipio(db, muni)
    if etapa == "territorios_especiais":
        return sync_territorios_municipio(db, muni)
    raise ValueError(f"Etapa desconhecida: {etapa}")


async def executar_recarga(db: Session, codigo_ibge: str, fontes: list[str]) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        update_recarga(code, status="erro", erro="Município não encontrado.", progresso_pct=0)
        return {"error": "Município não encontrado."}

    ordered = [e for e in ETAPAS if e in fontes]
    if not ordered:
        ordered = list(ETAPAS)

    init_recarga(code, ordered)
    resultados: dict[str, Any] = {}
    total = len(ordered)

    for idx, etapa in enumerate(ordered):
        pct = int(100 * idx / total)
        update_recarga(
            code,
            status="em_andamento",
            etapa_atual=etapa,
            progresso_pct=pct,
        )
        try:
            resultados[etapa] = await _run_etapa(db, muni, etapa)
            status = load_recarga_status(code) or {}
            concluidas = list(status.get("etapas_concluidas") or [])
            concluidas.append(etapa)
            update_recarga(code, etapas_concluidas=concluidas, resultado=resultados)
        except Exception as exc:
            logger.exception("Recarga %s falhou na etapa %s", code, etapa)
            update_recarga(
                code,
                status="erro",
                etapa_atual=etapa,
                progresso_pct=pct,
                erro=str(exc),
                resultado=resultados,
            )
            return {"codigo_ibge": code, "error": str(exc), "etapa": etapa, "resultados": resultados}

    audit = audit_municipio(db, muni, persist=True)
    score = compute_initial_score(db, muni)
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    if seed:
        seed.score_sinidu = score
        seed.score_confiabilidade = audit.get("score_confiabilidade")
        db.commit()

    update_recarga(
        code,
        status="concluido",
        etapa_atual="finalizado",
        progresso_pct=100,
        resultado={**resultados, "auditoria": audit, "score_sinidu": score},
    )
    return {
        "codigo_ibge": code,
        "status": "concluido",
        "resultados": resultados,
        "auditoria": audit,
        "score_sinidu": score,
    }


def iniciar_recarga_background(db_factory, codigo_ibge: str, fontes: list[str]) -> dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]
    lock = _get_lock(code)
    if not lock.acquire(blocking=False):
        current = get_recarga_status(code)
        if current.get("status") == "em_andamento":
            return {"codigo_ibge": code, "status": "em_andamento", "message": "Recarga já em execução."}
        lock.acquire()

    init_recarga(code, fontes)

    def _runner() -> None:
        db = db_factory()
        try:
            asyncio.run(executar_recarga(db, code, fontes))
        except Exception as exc:
            logger.exception("Recarga background falhou %s", code)
            update_recarga(code, status="erro", erro=str(exc))
        finally:
            db.close()
            lock.release()

    threading.Thread(target=_runner, daemon=True, name=f"recarga-{code}").start()
    return {"codigo_ibge": code, "status": "em_andamento", "fontes": fontes}
