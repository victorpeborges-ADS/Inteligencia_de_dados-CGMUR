from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, PlainTextResponse
from pathlib import Path
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas import (
    ImpermeabilizacaoSimRequest,
    PerdaVegetacaoSimRequest,
    IlhaCalorSimRequest,
    ChuvaExtremaSimRequest,
    ChuvaExtremaCompareRequest,
    ClimateModuleRequest,
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
    SolarRooftopRequest,
    GreenRoofMitigationRequest,
    GreenInfraHeatRequest,
    InterventionCompareRequest,
    ShadowInsolationRequest,
)
from app.services.analytical_engine import AnalyticalEngine
from app.services.heat_simulator import run_heat_island_simulation
from app.services.lst_heat_comparator import compare_heat_simulation_with_lst
from app.services.simulation_cache import compare_rainfall_cached, run_rainfall_cached
from app.services.idf_rainfall_service import idf_curve_catalog, resolve_idf_precipitacao
from app.services.sea_level_service import resolve_nivel_mar
from app.services.drainage_capacity_service import resolve_drainage_capacity
from app.services.uncertainty_bands_service import attach_uncertainty_bands
from app.services.simulation_job_service import (
    get_simulation_job_progress,
    run_rainfall_compare_job,
    run_rainfall_simulation_job,
)
from app.services.simulation_prewarm import schedule_rainfall_prewarm
from app.services.mitigation_planner import MitigationPlanner
from app.services.simulation_analyzer import analyze_simulation
from app.services.simulation_interpret_cache import interpret_simulation_cached
from app.services.simulation_interpreter import interpret_slope_zones
from app.services.simulation_export import (
    collect_kmz_package_features,
    export_download_meta,
    generate_simulation_pdf,
    save_simulation_geojson,
    save_simulation_kmz,
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


@router.post("/solar-rooftop")
def simulate_solar_rooftop(payload: SolarRooftopRequest, request: Request, db: Session = Depends(get_db)):
    """17d.1 — potencial fotovoltaico em telhados (footprint LOD1)."""
    from app.services.solar_rooftop_service import compute_solar_potential

    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    try:
        return compute_solar_potential(db, muni.codigo_ibge, limit=payload.limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/green-roof")
def simulate_green_roof(payload: GreenRoofMitigationRequest, request: Request, db: Session = Depends(get_db)):
    """17d.2 — cenário telhado verde × mancha de inundação."""
    from app.services.green_roof_mitigation_service import run_green_roof_mitigation

    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    try:
        return run_green_roof_mitigation(
            db,
            muni.codigo_ibge,
            precipitacao_mm=payload.precipitacao_mm,
            telhado_verde_pct=payload.telhado_verde_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/green-infra-heat")
def simulate_green_infra_heat(payload: GreenInfraHeatRequest, request: Request, db: Session = Depends(get_db)):
    """17d.4 — arborização/parques × ilha de calor (antes/depois)."""
    from app.services.green_infra_heat_service import run_green_infra_heat

    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    try:
        return run_green_infra_heat(
            db,
            muni.codigo_ibge,
            temperatura_pico_c=payload.temperatura_pico_c,
            arborizacao_pct=payload.arborizacao_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/interventions/compare")
def compare_mitigation_interventions(
    payload: InterventionCompareRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """17d.5 — comparador unificado antes/depois de intervenções."""
    from app.services.intervention_comparator_service import compare_interventions

    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    tipo = (payload.tipo or "telhado_verde").strip().lower()
    if tipo not in {"telhado_verde", "infraverde_calor", "solar"}:
        raise HTTPException(status_code=400, detail="tipo deve ser telhado_verde | infraverde_calor | solar")
    try:
        return compare_interventions(
            db,
            muni.codigo_ibge,
            tipo=tipo,  # type: ignore[arg-type]
            precipitacao_mm=payload.precipitacao_mm,
            telhado_verde_pct=payload.telhado_verde_pct,
            temperatura_pico_c=payload.temperatura_pico_c,
            arborizacao_pct=payload.arborizacao_pct,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/shadow-insolation")
def simulate_shadow_insolation(
    payload: ShadowInsolationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """17d.3 — sombra/insolação por edifício (posição solar + vizinhos)."""
    from app.services.shadow_insolation_service import compute_shadow_insolation

    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    try:
        return compute_shadow_insolation(
            db,
            muni.codigo_ibge,
            hora_local=payload.hora_local,
            limit=payload.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


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
        sombreamento_pct=float(payload.sombreamento_pct or 0),
        corredores_vento_pct=float(payload.corredores_vento_pct or 0),
    )


@router.post("/heat-lst-compare", response_model=HeatLstComparisonResponse)
def heat_lst_compare(payload: HeatLstCompareRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    return compare_heat_simulation_with_lst(db, muni, payload.simulation)


def _resolve_rainfall_request(payload: ChuvaExtremaSimRequest, muni) -> tuple[float, dict | None]:
    """17g.1a — TR/IDF → mm, ou mm direto."""
    if payload.periodo_retorno_anos is not None:
        idf = resolve_idf_precipitacao(
            muni.codigo_ibge,
            int(payload.periodo_retorno_anos),
            duracao_min=int(payload.duracao_min or 60),
            uf=getattr(muni, "uf", None),
        )
        return float(idf["precipitacao_mm"]), idf
    if payload.precipitacao_mm is not None:
        return float(payload.precipitacao_mm), None
    raise HTTPException(
        status_code=400,
        detail="Informe precipitacao_mm ou periodo_retorno_anos (TR 2/10/25/100).",
    )


def _attach_idf_meta(result: dict, idf_meta: dict | None) -> dict:
    if not idf_meta:
        return result
    out = dict(result)
    meta = dict(out.get("simulation_meta") or {})
    meta["idf"] = idf_meta
    out["simulation_meta"] = meta
    out["input_value"] = idf_meta["precipitacao_mm"]
    return out


@router.get("/idf/{codigo_ibge}")
def get_idf_curves(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """Catálogo IDF (TR × duração) para chips da UI — 17g.1a."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return idf_curve_catalog(muni.codigo_ibge, uf=getattr(muni, "uf", None))


class HydroCalibrationUpdate(BaseModel):
    runoff_scale: Optional[float] = None
    rise_scale: Optional[float] = None
    river_boost_scale: Optional[float] = None
    iri_scale: Optional[float] = None
    nota: Optional[str] = None
    auto: bool = False
    precip_mm: float = 120.0


@router.get("/hydro-calibration/{codigo_ibge}")
def get_hydro_calibration(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """Coeficientes calibrados do motor pluvial (17g.2b)."""
    from app.services.hydro_calibration_service import load_calibration

    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return load_calibration(muni.codigo_ibge, getattr(muni, "uf", None))


@router.post("/hydro-calibration/{codigo_ibge}")
def update_hydro_calibration(
    codigo_ibge: str,
    payload: HydroCalibrationUpdate,
    request: Request,
    db: Session = Depends(get_db),
):
    """Recalibra automaticamente (S2ID) ou aplica escalas manuais."""
    from app.services.hydro_calibration_service import apply_manual_scales, auto_calibrate

    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    actor = resolve_actor(request)
    if payload.auto:
        out = auto_calibrate(db, muni, precip_mm=float(payload.precip_mm or 120), run_simulation=True)
    else:
        scales = {
            k: getattr(payload, k)
            for k in ("runoff_scale", "rise_scale", "river_boost_scale", "iri_scale")
            if getattr(payload, k) is not None
        }
        if not scales:
            raise HTTPException(400, "Informe auto=true ou ao menos uma escala.")
        out = apply_manual_scales(
            muni.codigo_ibge,
            scales,
            uf=getattr(muni, "uf", None),
            nota=payload.nota,
        )
    log_audit(
        db,
        user=actor,
        action="hydro_calibration.update",
        resource_type="hydro_calibration",
        resource_id=None,
        codigo_ibge=muni.codigo_ibge,
        metadata={"source": out.get("source"), "version": out.get("version")},
        request=request,
    )
    return out


class MethodNoteRequest(BaseModel):
    tipo: str = "chuva"
    codigo_ibge: Optional[str] = None
    simulation_meta: dict[str, Any] = Field(default_factory=dict)
    format: Optional[str] = None  # json | markdown


@router.post("/method-note")
def build_simulation_method_note(payload: MethodNoteRequest, request: Request, db: Session = Depends(get_db)):
    """Nota metodológica publicável (17g.2g) a partir do simulation_meta."""
    from app.services.method_note_service import build_method_note

    municipio = None
    if payload.codigo_ibge:
        muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
        municipio = {"codigo_ibge": muni.codigo_ibge, "nome": muni.nome, "uf": muni.uf}
    nota = build_method_note(payload.simulation_meta, tipo=payload.tipo, municipio=municipio)
    if (payload.format or "").lower() == "markdown":
        return PlainTextResponse(nota["markdown"], media_type="text/markdown; charset=utf-8")
    return nota


@router.get("/sea-level/{codigo_ibge}")
def get_sea_level_scenarios(codigo_ibge: str, request: Request, db: Session = Depends(get_db)):
    """Cenários de nível do mar / storm surge (17g.1c) — só costeiros piloto."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return resolve_nivel_mar(muni.codigo_ibge, cenario_nivel_mar="atual")


@router.get("/drainage-capacity/{codigo_ibge}")
def get_drainage_capacity(
    codigo_ibge: str,
    request: Request,
    precip_mm: float = Query(default=120, ge=10, le=400),
    duracao_min: int = Query(default=60, ge=15, le=360),
    db: Session = Depends(get_db),
):
    """Proxy de capacidade da microdrenagem (17g.1d) — SNIS/densidade."""
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return resolve_drainage_capacity(
        db,
        muni,
        precip_mm=float(precip_mm),
        duracao_h=float(duracao_min) / 60.0,
    )


@router.post("/climate-modules", response_model=SimulationOutput)
def simulate_climate_module(payload: ClimateModuleRequest, request: Request, db: Session = Depends(get_db)):
    """Estresse hídrico/seca ou proxy de arbovírus (17g.1g)."""
    from app.services.climate_modules_service import run_climate_module

    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    modo = (payload.modo or "seca").strip().lower()
    if modo not in ("seca", "arbovirus"):
        raise HTTPException(status_code=400, detail="modo deve ser 'seca' ou 'arbovirus'")
    return run_climate_module(
        db,
        muni,
        modo,  # type: ignore[arg-type]
        precip_72h_mm=payload.precip_72h_mm,
        precip_esperada_72h_mm=float(payload.precip_esperada_72h_mm or 25.0),
        temperatura_media_c=payload.temperatura_media_c,
        precip_7d_mm=payload.precip_7d_mm,
    )


@router.get("/climate-modules/{codigo_ibge}")
def get_climate_module_defaults(
    codigo_ibge: str,
    request: Request,
    modo: str = Query(default="seca"),
    db: Session = Depends(get_db),
):
    """Roda módulo com defaults do cache meteorológico."""
    from app.services.climate_modules_service import run_climate_module

    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    m = (modo or "seca").strip().lower()
    if m not in ("seca", "arbovirus"):
        raise HTTPException(status_code=400, detail="modo deve ser 'seca' ou 'arbovirus'")
    return run_climate_module(db, muni, m)  # type: ignore[arg-type]


@router.post("/extreme-rainfall", response_model=SimulationOutput)
def simulate_extreme_rainfall(payload: ChuvaExtremaSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    mm, idf_meta = _resolve_rainfall_request(payload, muni)
    slr = resolve_nivel_mar(
        muni.codigo_ibge,
        nivel_mar_m=payload.nivel_mar_m,
        cenario_nivel_mar=payload.cenario_nivel_mar,
    )
    ant = float(payload.chuva_antecedente_mm or 0)
    dur_h = float(payload.duracao_min or 60) / 60.0
    dren = resolve_drainage_capacity(
        db,
        muni,
        precip_mm=mm,
        drainage_capacity_mm_h=payload.drainage_capacity_mm_h,
        aplicar_drenagem=bool(payload.aplicar_drenagem if payload.aplicar_drenagem is not None else True),
        duracao_h=dur_h,
    )
    result = run_rainfall_cached(
        db,
        muni.id,
        muni.codigo_ibge,
        mm,
        nivel_mar_m=float(slr["nivel_mar_m"]),
        chuva_antecedente_mm=ant,
        sea_level_meta=slr,
        drain_removed_mm=float(dren.get("removido_mm") or 0),
        rede_saturada=bool(dren.get("saturada")),
        drenagem_meta=dren,
    )
    result = attach_uncertainty_bands(db, muni.id, muni.codigo_ibge, result)
    return _attach_idf_meta(result, idf_meta)


@router.post("/extreme-rainfall/async", response_model=SimulationJobStartResponse)
def simulate_extreme_rainfall_async(payload: ChuvaExtremaSimRequest, request: Request, db: Session = Depends(get_db)):
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    mm, _idf_meta = _resolve_rainfall_request(payload, muni)
    slr = resolve_nivel_mar(
        muni.codigo_ibge,
        nivel_mar_m=payload.nivel_mar_m,
        cenario_nivel_mar=payload.cenario_nivel_mar,
    )
    ant = float(payload.chuva_antecedente_mm or 0)
    dur_h = float(payload.duracao_min or 60) / 60.0
    dren = resolve_drainage_capacity(
        db,
        muni,
        precip_mm=mm,
        drainage_capacity_mm_h=payload.drainage_capacity_mm_h,
        aplicar_drenagem=bool(payload.aplicar_drenagem if payload.aplicar_drenagem is not None else True),
        duracao_h=dur_h,
    )
    job_id = run_rainfall_simulation_job(
        muni.codigo_ibge,
        muni.id,
        mm,
        nivel_mar_m=float(slr["nivel_mar_m"]),
        chuva_antecedente_mm=ant,
        sea_level_meta=slr,
        drain_removed_mm=float(dren.get("removido_mm") or 0),
        rede_saturada=bool(dren.get("saturada")),
        drenagem_meta=dren,
    )
    return {
        "job_id": job_id,
        "async_mode": True,
        "status": "queued",
        "precipitacao_mm": mm,
        "idf": _idf_meta,
        "nivel_mar": slr,
        "drenagem_urbana": dren,
    }


@router.post("/extreme-rainfall/prewarm")
def prewarm_extreme_rainfall(payload: ChuvaExtremaSimRequest, request: Request, db: Session = Depends(get_db)):
    """Pré-aquece cache da simulação pluvial em background (demo/officina)."""
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    from app.config import settings

    mm, _idf = _resolve_rainfall_request(payload, muni)
    extra = [settings.SIMULATION_PREWARM_BASELINE_MM] if mm != settings.SIMULATION_PREWARM_BASELINE_MM else None
    return schedule_rainfall_prewarm(muni.codigo_ibge, mm, extra_mm=extra)


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


@router.post("/export/kmz", response_model=SimulationExportResponse)
def export_simulation_kmz(payload: SimulationExportRequest, request: Request, db: Session = Depends(get_db)):
    """Exporta pacote KMZ: mancha + bairros afetados + pontos de contingência (20e.2)."""
    muni = get_accessible_municipio(db, payload.codigo_ibge, request=request)
    if not payload.simulation.get("geometry"):
        raise HTTPException(status_code=400, detail="Simulação sem geometria para exportar.")
    extra = collect_kmz_package_features(db, muni, payload.simulation)
    path = save_simulation_kmz(
        payload.simulation,
        muni,
        comparison=payload.comparison_delta,
        extra_features=extra,
    )
    actor = resolve_actor(request)
    log_audit(
        db,
        user=actor,
        action="simulation.export_kmz",
        resource_type="simulation",
        resource_id=muni.codigo_ibge,
        codigo_ibge=muni.codigo_ibge,
        metadata={
            "filename": path.name,
            "scenario": payload.simulation.get("scenario_type"),
            "package_features": len(extra),
        },
        request=request,
    )
    meta = export_download_meta(path)
    return SimulationExportResponse(format="kmz", **meta)


@router.get("/download/{filename}")
def download_simulation_export(filename: str, request: Request, db: Session = Depends(get_db)):
    safe = Path(filename).name
    if safe != filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    path = simulation_export_dir() / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    suffix = path.suffix.lower()
    media = {
        ".pdf": "application/pdf",
        ".geojson": "application/geo+json",
        ".json": "application/geo+json",
        ".kmz": "application/vnd.google-earth.kmz",
        ".kml": "application/vnd.google-earth.kml+xml",
    }.get(suffix, "application/octet-stream")
    return FileResponse(path, media_type=media, filename=safe)

