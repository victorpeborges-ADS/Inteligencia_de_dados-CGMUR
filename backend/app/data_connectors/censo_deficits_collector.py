"""Censo 2022 — déficits domiciliares municipais (SIDRA) e distribuição por setor."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.base import fetch_json
from app.models import Municipio, SetorCensitario

logger = logging.getLogger(__name__)

SIDRA_BASE = "https://apisidra.ibge.gov.br"
CENSO_PERIOD = "2022"
CENSO_FONTE = "ibge_censo2022_sidra_deficits"

# Tabela 10053 — PUE entorno (denominador: domicílios PUE)
_PUE_DOM = {"table": 10053, "var": 9599, "cls_entorno": 14, "cls_esgoto": 11558, "cat_total_entorno": 200, "cat_total_esgoto": 46292}

DEFICIT_KEYS = (
    "arborizacao",
    "calcada",
    "iluminacao",
    "agua",
    "esgoto",
    "lixo",
    "alfabetizacao",
)


def _sidra_rows(path: str) -> list[dict[str, Any]]:
    try:
        payload = fetch_json(
            f"{SIDRA_BASE}{path}",
            cache_key=f"sidra:{path}",
            cache_ttl=86400 * 7,
        )
    except Exception as exc:
        logger.warning("SIDRA falhou %s: %s", path, exc)
        return []
    if isinstance(payload, list):
        return payload[1:] if len(payload) > 1 else []
    return []


def _sidra_count(path: str) -> float | None:
    rows = _sidra_rows(path)
    if not rows:
        return None
    try:
        return float(str(rows[-1].get("V", "")).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(100.0 * numerator / denominator, 1)


def fetch_municipal_deficits(codigo_ibge: str) -> dict[str, Any]:
    """Busca taxas municipais de déficit via API SIDRA (Censo 2022)."""
    code = str(codigo_ibge).strip().zfill(7)[:7]
    pue = _PUE_DOM

    dom_pue = _sidra_count(
        f"/values/t/{pue['table']}/n6/{code}/p/{CENSO_PERIOD}/v/{pue['var']}"
        f"/c{pue['cls_entorno']}/{pue['cat_total_entorno']}/c{pue['cls_esgoto']}/{pue['cat_total_esgoto']}"
    )

    iluminacao_n = _sidra_count(
        f"/values/t/{pue['table']}/n6/{code}/p/{CENSO_PERIOD}/v/{pue['var']}"
        f"/c{pue['cls_entorno']}/72255/c{pue['cls_esgoto']}/{pue['cat_total_esgoto']}"
    )
    calcada_n = _sidra_count(
        f"/values/t/{pue['table']}/n6/{code}/p/{CENSO_PERIOD}/v/{pue['var']}"
        f"/c{pue['cls_entorno']}/72267/c{pue['cls_esgoto']}/{pue['cat_total_esgoto']}"
    )
    arborizacao_n = _sidra_count(
        f"/values/t/{pue['table']}/n6/{code}/p/{CENSO_PERIOD}/v/{pue['var']}"
        f"/c{pue['cls_entorno']}/72278/c{pue['cls_esgoto']}/{pue['cat_total_esgoto']}"
    )

    agua_n = _sidra_count(
        f"/values/t/6751/n6/{code}/p/{CENSO_PERIOD}/v/9599/c1821/72153/c14/200"
    )

    esgoto_cats = (72113, 92858, 72114, 72115, 92861)
    esgoto_n = 0.0
    esgoto_ok = False
    for cat in esgoto_cats:
        val = _sidra_count(
            f"/values/t/{pue['table']}/n6/{code}/p/{CENSO_PERIOD}/v/{pue['var']}"
            f"/c{pue['cls_entorno']}/{pue['cat_total_entorno']}/c{pue['cls_esgoto']}/{cat}"
        )
        if val is not None:
            esgoto_n += val
            esgoto_ok = True
    esgoto_n = esgoto_n if esgoto_ok else None

    dom_all = _sidra_count(
        f"/values/t/6892/n6/{code}/p/{CENSO_PERIOD}/v/381/c67/10972"
    )
    lixo_cats = (72122, 72123, 72124, 1091)
    lixo_n = 0.0
    lixo_ok = False
    for cat in lixo_cats:
        val = _sidra_count(
            f"/values/t/6892/n6/{code}/p/{CENSO_PERIOD}/v/381/c67/{cat}"
        )
        if val is not None:
            lixo_n += val
            lixo_ok = True
    lixo_n = lixo_n if lixo_ok else None

    alfabet_taxa = _sidra_count(
        f"/values/t/9543/n6/{code}/p/{CENSO_PERIOD}/v/2513/c2/6794"
    )
    alfabetizacao_pct = (
        round(100.0 - alfabet_taxa, 1) if alfabet_taxa is not None else None
    )

    rates = {
        "arborizacao_pct": _pct(arborizacao_n, dom_pue),
        "calcada_pct": _pct(calcada_n, dom_pue),
        "iluminacao_pct": _pct(iluminacao_n, dom_pue),
        "agua_pct": _pct(agua_n, dom_pue),
        "esgoto_pct": _pct(esgoto_n, dom_pue),
        "lixo_pct": _pct(lixo_n, dom_all),
        "alfabetizacao_pct": alfabetizacao_pct,
    }

    return {
        "codigo_ibge": code,
        "ano": 2022,
        "fonte": CENSO_FONTE,
        "denominadores": {
            "domicilios_pue": dom_pue,
            "domicilios_total": dom_all,
        },
        "taxas_municipais": rates,
        "disponivel": any(v is not None for v in rates.values()),
    }


def _poverty_factor(renda: float, renda_ref: float) -> float:
    if renda_ref <= 0:
        return 1.0
    ratio = min(2.5, max(0.2, renda / renda_ref))
    return max(0.55, min(1.85, 1.75 - 0.55 * ratio))


def distribute_deficits_to_setores(
    db: Session,
    muni: Municipio,
    municipal: dict[str, Any],
) -> int:
    """Distribui taxas municipais aos setores com ponderação por renda (proxy intra-urbano)."""
    rates = municipal.get("taxas_municipais") or {}
    if not rates:
        return 0

    setores = db.query(SetorCensitario).filter(SetorCensitario.municipio_id == muni.id).all()
    if not setores:
        return 0

    rendas = [float(s.renda_media or 0.0) for s in setores if s.renda_media]
    renda_ref = sum(rendas) / len(rendas) if rendas else 2200.0
    now = datetime.now(timezone.utc)
    updated = 0

    for setor in setores:
        renda = float(setor.renda_media or renda_ref)
        factor = _poverty_factor(renda, renda_ref)
        deficits: dict[str, float] = {}
        for key in DEFICIT_KEYS:
            base_key = f"{key}_pct"
            base_val = rates.get(base_key)
            if base_val is None:
                continue
            local = round(min(100.0, max(0.0, float(base_val) * factor)), 1)
            deficits[key] = local

        if not deficits:
            continue

        setor.deficits_censo_json = deficits
        setor.deficits_censo_fonte = CENSO_FONTE
        setor.deficits_censo_atualizado_em = now
        updated += 1

    return updated


def enrich_setores_deficits(db: Session, muni: Municipio) -> dict[str, Any]:
    municipal = fetch_municipal_deficits(muni.codigo_ibge)
    updated = distribute_deficits_to_setores(db, muni, municipal)
    return {
        "codigo_ibge": muni.codigo_ibge,
        "setores_atualizados": updated,
        "taxas_municipais": municipal.get("taxas_municipais"),
        "fonte": CENSO_FONTE,
        "disponivel": municipal.get("disponivel", False),
    }
