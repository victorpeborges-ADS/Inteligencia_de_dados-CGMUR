"""Motor de onboarding municipal — reutiliza municipio_loader e conectores existentes."""

from __future__ import annotations

from app.timeutil import utc_now
import logging
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.models import (
    HistoricoDesastreS2ID,
    Municipio,
    MunicipioFiscal,
    MunicipioIbge,
    MunicipioSeed,
)
from app.services.maturity_engine import persist_maturity
from app.services.municipio_loader import (
    compute_initial_score,
    fetch_ibge_geometry,
    load_municipio_from_seed,
    upsert_seed_rows,
)

logger = logging.getLogger(__name__)

IBGE_LOCALIDADES_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/{codigo}"

STEP_WEIGHTS = {
    "ibge_validacao": 5,
    "geometria": 20,
    "ibge_indicadores": 15,
    "siconfi": 15,
    "capag": 15,
    "camadas_territoriais": 20,
    "s2id": 10,
    "mapbiomas": 10,
}

ONBOARDING_TO_CARGA = {
    "concluido": "carregado",
    "parcial": "parcial",
    "falha": "parcial",
    "em_progresso": "parcial",
    "pendente": "pendente",
}


def _tier_from_score(score: float | None) -> str | None:
    if score is None:
        return None
    from app.services.maturity_engine import classify_tier
    return classify_tier(float(score))


