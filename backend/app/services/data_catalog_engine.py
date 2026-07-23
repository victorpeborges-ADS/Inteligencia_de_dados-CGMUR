"""Status dinâmico do catálogo de dados — derivado do banco, não só mock."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    AlertaCemaden,
    CoberturaVegetalMapBiomas,
    HistoricoDesastreS2ID,
    MapBiomasMunicipalStat,
    Municipio,
    MunicipioFiscal,
    MunicipioFonteExterna,
    MunicipioIbge,
    MunicipioSeed,
    MunicipioSaneamento,
    MunicipioSingedlabRs,
)
from app.data_connectors.singedlab_rs_collector import catalog_status_for_row
from app.data_connectors.snis_sinisa_collector import snis_status_label
from app.data_connectors.external_sources_collector import catalog_status_from_quality
from app.services.building_catalog_service import catalog_status_gemeo_digital

# Fallback demo para municípios piloto (compatibilidade)
_PILOT_FALLBACK: dict[str, dict[str, str]] = {
    "2611606": {
        "adapta_brasil": "Estimado",
        "geosgb": "Em integracao",
        "sinter": "Estimado",
        "munic": "Em integracao",
        "sirene": "Ausente",
        "inde": "Integrado",
        "brasil_mais": "Em integracao",
    },
}


def _status_ibge(db: Session, codigo_ibge: str, muni: Municipio | None) -> str:
    if not muni:
        return "Ausente"
    row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
    if row and row.populacao:
        return "Integrado"
    if muni.populacao:
        return "Estimado"
    return "Em integracao"


def _status_snis(db: Session, codigo_ibge: str) -> str:
    row = db.query(MunicipioSaneamento).filter(MunicipioSaneamento.codigo_ibge == codigo_ibge).first()
    if not row:
        return "Ausente"
    label = snis_status_label(row.data_quality)
    mapping = {"Integrado": "Integrado", "Estimado": "Estimado", "Em integração": "Em integracao", "Ausente": "Ausente"}
    return mapping.get(label, "Estimado")


def _status_s2id(db: Session, muni: Municipio | None) -> str:
    if not muni:
        return "Ausente"
    count = db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == muni.id).count()
    return "Integrado" if count else "Em integracao"


def _status_mapbiomas(db: Session, codigo_ibge: str, muni: Municipio | None) -> str:
    stats = (
        db.query(MapBiomasMunicipalStat)
        .filter(MapBiomasMunicipalStat.codigo_ibge == codigo_ibge)
        .count()
    )
    if stats >= 6:
        official = (
            db.query(MapBiomasMunicipalStat)
            .filter(
                MapBiomasMunicipalStat.codigo_ibge == codigo_ibge,
                MapBiomasMunicipalStat.data_quality.in_(("oficial", "referencia_mapbiomas")),
            )
            .count()
        )
        return "Integrado" if official >= 3 else "Estimado"
    if muni:
        count = db.query(CoberturaVegetalMapBiomas).filter(CoberturaVegetalMapBiomas.municipio_id == muni.id).count()
        if count >= 2:
            return "Estimado"
    return "Ausente"


def _status_cemaden(db: Session, muni: Municipio | None) -> str:
    if not muni:
        return "Ausente"
    count = db.query(AlertaCemaden).filter(AlertaCemaden.municipio_id == muni.id).count()
    return "Integrado" if count else "Em integracao"


def _status_fiscal(db: Session, codigo_ibge: str, field: str) -> str:
    row = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == codigo_ibge).first()
    if not row:
        return "Ausente"
    if field == "capag" and row.nota_capag:
        return "Integrado"
    if field == "siconfi" and (row.receita_corrente_liquida or row.resultado_primario):
        return "Integrado"
    return "Estimado"


def _status_from_seed(seed: MunicipioSeed | None, step_key: str) -> str | None:
    if not seed or not seed.integration_steps:
        return None
    step = seed.integration_steps.get(step_key) or {}
    status = step.get("status")
    quality = step.get("qualidade")
    if status == "ok":
        return "Integrado"
    if status in ("parcial", "estimado"):
        return "Estimado"
    if status == "lacuna":
        return "Em integracao"
    if status == "falha":
        return "Ausente"
    if quality == "oficial":
        return "Integrado"
    return None


def _status_singedlab(db: Session, codigo_ibge: str) -> str:
    row = db.query(MunicipioSingedlabRs).filter(MunicipioSingedlabRs.codigo_ibge == codigo_ibge).first()
    return catalog_status_for_row(row)


def resolve_catalog_status(
    db: Session,
    codigo_ibge: str,
    base_id: str,
    *,
    muni: Municipio | None = None,
    seed: MunicipioSeed | None = None,
) -> str:
    if muni is None:
        muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    if seed is None:
        seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == codigo_ibge).first()

    resolvers = {
        "ibge_cidades": lambda: _status_ibge(db, codigo_ibge, muni),
        "snis_sinisa": lambda: _status_snis(db, codigo_ibge),
        "s2id": lambda: _status_s2id(db, muni),
        "mapbiomas": lambda: _status_mapbiomas(db, codigo_ibge, muni),
        "cemaden_georiscos": lambda: _status_cemaden(db, muni),
        "ibge_singedlab_rs": lambda: _status_singedlab(db, codigo_ibge),
        "gemeo_digital_3d": lambda: catalog_status_gemeo_digital(db, codigo_ibge, muni=muni),
    }
    if base_id in resolvers:
        return resolvers[base_id]()

    if base_id == "adapta_brasil":
        ext = db.query(MunicipioFonteExterna).filter(MunicipioFonteExterna.codigo_ibge == codigo_ibge).first()
        if ext and ext.adapta_data_quality and ext.adapta_data_quality != "ausente":
            return catalog_status_from_quality(ext.adapta_data_quality)
        return _status_from_seed(seed, "camadas_territoriais") or _PILOT_FALLBACK.get(codigo_ibge, {}).get(base_id, "Em integracao" if muni else "Ausente")

    if base_id == "geosgb":
        ext = db.query(MunicipioFonteExterna).filter(MunicipioFonteExterna.codigo_ibge == codigo_ibge).first()
        if ext and ext.geosgb_data_quality and ext.geosgb_data_quality != "ausente":
            return catalog_status_from_quality(ext.geosgb_data_quality)
        fallback = _PILOT_FALLBACK.get(codigo_ibge, {}).get(base_id)
        if fallback:
            return fallback
        return "Em integracao" if muni else "Ausente"

    if base_id == "sirene":
        ext = db.query(MunicipioFonteExterna).filter(MunicipioFonteExterna.codigo_ibge == codigo_ibge).first()
        if ext and ext.sirene_data_quality and ext.sirene_data_quality != "ausente":
            return catalog_status_from_quality(ext.sirene_data_quality)
        return _PILOT_FALLBACK.get(codigo_ibge, {}).get(base_id, "Ausente")

    if base_id == "brasil_mais":
        ext = db.query(MunicipioFonteExterna).filter(MunicipioFonteExterna.codigo_ibge == codigo_ibge).first()
        if ext and ext.brasil_mais_data_quality and ext.brasil_mais_data_quality != "ausente":
            return catalog_status_from_quality(ext.brasil_mais_data_quality)
        fallback = _PILOT_FALLBACK.get(codigo_ibge, {}).get(base_id)
        if fallback:
            return fallback
        return "Em integracao" if muni else "Ausente"

    step_map = {
        "munic": "ibge_indicadores",
        "sinter": "siconfi",
        "inde": "geometria",
    }
    if base_id in step_map:
        derived = _status_from_seed(seed, step_map[base_id])
        if derived:
            return derived

    return "Ausente"
