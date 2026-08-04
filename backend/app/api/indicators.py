import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from app.db import get_db
from app.models import Municipio, Bairro, SetorCensitario, CoberturaVegetalMapBiomas, HistoricoDesastreS2ID, AlertaCemaden, InfraestruturaUrbana, Edificacao, MunicipioIbge, MunicipioFiscal, MunicipioSeed, MunicipioSeguranca, MunicipioSaneamento, EscolaInep, TerritorioEspecial
from app.services.municipio_audit_service import audit_municipio
from app.config import settings
from app.schemas import ExecutiveIndicators, GeoJSONFeatureCollection
from app.services.analytical_engine import AnalyticalEngine
from app.seed_demo_municipalities import RENDA_REFERENCIA_MENSAL
from app.api.data_catalog import coverage_for_code
from app.assistant.siconfi_ia_bridge import build_siconfi_ia_url
from app.services.maturity_engine import classify_tier
from app.security.municipio_access import filter_municipio_query, filter_seed_query, get_accessible_municipio
from app.services.audit_service import resolve_actor
from app.data_connectors.mapbiomas_collector import vegetation_coverage_percent
from app.data_connectors.s2id_collector import s2id_quality_label
from app.data_connectors.territorial_mesh_collector import needs_territorial_refresh, sync_territorial_mesh
from app.data_connectors.official_bairros_collector import is_official_ibge_mesh
from app.data_connectors.mapbiomas_collector import ensure_spatial_coverage_polygons, needs_coverage_polygon_refresh
from app.services.socioeconomic_engine import RECIFE_BAIRRO_RENDA
from app.services.atlas_economico_service import build_atlas_uf_context
from app.services.layer_meta_registry import merge_layers_meta
from app.services.layer_temporal_service import resolve_layer_year, temporal_options_for_municipio
from app.services.regional_context_service import build_regional_overlay
from app.data_connectors.inep_educacao_collector import (
    ETAPAS_VALIDAS,
    etapa_dominante,
    matriculas_por_etapa,
    sync_educacao_municipio,
)
from app.data_connectors.territorios_especiais_collector import (
    TIPOS_VALIDOS,
    sync_territorios_municipio,
    territorio_matches_tipo,
    tipo_label,
)

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

    official_layers = {"municipio", "setores", "alertas"}
    derived_layers = {"cobertura", "vulnerabilidade", "inundacao", "desastres"}
    estimated_layers = {"bairros", "socioeconomico", "infraestrutura"}
    if layer_name in official_layers:
        return "Oficial"
    if layer_name in derived_layers:
        return "Derivado Sinidu+Clima"
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


def _drainage_risk_score(flood: dict, snis_deficit: float, has_snis: bool) -> tuple[float, str]:
    iri = float(flood.get("indice_risco_inundacao", 0.0))
    impermeabilizacao = float(flood.get("impermeabilizacao_score", 0.0))
    hidrografia = float(flood.get("hidrografia_proximidade_score", 0.0))
    if has_snis:
        score = min(1.0, (iri * 0.35) + (impermeabilizacao * 0.25) + (hidrografia * 0.15) + (snis_deficit * 0.25))
        explanation = "Score = 35% IRI + 25% impermeabilização + 15% prox. hidrografia + 25% déficit SNIS"
    else:
        score = min(1.0, (iri * 0.45) + (impermeabilizacao * 0.35) + (hidrografia * 0.20))
        explanation = "Score territorial (IRI + impermeab. + hidrografia) — SNIS/SINISA pendente"
    return round(score, 2), explanation


def _drainage_class(score: float) -> str:
    if score >= 0.66:
        return "CRITICA"
    if score >= 0.33:
        return "ATENCAO"
    return "MONITORAMENTO"


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = int(round((len(sorted_vals) - 1) * p))
    return sorted_vals[max(0, min(idx, len(sorted_vals) - 1))]


def _relative_tertile_class(value: float, p33: float, p66: float) -> str:
    if value >= p66:
        return "ALTA"
    if value <= p33:
        return "BAIXA"
    return "MEDIA"


