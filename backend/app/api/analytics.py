from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Municipio, SetorCensitario, CoberturaVegetalMapBiomas, HistoricoDesastreS2ID, AlertaCemaden
from app.schemas import ClimateIndicesResponse
from app.services.analytical_engine import AnalyticalEngine
from app.services.official_climate import OfficialClimateService
from app.security.municipio_access import get_accessible_municipio
from etl.etl_sentinel import query_sentinel_stac
from typing import List, Dict, Any
import json
from shapely.geometry import shape

router = APIRouter()

def executive_snapshot(db: Session, muni: Municipio):
    alerts_count = db.query(AlertaCemaden).filter(AlertaCemaden.municipio_id == muni.id).count()
    disasters_count = db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == muni.id).count()
    damages_total = db.query(func.sum(HistoricoDesastreS2ID.danos_materiais)).filter(
        HistoricoDesastreS2ID.municipio_id == muni.id
    ).scalar()
    avg_income = db.query(func.avg(SetorCensitario.renda_media)).filter(SetorCensitario.municipio_id == muni.id).scalar()
    total_area_deg = db.scalar(func.ST_Area(muni.geom))
    forest_area_deg = db.query(func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom))).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id,
        CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta"
    ).scalar()
    veg_percent = (float(forest_area_deg) / float(total_area_deg)) * 100.0 if forest_area_deg and total_area_deg else 0.0
    vulnerabilities = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
    floods = AnalyticalEngine.calculate_flood_risk(db, muni.id)
    avg_ivc = sum(item["indice_vulnerabilidade"] for item in vulnerabilities) / len(vulnerabilities) if vulnerabilities else 0.0
    avg_iri = sum(item["indice_risco_inundacao"] for item in floods) / len(floods) if floods else 0.0
    avg_adaptation = sum(item["capacidade_adaptacao"] for item in vulnerabilities) / len(vulnerabilities) if vulnerabilities else 0.0
    score = round(((avg_ivc * 0.45) + (avg_iri * 0.35) + ((1.0 - avg_adaptation) * 0.20)) * 100)
    return {
        "codigo_ibge": muni.codigo_ibge,
        "nome": muni.nome,
        "uf": muni.uf,
        "populacao": muni.populacao,
        "area_km2": float(muni.area_km2),
        "densidade_demografica": round(muni.populacao / float(muni.area_km2), 2) if muni.area_km2 else 0,
        "renda_media_setores": round(float(avg_income or 0.0), 2),
        "cobertura_vegetal_percent": round(veg_percent, 2),
        "alertas_ativos_count": alerts_count,
        "historico_desastres_count": disasters_count,
        "danos_materiais_total": round(float(damages_total or 0.0), 2),
        "score_sinidu": score,
        "media_ivc": round(avg_ivc, 2),
        "media_iri": round(avg_iri, 2),
        "media_adaptacao": round(avg_adaptation, 2),
    }

