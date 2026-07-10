"""Opções temporais por tema de camada — MapBiomas, S2ID, PIB, LST, INEP."""

from __future__ import annotations

from typing import Any

from sqlalchemy import extract, func
from sqlalchemy.orm import Session

from app.data_connectors.inep_educacao_collector import CENSO_ANO_DEFAULT
from app.models import (
    CoberturaVegetalMapBiomas,
    EscolaInep,
    HistoricoDesastreS2ID,
    MapBiomasMunicipalStat,
    Municipio,
    MunicipioIbge,
)
from app.services.georedus_lst_service import LST_PERIODO_LABEL

TEMPORAL_TEMAS = ("mapbiomas", "s2id", "inep", "lst", "pib")

LAYER_BY_TEMA: dict[str, str | None] = {
    "mapbiomas": "cobertura",
    "s2id": "desastres",
    "inep": "educacao",
    "lst": "lst_observada",
    "pib": None,
}

TEMA_LABELS: dict[str, str] = {
    "mapbiomas": "MapBiomas",
    "s2id": "S2ID / desastres",
    "inep": "INEP Censo Escolar",
    "lst": "LST observada",
    "pib": "PIB municipal (IBGE)",
}

LST_ANOS = [2021, 2022, 2023, 2024, 2025]
PIB_FALLBACK_ANOS = [2019, 2020, 2021, 2022, 2023]


def _sorted_years(values: list[int]) -> list[int]:
    return sorted({int(v) for v in values if v}, reverse=True)


def _mapbiomas_years(db: Session, muni: Municipio) -> list[int]:
    polygon_years = [
        row[0]
        for row in db.query(CoberturaVegetalMapBiomas.ano)
        .filter(CoberturaVegetalMapBiomas.municipio_id == muni.id)
        .distinct()
        .all()
        if row[0]
    ]
    if polygon_years:
        return _sorted_years(polygon_years)

    stat_years = [
        row[0]
        for row in db.query(MapBiomasMunicipalStat.ano)
        .filter(MapBiomasMunicipalStat.codigo_ibge == muni.codigo_ibge)
        .distinct()
        .all()
        if row[0]
    ]
    if stat_years:
        return _sorted_years(stat_years)
    return [2023, 2022, 2021]


def _s2id_years(db: Session, muni: Municipio) -> list[int]:
    years = [
        row[0]
        for row in db.query(extract("year", HistoricoDesastreS2ID.data_ocorrencia))
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .distinct()
        .all()
        if row[0]
    ]
    if years:
        return _sorted_years([int(y) for y in years])
    return list(range(2024, 2014, -1))


def _inep_years(db: Session, muni: Municipio) -> list[int]:
    years = [
        row[0]
        for row in db.query(EscolaInep.ano)
        .filter(EscolaInep.municipio_id == muni.id)
        .distinct()
        .all()
        if row[0]
    ]
    if years:
        return _sorted_years(years)
    return [CENSO_ANO_DEFAULT, CENSO_ANO_DEFAULT - 1]


def _pib_years(db: Session, codigo_ibge: str) -> list[int]:
    row = db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == codigo_ibge).first()
    if row and row.pib_serie:
        anos = [int(item["ano"]) for item in row.pib_serie if item.get("ano")]
        if anos:
            return _sorted_years(anos)
    if row and row.pib_ano:
        return [int(row.pib_ano)]
    return list(reversed(PIB_FALLBACK_ANOS))


def build_tema_entry(
    tema_id: str,
    anos: list[int],
    *,
    context_only: bool = False,
    nota: str | None = None,
) -> dict[str, Any]:
    padrao = anos[0] if anos else None
    return {
        "tema_id": tema_id,
        "label": TEMA_LABELS.get(tema_id, tema_id),
        "layer_id": LAYER_BY_TEMA.get(tema_id),
        "anos": anos,
        "padrao": padrao,
        "context_only": context_only,
        "nota": nota,
    }


def temporal_options_for_municipio(db: Session, muni: Municipio) -> dict[str, Any]:
    mapbiomas_anos = _mapbiomas_years(db, muni)
    s2id_anos = _s2id_years(db, muni)
    inep_anos = _inep_years(db, muni)
    pib_anos = _pib_years(db, muni.codigo_ibge)

    temas = {
        "mapbiomas": build_tema_entry("mapbiomas", mapbiomas_anos),
        "s2id": build_tema_entry(
            "s2id",
            s2id_anos,
            nota="Selecione um ano ou deixe em «Todos os anos».",
        ),
        "inep": build_tema_entry("inep", inep_anos),
        "lst": build_tema_entry(
            "lst",
            list(reversed(LST_ANOS)),
            nota=f"Mosaico GeoReDUS {LST_PERIODO_LABEL} — ano refinando rótulo e comparações.",
        ),
        "pib": build_tema_entry(
            "pib",
            pib_anos,
            context_only=True,
            nota="Referência socioeconômica municipal (painel e contexto).",
        ),
    }
    temas["s2id"]["padrao"] = None
    return {
        "codigo_ibge": muni.codigo_ibge,
        "temas": temas,
    }


def resolve_layer_year(
    layer_name: str,
    ano: int | None,
    db: Session,
    muni: Municipio,
) -> int | None:
    """Resolve ano efetivo para filtro de camada (None = sem filtro / todas)."""
    if ano is not None:
        return int(ano)

    if layer_name == "cobertura":
        years = _mapbiomas_years(db, muni)
        return years[0] if years else 2023
    if layer_name == "desastres":
        return None
    if layer_name == "educacao":
        years = _inep_years(db, muni)
        return years[0] if years else CENSO_ANO_DEFAULT
    return None
