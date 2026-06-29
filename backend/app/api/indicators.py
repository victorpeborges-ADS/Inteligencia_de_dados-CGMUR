import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.models import Municipio, Bairro, SetorCensitario, CoberturaVegetalMapBiomas, HistoricoDesastreS2ID, AlertaCemaden, InfraestruturaUrbana, MunicipioIbge, MunicipioFiscal, MunicipioSeed, MunicipioSeguranca, MunicipioSaneamento
from app.config import settings
from app.schemas import ExecutiveIndicators, GeoJSONFeatureCollection
from app.services.analytical_engine import AnalyticalEngine
from app.seed_demo_municipalities import RENDA_REFERENCIA_MENSAL
from app.api.data_catalog import coverage_for_code
from app.assistant.siconfi_ia_bridge import build_siconfi_ia_url
from app.services.maturity_engine import classify_tier
from app.security.municipio_access import filter_municipio_query, filter_seed_query, get_accessible_municipio
from app.services.audit_service import resolve_actor

router = APIRouter()

def _snis_row(db: Session, codigo_ibge: str) -> MunicipioSaneamento | None:
    return db.query(MunicipioSaneamento).filter(MunicipioSaneamento.codigo_ibge == codigo_ibge).first()


def quality_badge(layer_name: str, db: Session | None = None, codigo_ibge: str | None = None):
    if layer_name == "saneamento_drenagem" and db and codigo_ibge:
        row = _snis_row(db, codigo_ibge)
        if row and row.data_quality == "oficial":
            return "Oficial"
        if row and row.data_quality == "estimado":
            return "Estimado"

    official_layers = {"municipio", "setores", "cobertura", "alertas", "desastres"}
    estimated_layers = {"bairros", "socioeconomico", "infraestrutura"}
    if layer_name in official_layers:
        return "Oficial"
    if layer_name in estimated_layers:
        return "Estimado"
    return "Derivado Sinidu+Clima"


def _saneamento_deficit(snis: MunicipioSaneamento | None) -> float:
    if not snis:
        return 0.0
    if snis.cobertura_esgoto_pct is not None:
        return max(0.0, 1.0 - float(snis.cobertura_esgoto_pct) / 100.0)
    if snis.cobertura_agua_pct is not None:
        return max(0.0, 1.0 - float(snis.cobertura_agua_pct) / 100.0)
    return 0.0


