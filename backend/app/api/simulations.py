from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import (
    ImpermeabilizacaoSimRequest,
    PerdaVegetacaoSimRequest,
    IlhaCalorSimRequest,
    ChuvaExtremaSimRequest,
    ChuvaExtremaCompareRequest,
    RainfallComparisonResponse,
    DrenagemSimRequest,
    SimulationOutput,
    SimulationJobStartResponse,
    SimulationAnalyzeRequest,
    SimulationAnalysisResponse,
    SimulationInterpretRequest,
    SimulationInterpretResponse,
    SlopeInterpretationResponse,
    SimulationExportRequest,
    SimulationExportResponse,
    MitigationPlanRequest,
    MitigationPlanResponse,
    GeoJSONFeatureCollection,
    HeatLstCompareRequest,
    HeatLstComparisonResponse,
)
from app.services.analytical_engine import AnalyticalEngine
from app.services.heat_simulator import run_heat_island_simulation
from app.services.lst_heat_comparator import compare_heat_simulation_with_lst
from app.services.simulation_cache import compare_rainfall_cached, run_rainfall_cached
from app.services.simulation_job_service import (
    get_simulation_job_progress,
    run_rainfall_compare_job,
    run_rainfall_simulation_job,
)
from app.services.mitigation_planner import MitigationPlanner
from app.services.simulation_analyzer import analyze_simulation
from app.services.simulation_interpret_cache import interpret_simulation_cached
from app.services.simulation_interpreter import interpret_slope_zones
from app.services.simulation_export import (
    export_download_meta,
    generate_simulation_pdf,
    save_simulation_geojson,
    simulation_export_dir,
)
from app.security.municipio_access import get_accessible_municipio
from app.services.audit_service import log_audit, resolve_actor

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
    result = run_heat_island_simulation(
        db,
        muni.id,
        perda_vegetal_pct=payload.taxa_desmatamento,
        impermeabilizacao_extra_pct=0.0,
    )
    result["scenario_type"] = "VegetationLoss"
    result["input_value"] = payload.taxa_desmatamento
    return result


@router.post("/heat-island", response_model=SimulationOutput)
def simulate_heat_island(payload: IlhaCalorSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return run_heat_island_simulation(
        db,
        muni.id,
        temperatura_pico_c=payload.temperatura_pico_c,
        perda_vegetal_pct=payload.perda_vegetal_pct,
        ganho_vegetal_pct=payload.ganho_vegetal_pct,
        impermeabilizacao_extra_pct=payload.impermeabilizacao_extra_pct,
    )


@router.post("/heat-lst-compare", response_model=HeatLstComparisonResponse)
def heat_lst_compare(payload: HeatLstCompareRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return compare_heat_simulation_with_lst(db, muni, payload.simulation)


@router.post("/extreme-rainfall", response_model=SimulationOutput)
def simulate_extreme_rainfall(payload: ChuvaExtremaSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return run_rainfall_cached(db, muni.id, muni.codigo_ibge, payload.precipitacao_mm)


@router.post("/extreme-rainfall/async", response_model=SimulationJobStartResponse)
def simulate_extreme_rainfall_async(payload: ChuvaExtremaSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    job_id = run_rainfall_simulation_job(muni.codigo_ibge, muni.id, payload.precipitacao_mm)
    return {"job_id": job_id, "async_mode": True, "status": "queued"}


@router.post("/extreme-rainfall/compare", response_model=RainfallComparisonResponse)
def compare_extreme_rainfall(payload: ChuvaExtremaCompareRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return compare_rainfall_cached(
        db, muni.id, muni.codigo_ibge, payload.baseline_mm, payload.scenario_mm
    )


@router.post("/extreme-rainfall/compare/async", response_model=SimulationJobStartResponse)
def compare_extreme_rainfall_async(
    payload: ChuvaExtremaCompareRequest, request: Request, db: Session = Depends(get_db)
):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    job_id = run_rainfall_compare_job(
        muni.codigo_ibge, muni.id, payload.scenario_mm, payload.baseline_mm
    )
    return {"job_id": job_id, "async_mode": True, "status": "queued"}


@router.get("/jobs/{job_id}")
def simulation_job_status(job_id: str):
    progress = get_simulation_job_progress(job_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Job de simulação não encontrado.")
    return progress


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


@router.post("/interpret", response_model=SimulationInterpretResponse)
def interpret_simulation_result(payload: SimulationInterpretRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.municipio_codigo, request=request)
    tipo = payload.tipo_simulacao.strip().lower()
    if tipo not in {"chuva", "asfalto", "vegetacao", "drenagem", "calor"}:
        raise HTTPException(status_code=400, detail="tipo_simulacao inválido.")
    return interpret_simulation_cached(
        db,
        muni,
        tipo_simulacao=tipo,  # type: ignore[arg-type]
        parametro_atual=payload.parametro_atual,
        parametro_referencia=payload.parametro_referencia,
        resultado_simulacao=payload.resultado_simulacao,
        resultado_referencia=payload.resultado_referencia,
        comparacao_delta=payload.comparacao_delta,
        lst_comparison=payload.lst_comparison,
        ai_provider=payload.ai_provider,
        ai_model=payload.ai_model,
        ai_api_key=payload.ai_api_key,
        use_ai=payload.use_ai,
    )


@router.get("/slope-interpretation/{codigo_ibge}", response_model=SlopeInterpretationResponse)
def slope_interpretation(
    codigo_ibge: str,
    request: Request,
    precipitacao_mm: float = 80.0,
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return interpret_slope_zones(db, muni, precip_mm=precipitacao_mm)


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


@router.post("/export/geojson", response_model=SimulationExportResponse)
def export_simulation_geojson(payload: SimulationExportRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    path = save_simulation_geojson(
        payload.simulation,
        muni,
        comparison=payload.comparison_delta,
    )
    actor = resolve_actor(request)
    log_audit(
        db,
        user=actor,
        action="simulation.export_geojson",
        resource_type="simulation",
        resource_id=muni.codigo_ibge,
        codigo_ibge=muni.codigo_ibge,
        metadata={"filename": path.name, "scenario": payload.simulation.get("scenario_type")},
        request=request,
    )
    meta = export_download_meta(path)
    return SimulationExportResponse(format="geojson", **meta)


@router.post("/export/pdf", response_model=SimulationExportResponse)
def export_simulation_pdf(payload: SimulationExportRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    path = generate_simulation_pdf(
        payload.simulation,
        muni,
        comparison=payload.comparison_delta,
        analysis=payload.analysis,
    )
    actor = resolve_actor(request)
    log_audit(
        db,
        user=actor,
        action="simulation.export_pdf",
        resource_type="simulation",
        resource_id=muni.codigo_ibge,
        codigo_ibge=muni.codigo_ibge,
        metadata={"filename": path.name, "scenario": payload.simulation.get("scenario_type")},
        request=request,
    )
    meta = export_download_meta(path)
    return SimulationExportResponse(format="pdf", **meta)


@router.get("/download/{filename}")
def download_simulation_export(filename: str, request: Request, db: Session = Depends(get_db)):
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    path = simulation_export_dir() / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    media = "application/pdf" if path.suffix.lower() == ".pdf" else "application/geo+json"
    return FileResponse(path, media_type=media, filename=safe)

