from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import FloodRiskPredictionRequest, FloodRiskPredictionResponse
from app.security.municipio_access import assert_codigo_ibge_access
from ml.bootstrap import ensure_flood_models, ensure_model_for
from ml.constants import ML_TARGET_IBGE_CODES
from ml.paths import model_meta_path, model_path
from ml.predictor import predictor

router = APIRouter()


@router.get("/flood-risk/status")
def flood_model_status():
    """Status dos modelos ML por município-alvo."""
    models = []
    for codigo in ML_TARGET_IBGE_CODES:
        p = model_path(codigo)
        meta = {}
        meta_path = model_meta_path(codigo)
        if meta_path.exists():
            import json
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        models.append({
            "codigo_ibge": codigo,
            "ready": p.exists(),
            "model_kind": meta.get("model_kind", "full" if p.exists() else None),
            "auc_roc_cv": meta.get("auc_roc_cv"),
            "threshold_mm_24h": meta.get("threshold_mm_24h"),
        })
    return {
        "ready_count": sum(1 for m in models if m["ready"]),
        "total": len(models),
        "on_demand_baseline": True,
        "note": (
            f"Qualquer município no banco recebe baseline on-demand; "
            f"{len(ML_TARGET_IBGE_CODES)} alvos têm artefato dedicado (treino full via etl_flood_ml)."
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
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha na inferência ML: {exc}") from exc

    return FloodRiskPredictionResponse(**result)