@router.get("/indices", response_model=ClimateIndicesResponse)
def get_climate_risk_indices(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
        
    vulnerability_results = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
    flood_results = AnalyticalEngine.calculate_flood_risk(db, muni.id)
    
    return ClimateIndicesResponse(
        vulnerabilidade=vulnerability_results,
        inundacao=flood_results
    )

@router.get("/heat-islands")
def get_heat_islands_data(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
        
    # We return calculated Surface Temperature anomalies per neighborhood and a historical timeline
    # Based on our MapBiomas forest cover correlation (lower cover = higher temperature)
    vulnerabilities = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
    
    anomalies = []
    for v in vulnerabilities:
        # Base temperature of Recife is 27°C. Heat islands increase it by up to 5°C
        # depending on adaptive capacity (vegetation cover inverse)
        cooling_effect = v["capacidade_adaptacao"] * 4.0 # up to 4°C cooling
        lst_temp = 32.5 - cooling_effect
        anomaly = max(0.0, lst_temp - 27.0)
        
        anomalies.append({
            "bairro_nome": v["bairro_nome"],
            "temperatura_superficial_celsius": round(lst_temp, 1),
            "anomalia_calor_celsius": round(anomaly, 1),
            "intensidade_ilha": "ALTA" if anomaly > 3.0 else ("MEDIA" if anomaly > 1.5 else "BAIXA")
        })
        
    # Demonstrative internal timeline. Replace with MapBiomas + INMET/Sentinel/Landsat integration for official use.
    timeline = [
        {"ano": 1985, "temperatura_media": 26.1, "area_urbanizada_km2": 85.0},
        {"ano": 1995, "temperatura_media": 26.6, "area_urbanizada_km2": 110.0},
        {"ano": 2005, "temperatura_media": 27.0, "area_urbanizada_km2": 145.0},
        {"ano": 2015, "temperatura_media": 27.5, "area_urbanizada_km2": 180.0},
        {"ano": 2025, "temperatura_media": 28.2, "area_urbanizada_km2": 218.4}
    ]
    
    return {
        "anomalies": anomalies,
        "historical_timeline": timeline,
        "source": "Série demonstrativa interna Sinidu+Clima",
        "source_note": "Substituir por integração oficial MapBiomas + INMET/Sentinel/Landsat antes de uso técnico conclusivo."
    }

@router.get("/urban-climate-official")
def get_official_urban_climate(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return OfficialClimateService.urban_climate_series(db, muni)

@router.get("/diagnostic")
def get_workshop_diagnostic(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)

    vulnerabilities = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
    floods = AnalyticalEngine.calculate_flood_risk(db, muni.id)
    flood_by_id = {item["id"]: item for item in floods}

    coords_by_bairro = {
        "Ibura": [-8.1368, -34.9587],
        "Santo Amaro": [-8.0476, -34.8817],
        "Arruda": [-8.0268, -34.8928],
        "Boa Viagem": [-8.1259, -34.9009],
        "Várzea": [-8.0472, -34.9576],
    }
    muni_shape = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))
    centroid = muni_shape.centroid
    default_focus = [round(centroid.y, 5), round(centroid.x, 5)]

    ranking = []
    for item in vulnerabilities:
        flood = flood_by_id.get(item["id"], {})
        ivc = float(item.get("indice_vulnerabilidade", 0.0))
        iri = float(flood.get("indice_risco_inundacao", 0.0))
        adaptation_gap = 1.0 - float(item.get("capacidade_adaptacao", 0.0))
        score = round(((ivc * 0.45) + (iri * 0.35) + (adaptation_gap * 0.20)) * 100)

        if iri >= 0.66:
            recommended_action = "Priorizar drenagem urbana, renaturalizacao de margens e alerta comunitario."
        elif ivc >= 0.66:
            recommended_action = "Priorizar adaptacao climatica, arborizacao e equipamentos de apoio social."
        elif adaptation_gap >= 0.66:
            recommended_action = "Ampliar capacidade adaptativa com infraestrutura verde e servicos urbanos."
        else:
            recommended_action = "Monitorar indicadores e integrar aos planos locais."

        ranking.append({
            "bairro": item["bairro_nome"],
            "score_sinidu": score,
            "indice_vulnerabilidade": ivc,
            "indice_risco_inundacao": iri,
            "capacidade_adaptacao": float(item.get("capacidade_adaptacao", 0.0)),
            "score_componentes": {
                "vulnerabilidade_pct": round(ivc * 45, 1),
                "inundacao_pct": round(iri * 35, 1),
                "deficit_adaptacao_pct": round(adaptation_gap * 20, 1),
            },
            "score_explicacao": "Score = 45% IVC + 35% IRI + 20% deficit de adaptacao",
            "acao_recomendada": recommended_action,
            "coordinates": coords_by_bairro.get(item["bairro_nome"], default_focus)
        })

    ranking.sort(key=lambda row: row["score_sinidu"], reverse=True)
    top3 = ranking[:3]

    return {
        "municipio": {
            "nome": muni.nome,
            "uf": muni.uf,
            "codigo_ibge": muni.codigo_ibge,
            "populacao": muni.populacao,
            "area_km2": float(muni.area_km2),
        },
        "headline": f"Diagnostico Sinidu+Clima aponta {len(top3)} areas prioritarias para acao integrada em {muni.nome}.",
        "score_formula": "Score Sinidu+Clima = 45% vulnerabilidade + 35% inundacao + 20% deficit de adaptacao",
        "critical_areas": top3,
        "ranking": ranking,
        "recommended_layers": [
            "bairros",
            "vulnerabilidade",
            "inundacao",
            "saneamento_drenagem",
            "prioridade_planejamento"
        ],
        "opportunities": [
            "Conectar S2ID, CEMADEN, MapBiomas, SNIS/SINISA e IBGE em uma leitura unica de risco urbano.",
            "Transformar diagnosticos em carteira priorizada de obras, planos locais e medidas de adaptacao.",
            "Usar o assistente Sinidu+Clima para explicar o porquê de cada prioridade em linguagem executiva."
        ],
        "narrative_steps": [
            {
                "title": "1. Contexto urbano",
                "description": "Comece pela malha territorial e pelos indicadores socioeconomicos.",
                "layers": ["bairros", "socioeconomico"],
                "focus": default_focus,
                "zoom": 12
            },
            {
                "title": "2. Risco climatico",
                "description": "Sobreponha vulnerabilidade, inundacao e alertas ativos.",
                "layers": ["bairros", "vulnerabilidade", "inundacao", "alertas"],
                "focus": top3[0]["coordinates"] if top3 else default_focus,
                "zoom": 13
            },
            {
                "title": "3. Decisao publica",
                "description": "Feche com prioridade de planejamento e saneamento/drenagem.",
                "layers": ["bairros", "prioridade_planejamento", "saneamento_drenagem", "infraestrutura"],
                "focus": top3[0]["coordinates"] if top3 else default_focus,
                "zoom": 13
            }
        ]
    }

@router.get("/compare")
def compare_municipalities(codigos: str = Query(...), request: Request = ..., db: Session = Depends(get_db)):
    codes = [code.strip() for code in codigos.split(",") if code.strip()]
    if len(codes) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two municipality codes.")
    if len(codes) > 5:
        raise HTTPException(status_code=400, detail="Compare up to five municipalities at once.")

    return {
        "codigos": codes,
        "metricas": [
            "populacao",
            "densidade_demografica",
            "renda_media_setores",
            "cobertura_vegetal_percent",
            "alertas_ativos_count",
            "historico_desastres_count",
            "danos_materiais_total",
            "score_sinidu",
        ],
        "qualidade_dado": "Comparacao demonstrativa: mistura dados oficiais, estimativas e derivados Sinidu+Clima.",
        "municipios": [
            executive_snapshot(db, get_accessible_municipio(db, code, request=request))
            for code in codes
        ]
    }

@router.get("/sentinel-stac")
def get_sentinel_stac_images():
    """
    Queries Sentinel STAC API for Recife bounds and returns latest scenes metadata.
    """
    scenes = query_sentinel_stac()
    return {
        "count": len(scenes),
        "results": scenes
    }