def validate_ibge_code(codigo_ibge: str) -> dict[str, Any]:
    """Valida código IBGE via API oficial de localidades."""
    code = str(codigo_ibge).strip().zfill(7)[:7]
    if not code.isdigit() or len(code) != 7:
        raise ValueError("Código IBGE deve conter 7 dígitos numéricos.")

    try:
        resp = requests.get(IBGE_LOCALIDADES_URL.format(codigo=code), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise ValueError(f"IBGE não respondeu para o código {code}: {exc}") from exc

    if not data or not data.get("id"):
        raise ValueError(f"Município IBGE {code} não encontrado.")

    uf = (data.get("microrregiao") or {}).get("mesorregiao", {}).get("UF", {})
    return {
        "codigo_ibge": code,
        "nome": data.get("nome"),
        "uf": uf.get("sigla") or "—",
        "regiao": (uf.get("regiao") or {}).get("nome"),
        "valido": True,
    }


def ensure_seed_row(db: Session, codigo_ibge: str, nome: str, uf: str, criterio: str = "onboarding") -> MunicipioSeed:
    upsert_seed_rows(db)
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first()
    if seed:
        if criterio == "onboarding" and seed.criterio != "onboarding":
            pass
        else:
            seed.nome = nome or seed.nome
            seed.uf = uf or seed.uf
    else:
        seed = MunicipioSeed(
            codigo_ibge=codigo_ibge,
            nome=nome,
            uf=uf,
            criterio=criterio,
            decretos_emergencia=0,
            prioridade=999,
            status_carga="pendente",
            onboarding_status="pendente",
            lacunas=["geometria", "ibge", "siconfi", "capag", "s2id"],
        )
        db.add(seed)
    db.commit()
    db.refresh(seed)
    return seed


def _step(status: str, detail: str = "", quality: str = "oficial") -> dict[str, Any]:
    return {
        "status": status,
        "detail": detail,
        "quality": quality,
        "at": utc_now().isoformat(),
    }


def _completeness_from_steps(steps: dict[str, dict]) -> float:
    total = 0.0
    for key, weight in STEP_WEIGHTS.items():
        step = steps.get(key) or {}
        st = step.get("status")
        if st == "ok":
            total += weight
        elif st == "parcial":
            total += weight * 0.5
    return round(total, 2)


def _maturity_from_scores(completeness: float, sinidu_score: float | None) -> float:
    comp = completeness
    terr = float(sinidu_score or 0.0)
    return round(min(100.0, comp * 0.55 + terr * 0.45), 2)


def run_onboarding(db: Session, codigo_ibge: str, *, force: bool = False) -> dict[str, Any]:
    """
    Executa pipeline completo de onboarding para um município.
    Reutiliza load_municipio_from_seed + IntegrationOrchestrator.
    """
    meta = validate_ibge_code(codigo_ibge)
    code = meta["codigo_ibge"]
    seed = ensure_seed_row(db, code, meta["nome"], meta["uf"])

    if seed.onboarding_status == "concluido" and not force:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
        return onboarding_status_dict(db, seed, muni)

    errors: list[dict[str, str]] = []
    steps: dict[str, dict] = {"ibge_validacao": _step("ok", f"{meta['nome']}-{meta['uf']}")}

    seed.onboarding_status = "em_progresso"
    seed.integration_errors = []
    seed.integration_steps = steps
    seed.updated_at = utc_now()
    db.commit()

    try:
        _, geom_fonte = fetch_ibge_geometry(code)
        if geom_fonte == "lacuna_bbox":
            steps["geometria"] = _step("parcial", "Malha IBGE indisponível; bbox fallback.", "estimado")
            errors.append({"step": "geometria", "message": "Geometria municipal via fallback."})
        else:
            steps["geometria"] = _step("ok", f"Malha IBGE ({geom_fonte}).")
    except Exception as exc:
        steps["geometria"] = _step("falha", str(exc))
        errors.append({"step": "geometria", "message": str(exc)})

    muni = load_municipio_from_seed(db, seed, skip_integrations=True)
    steps["camadas_territoriais"] = _step(
        "parcial",
        "Bairros/setores e camadas base gerados (qualidade estimada até carga oficial).",
        "estimado",
    )

    orchestrator = IntegrationOrchestrator(db)
    for step_key, sync_fn, label in (
        ("ibge_indicadores", orchestrator._sync_ibge, "IBGE indicadores"),
        ("siconfi", orchestrator._sync_siconfi, "SICONFI"),
    ):
        try:
            ok = sync_fn(code)
            if ok:
                steps[step_key] = _step("ok", label)
            else:
                steps[step_key] = _step("parcial", f"{label} sem dados retornados.")
                errors.append({"step": step_key, "message": f"{label} vazio."})
        except Exception as exc:
            steps[step_key] = _step("falha", str(exc))
            errors.append({"step": step_key, "message": str(exc)})

    try:
        from app.data_connectors.capag_collector import collect_capag_municipality

        capag = collect_capag_municipality(code)
        orchestrator._upsert_fiscal_capag(code, capag)
        db.commit()
        if capag.get("nota_capag"):
            steps["capag"] = _step("ok", f"CAPAG {capag.get('nota_capag')}")
        else:
            steps["capag"] = _step("parcial", "CAPAG consultado sem nota.")
            errors.append({"step": "capag", "message": "Nota CAPAG ausente."})
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        steps["capag"] = _step("falha", str(exc))
        errors.append({"step": "capag", "message": str(exc)})

    risk = "encosta" if seed.uf in {"RJ", "ES"} and seed.criterio == "s2id_emergencia" else "inundacao"
    try:
        from app.services.territorial_etl import ensure_s2id_mapbiomas_layers

        etl = ensure_s2id_mapbiomas_layers(db, muni, risk=risk)
        if etl["s2id_count"] > 0:
            detail = f"{etl['s2id_count']} evento(s) S2ID"
            if etl["created_s2id"]:
                detail += f" (+{etl['created_s2id']} gerado(s))"
            steps["s2id"] = _step("ok" if etl["created_s2id"] == 0 else "parcial", detail, "estimado")
        else:
            steps["s2id"] = _step("lacuna", "Nenhum registro S2ID após ETL.", "lacuna")
            errors.append({"step": "s2id", "message": "S2ID vazio."})

        if etl["mapbiomas_count"] > 0:
            quality = etl.get("mapbiomas_quality", "derivado")
            mb_detail = f"{etl['mapbiomas_count']} polígono(s) MapBiomas"
            if etl.get("mapbiomas_records"):
                mb_detail += f" · {etl['mapbiomas_records']} stats"
            if etl["created_mapbiomas"]:
                mb_detail += f" (+{etl['created_mapbiomas']} gerado(s))"
            step_quality = "oficial" if quality == "oficial" else "estimado"
            steps["mapbiomas"] = _step("ok", mb_detail, step_quality)
        else:
            steps["mapbiomas"] = _step("lacuna", "Camada MapBiomas ausente.", "lacuna")
            errors.append({"step": "mapbiomas", "message": "MapBiomas vazio."})
    except Exception as exc:
        steps["s2id"] = _step("falha", str(exc))
        steps["mapbiomas"] = _step("falha", str(exc))
        errors.append({"step": "s2id_mapbiomas", "message": str(exc)})

    db.refresh(muni)
    sinidu = compute_initial_score(db, muni)
    completeness = _completeness_from_steps(steps)
    maturity = _maturity_from_scores(completeness, sinidu)

    lacunas = list(seed.lacunas or [])
    if steps.get("geometria", {}).get("status") != "ok":
        lacunas.append("geometria_ibge")
    if steps.get("s2id", {}).get("status") != "ok":
        lacunas.append("s2id_oficial")
    if steps.get("mapbiomas", {}).get("status") != "ok":
        lacunas.append("mapbiomas_oficial")
    if steps.get("capag", {}).get("status") == "falha":
        lacunas.append("capag")
    lacunas = sorted(set(lacunas))

    failed = sum(1 for s in steps.values() if s.get("status") == "falha")
    if failed == 0 and completeness >= 85:
        onboarding_status = "concluido"
    elif failed >= 3:
        onboarding_status = "falha"
    else:
        onboarding_status = "parcial"

    seed.municipio_id = muni.id
    seed.score_sinidu = sinidu
    seed.completeness_score = completeness
    seed.maturity_score = maturity
    seed.onboarding_status = onboarding_status
    seed.status_carga = ONBOARDING_TO_CARGA.get(onboarding_status, "parcial")
    seed.lacunas = lacunas
    seed.integration_errors = errors
    seed.integration_steps = steps
    seed.updated_at = utc_now()
    db.commit()
    db.refresh(seed)

    try:
        maturity_result = persist_maturity(db, code)
        seed.maturity_score = maturity_result["score"]
        seed.completeness_score = maturity_result["completeness_score"]
        db.commit()
        db.refresh(seed)
    except Exception as exc:
        logger.warning("Maturidade nao persistida para %s: %s", code, exc)

    if onboarding_status in ("concluido", "parcial") and muni is not None:
        try:
            from app.services.executive_diagnostic_engine import generate_executive_diagnostic

            generate_executive_diagnostic(db, code, origem="onboarding")
            logger.info("Diagnóstico executivo gerado automaticamente para %s", code)
        except Exception as exc:
            logger.warning("Diagnóstico executivo pós-onboarding falhou para %s: %s", code, exc)

    return onboarding_status_dict(db, seed, muni)


def onboarding_status_dict(db: Session, seed: MunicipioSeed, muni: Municipio | None = None) -> dict[str, Any]:
    if muni is None and seed.municipio_id:
        muni = db.query(Municipio).filter(Municipio.id == seed.municipio_id).first()
    if muni is None:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == seed.codigo_ibge).first()

    ibge_row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == seed.codigo_ibge).first()
    fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == seed.codigo_ibge).first()

    return {
        "codigo_ibge": seed.codigo_ibge,
        "nome": seed.nome,
        "uf": seed.uf,
        "criterio": seed.criterio,
        "municipio_id": muni.id if muni else seed.municipio_id,
        "onboarding_status": seed.onboarding_status or seed.status_carga,
        "status_carga": seed.status_carga,
        "maturity_score": float(seed.maturity_score) if seed.maturity_score is not None else None,
        "completeness_score": float(seed.completeness_score) if seed.completeness_score is not None else None,
        "maturity_classificacao": _tier_from_score(seed.maturity_score),
        "score_sinidu": float(seed.score_sinidu) if seed.score_sinidu is not None else None,
        "lacunas": seed.lacunas or [],
        "integration_errors": seed.integration_errors or [],
        "integration_steps": seed.integration_steps or {},
        "populacao": muni.populacao if muni else (ibge_row.populacao if ibge_row else None),
        "area_km2": float(muni.area_km2) if muni else (float(ibge_row.area_km2) if ibge_row and ibge_row.area_km2 else None),
        "nota_capag": fiscal.nota_capag if fiscal else None,
        "geom_fonte": seed.geom_fonte,
        "updated_at": seed.updated_at.isoformat() if seed.updated_at else None,
        "pronto_para_uso": seed.onboarding_status in ("concluido", "parcial") and muni is not None,
    }