@router.get("/layers/meta")
def get_layers_meta(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)

    bairro_count = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
    if bairro_count == 0:
        sync_territorial_mesh(db, muni, force=True)
    ensure_spatial_coverage_polygons(db, muni)

    snis = _snis_row(db, muni.codigo_ibge)
    saneamento_quality = quality_badge("saneamento_drenagem", db, muni.codigo_ibge)
    saneamento_source = "SNIS/SINISA + estimativa Sinidu+Clima"
    if snis and snis.data_quality == "oficial":
        saneamento_source = f"SNIS/SINISA ({snis.ano_referencia or 2022}) + risco territorial Sinidu+Clima"
    elif snis and snis.data_quality == "estimado":
        saneamento_source = f"SNIS proxy UF + risco territorial Sinidu+Clima"

    bairro_count = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
    infra_count = (
        db.query(InfraestruturaUrbana)
        .filter(InfraestruturaUrbana.municipio_id == muni.id)
        .count()
    )
    edificacoes_count = (
        db.query(Edificacao)
        .filter(Edificacao.municipio_id == muni.id)
        .count()
    )
    is_official_mesh = is_official_ibge_mesh(db, muni)
    is_recife_mesh = muni.codigo_ibge == "2611606" and bairro_count >= 85 and not is_official_mesh
    is_recife_infra = muni.codigo_ibge == "2611606" and infra_count >= 12
    is_recife_socio = muni.codigo_ibge == "2611606" and bairro_count >= 85 and len(RECIFE_BAIRRO_RENDA) >= 80
    cobertura_spatial = not needs_coverage_polygon_refresh(db, muni)
    s2id_count = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .count()
    )

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
    audit = audit_municipio(db, muni, persist=False)
    malha_fonte = seed.malha_fonte if seed and seed.malha_fonte else audit.get("malha_fonte")
    malha_disponivel = audit["flag_malha"] != "MALHA_AUSENTE"
    camadas_bloqueadas: list[str] = []
    if not malha_disponivel and muni.codigo_ibge != "2611606":
        camadas_bloqueadas = [
            "bairros",
            "socioeconomico",
            "vulnerabilidade",
            "inundacao",
            "prioridade_planejamento",
            "risco_consolidado",
            "saneamento_drenagem",
            "adaptacao_climatica",
            "saude_risco",
            "vulnerabilidade_multidimensional",
        ]

    bairros_quality = (
        "Oficial"
        if is_official_mesh or malha_fonte in {"prefeitura_oficial", "geoportal_municipal"}
        else ("Referencia" if is_recife_mesh else ("Estimado" if malha_disponivel else "Indisponível"))
    )
    if malha_fonte in {"prefeitura_oficial", "geoportal_municipal"}:
        bairros_source = "CTM municipal / geoportal da prefeitura (malha oficial de bairros)"
    elif is_official_mesh or malha_fonte in {"ibge_censo2022", "ibge_censo2022_setores"}:
        bairros_source = "IBGE Censo 2022 — malha oficial de bairros e setores censitários"
    elif is_recife_mesh:
        bairros_source = "CTM Recife / malha Voronoi calibrada Sinidu+Clima"
    elif malha_disponivel:
        bairros_source = "Geometria aproximada (Voronoi Sinidu+Clima)"
    else:
        bairros_source = "Malha de bairros não disponível para este município"

    dynamic_layers = {
            "bairros": {
                "quality": bairros_quality,
                "source": bairros_source,
                "count": bairro_count,
                "disponivel": malha_disponivel or muni.codigo_ibge == "2611606",
                "malha_fonte": malha_fonte,
                "tooltip_estimado": (
                    "Geometria aproximada. Dados socioeconômicos podem não refletir a realidade local."
                    if bairros_quality == "Estimado"
                    else None
                ),
            },
            "infraestrutura": {
                "quality": "Referencia" if is_recife_infra else quality_badge("infraestrutura"),
                "source": (
                    "OpenStreetMap / bases locais curadas (Recife)"
                    if is_recife_infra
                    else "OpenStreetMap / bases locais de infraestrutura urbana"
                ),
                "count": infra_count,
            },
            "edificacoes": {
                "quality": (
                    "Observado"
                    if edificacoes_count > 0
                    else "Estimado"
                ),
                "source": "OSM / Microsoft Building Footprints · altura OSM/nDSM/heurística (LOD1)",
                "count": edificacoes_count,
                "disponivel": True,
                "tiles_mvt": True,
            },
            "risco_consolidado": {
                "quality": "Derivado Sinidu+Clima",
                "source": "Score Sinidu (IVC+IRI+adaptação) × alerta vivo CEMADEN",
                "disponivel": malha_disponivel or muni.codigo_ibge == "2611606",
            },
            "hand_suscetibilidade": {
                "quality": "Derivado Sinidu+Clima",
                "source": "HAND (DEM D8) — altura acima da drenagem mais próxima",
                "disponivel": True,
            },
            "hidrografia_osm": {
                "quality": "Referencia",
                "source": "OpenStreetMap waterway (Overpass)",
                "disponivel": True,
            },
            "hazard_referencia": {
                "quality": "Referencia",
                "source": "JRC CEMS-GloFAS Flood Hazard RP100",
                "disponivel": True,
            },
            "cobertura": {
                "quality": (
                    "Referencia"
                    if muni.codigo_ibge == "2611606" and cobertura_spatial
                    else "Derivado Sinidu+Clima"
                ),
                "source": (
                    "MapBiomas Coleção 10.1 + partição espacial Sinidu+Clima"
                    if cobertura_spatial
                    else "MapBiomas stats + polígonos derivados (atualizando…)"
                ),
            },
            "socioeconomico": {
                "quality": "Referencia" if is_recife_socio else quality_badge("socioeconomico"),
                "source": (
                    "Renda CTM Recife (bairros) · clip UCN Pref. + OSM"
                    if is_recife_socio
                    else "IBGE Censo 2022 / SIDRA (quando recarregado)"
                ),
                "disponivel": malha_disponivel or muni.codigo_ibge == "2611606",
                "tooltip_estimado": (
                    "Déficits domiciliares distribuídos por setor a partir de taxas municipais SIDRA; "
                    "proxy intra-urbano calibrado por renda."
                ),
                "subcamadas": [
                    "renda",
                    "arborizacao",
                    "calcada",
                    "iluminacao",
                    "agua",
                    "esgoto",
                    "lixo",
                    "alfabetizacao",
                ],
            },
            "desastres": {
                "quality": (
                    s2id_quality_label(db, muni)
                    if s2id_count > 0
                    else quality_badge("desastres")
                ),
                "source": "S2ID / SEDEC — desastres naturais",
                "count": s2id_count,
            },
            "lst_observada": {
                "quality": "Observado",
                "source": "GeoReDUS / Landsat 8-9 — média máxima 2021–2025",
                "disponivel": True,
                "tooltip_estimado": (
                    "Dado observado por satélite; complementa a simulação exploratória Sinidu."
                ),
            },
            "educacao": {
                "quality": "Oficial",
                "source": f"INEP Censo Escolar {2023} — matrículas por etapa",
                "disponivel": True,
                "tooltip_estimado": (
                    "Tamanho proporcional às matrículas; buffer de influência configurável no painel."
                ),
            },
            "territorios_especiais": {
                "quality": "Oficial",
                "source": "INCRA / FUNAI / IBGE aglomerados subnormais — territórios tradicionais e periferias",
                "disponivel": True,
                "tooltip_estimado": (
                    "Quilombos certificados, terras indígenas e comunidades urbanas para VM e planejamento."
                ),
            },
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
            },
        }

    return {
        "codigo_ibge": muni.codigo_ibge,
        "malha_fonte": malha_fonte,
        "malha_disponivel": malha_disponivel,
        "camadas_bloqueadas": camadas_bloqueadas,
        "score_confiabilidade": audit.get("score_confiabilidade"),
        "confiabilidade_geral": audit.get("confiabilidade_geral"),
        "layers": merge_layers_meta(dynamic_layers),
    }


@router.get("/layers/temporal-options")
def get_layers_temporal_options(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return temporal_options_for_municipio(db, muni)


@router.get("/regional-overlay")
def get_regional_overlay(
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    escopo: str = Query(default="regiao_imediata"),
    db: Session = Depends(get_db),
):
    muni = get_accessible_municipio(db, codigo_ibge, request=request)
    return build_regional_overlay(db, muni, escopo=escopo)

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

    # Não sincronizar S2ID no GET do painel — bloqueava o worker único e atrasava a malha do mapa.
        
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
    
    # Cobertura vegetal — estatísticas MapBiomas (ha) sobre área municipal
    veg_percent, cobertura_qualidade = vegetation_coverage_percent(db, muni)
    veg_count = db.query(CoberturaVegetalMapBiomas).filter(
        CoberturaVegetalMapBiomas.municipio_id == muni.id
    ).count()
    if cobertura_qualidade == "lacuna" and veg_count > 0:
        cobertura_qualidade = "derivado"
    alertas_qualidade = "derivado" if alerts_count > 0 else "lacuna"
    desastres_qualidade = s2id_quality_label(db, muni) if disasters_count > 0 else "lacuna"
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
    pib_total_mil_reais = None
    pib_ano = None
    pib_serie = None
    idh = None
    idh_ano = None
    idh_fonte = None
    idh_qualidade = None
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
        if ibge_row.pib_total_mil_reais is not None:
            pib_total_mil_reais = float(ibge_row.pib_total_mil_reais)
            pib_ano = ibge_row.pib_ano
            if ibge_row.pib_serie:
                pib_serie = ibge_row.pib_serie
            if not pib_fonte:
                pib_fonte = "IBGE SIDRA agregado 5938/37"
                pib_qualidade = ibge_row.data_quality or "oficial"
        if ibge_row.idh:
            idh = float(ibge_row.idh)
            idh_ano = ibge_row.idh_ano
            idh_fonte = "Atlas DH / Ipeadata"
            idh_qualidade = "oficial"

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

    audit = audit_municipio(db, muni, persist=False)
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
    score_confiabilidade = (
        seed.score_confiabilidade if seed and seed.score_confiabilidade else audit.get("score_confiabilidade")
    )
    confiabilidade_geral = audit.get("confiabilidade_geral")
    malha_fonte = seed.malha_fonte if seed and seed.malha_fonte else audit.get("malha_fonte")

    atlas_uf_context = build_atlas_uf_context(muni.uf, codigo_ibge=muni.codigo_ibge)
    # Snapshot completo (IVC/IRI por bairro) é caro demais para o GET do painel —
    # usa score da auditoria já calculada acima.
    territorial = {
        "score_sinidu": int(round(float(audit["score_sinidu"]))) if audit.get("score_sinidu") is not None else None,
        "media_ivc": None,
        "media_iri": None,
        "media_adaptacao": None,
    }

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
        pib_total_mil_reais=pib_total_mil_reais,
        pib_ano=pib_ano,
        pib_serie=pib_serie,
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
        idh=idh,
        idh_ano=idh_ano,
        idh_fonte=idh_fonte,
        idh_qualidade=idh_qualidade,
        atlas_uf_context=atlas_uf_context,
        score_confiabilidade=score_confiabilidade,
        confiabilidade_geral=confiabilidade_geral,
        malha_fonte=malha_fonte,
        score_sinidu=territorial.get("score_sinidu"),
        media_ivc=territorial.get("media_ivc"),
        media_iri=territorial.get("media_iri"),
        media_adaptacao=territorial.get("media_adaptacao"),
    )