@router.get("/layers/meta")
def get_layers_meta(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    snis = _snis_row(db, muni.codigo_ibge)
    saneamento_quality = quality_badge("saneamento_drenagem", db, muni.codigo_ibge)
    saneamento_source = "SNIS/SINISA + estimativa Sinidu+Clima"
    if snis and snis.data_quality == "oficial":
        saneamento_source = f"SNIS/SINISA ({snis.ano_referencia or 2022}) + risco territorial Sinidu+Clima"
    elif snis and snis.data_quality == "estimado":
        saneamento_source = f"SNIS proxy UF + risco territorial Sinidu+Clima"

    return {
        "codigo_ibge": muni.codigo_ibge,
        "layers": {
            "saneamento_drenagem": {
                "quality": saneamento_quality,
                "source": saneamento_source,
                "snis": {
                    "cobertura_agua_pct": float(snis.cobertura_agua_pct) if snis and snis.cobertura_agua_pct is not None else None,
                    "cobertura_esgoto_pct": float(snis.cobertura_esgoto_pct) if snis and snis.cobertura_esgoto_pct is not None else None,
                    "indice_perdas_agua_pct": float(snis.indice_perdas_agua_pct) if snis and snis.indice_perdas_agua_pct is not None else None,
                    "indice_atendimento_esgoto_pct": float(snis.indice_atendimento_esgoto_pct) if snis and snis.indice_atendimento_esgoto_pct is not None else None,
                    "ano_referencia": snis.ano_referencia if snis else None,
                    "fonte": snis.fonte if snis else None,
                    "data_quality": snis.data_quality if snis else "lacuna",
                },
            }
        },
    }

@router.get("/municipalities")
def list_municipalities(request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request)
    query = filter_municipio_query(db.query(Municipio), actor)
    rows = query.order_by(Municipio.nome.asc()).all()
    return [
        {
            "id": row.id,
            "codigo_ibge": row.codigo_ibge,
            "nome": row.nome,
            "uf": row.uf,
            "populacao": row.populacao,
            "area_km2": float(row.area_km2),
        }
        for row in rows
    ]

@router.get("/seeds")
def list_seed_municipalities(request: Request, db: Session = Depends(get_db)):
    actor = resolve_actor(request)
    try:
        query = filter_seed_query(db.query(MunicipioSeed), actor)
        rows = query.order_by(MunicipioSeed.prioridade.asc(), MunicipioSeed.nome.asc()).all()
    except Exception:
        rows = []
    if rows:
        return [
            {
                "codigo_ibge": r.codigo_ibge,
                "nome": r.nome,
                "uf": r.uf,
                "criterio": r.criterio,
                "decretos_emergencia": r.decretos_emergencia,
                "score_sinidu": float(r.score_sinidu) if r.score_sinidu is not None else None,
                "status_carga": r.status_carga,
                "onboarding_status": getattr(r, "onboarding_status", None) or r.status_carga,
                "maturity_score": float(r.maturity_score) if getattr(r, "maturity_score", None) is not None else None,
                "completeness_score": float(r.completeness_score) if getattr(r, "completeness_score", None) is not None else None,
                "maturity_classificacao": classify_tier(float(r.maturity_score)) if getattr(r, "maturity_score", None) is not None else None,
                "lacunas": r.lacunas or [],
            }
            for r in rows
        ]
    # Fallback: YAML local quando tabela ainda não foi migrada
    import yaml
    from pathlib import Path
    yaml_path = Path(__file__).resolve().parents[2] / "seeds" / "municipios_seed_50.yaml"
    if yaml_path.exists():
        with yaml_path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh).get("municipios", [])
    return []

