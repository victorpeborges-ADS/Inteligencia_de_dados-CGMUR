from __future__ import annotations

import io
import os
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
import requests

from app.data_connectors.cache import cache_get_json, cache_set_json
from app.data_connectors.constants import TARGET_MUNICIPALITIES
from app.data_connectors.snis_reference_data import SNIS_MUNICIPAL_2022, SNIS_UF_MEDIA_2022

SNIS_ANO_REFERENCIA = 2022
SNIS_FONTE_OFICIAL = "SNIS Diagnóstico Água e Esgoto 2022 / MCID"
SNIS_FONTE_PROXY = "SNIS — média UF 2022 (proxy municipal)"


def _normalize_codigo(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().replace(".0", "")
    if not text.isdigit():
        return None
    return text.zfill(7)


def _ascii_col(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(name))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).strip().lower()


def _col_by_tokens(df: pd.DataFrame, tokens: tuple[str, ...]) -> Optional[str]:
    for col in df.columns:
        ascii_name = _ascii_col(col)
        if all(token in ascii_name for token in tokens):
            return col
    return None


def _detect_snis_columns(df: pd.DataFrame) -> dict[str, Optional[str]]:
    code_col = next(
        (
            col
            for col in df.columns
            if any(token in _ascii_col(col) for token in ("ibge", "codigo", "cod_ibge", "cod_mun"))
            and "nome" not in _ascii_col(col)
        ),
        None,
    )
    return {
        "codigo": code_col,
        "agua": _col_by_tokens(df, ("cobertura", "agua"))
        or _col_by_tokens(df, ("in055",))
        or _col_by_tokens(df, ("atendida", "agua")),
        "esgoto": _col_by_tokens(df, ("cobertura", "esgoto"))
        or _col_by_tokens(df, ("in056",))
        or _col_by_tokens(df, ("atendida", "esgoto")),
        "perdas": _col_by_tokens(df, ("perda", "agua")) or _col_by_tokens(df, ("in089",)),
        "tratamento": _col_by_tokens(df, ("trat", "esgoto"))
        or _col_by_tokens(df, ("in063",))
        or _col_by_tokens(df, ("atendimento", "esgoto")),
        "drenagem": _col_by_tokens(df, ("drenagem",)) or _col_by_tokens(df, ("pluvial",)),
    }


def _parse_pct(value: Any) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace("%", "").replace(",", ".")
    if not text or text.lower() in {"nan", "none", "-", "s/info"}:
        return None
    try:
        parsed = float(text)
        if parsed > 100:
            parsed = parsed / 100.0
        return round(parsed, 2)
    except (TypeError, ValueError):
        return None


def _uf_for_codigo(codigo_ibge: str) -> str:
    for item in TARGET_MUNICIPALITIES:
        if item["codigo_ibge"] == codigo_ibge:
            return item["uf"]
    return codigo_ibge[0:2]


def _payload_from_mapping(
    codigo_ibge: str,
    mapping: Dict[str, Any],
    *,
    data_quality: str,
    fonte: str,
    origem: str,
) -> Dict[str, Any]:
    return {
        "codigo_ibge": codigo_ibge,
        "cobertura_agua_pct": mapping.get("cobertura_agua_pct"),
        "cobertura_esgoto_pct": mapping.get("cobertura_esgoto_pct"),
        "indice_perdas_agua_pct": mapping.get("indice_perdas_agua_pct"),
        "indice_atendimento_esgoto_pct": mapping.get("indice_atendimento_esgoto_pct"),
        "indice_drenagem": mapping.get("indice_drenagem"),
        "ano_referencia": SNIS_ANO_REFERENCIA,
        "data_quality": data_quality,
        "fonte": fonte,
        "atualizado_em": datetime.now(timezone.utc),
        "raw_payload": {"origem": origem},
    }