@router.get("/layers/{layer_name}", response_model=GeoJSONFeatureCollection)
def get_geojson_layer(
    layer_name: str,
    request: Request,
    codigo_ibge: str | None = Query(default=None),
    etapa: str | None = Query(default="todas"),
    tipo: str | None = Query(default="todas"),
    ano: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Returns the requested geospatial layer as a standard GeoJSON FeatureCollection.
    Supported layers: municipio, bairros, vulnerabilidade, inundacao, manchas_oficiais, hand_suscetibilidade,
    hidrografia_osm, hazard_referencia, socioeconomico, adaptacao_climatica, prioridade_planejamento,
    saneamento_drenagem, lacunas_dados, setores, desastres, alertas, cobertura, infraestrutura, educacao,
    territorios_especiais
    """
    muni = get_accessible_municipio(db, codigo_ibge, request=request)

    if layer_name == "lst_observada":
        raise HTTPException(
            status_code=400,
            detail="Camada raster LST — use GET /api/v1/map/lst-observada/config",
        )

    if layer_name in ("bairros", "infraestrutura"):
        bairro_count = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
        if bairro_count == 0:
            sync_territorial_mesh(db, muni, force=True)
    if layer_name == "cobertura":
        ensure_spatial_coverage_polygons(db, muni)
        
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
        audit = audit_municipio(db, muni, persist=False)
        if audit["flag_malha"] == "MALHA_AUSENTE" and muni.codigo_ibge != "2611606":
            return GeoJSONFeatureCollection(type="FeatureCollection", features=[])

        bairros = db.query(
            Bairro.id,
            Bairro.nome, Bairro.codigo_bairro,
            func.ST_AsGeoJSON(Bairro.geom).label("geojson")
        ).filter(Bairro.municipio_id == muni.id).all()

        setores = db.query(
            SetorCensitario.id,
            SetorCensitario.codigo_setor,
            func.ST_AsGeoJSON(SetorCensitario.geom).label("geojson"),
        ).filter(SetorCensitario.municipio_id == muni.id).all()

        from app.data_connectors.territorial_mesh_collector import GENERIC_BAIRRO_NAMES

        bairro_names = {b.nome for b in bairros}
        is_estimated_mesh = bool(bairro_names) and bairro_names <= GENERIC_BAIRRO_NAMES
        is_official_mesh = is_official_ibge_mesh(db, muni)
        # Bairros densos (≥8 oficiais): plotar bairros. Caso contrário, setores censitários.
        has_dense_bairros = len(bairros) >= 8 and is_official_mesh and not is_estimated_mesh
        use_setores = len(setores) >= 4 and not has_dense_bairros

        is_recife_mesh = muni.codigo_ibge == "2611606" and len(bairros) >= 85 and not is_official_mesh

        if use_setores:
            for s in setores:
                label = f"Setor {s.codigo_setor[-4:]}" if s.codigo_setor else "Setor"
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(s.geojson),
                    "properties": {
                        "nome": label,
                        "codigo_bairro": s.codigo_setor,
                        "fonte_referencia": "IBGE Censo 2022 — setores censitários",
                        "qualidade_dado": "Oficial",
                        "malha_fonte": "ibge_censo2022_setores",
                    },
                })
        else:
            seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == muni.codigo_ibge).first()
            malha_fonte = (seed.malha_fonte if seed and seed.malha_fonte else None) or (
                "ibge_censo2022" if is_official_mesh else ("estimado_sinidu" if not is_recife_mesh else "prefeitura_oficial")
            )
            is_ctm = malha_fonte in {"prefeitura_oficial", "geoportal_municipal"}
            for b in bairros:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(b.geojson),
                    "properties": {
                        "nome": b.nome,
                        "codigo_bairro": b.codigo_bairro,
                        "fonte_referencia": (
                            "CTM municipal / geoportal da prefeitura"
                            if is_ctm
                            else (
                                "IBGE Censo 2022 — malha oficial de bairros"
                                if is_official_mesh
                                else (
                                    "CTM Recife / malha Voronoi calibrada Sinidu+Clima"
                                    if is_recife_mesh
                                    else "Malha territorial estimada Sinidu+Clima (Voronoi)"
                                )
                            )
                        ),
                        "qualidade_dado": (
                            "Oficial"
                            if is_official_mesh or is_ctm
                            else ("Referencia" if is_recife_mesh else quality_badge(layer_name))
                        ),
                        "malha_fonte": malha_fonte,
                    }
                })

    elif layer_name in ("vulnerabilidade", "inundacao"):
        from shapely.geometry import shape as shp_shape, mapping as shp_mapping
        from shapely.validation import make_valid as shp_make_valid

        # Recife: IVC/IRI por bairro clipado à área habitável (UCN oficial + OSM).
        # Evita pintar reservas/mata (Guabiraba, Dois Irmãos…) como vulnerabilidade alta.
        use_recife_habitable = muni.codigo_ibge == "2611606"
        hab_mask = None
        extract_polygons = None
        if use_recife_habitable:
            try:
                from app.data_connectors.osm_landcover_collector import (
                    extract_polygons as _extract_polygons,
                    get_recife_habitable_mask,
                )

                extract_polygons = _extract_polygons
                muni_gj = db.scalar(func.ST_AsGeoJSON(muni.geom))
                muni_poly = shp_make_valid(shp_shape(json.loads(muni_gj))) if muni_gj else None
                hab_mask = get_recife_habitable_mask(muni_poly) if muni_poly is not None else None
            except Exception as exc:
                logger = __import__("logging").getLogger(__name__)
                logger.warning("máscara habitável IVC Recife: %s", exc)
                use_recife_habitable = False

        setores = (
            []
            if use_recife_habitable
            else db.query(
                SetorCensitario.id,
                SetorCensitario.codigo_setor,
                func.ST_AsGeoJSON(SetorCensitario.geom).label("geojson"),
            )
            .filter(SetorCensitario.municipio_id == muni.id)
            .all()
        )

        if (not use_recife_habitable) and len(setores) >= 4:
            if layer_name == "vulnerabilidade":
                scores = {
                    item["id"]: item
                    for item in AnalyticalEngine.calculate_climate_vulnerability_setores(db, muni.id)
                }
            else:
                scores = {
                    item["id"]: item
                    for item in AnalyticalEngine.calculate_flood_risk_setores(db, muni.id)
                }

            ivc_tertis: tuple[float, float] | None = None
            if layer_name == "vulnerabilidade" and len(scores) >= 3:
                ordered_ivc = sorted(float(v.get("indice_vulnerabilidade", 0)) for v in scores.values())
                ivc_tertis = (_percentile(ordered_ivc, 0.33), _percentile(ordered_ivc, 0.66))

            for s in setores:
                properties = {
                    "nome": scores.get(s.id, {}).get("nome", f"Setor {s.codigo_setor[-4:]}"),
                    "codigo_setor": s.codigo_setor,
                    "layer": layer_name,
                    "granularidade": "setor_censitario",
                    "fonte_referencia": "Sinidu+Clima: IRI/IVC por setor (S2ID, MapBiomas, CEMADEN, hidrografia)",
                    "qualidade_dado": quality_badge(layer_name),
                }
                properties.update(scores.get(s.id, {}))
                if ivc_tertis and "indice_vulnerabilidade" in properties:
                    ivc = float(properties["indice_vulnerabilidade"])
                    properties["classe_vulnerabilidade"] = _relative_tertile_class(ivc, *ivc_tertis)
                    properties["classificacao_relativa"] = True
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(s.geojson),
                    "properties": properties,
                })
        else:
            bairro_objs = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()

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

            ivc_tertis = None
            if layer_name == "vulnerabilidade" and len(scores) >= 3:
                ordered_ivc = sorted(
                    float(v.get("indice_vulnerabilidade", 0)) for v in scores.values()
                )
                ivc_tertis = (_percentile(ordered_ivc, 0.33), _percentile(ordered_ivc, 0.66))

            fonte_hab = (
                "Sinidu+Clima IVC/IRI por bairro · só área habitável "
                "(exclui UCN Pref. Recife Lei 18.014/2014 + vegetação/água OSM)"
                if hab_mask is not None
                else "Sinidu+Clima: cruzamento de IBGE, MapBiomas, S2ID, CEMADEN e infraestrutura urbana"
            )

            for b in bairro_objs:
                try:
                    gj = db.scalar(func.ST_AsGeoJSON(b.geom))
                    geom = shp_shape(json.loads(gj)) if gj else None
                except (TypeError, json.JSONDecodeError, ValueError):
                    continue
                if geom is None or geom.is_empty:
                    continue
                geom_out = geom
                if hab_mask is not None and extract_polygons is not None:
                    try:
                        inter = extract_polygons(shp_make_valid(geom.intersection(hab_mask)))
                    except Exception:
                        continue
                    if inter is None or inter.is_empty or inter.area < 1e-9:
                        continue
                    geom_out = inter

                properties = {
                    "nome": b.nome,
                    "codigo_bairro": b.codigo_bairro,
                    "layer": layer_name,
                    "granularidade": "bairro",
                    "fonte_referencia": fonte_hab,
                    "qualidade_dado": (
                        "Referencia" if hab_mask is not None else quality_badge(layer_name)
                    ),
                    "mascarado_area_urbana": hab_mask is not None,
                }
                properties.update(scores.get(b.id, {}))
                if ivc_tertis and "indice_vulnerabilidade" in properties:
                    ivc = float(properties["indice_vulnerabilidade"])
                    properties["classe_vulnerabilidade"] = _relative_tertile_class(ivc, *ivc_tertis)
                    properties["classificacao_relativa"] = True
                features.append({
                    "type": "Feature",
                    "geometry": shp_mapping(geom_out),
                    "properties": properties,
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
        from app.services.socioeconomic_engine import (
            classify_renda_tertiles,
            classe_renda_from_value,
        )
        from shapely.geometry import shape as shp_shape, mapping as shp_mapping
        from shapely.validation import make_valid as shp_make_valid

        # Recife: renda CTM por bairro, clipada a área habitável
        # (exclui UCN oficial Pref. Recife + vegetação/água OSM)
        if muni.codigo_ibge == "2611606":
            from app.data_connectors.osm_landcover_collector import (
                extract_polygons,
                get_recife_habitable_mask,
            )

            muni_gj = db.scalar(func.ST_AsGeoJSON(muni.geom))
            muni_poly = shp_make_valid(shp_shape(json.loads(muni_gj))) if muni_gj else None
            hab_mask = get_recife_habitable_mask(muni_poly) if muni_poly is not None else None

            bairro_rows = (
                db.query(Bairro)
                .filter(Bairro.municipio_id == muni.id)
                .all()
            )

            clipped_bairros: list[tuple] = []
            for bairro_obj in bairro_rows:
                try:
                    gj = db.scalar(func.ST_AsGeoJSON(bairro_obj.geom))
                    geom = shp_shape(json.loads(gj)) if gj else None
                except (TypeError, json.JSONDecodeError, ValueError):
                    continue
                if geom is None or geom.is_empty:
                    continue
                geom_out = geom
                if hab_mask is not None:
                    try:
                        inter = extract_polygons(shp_make_valid(geom.intersection(hab_mask)))
                    except Exception:
                        continue
                    if inter is None or inter.is_empty or inter.area < 1e-9:
                        continue
                    geom_out = inter
                renda, renda_fonte = AnalyticalEngine._resolve_bairro_renda(db, muni, bairro_obj)
                area_deg = float(geom_out.area or 0.0)
                pop = float(bairro_obj.pop_censo2022 or 0)
                clipped_bairros.append((bairro_obj, geom_out, area_deg, pop, float(renda), renda_fonte))

            rendas = [row[4] for row in clipped_bairros]
            p33, p66 = classify_renda_tertiles(rendas)

            for b, geom_out, area_deg, pop, renda, renda_fonte in clipped_bairros:
                area_km2 = float(area_deg or 0.0) * 12300.0
                densidade = float(pop) / area_km2 if area_km2 > 0 and pop > 0 else 0.0
                classe_renda = classe_renda_from_value(renda, p33, p66)
                features.append({
                    "type": "Feature",
                    "geometry": shp_mapping(geom_out),
                    "properties": {
                        "layer": layer_name,
                        "nome_bairro": b.nome,
                        "codigo_bairro": b.codigo_bairro,
                        "populacao": int(pop) if pop else None,
                        "renda_media": round(renda, 2),
                        "densidade_demografica": round(densidade, 2),
                        "classe_renda": classe_renda,
                        "classificacao_relativa": True,
                        "limiar_p33": round(p33, 2),
                        "limiar_p66": round(p66, 2),
                        "mascarado_area_urbana": hab_mask is not None,
                        "fonte_renda": renda_fonte,
                        "fonte_referencia": (
                            "Renda CTM Recife por bairro · geometria habitável "
                            "(exclui UCN Pref. Recife Lei 18.014/2014 + vegetação/água OSM)"
                        ),
                        "qualidade_dado": "Referencia",
                    },
                })
        else:
            setores = db.query(
                SetorCensitario.codigo_setor,
                SetorCensitario.populacao,
                SetorCensitario.renda_media,
                SetorCensitario.deficits_censo_json,
                SetorCensitario.deficits_censo_fonte,
                func.ST_Area(SetorCensitario.geom).label("area_deg"),
                func.ST_AsGeoJSON(SetorCensitario.geom).label("geojson"),
            ).filter(SetorCensitario.municipio_id == muni.id).all()

            clipped_rows: list[tuple] = []
            for s in setores:
                try:
                    geom = shp_shape(json.loads(s.geojson)) if s.geojson else None
                except (TypeError, json.JSONDecodeError, ValueError):
                    continue
                if geom is None or geom.is_empty:
                    continue
                area_deg = float(s.area_deg or geom.area or 0.0)
                pop = float(s.populacao or 0)
                clipped_rows.append((s, geom, area_deg, pop))

            rendas = [float(s.renda_media or 0.0) for s, _, _, _ in clipped_rows]
            p33, p66 = classify_renda_tertiles(rendas)
            ibge_row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == muni.codigo_ibge).first()
            renda_qualidade = "derivado" if ibge_row and ibge_row.pib_per_capita else "estimado"

            for s, geom_out, area_deg, pop in clipped_rows:
                renda = float(s.renda_media or 0.0)
                area_km2 = float(area_deg or 0.0) * 12300.0
                densidade = float(pop) / area_km2 if area_km2 > 0 else 0.0
                classe_renda = classe_renda_from_value(renda, p33, p66)
                deficits = s.deficits_censo_json if isinstance(s.deficits_censo_json, dict) else {}
                deficit_composto = None
                if deficits:
                    vals = [float(v) for v in deficits.values() if v is not None]
                    deficit_composto = round(sum(vals) / len(vals), 1) if vals else None

                features.append({
                    "type": "Feature",
                    "geometry": shp_mapping(geom_out),
                    "properties": {
                        "layer": layer_name,
                        "codigo_setor": s.codigo_setor,
                        "populacao": int(pop),
                        "renda_media": renda,
                        "densidade_demografica": round(densidade, 2),
                        "classe_renda": classe_renda,
                        "classificacao_relativa": True,
                        "limiar_p33": round(p33, 2),
                        "limiar_p66": round(p66, 2),
                        "deficits_censo": deficits,
                        "deficit_composto_pct": deficit_composto,
                        "deficits_fonte": s.deficits_censo_fonte or "ibge_censo2022_sidra_deficits",
                        "fonte_referencia": (
                            "IBGE Censo 2022 / SIDRA — déficits domiciliares e renda por setor"
                            if deficits
                            else "IBGE PIB municipal + gradiente intra-urbano calibrado"
                        ),
                        "qualidade_dado": "Referencia" if deficits else renda_qualidade,
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
        from shapely.geometry import shape as shp_shape, mapping as shp_mapping
        from shapely.validation import make_valid as shp_make_valid

        snis = _snis_row(db, muni.codigo_ibge)
        snis_deficit = _saneamento_deficit(snis)
        has_snis = bool(snis and snis.data_quality in ("oficial", "estimado"))

        # Recife: bairros + máscara habitável (evita timeout nos 2.8k setores e pintar reservas).
        use_recife_habitable = muni.codigo_ibge == "2611606"
        hab_mask = None
        extract_polygons = None
        if use_recife_habitable:
            try:
                from app.data_connectors.osm_landcover_collector import (
                    extract_polygons as _extract_polygons,
                    get_recife_habitable_mask,
                )

                extract_polygons = _extract_polygons
                muni_gj = db.scalar(func.ST_AsGeoJSON(muni.geom))
                muni_poly = shp_make_valid(shp_shape(json.loads(muni_gj))) if muni_gj else None
                hab_mask = get_recife_habitable_mask(muni_poly) if muni_poly is not None else None
            except Exception as exc:
                logger = __import__("logging").getLogger(__name__)
                logger.warning("máscara habitável saneamento/adaptação Recife: %s", exc)

        setores = (
            []
            if use_recife_habitable
            else db.query(
                SetorCensitario.id,
                SetorCensitario.codigo_setor,
                func.ST_AsGeoJSON(SetorCensitario.geom).label("geojson"),
            )
            .filter(SetorCensitario.municipio_id == muni.id)
            .all()
        )

        need_vuln = layer_name in ("adaptacao_climatica", "prioridade_planejamento")

        if (not use_recife_habitable) and len(setores) >= 4:
            vulnerability = (
                {
                    item["id"]: item
                    for item in AnalyticalEngine.calculate_climate_vulnerability_setores(db, muni.id)
                }
                if need_vuln
                else {}
            )
            flood = {
                item["id"]: item
                for item in AnalyticalEngine.calculate_flood_risk_setores(db, muni.id)
            }
            units = [
                {
                    "id": s.id,
                    "code": s.codigo_setor,
                    "geojson": s.geojson,
                    "granularidade": "setor_censitario",
                    "nome": None,
                    "codigo_bairro": None,
                    "codigo_setor": s.codigo_setor,
                }
                for s in setores
            ]
        else:
            bairro_objs = db.query(Bairro).filter(Bairro.municipio_id == muni.id).all()
            vulnerability = (
                {
                    item["id"]: item
                    for item in AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
                }
                if need_vuln
                else {}
            )
            flood = {
                item["id"]: item
                for item in AnalyticalEngine.calculate_flood_risk(db, muni.id)
            }
            units = []
            for b in bairro_objs:
                try:
                    gj = db.scalar(func.ST_AsGeoJSON(b.geom))
                except Exception:
                    continue
                if not gj:
                    continue
                geom_out_json = gj
                if hab_mask is not None and extract_polygons is not None:
                    try:
                        geom = shp_make_valid(shp_shape(json.loads(gj)))
                        inter = extract_polygons(shp_make_valid(geom.intersection(hab_mask)))
                    except Exception:
                        continue
                    if inter is None or inter.is_empty or inter.area < 1e-9:
                        continue
                    geom_out_json = json.dumps(shp_mapping(inter))
                units.append(
                    {
                        "id": b.id,
                        "code": b.codigo_bairro,
                        "geojson": geom_out_json,
                        "granularidade": "bairro",
                        "nome": b.nome,
                        "codigo_bairro": b.codigo_bairro,
                        "codigo_setor": None,
                    }
                )

        prioridade_tertis: tuple[float, float] | None = None
        if layer_name == "prioridade_planejamento" and len(units) >= 3:
            raw_scores: list[float] = []
            for unit in units:
                uid = unit["id"]
                v = vulnerability.get(uid, {})
                f = flood.get(uid, {})
                ivc = float(v.get("indice_vulnerabilidade", 0.0))
                iri = float(f.get("indice_risco_inundacao", 0.0))
                capacidade = float(v.get("capacidade_adaptacao", 0.0))
                raw_scores.append(round((ivc * 0.45) + (iri * 0.35) + ((1.0 - capacidade) * 0.20), 4))
            ordered = sorted(raw_scores)
            prioridade_tertis = (_percentile(ordered, 0.33), _percentile(ordered, 0.66))

        for unit in units:
            uid = unit["id"]
            geojson = unit["geojson"]
            granularidade = unit["granularidade"]
            nome = unit["nome"] or vulnerability.get(uid, {}).get("nome") or flood.get(uid, {}).get("nome") or f"Unidade {uid}"
            codigo_bairro = unit["codigo_bairro"]
            codigo_setor = unit["codigo_setor"]

            v = vulnerability.get(uid, {})
            f = flood.get(uid, {})
            ivc = float(v.get("indice_vulnerabilidade", 0.0))
            iri = float(f.get("indice_risco_inundacao", 0.0))
            capacidade = float(v.get("capacidade_adaptacao", 0.0))

            if layer_name == "adaptacao_climatica":
                properties = {
                    "layer": layer_name,
                    "nome": nome,
                    "codigo_bairro": codigo_bairro,
                    "codigo_setor": codigo_setor,
                    "granularidade": granularidade,
                    "capacidade_adaptacao": round(capacidade, 2),
                    "indice_vulnerabilidade": round(ivc, 2),
                    "classe_adaptacao": "ALTA" if capacidade >= 0.66 else ("MEDIA" if capacidade >= 0.33 else "BAIXA"),
                    "fonte_referencia": "MapBiomas / Adapta Brasil / equipamentos urbanos",
                    "qualidade_dado": (
                        "Referencia" if hab_mask is not None else quality_badge(layer_name)
                    ),
                    "mascarado_area_urbana": hab_mask is not None,
                }
            elif layer_name == "prioridade_planejamento":
                prioridade = round(((ivc * 0.45) + (iri * 0.35) + ((1.0 - capacidade) * 0.20)), 2)
                deficit_adaptacao = 1.0 - capacidade
                if prioridade_tertis:
                    p33, p66 = prioridade_tertis
                    classe = _relative_tertile_class(prioridade, p33, p66)
                    explicacao = (
                        f"Score = 45% IVC + 35% IRI + 20% déficit adaptação. "
                        f"Classe relativa ao município: alta ≥ {p66:.2f}, baixa ≤ {p33:.2f}."
                    )
                else:
                    classe = "ALTA" if prioridade >= 0.66 else ("MEDIA" if prioridade >= 0.33 else "BAIXA")
                    explicacao = "Score = 45% IVC + 35% IRI + 20% deficit de adaptacao"
                properties = {
                    "layer": layer_name,
                    "nome": nome,
                    "codigo_bairro": codigo_bairro,
                    "codigo_setor": codigo_setor,
                    "granularidade": granularidade,
                    "prioridade_planejamento": prioridade,
                    "indice_vulnerabilidade": round(ivc, 2),
                    "indice_risco_inundacao": round(iri, 2),
                    "capacidade_adaptacao": round(capacidade, 2),
                    "classe_prioridade": classe,
                    "classificacao_relativa": prioridade_tertis is not None,
                    "score_componentes": {
                        "vulnerabilidade_pct": round(ivc * 45, 1),
                        "inundacao_pct": round(iri * 35, 1),
                        "deficit_adaptacao_pct": round(deficit_adaptacao * 20, 1),
                    },
                    "score_explicacao": explicacao,
                    "fonte_referencia": (
                        "Alinhado ao Plano Diretor municipal · Score Sinidu+Clima (IVC+IRI+adaptação)"
                    ),
                    "qualidade_dado": (
                        "Referencia" if hab_mask is not None else quality_badge(layer_name)
                    ),
                    "mascarado_area_urbana": hab_mask is not None,
                }
            else:
                risco_drenagem, score_explicacao = _drainage_risk_score(f, snis_deficit, has_snis)
                fonte_base = (
                    f"{snis.fonte} (indicadores municipais oficiais) + IRI territorial Sinidu+Clima"
                    if snis and snis.fonte
                    else "SNIS/SINISA + estimativa territorial de drenagem Sinidu+Clima"
                )
                if hab_mask is not None:
                    fonte_base += " · só área habitável (UCN Pref. + OSM)"
                properties = {
                    "layer": layer_name,
                    "nome": nome,
                    "codigo_bairro": codigo_bairro,
                    "codigo_setor": codigo_setor,
                    "granularidade": granularidade,
                    "risco_drenagem": risco_drenagem,
                    "indice_risco_inundacao": round(iri, 2),
                    "impermeabilizacao_score": round(float(f.get("impermeabilizacao_score", 0.0)), 2),
                    "hidrografia_proximidade_score": round(float(f.get("hidrografia_proximidade_score", 0.0)), 2),
                    "classe_drenagem": _drainage_class(risco_drenagem),
                    "score_explicacao": score_explicacao,
                    "fonte_referencia": fonte_base,
                    "qualidade_dado": quality_badge(layer_name, db, muni.codigo_ibge),
                    "mascarado_area_urbana": hab_mask is not None,
                    "nota_geometria": (
                        "SNIS/SINISA não publica rede de drenagem georreferenciada por bairro; "
                        "espacialização usa malha de bairros + risco hídrico territorial."
                        if has_snis
                        else "Sem SNIS municipal — score só territorial."
                    ),
                }
                if snis:
                    properties["snis"] = {
                        "cobertura_agua_pct": float(snis.cobertura_agua_pct) if snis.cobertura_agua_pct is not None else None,
                        "cobertura_esgoto_pct": float(snis.cobertura_esgoto_pct) if snis.cobertura_esgoto_pct is not None else None,
                        "indice_perdas_agua_pct": float(snis.indice_perdas_agua_pct) if snis.indice_perdas_agua_pct is not None else None,
                        "indice_atendimento_esgoto_pct": float(snis.indice_atendimento_esgoto_pct) if snis.indice_atendimento_esgoto_pct is not None else None,
                        "deficit_saneamento_pct": round(snis_deficit * 100, 1),
                        "ano_referencia": snis.ano_referencia,
                        "data_quality": snis.data_quality,
                    }

            try:
                geometry = json.loads(geojson) if isinstance(geojson, str) else geojson
            except (TypeError, json.JSONDecodeError):
                continue
            features.append({
                "type": "Feature",
                "geometry": geometry,
                "properties": properties,
            })

    elif layer_name == "desastres":
        from app.data_connectors.s2id_collector import (
            build_s2id_enrichment_index,
            enrich_s2id_feature_props,
            ensure_s2id_loaded,
        )

        try:
            ensure_s2id_loaded(db, muni)
        except Exception as exc:
            logger = __import__("logging").getLogger(__name__)
            logger.warning("ensure_s2id_loaded desastres: %s", exc)

        ano_efetivo = resolve_layer_year(layer_name, ano, db, muni)
        desastres_q = db.query(
            HistoricoDesastreS2ID.tipo_desastre,
            HistoricoDesastreS2ID.data_ocorrencia,
            HistoricoDesastreS2ID.populacao_afetada,
            HistoricoDesastreS2ID.danos_materiais,
            HistoricoDesastreS2ID.referencia,
            HistoricoDesastreS2ID.data_quality,
            HistoricoDesastreS2ID.fonte,
            func.ST_AsGeoJSON(HistoricoDesastreS2ID.geom).label("geojson"),
        ).filter(
            HistoricoDesastreS2ID.municipio_id == muni.id,
            HistoricoDesastreS2ID.geom.isnot(None),
        )
        if ano_efetivo is not None:
            desastres_q = desastres_q.filter(
                extract("year", HistoricoDesastreS2ID.data_ocorrencia) == ano_efetivo
            )
        desastres = desastres_q.order_by(HistoricoDesastreS2ID.data_ocorrencia.desc()).all()
        s2id_count = len(desastres)
        enrichment = build_s2id_enrichment_index(muni.codigo_ibge)
        for d in desastres:
            if not d.geojson:
                continue
            props = enrich_s2id_feature_props(
                tipo_desastre=d.tipo_desastre,
                data_ocorrencia=d.data_ocorrencia,
                populacao_afetada=d.populacao_afetada,
                danos_materiais=float(d.danos_materiais or 0),
                referencia=d.referencia,
                data_quality=d.data_quality,
                fonte=d.fonte,
                enrichment=enrichment,
                eventos_municipio=s2id_count,
            )
            features.append({
                "type": "Feature",
                "geometry": json.loads(d.geojson),
                "properties": props,
            })
            
    elif layer_name == "manchas_oficiais":
        from app.services.official_flood_map_service import load_official_flood_geojson

        official = load_official_flood_geojson(muni.codigo_ibge)
        if official:
            official_feats = (
                official.get("features")
                if official.get("type") == "FeatureCollection"
                else [official]
            )
            for feat in official_feats or []:
                geom = feat.get("geometry")
                if not geom:
                    continue
                props = dict(feat.get("properties") or {})
                props.setdefault("fonte_referencia", props.get("fonte") or "Estudo/mancha oficial depositada")
                props.setdefault("qualidade_dado", props.get("qualidade") or "Oficial")
                features.append({
                    "type": "Feature",
                    "geometry": geom,
                    "properties": props,
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
        ano_efetivo = resolve_layer_year(layer_name, ano, db, muni)
        coberturas_q = db.query(
            CoberturaVegetalMapBiomas.classe_uso, CoberturaVegetalMapBiomas.ano,
            func.ST_AsGeoJSON(CoberturaVegetalMapBiomas.geom).label("geojson")
        ).filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
        if ano_efetivo is not None:
            coberturas_q = coberturas_q.filter(CoberturaVegetalMapBiomas.ano == ano_efetivo)
        coberturas = coberturas_q.all()
        is_recife_osm = muni.codigo_ibge == "2611606" and len(coberturas) >= 3
        for c in coberturas:
            features.append({
                "type": "Feature",
                "geometry": json.loads(c.geojson),
                "properties": {
                    "classe_uso": c.classe_uso,
                    "ano": c.ano,
                    "fonte_referencia": (
                        "OpenStreetMap (água, parques, mata) + eixos fluviais · ha MapBiomas Coleção 10.1"
                        if is_recife_osm
                        else "MapBiomas / Observatorio do Clima"
                    ),
                    "qualidade_dado": "Referencia" if is_recife_osm else quality_badge(layer_name),
                }
            })
            
    elif layer_name == "infraestrutura":
        # Recife: garante inventário ampliado (escolas/creches/faculdades/UPAs/hospitais)
        if muni.codigo_ibge == "2611606":
            infra_n = db.query(InfraestruturaUrbana).filter(
                InfraestruturaUrbana.municipio_id == muni.id,
                InfraestruturaUrbana.tipo != "via",
            ).count()
            if infra_n < 400:
                try:
                    from app.data_connectors.equipamentos_recife_collector import sync_equipamentos_recife
                    sync_equipamentos_recife(db, force=True, commit=True)
                except Exception as exc:
                    logger = __import__("logging").getLogger(__name__)
                    logger.warning("sync equipamentos Recife: %s", exc)

        items = db.query(
            InfraestruturaUrbana.tipo, InfraestruturaUrbana.nome, InfraestruturaUrbana.subgrupo,
            func.ST_AsGeoJSON(InfraestruturaUrbana.geom).label("geojson")
        ).filter(InfraestruturaUrbana.municipio_id == muni.id).all()
        is_recife_infra = muni.codigo_ibge == "2611606" and len(items) >= 400
        dep_ok = {"federal", "estadual", "municipal", "privada"}
        for item in items:
            sub = (item.subgrupo or "").strip().lower()
            dependencia = sub if sub in dep_ok else None
            if dependencia is None and sub:
                # legado: escola_federal → federal
                for key in dep_ok:
                    if key in sub:
                        dependencia = key
                        break
            features.append({
                "type": "Feature",
                "geometry": json.loads(item.geojson),
                "properties": {
                    "tipo": item.tipo,
                    "nome": item.nome,
                    "subgrupo": item.subgrupo,
                    "dependencia": dependencia,
                    "fonte_referencia": (
                        "Inventário Recife OSM+INEP (escolas, creches, faculdades, UPAs, hospitais) classificado por dependência"
                        if is_recife_infra
                        else "OpenStreetMap / bases locais de infraestrutura urbana"
                    ),
                    "qualidade_dado": "Referencia" if is_recife_infra else quality_badge(layer_name),
                },
            })

    elif layer_name == "edificacoes":
        from app.data_connectors.building_footprints_collector import buildings_geojson

        # Cap GeoJSON para mapas 2D; o 3D preferencialmente usa MVT (17f.10).
        limit_raw = request.query_params.get("limit") if request else None
        try:
            geo_limit = int(limit_raw) if limit_raw else 1500
        except (TypeError, ValueError):
            geo_limit = 1500
        geo_limit = max(100, min(geo_limit, 3500))
        fc = buildings_geojson(db, muni.codigo_ibge, ensure=True, limit=geo_limit)
        features.extend(fc.get("features") or [])

    elif layer_name == "hand_suscetibilidade":
        from app.services.hand_service import build_hand_bands_geojson

        fc = build_hand_bands_geojson(db, muni.codigo_ibge)
        for feat in fc.get("features") or []:
            features.append(feat)

    elif layer_name == "hidrografia_osm":
        from app.services.osm_hydrography_service import build_osm_hydrography_geojson

        fc = build_osm_hydrography_geojson(db, muni.codigo_ibge)
        for feat in fc.get("features") or []:
            features.append(feat)

    elif layer_name == "hazard_referencia":
        from app.services.glofas_hazard_service import build_glofas_rp100_geojson

        fc = build_glofas_rp100_geojson(db, muni.codigo_ibge)
        for feat in fc.get("features") or []:
            features.append(feat)

    elif layer_name == "risco_consolidado":
        from app.services.risco_consolidado_service import build_risco_consolidado_geojson

        fc = build_risco_consolidado_geojson(db, muni.codigo_ibge)
        features.extend(fc.get("features") or [])

    elif layer_name == "educacao":
        etapa_norm = (etapa or "todas").strip().lower()
        if etapa_norm not in ETAPAS_VALIDAS:
            etapa_norm = "todas"
        ano_efetivo = resolve_layer_year(layer_name, ano, db, muni)

        escola_count = db.query(EscolaInep).filter(EscolaInep.municipio_id == muni.id).count()
        if muni.codigo_ibge == "2611606" and escola_count < 200:
            try:
                from app.data_connectors.equipamentos_recife_collector import sync_equipamentos_recife
                sync_equipamentos_recife(db, force=True, commit=True)
                escola_count = db.query(EscolaInep).filter(EscolaInep.municipio_id == muni.id).count()
            except Exception as exc:
                logger = __import__("logging").getLogger(__name__)
                logger.warning("sync equipamentos educacao Recife: %s", exc)
        if escola_count == 0:
            sync_educacao_municipio(db, muni)
            db.commit()

        escolas_q = db.query(EscolaInep).filter(EscolaInep.municipio_id == muni.id)
        if ano_efetivo is not None:
            escolas_q = escolas_q.filter(EscolaInep.ano == ano_efetivo)
        escolas = escolas_q.all()

        for esc in escolas:
            geojson = (
                db.query(func.ST_AsGeoJSON(EscolaInep.geom))
                .filter(EscolaInep.id == esc.id)
                .scalar()
            )
            if not geojson:
                continue
            mat_ativa = matriculas_por_etapa(esc, etapa_norm)
            if etapa_norm != "todas" and mat_ativa <= 0:
                continue
            nome_u = (esc.nome or "").upper()
            loc = (esc.localizacao or "").lower()
            if "|faculdade" in loc or any(
                k in nome_u for k in ("UNIVERSIDADE", "FACULDADE", "CENTRO UNIVERSITÁRIO", "CENTRO UNIVERSITARIO", "IFPE", "UFPE", "UFRPE")
            ):
                tipo_educ = "faculdade"
            elif "|creche" in loc or (
                (esc.matriculas_infantil or 0) > 0
                and (esc.matriculas_fundamental or 0) == 0
                and (esc.matriculas_medio or 0) == 0
            ):
                tipo_educ = "creche"
            elif any(k in nome_u for k in ("CRECHE", "EMEI", "CMEI", "EDUCAÇÃO INFANTIL", "EDUCACAO INFANTIL")):
                tipo_educ = "creche"
            else:
                tipo_educ = "escola"
            features.append({
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {
                    "codigo_inep": esc.codigo_inep,
                    "nome": esc.nome,
                    "tipo": tipo_educ,
                    "dependencia": esc.dependencia,
                    "localizacao": esc.localizacao,
                    "ano": esc.ano,
                    "etapa": etapa_norm,
                    "etapa_dominante": etapa_dominante(esc),
                    "matriculas_total": int(esc.matriculas_total or 0),
                    "matriculas_infantil": int(esc.matriculas_infantil or 0),
                    "matriculas_fundamental": int(esc.matriculas_fundamental or 0),
                    "matriculas_medio": int(esc.matriculas_medio or 0),
                    "matriculas_ativas": mat_ativa,
                    "fonte_referencia": f"INEP Censo Escolar {esc.ano or 2023}",
                    "qualidade_dado": "Oficial" if esc.data_quality == "oficial" else "Estimado",
                },
            })

    elif layer_name == "territorios_especiais":
        tipo_norm = (tipo or "todas").strip().lower()
        if tipo_norm not in TIPOS_VALIDOS:
            tipo_norm = "todas"

        terr_count = db.query(TerritorioEspecial).filter(TerritorioEspecial.municipio_id == muni.id).count()
        if terr_count == 0:
            sync_territorios_municipio(db, muni)
            db.commit()

        territorios = db.query(TerritorioEspecial).filter(TerritorioEspecial.municipio_id == muni.id).all()
        for terr in territorios:
            if not territorio_matches_tipo(terr, tipo_norm):
                continue
            geojson = (
                db.query(func.ST_AsGeoJSON(TerritorioEspecial.geom))
                .filter(TerritorioEspecial.id == terr.id)
                .scalar()
            )
            if not geojson:
                continue
            features.append({
                "type": "Feature",
                "geometry": json.loads(geojson),
                "properties": {
                    "nome": terr.nome,
                    "tipo": terr.tipo,
                    "tipo_label": tipo_label(terr.tipo),
                    "codigo_oficial": terr.codigo_oficial,
                    "populacao_estimada": terr.populacao_estimada,
                    "ano": terr.ano,
                    "fonte_referencia": terr.fonte or "INCRA / FUNAI / IBGE",
                    "qualidade_dado": "Oficial" if terr.data_quality == "oficial" else "Estimado",
                    "layer": layer_name,
                },
            })

    elif layer_name == "saude_risco":
        for pt in AnalyticalEngine.health_risk_points(db, muni.id):
            features.append({
                "type": "Feature",
                "geometry": json.loads(pt["geom_json"]),
                "properties": {
                    "layer": layer_name,
                    "feature_kind": "estabelecimento",
                    "nome": pt["nome"],
                    "tipo": pt["tipo"],
                    "leitos_sus": pt["leitos_sus"],
                    "bairro": pt["bairro"],
                    "cobertura_classe": pt["cobertura_classe"],
                    "distancia_maior_risco_km": pt["distancia_maior_risco_km"],
                    "indice_vulnerabilidade": pt.get("indice_vulnerabilidade"),
                    "indice_risco_inundacao": pt.get("indice_risco_inundacao"),
                    "fonte_referencia": "CNES/DataSUS × risco climático Sinidu+Clima",
                    "qualidade_dado": quality_badge(layer_name),
                },
            })
        for sec in AnalyticalEngine.health_risk_setores(db, muni.id):
            features.append({
                "type": "Feature",
                "geometry": json.loads(sec["geom_json"]),
                "properties": {
                    "layer": layer_name,
                    "feature_kind": "setor_pressao",
                    "nome": sec["nome"],
                    "codigo_setor": sec["codigo_setor"],
                    "pressao_assistencial": sec["pressao_assistencial"],
                    "cobertura_classe": sec["cobertura_classe"],
                    "granularidade": "setor_censitario",
                    "fonte_referencia": "Pressão assistencial = IVC + IRI + distância ao equipamento mais próximo",
                    "qualidade_dado": quality_badge(layer_name),
                },
            })

    elif layer_name == "seguranca_publica":
        seg = (
            db.query(MunicipioSeguranca)
            .filter(MunicipioSeguranca.codigo_ibge == muni.codigo_ibge)
            .order_by(MunicipioSeguranca.mes_ref.desc())
            .first()
        )
        taxa = float(seg.taxa_100k) if seg and seg.taxa_100k else 120.0

        setor_rows = AnalyticalEngine.security_intensity_setores(db, muni.id, taxa)
        if setor_rows:
            for row in setor_rows:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(row["geom_json"]),
                    "properties": {
                        "layer": layer_name,
                        "nome": row["nome"],
                        "codigo_setor": row["codigo_setor"],
                        "granularidade": "setor_censitario",
                        "taxa_violenta_100k": round(taxa, 1),
                        "intensidade_seguranca": row["intensidade_seguranca"],
                        "classe_intensidade": row["classe_intensidade"],
                        "classificacao_relativa": True,
                        "indice_vulnerabilidade": row["indice_vulnerabilidade"],
                        "estresse_renda": row["estresse_renda"],
                        "ocorrencias_violentas": seg.ocorrencias_violentas if seg else None,
                        "score_explicacao": (
                            f"Intensidade = 22% taxa municipal ({taxa:.0f}/100k) + 32% estresse de renda "
                            f"+ 26% IVC + 12% densidade + 8% IRI. Classe relativa (tertil intra-urbano)."
                        ),
                        "fonte_referencia": seg.fonte if seg else "SINESP/dados.gov.br + gradiente Sinidu+Clima",
                        "qualidade_dado": quality_badge(layer_name),
                    },
                })
        else:
            bairros = db.query(
                Bairro.id, Bairro.nome, Bairro.codigo_bairro,
                func.ST_AsGeoJSON(Bairro.geom).label("geojson"),
            ).filter(Bairro.municipio_id == muni.id).all()
            vm_rows = {r["id"]: r for r in AnalyticalEngine.calculate_multidimensional_vulnerability(db, muni.id)}
            for b in bairros:
                vm = vm_rows.get(b.id, {})
                intensidade = min(1.0, (taxa / 450.0) * (0.5 + float(vm.get("indice_vm", 0.4)) * 0.5))
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(b.geojson),
                    "properties": {
                        "layer": layer_name,
                        "nome": b.nome,
                        "granularidade": "bairro",
                        "taxa_violenta_100k": round(taxa, 1),
                        "intensidade_seguranca": round(intensidade, 3),
                        "classe_intensidade": "MEDIA",
                        "ocorrencias_violentas": seg.ocorrencias_violentas if seg else None,
                        "fonte_referencia": seg.fonte if seg else "SINESP/dados.gov.br",
                        "qualidade_dado": quality_badge(layer_name),
                    },
                })

    elif layer_name == "vulnerabilidade_multidimensional":
        vm_rows = AnalyticalEngine.calculate_multidimensional_vulnerability_setores(db, muni.id)
        if vm_rows:
            for row in vm_rows:
                features.append({
                    "type": "Feature",
                    "geometry": json.loads(row["geom_json"]),
                    "properties": {
                        "layer": layer_name,
                        "nome": row["nome"],
                        "codigo_setor": row["codigo_setor"],
                        "granularidade": "setor_censitario",
                        "indice_vm": row["indice_vm"],
                        "classe_vm": row["classe_vm"],
                        "classificacao_relativa": row["classificacao_relativa"],
                        "risco_climatico": row["risco_climatico"],
                        "vulnerabilidade_social": row["vulnerabilidade_social"],
                        "cobertura_saude_inv": row["cobertura_saude_inv"],
                        "cobertura_seguranca_inv": row["cobertura_seguranca_inv"],
                        "capacidade_fiscal_inv": row["capacidade_fiscal_inv"],
                        "vulnerabilidade_multidimensional": row["vulnerabilidade_multidimensional"],
                        "score_explicacao": row["score_explicacao"],
                        "fonte_referencia": "VM Sinidu+Clima: clima + social + saúde + segurança + fiscal",
                        "qualidade_dado": "Derivado Sinidu+Clima",
                    },
                })
        else:
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
                        "granularidade": "bairro",
                        "indice_vm": vm.get("indice_vm", 0),
                        "classe_vm": "ALTA",
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
