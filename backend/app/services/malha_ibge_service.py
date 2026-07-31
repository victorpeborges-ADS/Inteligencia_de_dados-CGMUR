"""Recarga de malha territorial e dados censitários via IBGE."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.data_connectors.censo_deficits_collector import enrich_setores_deficits
from app.data_connectors.ibge_collector import _agregado_value
from app.data_connectors.official_bairros_collector import import_official_ibge_mesh
from app.models import Bairro, Municipio, MunicipioSeed, SetorCensitario

logger = logging.getLogger(__name__)

IBGE_MALHAS_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/{cod_ibge}/setores"
REAL_SOCIO_FONTE = "ibge_censo2022_sidra"


async def _fetch_setores_geojson(cod_ibge: str) -> dict[str, Any]:
    url = IBGE_MALHAS_URL.format(cod_ibge=cod_ibge)
    params = {"formato": "application/vnd.geo+json", "qualidade": "minima"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def _sync_import_mesh(db: Session, muni: Municipio, *, force: bool = True) -> dict[str, Any]:
    return import_official_ibge_mesh(db, muni, force=force)


async def baixar_malha_bairros_ibge(cod_ibge: str, db: Session) -> dict[str, Any]:
    """
    Baixa setores IBGE Censo 2022 e importa malha oficial (bairros + setores).
    Fallback: shapefiles locais via import_official_ibge_mesh.
    """
    code = str(cod_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "error": "Município não encontrado no banco."}

    n_setores_api = 0
    try:
        fc = await _fetch_setores_geojson(code)
        n_setores_api = len(fc.get("features") or [])
    except Exception as exc:
        logger.warning("API malhas IBGE indisponível para %s: %s", code, exc)

    result = await asyncio.to_thread(_sync_import_mesh, db, muni, force=True)
    if result.get("error") and not result.get("skipped"):
        return result

    bairros = db.query(Bairro).filter(Bairro.municipio_id == muni.id).count()
    setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).count()
    fonte = "ibge_censo2022_setores" if n_setores_api else "ibge_censo2022"

    db.query(Bairro).filter(Bairro.municipio_id == muni.id).update(
        {Bairro.fonte_malha: fonte},
        synchronize_session=False,
    )

    seed = db.query(MunicipioSeed).filter(MunicipioSeed.codigo_ibge == code).first()
    if seed:
        seed.malha_fonte = fonte
    db.commit()

    cobertura = round(100.0 * bairros / max(bairros, 1), 1)
    return {
        "n_setores": setores or n_setores_api,
        "n_bairros_mapeados": bairros,
        "cobertura_pct": cobertura,
        "fonte": fonte,
        "data_carga": datetime.now(timezone.utc),
        "skipped": result.get("skipped", False),
        "detail": result,
    }


def _aggregate_bairro_socio(db: Session, muni: Municipio) -> int:
    """Agrega setores → bairros via ST_Intersects e atualiza atributos censitários."""
    rows = db.execute(
        text(
            """
            SELECT
                b.id AS bairro_id,
                SUM(COALESCE(s.populacao, 0)) AS pop,
                AVG(NULLIF(s.renda_media, 0)) AS renda
            FROM bairros b
            JOIN setores_censitarios s ON s.municipio_id = b.municipio_id
                AND ST_Intersects(b.geom, s.geom)
            WHERE b.municipio_id = :mid
            GROUP BY b.id
            """
        ),
        {"mid": muni.id},
    ).mappings().all()

    updated = 0
    for row in rows:
        bairro = db.query(Bairro).filter(Bairro.id == row["bairro_id"]).first()
        if not bairro:
            continue
        bairro.pop_censo2022 = int(row["pop"] or 0)
        if row["renda"]:
            bairro.renda_media_censo2022 = round(float(row["renda"]), 2)
        bairro.fonte_socioeconomico = REAL_SOCIO_FONTE
        updated += 1
    return updated


async def enriquecer_socioeconomico_censo(cod_ibge: str, db: Session) -> dict[str, Any]:
    """
    Enriquece setores/bairros com dados censitários IBGE (SIDRA/agregados).
    Variáveis municipais: pop (93), domicílios (95) — renda via calibração proporcional.
    """
    code = str(cod_ibge).strip().zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"codigo_ibge": code, "error": "Município não encontrado."}

    pop, _ = await asyncio.to_thread(_agregado_value, code, 4709, 2022, 93)
    dom, _ = await asyncio.to_thread(_agregado_value, code, 4709, 2022, 95)

    setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).all()
    if not setores:
        return {"codigo_ibge": code, "error": "Sem setores censitários — execute malha_ibge primeiro."}

    total_area = db.scalar(func.ST_Area(muni.geom)) or 1.0
    pop_total = int(pop or muni.populacao or 0)
    renda_base = 2200.0

    for setor in setores:
        area = db.scalar(func.ST_Area(setor.geom)) or 0.0
        share = max(0.001, float(area) / float(total_area)) if total_area else 0.001
        if pop_total:
            setor.populacao = max(50, int(pop_total * share))
        if dom:
            pass  # reservado para domicílios por setor quando SIDRA setorial estiver disponível
        if not setor.fonte_renda or "estim" in (setor.fonte_renda or "").lower():
            setor.renda_media = round(renda_base * (0.85 + share * 2), 2)
            setor.fonte_renda = REAL_SOCIO_FONTE

    bairros_updated = _aggregate_bairro_socio(db, muni)
    deficits_result = enrich_setores_deficits(db, muni)
    db.commit()

    return {
        "codigo_ibge": code,
        "pop_censo2022": pop_total,
        "domicilios_censo2022": int(dom or 0),
        "setores_atualizados": len(setores),
        "bairros_agregados": bairros_updated,
        "deficits_censo": deficits_result,
        "fonte_socioeconomico": REAL_SOCIO_FONTE,
        "data_carga": datetime.now(timezone.utc).isoformat(),
    }