def run_batch_onboarding(
    db: Session,
    *,
    limit: int = 5,
    status_filter: str = "pendente",
    force: bool = False,
) -> dict[str, Any]:
    """Executa onboarding sequencial para municípios pendentes (admin)."""
    upsert_seed_rows(db)
    query = db.query(MunicipioSeed).order_by(MunicipioSeed.prioridade.asc(), MunicipioSeed.nome.asc())
    if status_filter and status_filter != "todos":
        query = query.filter(MunicipioSeed.onboarding_status == status_filter)
    seeds = query.limit(max(1, min(limit, 6))).all()

    processed: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for seed in seeds:
        try:
            processed.append(run_onboarding(db, seed.codigo_ibge, force=force))
        except Exception as exc:
            db.rollback()
            logger.exception("Onboarding batch falhou %s", seed.codigo_ibge)
            errors.append({"codigo_ibge": seed.codigo_ibge, "error": str(exc)})

    return {
        "requested": len(seeds),
        "processed": len(processed),
        "errors": errors,
        "items": processed,
    }


def list_onboarding_statuses(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    upsert_seed_rows(db)
    rows = (
        db.query(MunicipioSeed)
        .order_by(MunicipioSeed.prioridade.asc(), MunicipioSeed.nome.asc())
        .limit(limit)
        .all()
    )
    return [onboarding_status_dict(db, row) for row in rows]
