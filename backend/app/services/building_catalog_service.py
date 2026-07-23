"""Catálogo do gêmeo digital 3D (17c.3) — metadados, fonte de altura e maturidade."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import Edificacao, Municipio
from app.services.building_3dtiles_service import status_3dtiles
from app.services.building_cityjson_service import status_citymodel

# Fontes de altura com qualidade acima da heurística padrão
_FONTES_REFINADAS = frozenset({
    "ndsm_lidar",
    "lidar",
    "osm_levels",
    "osm_height",
    "height",
    "building:levels",
})


def _muni(db: Session, codigo_ibge: str, muni: Municipio | None = None) -> Municipio | None:
    if muni is not None:
        return muni
    return db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()


def height_source_breakdown(db: Session, municipio_id: int) -> dict[str, int]:
    by_fonte: dict[str, int] = {}
    rows = (
        db.query(Edificacao.fonte_altura)
        .filter(Edificacao.municipio_id == municipio_id)
        .all()
    )
    for (fonte,) in rows:
        key = (fonte or "heuristic").strip() or "heuristic"
        by_fonte[key] = by_fonte.get(key, 0) + 1
    return by_fonte


def quality_breakdown(db: Session, municipio_id: int) -> dict[str, int]:
    by_q: dict[str, int] = {}
    rows = (
        db.query(Edificacao.qualidade)
        .filter(Edificacao.municipio_id == municipio_id)
        .all()
    )
    for (q,) in rows:
        key = (q or "Derivado").strip() or "Derivado"
        by_q[key] = by_q.get(key, 0) + 1
    return by_q


def maturity_3d_pct(count: int, by_fonte: dict[str, int], *, tiles: bool, city: bool) -> int:
    """Score 0–100 da maturidade do modelo 3D (footprints + altura + export)."""
    if count <= 0:
        return 0
    refined = sum(n for f, n in by_fonte.items() if f in _FONTES_REFINADAS)
    share = refined / count
    base = 35.0  # footprints OSM presentes
    base += min(40.0, share * 100.0 * 0.4)  # até +40 por altura refinada
    if tiles:
        base += 15.0
    if city:
        base += 10.0
    return int(round(min(100.0, base)))


def catalog_status_gemeo_digital(
    db: Session,
    codigo_ibge: str,
    *,
    muni: Municipio | None = None,
) -> str:
    """Status no catálogo: Ausente | Em integracao | Estimado | Integrado."""
    muni = _muni(db, codigo_ibge, muni)
    if not muni:
        return "Ausente"

    count = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    if count == 0:
        return "Ausente"

    by_fonte = height_source_breakdown(db, muni.id)
    refined = sum(n for f, n in by_fonte.items() if f in _FONTES_REFINADAS)
    share = refined / count

    tiles = bool(status_3dtiles(codigo_ibge).get("disponivel"))
    city = bool(status_citymodel(codigo_ibge).get("disponivel"))

    if share >= 0.2 and (tiles or city):
        return "Integrado"
    if share >= 0.05 or tiles or city or count >= 50:
        return "Estimado"
    return "Em integracao"


def catalog_meta_gemeo_digital(
    db: Session,
    codigo_ibge: str,
    *,
    muni: Municipio | None = None,
) -> dict[str, Any]:
    """Metadados ricos para coverage/enrich/preview do gêmeo digital."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = _muni(db, code, muni)
    if not muni:
        return {
            "codigo_ibge": code,
            "registros": 0,
            "status": "Ausente",
            "por_fonte_altura": {},
            "por_qualidade": {},
            "maturidade_3d_pct": 0,
            "lod": "LOD1",
            "tiles_3d": status_3dtiles(code),
            "citymodel": status_citymodel(code),
        }

    count = db.query(Edificacao).filter(Edificacao.municipio_id == muni.id).count()
    by_fonte = height_source_breakdown(db, muni.id) if count else {}
    by_q = quality_breakdown(db, muni.id) if count else {}
    tiles = status_3dtiles(code)
    city = status_citymodel(code)
    status = catalog_status_gemeo_digital(db, code, muni=muni)
    ultima = (
        db.query(Edificacao.atualizado_em)
        .filter(Edificacao.municipio_id == muni.id)
        .order_by(Edificacao.atualizado_em.desc())
        .first()
    )
    ultima_sync = ultima[0] if ultima else None

    return {
        "codigo_ibge": code,
        "registros": count,
        "status": status,
        "por_fonte_altura": by_fonte,
        "por_qualidade": by_q,
        "maturidade_3d_pct": maturity_3d_pct(
            count,
            by_fonte,
            tiles=bool(tiles.get("disponivel")),
            city=bool(city.get("disponivel")),
        ),
        "lod": "LOD1",
        "especificacao": "3D Tiles 1.0 + CityJSON 2.0 / CityGML 2.0 Building LOD1",
        "tiles_3d": tiles,
        "citymodel": city,
        "ultima_sync": ultima_sync.isoformat() if isinstance(ultima_sync, datetime) else None,
        "fonte_altura_predominante": (
            max(by_fonte.items(), key=lambda x: x[1])[0] if by_fonte else None
        ),
    }
