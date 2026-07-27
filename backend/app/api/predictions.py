from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import FloodRiskPredictionRequest, FloodRiskPredictionResponse
from app.security.municipio_access import assert_codigo_ibge_access
from ml.bootstrap import ensure_flood_models, ensure_model_for
from ml.constants import ML_TARGET_IBGE_CODES
from ml.model_policy import load_model_meta, public_auc
from ml.paths import model_path
from ml.predictor import predictor

router = APIRouter()


@router.get("/flood-risk/status")
def flood_model_status():
    """Status dos modelos ML por município-alvo (AUC só para model_kind=full)."""
    models = []
    for codigo in ML_TARGET_IBGE_CODES:
        p = model_path(codigo)
        meta = load_model_meta(codigo) if p.exists() else {}
        kind = meta.get("model_kind") if meta else None
        if p.exists() and not kind:
            kind = "full"
        spatial = (meta.get("spatial_validation") or (meta.get("validation") or {}).get("spatial") or {})
        models.append({
            "codigo_ibge": codigo,
            "ready": p.exists(),
            "production_ready": kind == "full",
            "model_kind": kind,
            "auc_roc_cv": public_auc(meta) if meta else None,
            "threshold_mm_24h": meta.get("threshold_mm_24h") if meta else None,
            "brier_model": (meta.get("validation") or {}).get("brier_model") if meta else None,
            "spatial_hit_rate": spatial.get("hit_rate"),
            "spatial_acordo": spatial.get("acordo"),
            "algorithm": meta.get("algorithm") if meta else None,
        })
    return {
        "ready_count": sum(1 for m in models if m["ready"]),
        "production_ready_count": sum(1 for m in models if m["production_ready"]),
        "total": len(models),
        "on_demand_baseline": True,
        "note": (
            "Monitor operacional só usa ML com model_kind=full. "
            "Artefatos baseline_synthetic alimentam apenas análise experimental na aba Simulações "
            "e são rotulados como score sintético (Fase 21a)."
        ),
        "models": models,
    }


@router.post("/flood-risk/bootstrap")
def bootstrap_flood_models(db: Session = Depends(get_db)):
    """Força bootstrap dos modelos (artifacts → treino completo → baseline)."""
    status = ensure_flood_models(db)
    if not all(status.values()):
        raise HTTPException(status_code=503, detail={"message": "Alguns modelos não puderam ser criados.", "status": status})
    return {"message": "Modelos ML prontos.", "status": status}


@router.post("/flood-risk", response_model=FloodRiskPredictionResponse)
def predict_flood_risk(body: FloodRiskPredictionRequest, request: Request, db: Session = Depends(get_db)):
    try:
        codigo = body.municipio_id
        if codigo.isdigit() and len(codigo) == 7:
            assert_codigo_ibge_access(db, codigo, request=request)
            ensure_model_for(codigo, db)
        result = predictor.predict(
            db,
            municipio_slug=body.municipio_id,
            precip_24h=body.precip_24h,
            precip_48h=body.precip_48h,
            precip_72h=body.precip_72h,
            mes_do_ano=body.mes_do_ano,
            precip_7d=body.precip_7d,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha na inferência ML: {exc}") from exc

    return FloodRiskPredictionResponse(**result)
