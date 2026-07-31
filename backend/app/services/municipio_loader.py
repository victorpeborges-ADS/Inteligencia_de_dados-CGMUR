"""Carga automática de municípios prioritários via malhas IBGE."""
from __future__ import annotations

from app.timeutil import utc_now
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml
from geoalchemy2.shape import from_shape
from shapely.geometry import MultiPolygon, Point, Polygon, shape
from sqlalchemy.orm import Session

from app.data_connectors.orchestrator import IntegrationOrchestrator
from app.models import (
    AlertaCemaden,
    Bairro,
    CoberturaVegetalMapBiomas,
    HistoricoDesastreS2ID,
    InfraestruturaUrbana,
    Municipio,
    MunicipioSeed,
    SetorCensitario,
)
from app.services.analytical_engine import AnalyticalEngine

logger = logging.getLogger(__name__)

SEED_YAML = Path(__file__).resolve().parents[2] / "seeds" / "municipios_seed_50.yaml"
IBGE_MALHA_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{codigo}?qualidade=minima&formato=application/vnd.geo+json"

# População/área estimadas para carga inicial (substituídas pelo conector IBGE)
POPULACAO_ESTIMADA = {
    "3550308": 11450000,
    "3304557": 6211000,
    "3106200": 2315000,
    "2927408": 2418000,
    "2304400": 2573000,
    "2611606": 1489000,
    "4314902": 1333000,
    "1302603": 2063000,
    "5208707": 1437000,
    "4106902": 1777000,
}


def load_seed_manifest() -> List[Dict[str, Any]]:
    with SEED_YAML.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data.get("municipios", [])


def upsert_seed_rows(db: Session) -> int:
    count = 0
    for row in load_seed_manifest():
        existing = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == row["codigo_ibge"]).first()
        if existing:
            existing.nome = row["nome"]
            existing.uf = row["uf"]
            existing.criterio = row["criterio"]
            existing.decretos_emergencia = row.get("decretos", 0)
            existing.prioridade = row.get("prioridade", 0)
            existing.updated_at = utc_now()
        else:
            db.add(MunicipioSeed(
                codigo_ibge=row["codigo_ibge"],
                nome=row["nome"],
                uf=row["uf"],
                criterio=row["criterio"],
                decretos_emergencia=row.get("decretos", 0),
                prioridade=row.get("prioridade", 0),
                status_carga="pendente",
                lacunas=["geometria", "ibge", "siconfi", "saude", "seguranca"],
            ))
            count += 1
    db.commit()
    return count


def fetch_ibge_geometry(codigo_ibge: str) -> Tuple[Any, str]:
    try:
        response = requests.get(IBGE_MALHA_URL.format(codigo=codigo_ibge), timeout=20)
        response.raise_for_status()
        geojson = response.json()
        features = geojson.get("features") or []
        if not features:
            raise ValueError("GeoJSON vazio")
        geom = shape(features[0]["geometry"])
        if isinstance(geom, Polygon):
            geom = MultiPolygon([geom])
        elif not isinstance(geom, MultiPolygon):
            geom = MultiPolygon([part for part in geom.geoms if isinstance(part, Polygon)])
        if geom.is_empty:
            raise ValueError("Geometria vazia")
        return geom, "ibge_malhas_v3"
    except Exception as exc:
        logger.warning("Malha IBGE falhou para %s: %s", codigo_ibge, exc)
        min_x, min_y, max_x, max_y = -48.0, -16.0, -47.0, -15.0
        fallback = MultiPolygon([Polygon([[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y], [min_x, min_y]])])
        return fallback, "lacuna_bbox"


def _grid_cells(poly, count: int = 6):
    min_x, min_y, max_x, max_y = poly.bounds
    cols, rows = 3, 2
    dx = (max_x - min_x) / cols
    dy = (max_y - min_y) / rows
    cells = []
    for row in range(rows):
        for col in range(cols):
            if len(cells) >= count:
                return cells
            x1 = min_x + col * dx
            y1 = min_y + row * dy
            cell = Polygon([[x1, y1], [x1 + dx, y1], [x1 + dx, y1 + dy], [x1, y1 + dy], [x1, y1]])
            clipped = poly.intersection(cell)
            if clipped.is_empty:
                continue
            if isinstance(clipped, Polygon):
                clipped = MultiPolygon([clipped])
            elif not isinstance(clipped, MultiPolygon):
                clipped = MultiPolygon([part for part in clipped.geoms if isinstance(part, Polygon)])
            if not clipped.is_empty:
                cells.append(clipped)
    while len(cells) < count:
        cells.append(poly)
    return cells


def _minimal_layers(db: Session, muni: Municipio, risk: str = "inundacao") -> None:
    poly = shape(json.loads(db.scalar(muni.geom.ST_AsGeoJSON())))

    for model in (Bairro, SetorCensitario, HistoricoDesastreS2ID, AlertaCemaden, CoberturaVegetalMapBiomas, InfraestruturaUrbana):
        db.query(model).filter(model.municipio_id == muni.id).delete(synchronize_session=False)
    db.commit()

    from app.data_connectors.territorial_mesh_collector import sync_territorial_mesh

    sync_territorial_mesh(db, muni, force=True)

    from app.data_connectors.s2id_collector import collect_s2id_municipality

    collect_s2id_municipality(db, muni.codigo_ibge, force=True, risk=risk)
    cells = _grid_cells(poly, 6)
    db.add(AlertaCemaden(
        municipio_id=muni.id,
        nivel_alerta="MEDIO",
        descricao=f"Monitoramento climático — {muni.nome}",
        geom=from_shape(cells[0], srid=4326),
    ))
    db.commit()


