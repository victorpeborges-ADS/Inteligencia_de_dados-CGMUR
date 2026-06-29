from __future__ import annotations

import io
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
import requests

from app.data_connectors.base import fetch_json
from app.data_connectors.cache import cache_get_json, cache_set_json
from app.data_connectors.constants import CAPAG_CKAN_URL


def _latest_capag_resource_url() -> Optional[str]:
    cached = cache_get_json("capag:latest_resource")
    if cached:
        return cached.get("url")

    payload = fetch_json(CAPAG_CKAN_URL, cache_key="capag:package", cache_ttl=86400)
    resources = (payload or {}).get("result", {}).get("resources") or []
    xlsx_resources = [res for res in resources if str(res.get("format", "")).upper() == "XLSX"]
    if not xlsx_resources:
        return None
    latest = sorted(xlsx_resources, key=lambda item: item.get("last_modified") or "", reverse=True)[0]
    cache_set_json("capag:latest_resource", {"url": latest.get("url")}, ttl=86400)
    return latest.get("url")


CAPAG_INDICATORS = (
    {"numero": 1, "nome": "Endividamento", "valor_col": "indicador 1", "nota_col": "nota 1"},
    {"numero": 2, "nome": "Poupança Corrente", "valor_col": "indicador 2", "nota_col": "nota 2"},
    {"numero": 3, "nome": "Liquidez", "valor_col": "indicador 3", "nota_col": "nota 3"},
)


def _normalize_codigo(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().replace(".0", "")
    if not text.isdigit():
        return None
    return text.zfill(7)


def _normalize_indicador_nota(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text in {"NAN", "NONE", "-"}:
        return None
    if len(text) >= 2 and text[1] == "+":
        return text[:2]
    return text[:1]


def _col_by_ascii(df: pd.DataFrame, target: str) -> Optional[str]:
    for col in df.columns:
        if _ascii_col(col) == _ascii_col(target):
            return col
    return None


def _extract_indicadores(row: pd.Series, df: pd.DataFrame) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for spec in CAPAG_INDICATORS:
        valor_col = _col_by_ascii(df, spec["valor_col"])
        nota_col = _col_by_ascii(df, spec["nota_col"])
        raw_valor = row[valor_col] if valor_col else None
        valor = None
        if raw_valor is not None and str(raw_valor).strip().lower() not in {"", "nan", "none"}:
            try:
                valor = float(raw_valor)
            except (TypeError, ValueError):
                valor = None
        items.append(
            {
                "numero": spec["numero"],
                "nome": spec["nome"],
                "valor": valor,
                "nota": _normalize_indicador_nota(row[nota_col] if nota_col else None),
            }
        )
    return items


def _ascii_col(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(name))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip().lower()


def _detect_capag_columns(df: pd.DataFrame) -> tuple[Optional[str], Optional[str]]:
    code_col = next(
        (
            col
            for col in df.columns
            if any(token in _ascii_col(col) for token in ("ibge", "codigo", "cod_ibge", "cod_mun"))
            and "nome" not in _ascii_col(col)
        ),
        None,
    )
    note_col = next(
        (
            col
            for col in df.columns
            if _ascii_col(col) == "capag" or (_ascii_col(col).startswith("capag") and "ano" not in _ascii_col(col))
        ),
        None,
    )
    if not note_col:
        note_col = next((col for col in df.columns if _ascii_col(col) in {"nota", "classificacao"}), None)
    return code_col, note_col


def _load_capag_dataframe() -> pd.DataFrame:
    url = _latest_capag_resource_url()
    if not url:
        raise RuntimeError("Recurso CAPAG não encontrado no CKAN do Tesouro.")

    response = requests.get(url, timeout=60, headers={"User-Agent": "Sinidu+Clima/1.0"})
    response.raise_for_status()
    raw = io.BytesIO(response.content)

    df: pd.DataFrame | None = None
    for header_row in range(0, 8):
        candidate = pd.read_excel(raw, engine="openpyxl", header=header_row)
        candidate.columns = [str(col).strip().lower() for col in candidate.columns]
        code_col, note_col = _detect_capag_columns(candidate)
        if code_col and note_col:
            df = candidate
            break
        raw.seek(0)

    if df is None:
        raw.seek(0)
        df = pd.read_excel(raw, engine="openpyxl", header=2)
        df.columns = [str(col).strip().lower() for col in df.columns]

    cache_set_json("capag:dataframe_meta", {"url": url, "columns": list(df.columns)}, ttl=86400)
    return df


def _normalize_nota(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().upper()
    if not text or text in {"NAN", "NONE", "-"}:
        return None
    # CAPAG publicada como A+, B+, C etc.
    letter = text[0]
    if letter in {"A", "B", "C", "D", "E"}:
        return letter
    return None


def collect_capag_municipality(codigo_ibge: str) -> Dict[str, Any]:
    df = _load_capag_dataframe()
    code_col, note_col = _detect_capag_columns(df)
    if not code_col or not note_col:
        raise RuntimeError("Colunas esperadas do CAPAG não encontradas no arquivo oficial.")

    df["_codigo"] = df[code_col].apply(_normalize_codigo)
    row = df[df["_codigo"] == codigo_ibge]
    nota = None
    nota_raw = None
    indicadores: list[dict[str, Any]] = []
    origem_nota = None
    if not row.empty:
        raw_nota = row.iloc[0][note_col]
        if raw_nota is not None and str(raw_nota).strip():
            nota_raw = str(raw_nota).strip().upper()
            nota = _normalize_nota(raw_nota)
        indicadores = _extract_indicadores(row.iloc[0], df)
        origem_col = _col_by_ascii(df, "origem da nota final")
        if origem_col:
            raw_origem = row.iloc[0][origem_col]
            if raw_origem is not None and str(raw_origem).strip().lower() not in {"", "nan"}:
                origem_nota = str(raw_origem).strip()

    return {
        "codigo_ibge": codigo_ibge,
        "nota_capag": nota,
        "nota_capag_raw": nota_raw,
        "indicadores": indicadores,
        "origem_nota": origem_nota,
        "data_quality": "oficial" if nota else "estimado",
        "fonte": "CAPAG / Tesouro Transparente",
        "atualizado_em": datetime.now(timezone.utc),
        "raw_payload": {"rows_matched": int(len(row))},
    }
