"""Bootstrap em lote por UF — cobertura mínima sem GIS (18c.1).

Ativa municípios com: geometria IBGE + indicadores + S2ID + MapBiomas
(proxy / CSV). Adequado ao modo baixa maturidade.
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.models import HistoricoDesastreS2ID, MapBiomasMunicipalStat, Municipio, MunicipioIbge
from app.services.municipio_loader import ensure_municipality_loaded
from app.timeutil import utc_now

logger = logging.getLogger(__name__)

IBGE_UF_MUNICIPIOS_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
)

VALID_UFS = {
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
}


def normalize_uf(uf: str) -> str:
    code = str(uf or "").strip().upper()[:2]
    if code not in VALID_UFS:
        raise ValueError(f"UF inválida: {uf!r}. Use sigla de 2 letras (ex.: PE, RJ).")
    return code


def list_municipios_ibge_uf(uf: str) -> list[dict[str, str]]:
    """Lista municípios oficiais da UF via API IBGE Localidades."""
    uf_code = normalize_uf(uf)
    resp = requests.get(IBGE_UF_MUNICIPIOS_URL.format(uf=uf_code), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    out: list[dict[str, str]] = []
    for row in data or []:
        codigo = str(row.get("id") or "").zfill(7)[:7]
        nome = str(row.get("nome") or "").strip()
        if codigo.isdigit() and len(codigo) == 7 and nome:
            out.append({"codigo_ibge": codigo, "nome": nome, "uf": uf_code})
    out.sort(key=lambda r: r["nome"])
    return out


def preview_uf_bootstrap(db: Session, uf: str, *, limit: int = 50) -> dict[str, Any]:
    """Prévia: quantos municípios a UF tem e quantos já estão carregados."""
    uf_code = normalize_uf(uf)
    try:
        catalog = list_municipios_ibge_uf(uf_code)
    except requests.RequestException as exc:
        raise ValueError(f"IBGE indisponível para UF {uf_code}: {exc}") from exc

    codes = [m["codigo_ibge"] for m in catalog]
    loaded = {
        r.codigo_ibge
        for r in db.query(Municipio.codigo_ibge)
        .filter(Municipio.codigo_ibge.in_(codes))
        .all()
    }
    pending = [m for m in catalog if m["codigo_ibge"] not in loaded]
    sample = pending[: max(1, min(limit, 200))]
    return {
        "uf": uf_code,
        "total_ibge": len(catalog),
        "ja_carregados": len(loaded),
        "pendentes": len(pending),
        "limit_solicitado": limit,
        "a_processar": len(sample),
        "amostra": sample[:20],
        "versao": "18c.1",
    }


def _bootstrap_one(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Cobertura mínima: ensure + S2ID + MapBiomas (melhor esforço)."""
    code = str(codigo_ibge).zfill(7)[:7]
    steps: dict[str, str] = {}
    errors: list[str] = []

    ensured = ensure_municipality_loaded(db, code)
    steps["ensure"] = "ok" if ensured.get("loaded") else "falha"
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {
            "codigo_ibge": code,
            "status": "falha",
            "steps": steps,
            "errors": ["municipio_nao_criado"],
        }

    # S2ID
    try:
        from app.data_connectors.s2id_collector import ensure_s2id_loaded

        s2id = ensure_s2id_loaded(db, muni)
        n = (
            db.query(HistoricoDesastreS2ID)
            .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
            .count()
        )
        steps["s2id"] = "ok" if (s2id is not None or n > 0) else "parcial"
    except Exception as exc:
        steps["s2id"] = "falha"
        errors.append(f"s2id: {exc}")
        logger.warning("S2ID bootstrap %s: %s", code, exc)

    # MapBiomas (CSV/stats — sem GIS)
    try:
        from app.data_connectors.mapbiomas_collector import collect_mapbiomas_municipality

        collect_mapbiomas_municipality(db, code, force=False)
        stats_n = (
            db.query(MapBiomasMunicipalStat)
            .filter(MapBiomasMunicipalStat.codigo_ibge == code)
            .count()
        )
        steps["mapbiomas"] = "ok" if stats_n > 0 else "parcial"
    except Exception as exc:
        steps["mapbiomas"] = "falha"
        errors.append(f"mapbiomas: {exc}")
        logger.warning("MapBiomas bootstrap %s: %s", code, exc)

    ibge_ok = (
        db.query(MunicipioIbge).filter(MunicipioIbge.codigo_ibge == code).first() is not None
    )
    steps["ibge"] = "ok" if ibge_ok else "parcial"

    failed = sum(1 for s in steps.values() if s == "falha")
    status = "ok" if failed == 0 else ("parcial" if steps.get("ensure") == "ok" else "falha")

    return {
        "codigo_ibge": code,
        "nome": muni.nome,
        "uf": muni.uf,
        "status": status,
        "steps": steps,
        "errors": errors,
        "already_existed": bool(ensured.get("already_existed")),
    }


def bootstrap_uf(
    db: Session,
    uf: str,
    *,
    limit: int = 20,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Ativa até `limit` municípios da UF com cobertura mínima nacional."""
    uf_code = normalize_uf(uf)
    limit = max(1, min(int(limit), 100))

    try:
        catalog = list_municipios_ibge_uf(uf_code)
    except requests.RequestException as exc:
        raise ValueError(f"IBGE indisponível para UF {uf_code}: {exc}") from exc

    targets = catalog
    if skip_existing:
        codes = [m["codigo_ibge"] for m in catalog]
        loaded = {
            r.codigo_ibge
            for r in db.query(Municipio.codigo_ibge)
            .filter(Municipio.codigo_ibge.in_(codes))
            .all()
        }
        targets = [m for m in catalog if m["codigo_ibge"] not in loaded]

    targets = targets[:limit]
    items: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for meta in targets:
        try:
            items.append(_bootstrap_one(db, meta["codigo_ibge"]))
        except Exception as exc:
            db.rollback()
            logger.exception("Bootstrap UF falhou %s", meta["codigo_ibge"])
            errors.append({"codigo_ibge": meta["codigo_ibge"], "error": str(exc)})

    ok = sum(1 for i in items if i.get("status") == "ok")
    parcial = sum(1 for i in items if i.get("status") == "parcial")

    return {
        "uf": uf_code,
        "requested": len(targets),
        "processed": len(items),
        "ok": ok,
        "parcial": parcial,
        "errors": errors,
        "items": items,
        "skip_existing": skip_existing,
        "gerado_em": utc_now().isoformat() + "Z",
        "versao": "18c.1",
        "cobertura": "IBGE + S2ID + MapBiomas (mínimo, sem GIS)",
    }