@router.get("/executive", response_model=ExecutiveIndicators)
def get_executive_indicators(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Returns general KPIs for the executive dashboard.
    """
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
        
    # Count of active alerts
    alerts_count = db.query(AlertaCemaden).filter(AlertaCemaden.municipio_id == muni.id).count()
    
    # Count of historical disasters
    disasters_count = db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == muni.id).count()
    damages_total = db.query(func.sum(HistoricoDesastreS2ID.danos_materiais)).filter(
        HistoricoDesastreS2ID.municipio_id == muni.id
    ).scalar()
    
    # Average income of census sectors
    avg_income = db.query(func.avg(SetorCensitario.renda_media)).filter(SetorCensitario.municipio_id == muni.id).scalar()
    reference_income = RENDA_REFERENCIA_MENSAL.get(muni.codigo_ibge)
    income_value = reference_income if reference_income is not None else float(avg_income or 0.0)
    
    # Calculate vegetation coverage percentage
    # Total forest area vs total municipal area
    total_area_deg = db.scalar(func.ST_Area(muni.geom))
    forest_area_deg = db.query(func.sum(func.ST_Area(CoberturaVegetalMapBiomas.geom))).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id,
        CoberturaVegetalMapBiomas.classe_uso == "Vegetação / Floresta"
    ).scalar()
    
    veg_percent = 0.0
    veg_count = db.query(CoberturaVegetalMapBiomas).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id
    ).count()
    if forest_area_deg and total_area_deg:
        veg_percent = (float(forest_area_deg) / float(total_area_deg)) * 100.0

    cobertura_qualidade = "derivado" if veg_count > 0 else "lacuna"
    alertas_qualidade = "derivado" if alerts_count > 0 else "lacuna"
    desastres_qualidade = "derivado" if disasters_count > 0 else "lacuna"
    renda_qualidade = "estimado"
    densidade_qualidade = "estimado"
        
    densidade = muni.populacao / float(muni.area_km2) if muni.area_km2 > 0 else 0

    ibge_row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == muni.codigo_ibge).first()
    fiscal_row = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == muni.codigo_ibge).first()

    populacao = muni.populacao
    area_km2 = float(muni.area_km2)
    populacao_fonte = "Estimativa demonstrativa interna"
    populacao_qualidade = "estimado"
    area_fonte = "Estimativa demonstrativa interna"
    area_qualidade = "estimado"
    pib_per_capita = None
    pib_fonte = None
    pib_qualidade = None
    selo_ibge = None
    selo_fiscal = None

    if ibge_row:
        if ibge_row.populacao:
            populacao = ibge_row.populacao
            populacao_fonte = ibge_row.fonte or "IBGE Cidades"
            populacao_qualidade = ibge_row.data_quality or "oficial"
            selo_ibge = f"Oficial IBGE {ibge_row.populacao_ano or 2022}"
            densidade_qualidade = populacao_qualidade
        if ibge_row.area_km2:
            area_km2 = float(ibge_row.area_km2)
            area_fonte = ibge_row.fonte or "IBGE Cidades"
            area_qualidade = ibge_row.data_quality or "oficial"
        if ibge_row.densidade_demografica:
            densidade = float(ibge_row.densidade_demografica)
            densidade_qualidade = ibge_row.data_quality or "oficial"
        if ibge_row.pib_per_capita:
            pib_per_capita = float(ibge_row.pib_per_capita)
            pib_fonte = ibge_row.fonte or "IBGE / PIB Municipal"
            pib_qualidade = ibge_row.data_quality or "oficial"
            if not selo_ibge:
                selo_ibge = f"Oficial IBGE {ibge_row.pib_ano or 2021}"

    fiscal_fonte = None
    fiscal_qualidade = None
    nota_capag = None
    capag_fonte = None
    receita_corrente_liquida = None
    despesa_pessoal_pct_rcl = None
    divida_consolidada = None
    divida_consolidada_pct_rcl = None
    fiscal_exercicio = None
    if fiscal_row:
        nota_capag = fiscal_row.nota_capag
        capag_fonte = fiscal_row.fonte
        receita_corrente_liquida = float(fiscal_row.receita_corrente_liquida) if fiscal_row.receita_corrente_liquida is not None else None
        despesa_pessoal_pct_rcl = float(fiscal_row.despesa_pessoal_pct_rcl) if fiscal_row.despesa_pessoal_pct_rcl is not None else None
        divida_consolidada = float(fiscal_row.divida_consolidada) if fiscal_row.divida_consolidada is not None else None
        fiscal_exercicio = fiscal_row.exercicio
        if receita_corrente_liquida and divida_consolidada:
            divida_consolidada_pct_rcl = round((divida_consolidada / receita_corrente_liquida) * 100, 2)
        fiscal_fonte = fiscal_row.fonte
        fiscal_qualidade = fiscal_row.data_quality
        if fiscal_row.receita_corrente_liquida is not None:
            selo_fiscal = f"Fiscal SICONFI {fiscal_row.exercicio or 2024}"

    siconfi_ia_url = build_siconfi_ia_url(muni.nome, muni.uf, f"Resumo fiscal de {muni.nome}")

    return ExecutiveIndicators(
        codigo_ibge=muni.codigo_ibge,
        nome=muni.nome,
        uf=muni.uf,
        populacao=populacao,
        area_km2=area_km2,
        cobertura_vegetal_percent=round(veg_percent, 2),
        densidade_demografica=round(densidade, 2),
        historico_desastres_count=disasters_count,
        alertas_ativos_count=alerts_count,
        renda_media_setores=round(float(income_value or 0.0), 2),
        renda_media_fonte="Estimativa demonstrativa calibrada por municipio; substituir por IBGE/PNAD ou cadastro local na carga oficial.",
        danos_materiais_total=round(float(damages_total or 0.0), 2),
        populacao_fonte=populacao_fonte,
        populacao_qualidade=populacao_qualidade,
        area_fonte=area_fonte,
        area_qualidade=area_qualidade,
        pib_per_capita=pib_per_capita,
        pib_fonte=pib_fonte,
        pib_qualidade=pib_qualidade,
        nota_capag=nota_capag,
        capag_fonte=capag_fonte,
        receita_corrente_liquida=receita_corrente_liquida,
        despesa_pessoal_pct_rcl=despesa_pessoal_pct_rcl,
        divida_consolidada=divida_consolidada,
        divida_consolidada_pct_rcl=divida_consolidada_pct_rcl,
        fiscal_exercicio=fiscal_exercicio,
        siconfi_ia_url=siconfi_ia_url,
        fiscal_fonte=fiscal_fonte,
        fiscal_qualidade=fiscal_qualidade,
        selo_ibge=selo_ibge,
        selo_fiscal=selo_fiscal,
        cobertura_qualidade=cobertura_qualidade,
        alertas_qualidade=alertas_qualidade,
        desastres_qualidade=desastres_qualidade,
        renda_qualidade=renda_qualidade,
        densidade_qualidade=densidade_qualidade,
    )

@router.get("/layers/{layer_name}", response_model=GeoJSONFeatureCollection)
def get_geojson_layer(
    layer_name: str,
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Returns the requested geospatial layer as a standard GeoJSON FeatureCollection.
    Supported layers: municipio, bairros, vulnerabilidade, inundacao, socioeconomico,
    adaptacao_climatica, prioridade_planejamento, saneamento_drenagem, lacunas_dados, setores,
    desastres, alertas, cobertura, infraestrutura
    """
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
        
    features = []
    
    if layer_name == "municipio":
        # Get municipal boundary
        res = db.query(
            Municipio.nome, Municipio.uf, Municipio.codigo_ibge,
            func.ST_AsGeoJSON(Municipio.geom).label("geojson")
        ).filter(Municipio.id == muni.id).first()
        if res:
            features.append({
                "type": "Feature",
                "geometry": json.loads(res.geojson),
                "properties": {
                    "nome": res.nome,
                    "uf": res.uf,
                    "codigo_ibge": res.codigo_ibge,
                    "fonte_referencia": "IBGE / Geocidades",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })
            
    elif layer_name == "bairros":
        # Get neighborhood boundaries
        bairros = db.query(
            Bairro.id,
            Bairro.nome, Bairro.codigo_bairro,
            func.ST_AsGeoJSON(Bairro.geom).label("geojson")
        ).filter(Bairro.municipio_id == muni.id).all()
        for b in bairros:
            features.append({
                "type": "Feature",
                "geometry": json.loads(b.geojson),
                "properties": {
                    "nome": b.nome,
                    "codigo_bairro": b.codigo_bairro,
                    "fonte_referencia": "Cadastro Territorial Multifinalitario municipal / CTM",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })

    elif layer_name in ("vulnerabilidade", "inundacao"):
        # The frontend can request thematic risk layers suggested by the assistant.
        bairros = db.query(
            Bairro.id,
            Bairro.nome,
            Bairro.codigo_bairro,
            func.ST_AsGeoJSON(Bairro.geom).label("geojson")
        ).filter(Bairro.municipio_id == muni.id).all()

        if layer_name == "vulnerabilidade":
            scores = {
                item["id"]: item
                for item in AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
            }
        else:
            scores = {
                item["id"]: item
                for item in AnalyticalEngine.calculate_flood_risk(db, muni.id)
            }

        for b in bairros:
            properties = {
                "nome": b.nome,
                "codigo_bairro": b.codigo_bairro,
                "layer": layer_name,
                "fonte_referencia": "Sinidu+Clima: cruzamento de IBGE, MapBiomas, S2ID, CEMADEN e infraestrutura urbana",
                "qualidade_dado": quality_badge(layer_name),
            }
            properties.update(scores.get(b.id, {}))
            features.append({
                "type": "Feature",
                "geometry": json.loads(b.geojson),
                "properties": properties
            })
            
    elif layer_name == "setores":
        # Get census sectors
        setores = db.query(
            SetorCensitario.codigo_setor, SetorCensitario.populacao, SetorCensitario.renda_media,
            func.ST_AsGeoJSON(SetorCensitario.geom).label("geojson")
        ).filter(SetorCensitario.municipio_id == muni.id).all()
        for s in setores:
            features.append({
                "type": "Feature",
                "geometry": json.loads(s.geojson),
                "properties": {
                    "codigo_setor": s.codigo_setor,
                    "populacao": s.populacao,
                    "renda_media": float(s.renda_media),
                    "fonte_referencia": "IBGE Censo / Setores censitarios",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })

    elif layer_name == "socioeconomico":
        # IBGE/Cidades/CTM socioeconomic lens over census sectors.
        setores = db.query(
            SetorCensitario.codigo_setor,
            SetorCensitario.populacao,
            SetorCensitario.renda_media,
            func.ST_Area(SetorCensitario.geom).label("area_deg"),
            func.ST_AsGeoJSON(SetorCensitario.geom).label("geojson")
        ).filter(SetorCensitario.municipio_id == muni.id).all()
        for s in setores:
            renda = float(s.renda_media or 0.0)
            area_km2 = float(s.area_deg or 0.0) * 12300.0
            densidade = float(s.populacao or 0) / area_km2 if area_km2 > 0 else 0.0
            if renda >= 5000:
                classe_renda = "ALTA"
            elif renda >= 3000:
                classe_renda = "MEDIA"
            else:
                classe_renda = "BAIXA"

            features.append({
                "type": "Feature",
                "geometry": json.loads(s.geojson),
                "properties": {
                    "layer": layer_name,
                    "codigo_setor": s.codigo_setor,
                    "populacao": s.populacao,
                    "renda_media": renda,
                    "densidade_demografica": round(densidade, 2),
                    "classe_renda": classe_renda,
                    "fonte_referencia": "IBGE Cidades / Cadastro Territorial Multifinalitário",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })

    elif layer_name == "lacunas_dados":
        maturidade, bases, gaps = coverage_for_code(muni.codigo_ibge, db)
        res = db.query(
            Municipio.nome, Municipio.uf, Municipio.codigo_ibge,
            func.ST_AsGeoJSON(Municipio.geom).label("geojson")
        ).filter(Municipio.id == muni.id).first()
        if res:
            features.append({
                "type": "Feature",
                "geometry": json.loads(res.geojson),
                "properties": {
                    "nome": res.nome,
                    "uf": res.uf,
                    "codigo_ibge": res.codigo_ibge,
                    "layer": layer_name,
                    "maturidade_dados": maturidade,
                    "classe_maturidade": "ALTA" if maturidade >= 75 else ("MEDIA" if maturidade >= 50 else "BAIXA"),
                    "lacunas_prioritarias": ", ".join([item["nome"] for item in gaps[:4]]),
                    "fonte_referencia": "Radar Sinidu+Clima de integração: SNIS/SINISA, S2ID, MapBiomas, CEMADEN, IBGE, INDE, SINTER e bases correlatas",
                    "qualidade_dado": "Derivado Sinidu+Clima"
                }
            })

    elif layer_name in ("adaptacao_climatica", "prioridade_planejamento", "saneamento_drenagem"):
        bairros = db.query(
            Bairro.id,
            Bairro.nome,
            Bairro.codigo_bairro,
            func.ST_AsGeoJSON(Bairro.geom).label("geojson")
        ).filter(Bairro.municipio_id == muni.id).all()

        vulnerability = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
        }
        flood = {
            item["id"]: item
            for item in AnalyticalEngine.calculate_flood_risk(db, muni.id)
        }

        snis = _snis_row(db, muni.codigo_ibge)
        snis_deficit = _saneamento_deficit(snis)

        for b in bairros:
            v = vulnerability.get(b.id, {})
            f = flood.get(b.id, {})
            ivc = float(v.get("indice_vulnerabilidade", 0.0))
            iri = float(f.get("indice_risco_inundacao", 0.0))
            capacidade = float(v.get("capacidade_adaptacao", 0.0))

            if layer_name == "adaptacao_climatica":
                properties = {
                    "layer": layer_name,
                    "nome": b.nome,
                    "codigo_bairro": b.codigo_bairro,
                    "capacidade_adaptacao": round(capacidade, 2),
                    "indice_vulnerabilidade": round(ivc, 2),
                    "classe_adaptacao": "ALTA" if capacidade >= 0.66 else ("MEDIA" if capacidade >= 0.33 else "BAIXA"),
                    "fonte_referencia": "MapBiomas / Adapta Brasil / equipamentos urbanos",
                    "qualidade_dado": quality_badge(layer_name)
                }
            elif layer_name == "prioridade_planejamento":
                prioridade = ((ivc * 0.45) + (iri * 0.35) + ((1.0 - capacidade) * 0.20))
                deficit_adaptacao = 1.0 - capacidade
                properties = {
                    "layer": layer_name,
                    "nome": b.nome,
                    "codigo_bairro": b.codigo_bairro,
                    "prioridade_planejamento": round(prioridade, 2),
                    "indice_vulnerabilidade": round(ivc, 2),
                    "indice_risco_inundacao": round(iri, 2),
                    "capacidade_adaptacao": round(capacidade, 2),
                    "classe_prioridade": "ALTA" if prioridade >= 0.66 else ("MEDIA" if prioridade >= 0.33 else "BAIXA"),
                    "score_componentes": {
                        "vulnerabilidade_pct": round(ivc * 45, 1),
                        "inundacao_pct": round(iri * 35, 1),
                        "deficit_adaptacao_pct": round(deficit_adaptacao * 20, 1),
                    },
                    "score_explicacao": "Score = 45% IVC + 35% IRI + 20% deficit de adaptacao",
                    "fonte_referencia": "Plano Diretor / Planos locais / CTM",
                    "qualidade_dado": quality_badge(layer_name)
                }
            else:
                if snis and snis.data_quality in ("oficial", "estimado"):
                    risco_drenagem = min(1.0, (iri * 0.55) + (snis_deficit * 0.45))
                    score_explicacao = "Score = 55% IRI territorial + 45% déficit SNIS (esgoto/água)"
                else:
                    risco_drenagem = iri
                    score_explicacao = "Score territorial (IRI) — SNIS/SINISA pendente"
                properties = {
                    "layer": layer_name,
                    "nome": b.nome,
                    "codigo_bairro": b.codigo_bairro,
                    "risco_drenagem": round(risco_drenagem, 2),
                    "impermeabilizacao_score": round(float(f.get("impermeabilizacao_score", 0.0)), 2),
                    "hidrografia_proximidade_score": round(float(f.get("hidrografia_proximidade_score", 0.0)), 2),
                    "classe_drenagem": "CRITICA" if risco_drenagem >= 0.66 else ("ATENCAO" if risco_drenagem >= 0.33 else "MONITORAMENTO"),
                    "score_explicacao": score_explicacao,
                    "fonte_referencia": (
                        f"{snis.fonte} + S2ID + estimativa territorial Sinidu+Clima"
                        if snis and snis.fonte
                        else "SNIS/SINISA + S2ID + estimativa de drenagem urbana na versão interna"
                    ),
                    "qualidade_dado": quality_badge(layer_name, db, muni.codigo_ibge),
                }
                if snis:
                    properties["snis"] = {
                        "cobertura_agua_pct": float(snis.cobertura_agua_pct) if snis.cobertura_agua_pct is not None else None,
                        "cobertura_esgoto_pct": float(snis.cobertura_esgoto_pct) if snis.cobertura_esgoto_pct is not None else None,
                        "indice_perdas_agua_pct": float(snis.indice_perdas_agua_pct) if snis.indice_perdas_agua_pct is not None else None,
                        "indice_atendimento_esgoto_pct": float(snis.indice_atendimento_esgoto_pct) if snis.indice_atendimento_esgoto_pct is not None else None,
                        "ano_referencia": snis.ano_referencia,
                        "data_quality": snis.data_quality,
                    }

            features.append({
                "type": "Feature",
                "geometry": json.loads(b.geojson),
                "properties": properties
            })
            
    elif layer_name == "desastres":
        # Get historical disasters
        desastres = db.query(
            HistoricoDesastreS2ID.tipo_desastre, HistoricoDesastreS2ID.data_ocorrencia,
            HistoricoDesastreS2ID.populacao_afetada, HistoricoDesastreS2ID.danos_materiais,
            func.ST_AsGeoJSON(HistoricoDesastreS2ID.geom).label("geojson")
        ).filter(HistoricoDesastreS2ID.municipio_id == muni.id).all()
        for d in desastres:
            features.append({
                "type": "Feature",
                "geometry": json.loads(d.geojson),
                "properties": {
                    "tipo_desastre": d.tipo_desastre,
                    "data_ocorrencia": str(d.data_ocorrencia),
                    "populacao_afetada": d.populacao_afetada,
                    "danos_materiais": float(d.danos_materiais),
                    "fonte_referencia": "S2ID / Secretaria Nacional de Protecao e Defesa Civil",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })
            
    elif layer_name == "alertas":
        # Get active warnings
        alertas = db.query(
            AlertaCemaden.nivel_alerta, AlertaCemaden.descricao, AlertaCemaden.data_alerta,
            func.ST_AsGeoJSON(AlertaCemaden.geom).label("geojson")
        ).filter(AlertaCemaden.municipio_id == muni.id).all()
        for a in alertas:
            features.append({
                "type": "Feature",
                "geometry": json.loads(a.geojson),
                "properties": {
                    "nivel_alerta": a.nivel_alerta,
                    "descricao": a.descricao,
                    "data_alerta": str(a.data_alerta),
                    "fonte_referencia": "CEMADEN / GeoRiscos",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })
            
    elif layer_name == "cobertura":
        # Get land use/vegetation cover
        coberturas = db.query(
            CoberturaVegetalMapBiomas.classe_uso, CoberturaVegetalMapBiomas.ano,
            func.ST_AsGeoJSON(CoberturaVegetalMapBiomas.geom).label("geojson")
        ).filter(CoberturaVegetalMapBiomas.municipio_id == muni.id).all()
        for c in coberturas:
            features.append({
                "type": "Feature",
                "geometry": json.loads(c.geojson),
                "properties": {
                    "classe_uso": c.classe_uso,
                    "ano": c.ano,
                    "fonte_referencia": "MapBiomas / Observatorio do Clima",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })
            
    elif layer_name == "infraestrutura":
        # Get schools, hospitals, roads
        items = db.query(
            InfraestruturaUrbana.tipo, InfraestruturaUrbana.nome, InfraestruturaUrbana.subgrupo,
            func.ST_AsGeoJSON(InfraestruturaUrbana.geom).label("geojson")
        ).filter(InfraestruturaUrbana.municipio_id == muni.id).all()
        for item in items:
            features.append({
                "type": "Feature",
                "geometry": json.loads(item.geojson),
                "properties": {
                    "tipo": item.tipo,
                    "nome": item.nome,
                    "subgrupo": item.subgrupo,
                    "fonte_referencia": "OpenStreetMap / bases locais de infraestrutura urbana",
                    "qualidade_dado": quality_badge(layer_name)
                }
            })

    elif layer_name == "saude_risco":
        for pt in AnalyticalEngine.health_risk_points(db, muni.id):
            features.append({
                "type": "Feature",
                "geometry": json.loads(pt["geom_json"]),
                "properties": {
                    "layer": layer_name,
                    "nome": pt["nome"],
                    "tipo": pt["tipo"],
                    "leitos_sus": pt["leitos_sus"],
                    "bairro": pt["bairro"],
                    "cobertura_classe": pt["cobertura_classe"],
                    "distancia_maior_risco_km": pt["distancia_maior_risco_km"],
                    "fonte_referencia": "CNES/DataSUS × risco climático Sinidu+Clima",
                    "qualidade_dado": quality_badge(layer_name),
                },
            })

    elif layer_name == "seguranca_publica":
        bairros = db.query(
            Bairro.id, Bairro.nome, Bairro.codigo_bairro,
            func.ST_AsGeoJSON(Bairro.geom).label("geojson"),
        ).filter(Bairro.municipio_id == muni.id).all()
        seg = (
            db.query(MunicipioSeguranca)
            .filter(MunicipioSeguranca.codigo_ibge == muni.codigo_ibge)
            .order_by(MunicipioSeguranca.mes_ref.desc())
            .first()
        )
        taxa = float(seg.taxa_100k) if seg and seg.taxa_100k else 120.0
        vm_rows = {r["id"]: r for r in AnalyticalEngine.calculate_multidimensional_vulnerability(db, muni.id)}
        for b in bairros:
            vm = vm_rows.get(b.id, {})
            intensidade = min(1.0, taxa / 500.0) * (0.6 + float(vm.get("indice_vm", 0.4)) * 0.4)
            features.append({
                "type": "Feature",
                "geometry": json.loads(b.geojson),
                "properties": {
                    "layer": layer_name,
                    "nome": b.nome,
                    "taxa_violenta_100k": round(taxa, 1),
                    "intensidade_seguranca": round(intensidade, 3),
                    "ocorrencias_violentas": seg.ocorrencias_violentas if seg else None,
                    "fonte_referencia": seg.fonte if seg else "SINESP/dados.gov.br",
                    "qualidade_dado": quality_badge(layer_name),
                },
            })

    elif layer_name == "vulnerabilidade_multidimensional":
        bairros = db.query(
            Bairro.id, Bairro.nome, Bairro.codigo_bairro,
            func.ST_AsGeoJSON(Bairro.geom).label("geojson"),
        ).filter(Bairro.municipio_id == muni.id).all()
        vm_map = {r["id"]: r for r in AnalyticalEngine.calculate_multidimensional_vulnerability(db, muni.id)}
        for b in bairros:
            vm = vm_map.get(b.id, {})
            features.append({
                "type": "Feature",
                "geometry": json.loads(b.geojson),
                "properties": {
                    "layer": layer_name,
                    "nome": b.nome,
                    "indice_vm": vm.get("indice_vm", 0),
                    "risco_climatico": vm.get("risco_climatico", 0),
                    "vulnerabilidade_social": vm.get("vulnerabilidade_social", 0),
                    "cobertura_saude_inv": vm.get("cobertura_saude_inv", 0),
                    "cobertura_seguranca_inv": vm.get("cobertura_seguranca_inv", 0),
                    "capacidade_fiscal_inv": vm.get("capacidade_fiscal_inv", 0),
                    "vulnerabilidade_multidimensional": vm.get("vulnerabilidade_multidimensional", False),
                    "fonte_referencia": "VM Sinidu+Clima: clima + social + saúde + segurança + fiscal",
                    "qualidade_dado": "Derivado Sinidu+Clima",
                },
            })

    else:
        raise HTTPException(status_code=400, detail=f"Layer '{layer_name}' not supported.")
        
    return GeoJSONFeatureCollection(features=features)