def _load_remote_dataframe() -> Optional[pd.DataFrame]:
    url = os.getenv("SNIS_INDICADORES_URL", "").strip()
    if not url:
        return None

    cached = cache_get_json("snis:latest_resource")
    if cached and cached.get("url") == url and cached.get("columns"):
        return None

    response = requests.get(url, timeout=90, headers={"User-Agent": "Sinidu+Clima/1.0"})
    response.raise_for_status()
    raw = io.BytesIO(response.content)

    if url.lower().endswith(".csv"):
        df = pd.read_csv(raw)
    else:
        df = pd.read_excel(raw, engine="openpyxl")

    df.columns = [str(col).strip() for col in df.columns]
    cache_set_json("snis:latest_resource", {"url": url, "columns": list(df.columns)}, ttl=86400)
    return df


def _collect_from_dataframe(df: pd.DataFrame, codigo_ibge: str) -> Optional[Dict[str, Any]]:
    cols = _detect_snis_columns(df)
    if not cols["codigo"]:
        return None

    df = df.copy()
    df["_codigo"] = df[cols["codigo"]].apply(_normalize_codigo)
    row = df[df["_codigo"] == codigo_ibge]
    if row.empty:
        return None

    item = row.iloc[0]
    mapping = {
        "cobertura_agua_pct": _parse_pct(item[cols["agua"]]) if cols["agua"] else None,
        "cobertura_esgoto_pct": _parse_pct(item[cols["esgoto"]]) if cols["esgoto"] else None,
        "indice_perdas_agua_pct": _parse_pct(item[cols["perdas"]]) if cols["perdas"] else None,
        "indice_atendimento_esgoto_pct": _parse_pct(item[cols["tratamento"]]) if cols["tratamento"] else None,
        "indice_drenagem": _parse_pct(item[cols["drenagem"]]) if cols["drenagem"] else None,
    }
    if not any(mapping.values()):
        return None

    return _payload_from_mapping(
        codigo_ibge,
        mapping,
        data_quality="oficial",
        fonte=SNIS_FONTE_OFICIAL,
        origem="remote_xlsx",
    )


def _collect_from_reference(codigo_ibge: str) -> Optional[Dict[str, Any]]:
    municipal = SNIS_MUNICIPAL_2022.get(codigo_ibge)
    if municipal:
        return _payload_from_mapping(
            codigo_ibge,
            municipal,
            data_quality="oficial",
            fonte=SNIS_FONTE_OFICIAL,
            origem="referencia_municipal",
        )

    uf = _uf_for_codigo(codigo_ibge)
    uf_data = SNIS_UF_MEDIA_2022.get(uf)
    if not uf_data:
        return None

    return _payload_from_mapping(
        codigo_ibge,
        uf_data,
        data_quality="estimado",
        fonte=SNIS_FONTE_PROXY,
        origem="referencia_uf",
    )


def collect_snis_municipality(codigo_ibge: str) -> Dict[str, Any]:
    code = str(codigo_ibge).strip().zfill(7)[:7]

    try:
        remote_df = _load_remote_dataframe()
        if remote_df is not None:
            payload = _collect_from_dataframe(remote_df, code)
            if payload:
                return payload
    except Exception:
        pass

    payload = _collect_from_reference(code)
    if payload:
        return payload

    return {
        "codigo_ibge": code,
        "cobertura_agua_pct": None,
        "cobertura_esgoto_pct": None,
        "indice_perdas_agua_pct": None,
        "indice_atendimento_esgoto_pct": None,
        "indice_drenagem": None,
        "ano_referencia": None,
        "data_quality": "lacuna",
        "fonte": None,
        "atualizado_em": datetime.now(timezone.utc),
        "raw_payload": {"origem": "nao_encontrado"},
    }


def snis_status_label(data_quality: str | None) -> str:
    quality = (data_quality or "").lower()
    if quality == "oficial":
        return "Integrado"
    if quality in {"estimado", "derivado"}:
        return "Estimado"
    return "Ausente"
