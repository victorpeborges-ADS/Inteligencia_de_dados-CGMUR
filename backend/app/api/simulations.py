from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import (
    ImpermeabilizacaoSimRequest,
    PerdaVegetacaoSimRequest,
    ChuvaExtremaSimRequest,
    DrenagemSimRequest,
    SimulationOutput,
    SimulationAnalyzeRequest,
    SimulationAnalysisResponse,
    MitigationPlanRequest,
    MitigationPlanResponse,
)
from app.services.analytical_engine import AnalyticalEngine
from app.services.mitigation_planner import MitigationPlanner
from app.services.simulation_analyzer import analyze_simulation
from app.security.municipio_access import get_accessible_municipio

router = APIRouter()


@router.post("/waterproofing", response_model=SimulationOutput)
def simulate_waterproofing(payload: ImpermeabilizacaoSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return AnalyticalEngine.run_impermeabilizacao_simulation(
        db, muni.id, payload.taxa_impermeabilizacao_adicional
    )


@router.post("/vegetation-loss", response_model=SimulationOutput)
def simulate_vegetation_loss(payload: PerdaVegetacaoSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return AnalyticalEngine.run_perda_vegetacao_simulation(
        db, muni.id, payload.taxa_desmatamento
    )


@router.post("/extreme-rainfall", response_model=SimulationOutput)
def simulate_extreme_rainfall(payload: ChuvaExtremaSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return AnalyticalEngine.run_chuva_extrema_simulation(
        db, muni.id, payload.precipitacao_mm
    )


@router.post("/drainage-deficit", response_model=SimulationOutput)
def simulate_drainage_deficit(payload: DrenagemSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return AnalyticalEngine.run_drenagem_simulation(
        db, muni.id, payload.deficit_drenagem_pct
    )


@router.post("/analyze", response_model=SimulationAnalysisResponse)
def analyze_simulation_result(payload: SimulationAnalyzeRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return analyze_simulation(
        db,
        muni,
        payload.simulation,
        ai_provider=payload.ai_provider,
        ai_model=payload.ai_model,
        ai_api_key=payload.ai_api_key,
        use_ai=payload.use_ai,
    )


@router.post("/extreme-rainfall/mitigation-plan", response_model=MitigationPlanResponse)
def generate_rainfall_mitigation_plan(payload: MitigationPlanRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    value = payload.precipitacao_mm if payload.precipitacao_mm is not None else payload.input_value
    if value is None:
        raise HTTPException(status_code=400, detail="Provide precipitacao_mm or input_value.")
    return MitigationPlanner.build_plan(db, muni, "ExtremeRainfall", value)


@router.post("/mitigation-plan", response_model=MitigationPlanResponse)
def generate_mitigation_plan(payload: MitigationPlanRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    value = payload.input_value if payload.input_value is not None else payload.precipitacao_mm
    if value is None:
        raise HTTPException(status_code=400, detail="Provide input_value or precipitacao_mm.")
    try:
        return MitigationPlanner.build_plan(db, muni, payload.scenario_type, value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
