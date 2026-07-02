"""Coletor SINESP — vítimas de crimes violentos letais por município (MJ/dados.gov.br)."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

logger = logging.getLogger(__name__)

SINESP_XLSX_URL = (
    "https://dados.mj.gov.br/dataset/210b9ae2-21fc-4986-89c6-2006eb4db247/"
    "resource/03af7ce2-174e-4ebd-b085-384503cfb40f/download/"
    "dadosnacionaissegurancapublicamunicipios.xlsx"
)
CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "cache"
CACHE_XLSX = CACHE_DIR / "sinesp_municipios.xlsx"
CACHE_MAX_AGE_DAYS = 7

UF_SHEETS = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
)

_index: dict[str, dict[str, Any]] | None = None


def _cache_stale() -> bool:
    if not CACHE_XLSX.exists():
        return True
    age_days = (datetime.now().timestamp() - CACHE_XLSX.stat().st_mtime) / 86400
    return age_days > CACHE_MAX_AGE_DAYS


def download_sinesp_xlsx(*, force: bool = False) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not force and not _cache_stale():
        return CACHE_XLSX

    logger.info("Baixando XLSX SINESP (~10 MB)...")
    response = requests.get(
        SINESP_XLSX_URL,
        timeout=180,
        headers={"User-Agent": "Sinidu+Clima/1.0 (MCID integracao publica)"},
    )
    response.raise_for_status()
    CACHE_XLSX.write_bytes(response.content)
    logger.info("XLSX SINESP salvo em %s", CACHE_XLSX)
    return CACHE_XLSX


def _normalize_code(value: Any) -> str:
    try:
        return str(int(float(value))).zfill(7)[:7]
    except (TypeError, ValueError):
        return str(value).strip().zfill(7)[:7]


def _build_index(xlsx_path: Path) -> dict[str, dict[str, Any]]:
    frames: list[pd.DataFrame] = []
    xl = pd.ExcelFile(xlsx_path)
    for sheet in UF_SHEETS:
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(xl, sheet_name=sheet)
        if df.empty or "Cód_IBGE" not in df.columns:
            continue
        frames.append(df)

    if not frames:
        return {}

    all_rows = pd.concat(frames, ignore_index=True)
    all_rows["codigo_ibge"] = all_rows["Cód_IBGE"].map(_normalize_code)
    all_rows["mes"] = pd.to_datetime(all_rows["Mês/Ano"], errors="coerce")
    all_rows["vitimas"] = pd.to_numeric(all_rows["Vítimas"], errors="coerce").fillna(0).astype(int)

    index: dict[str, dict[str, Any]] = {}
    for code, group in all_rows.groupby("codigo_ibge"):
        group = group.dropna(subset=["mes"]).sort_values("mes")
        if group.empty:
            continue
        latest = group["mes"].max()
        window_start = latest - pd.DateOffset(months=11)
        last12 = group[(group["mes"] >= window_start) & (group["mes"] <= latest)]
        mortes = int(last12["vitimas"].sum())
        mes_ref = latest.strftime("%Y-%m")
        index[code] = {
            "mes_ref": mes_ref,
            "mortes_violentas": mortes,
            "ocorrencias_violentas": mortes,
            "roubos": 0,
            "fonte": "SINESP/dados.mj.gov.br (XLSX)",
            "periodo_meses": len(last12),
        }
    return index


def load_sinesp_index(*, force_download: bool = False) -> dict[str, dict[str, Any]]:
    global _index
    if _index is not None and not force_download:
        return _index

    path = download_sinesp_xlsx(force=force_download)
    _index = _build_index(path)
    logger.info("Índice SINESP: %d municípios", len(_index))
    return _index


def fetch_municipio_sinesp(codigo_ibge: str, populacao: int = 0) -> dict[str, Any] | None:
    code = _normalize_code(codigo_ibge)
    row = load_sinesp_index().get(code)
    if not row:
        return None

    pop = max(int(populacao or 0), 1)
    mortes = row["mortes_violentas"]
    taxa = round(mortes / pop * 100000, 2)
    return {
        "mes_ref": row["mes_ref"],
        "ocorrencias_violentas": mortes,
        "mortes_violentas": mortes,
        "roubos": row["roubos"],
        "taxa_100k": taxa,
        "fonte": row["fonte"],
    }


def ensure_sinesp_loaded(db, muni) -> dict[str, Any] | None:
    """Carrega segurança SINESP para um município (usado na recarga)."""
    from etl.etl_seguranca_sinesp import process_municipio

    if not process_municipio(db, muni.codigo_ibge):
        return None

    from app.models import MunicipioSeguranca

    row = (
        db.query(MunicipioSeguranca)
        .filter(MunicipioSeguranca.codigo_ibge == muni.codigo_ibge)
        .order_by(MunicipioSeguranca.mes_ref.desc())
        .first()
    )
    if not row:
        return None
    return {
        "codigo_ibge": muni.codigo_ibge,
        "mes_ref": row.mes_ref,
        "taxa_100k": float(row.taxa_100k or 0),
        "fonte": row.fonte,
    }