def _apply_socioeconomic_calibration(db: Session, muni: Municipio) -> None:
    try:
        from app.services.socioeconomic_engine import enrich_municipal_socioeconomics

        enrich_municipal_socioeconomics(db, muni)
    except Exception as exc:
        logger.warning("Calibração socioeconômica falhou para %s: %s", muni.codigo_ibge, exc)


def compute_initial_score(db: Session, muni: Municipio) -> float:
    vuln = AnalyticalEngine.calculate_climate_vulnerability(db, muni.id)
    floods = AnalyticalEngine.calculate_flood_risk(db, muni.id)
    if not vuln or not floods:
        return 0.0
    avg_ivc = sum(v["indice_vulnerabilidade"] for v in vuln) / len(vuln)
    avg_iri = sum(f["indice_risco_inundacao"] for f in floods) / len(floods)
    avg_adapt = sum(v["capacidade_adaptacao"] for v in vuln) / len(vuln)
    return round(((avg_ivc * 0.45) + (avg_iri * 0.35) + ((1.0 - avg_adapt) * 0.20)) * 100, 3)


def load_municipio_from_seed(db: Session, seed: MunicipioSeed, skip_integrations: bool = False) -> Municipio:
    lacunas: List[str] = []
    geom, geom_fonte = fetch_ibge_geometry(seed.codigo_ibge)
    if geom_fonte == "lacuna_bbox":
        lacunas.append("geometria_ibge")

    muni = db.query(Municipio).filter(Municipio.codigo_ibge == seed.codigo_ibge).first()
    pop = POPULACAO_ESTIMADA.get(seed.codigo_ibge, max(50000, seed.decretos_emergencia * 8000))
    area = round(float(geom.area) * 12300, 2) if geom.area else 500.0

    if muni:
        muni.nome = seed.nome
        muni.uf = seed.uf
        muni.populacao = pop
        muni.area_km2 = area
        muni.geom = from_shape(geom, srid=4326)
    else:
        muni = Municipio(
            codigo_ibge=seed.codigo_ibge,
            nome=seed.nome,
            uf=seed.uf,
            populacao=pop,
            area_km2=area,
            geom=from_shape(geom, srid=4326),
        )
        db.add(muni)
    db.flush()

    risk = "encosta" if seed.uf in {"RJ", "ES"} and seed.criterio == "s2id_emergencia" else "inundacao"
    _minimal_layers(db, muni, risk=risk)
    _apply_socioeconomic_calibration(db, muni)

    if not skip_integrations:
        try:
            IntegrationOrchestrator(db).sync_all(codigos=[seed.codigo_ibge])
        except Exception as exc:
            logger.warning("Integração IBGE/Siconfi falhou para %s: %s", seed.codigo_ibge, exc)
            lacunas.extend(["ibge_indicadores", "siconfi"])

    score = compute_initial_score(db, muni)
    seed.score_sinidu = score
    seed.geom_fonte = geom_fonte
    seed.status_carga = "carregado" if not lacunas else "parcial"
    seed.lacunas = lacunas or ["saude", "seguranca"]
    seed.updated_at = utc_now()
    db.commit()
    db.refresh(muni)
    return muni


def load_all_pending(db: Session, limit: Optional[int] = None) -> Dict[str, int]:
    upsert_seed_rows(db)
    query = db.query(MunicipioSeed).filter(MunicipioSeed.status_carga.in_(["pendente", "parcial"])).order_by(MunicipioSeed.prioridade.asc())
    if limit:
        query = query.limit(limit)
    seeds = query.all()
    stats = {"processados": 0, "carregados": 0, "parciais": 0}
    for seed in seeds:
        load_municipio_from_seed(db, seed)
        stats["processados"] += 1
        if seed.status_carga == "carregado":
            stats["carregados"] += 1
        else:
            stats["parciais"] += 1
    return stats


def ensure_municipality_loaded(db: Session, codigo_ibge: str) -> Dict[str, Any]:
    """Garante município no PostGIS com camadas territoriais mínimas."""
    code = str(codigo_ibge).strip().zfill(7)[:7]
    existing = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if existing:
        bairros = db.query(Bairro).filter(Bairro.municipio_id == existing.id).count()
        if bairros > 0:
            return {
                "codigo_ibge": code,
                "nome": existing.nome,
                "uf": existing.uf,
                "municipio_id": existing.id,
                "loaded": True,
                "already_existed": True,
            }

    try:
        upsert_seed_rows(db)
    except Exception as exc:
        logger.warning("Manifesto YAML indisponível (%s); usando seed SQL.", exc)

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    if not seed:
        from app.services.onboarding_engine import ensure_seed_row, validate_ibge_code

        meta = validate_ibge_code(code)
        seed = ensure_seed_row(db, meta["codigo_ibge"], meta["nome"], meta["uf"])

    muni = load_municipio_from_seed(db, seed, skip_integrations=True)
    try:
        orchestrator = IntegrationOrchestrator(db)
        orchestrator._sync_ibge(code)
        orchestrator._sync_snis(code)
        db.commit()
    except Exception as exc:
        logger.warning("Integração rápida falhou para %s: %s", code, exc)
    try:
        from app.services.maturity_engine import persist_maturity

        persist_maturity(db, code)
    except Exception as exc:
        logger.warning("Maturidade não calculada para %s: %s", code, exc)

    db.refresh(muni)
    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    if seed:
        seed.status_carga = "parcial"
        seed.onboarding_status = seed.onboarding_status or "parcial"
        db.commit()

    return {
        "codigo_ibge": code,
        "nome": muni.nome,
        "uf": muni.uf,
        "municipio_id": muni.id,
        "loaded": True,
        "already_existed": False,
    }
