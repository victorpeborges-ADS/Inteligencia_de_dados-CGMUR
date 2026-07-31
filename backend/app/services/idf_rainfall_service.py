"""Curvas IDF / período de retorno → lâmina (mm) — 17g.1a / 20h.4.

Tabelas de referência operacional para pilotos (Recife, Aracaju) e fallbacks
por UF / nacional. Qualidade "Estimado" até calibração com PDFs municipais
ou ANA/INMET. O motor hidráulico continua recebendo apenas precipitacao_mm.

20h.4 — Overrides oficiais: quando existe curva IDF curada por município em
`backend/data/idf/<codigo_ibge>.json` (ou diretório apontado por `IDF_DIR`),
ela tem precedência sobre a tabela interna `_IDF_MUNICIPAL` e é reportada com
`qualidade="Oficial"`. Ver `backend/data/idf/README.md`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# Lâmina acumulada (mm) por duração de projeto (min) e TR (anos).
# Valores típicos de projeto urbano costeiro NE — calibráveis.
# 1440 min = 24 h: alinhado a boletins APAC/INMET e extremos documentados (ex. maio/2022).
_IDF_MUNICIPAL: dict[str, dict[int, dict[int, float]]] = {
    "2611606": {  # Recife-PE
        60: {2: 48.0, 10: 78.0, 25: 105.0, 100: 145.0},
        120: {2: 62.0, 10: 98.0, 25: 130.0, 100: 180.0},
        1440: {2: 70.0, 10: 110.0, 25: 150.0, 100: 220.0},
    },
    "2800308": {  # Aracaju-SE
        60: {2: 42.0, 10: 70.0, 25: 95.0, 100: 132.0},
        120: {2: 55.0, 10: 88.0, 25: 118.0, 100: 165.0},
        1440: {2: 60.0, 10: 95.0, 25: 130.0, 100: 190.0},
    },
}

_IDF_UF: dict[str, dict[int, dict[int, float]]] = {
    "PE": {
        60: {2: 45.0, 10: 74.0, 25: 98.0, 100: 138.0},
        120: {2: 58.0, 10: 92.0, 25: 122.0, 100: 170.0},
        1440: {2: 65.0, 10: 100.0, 25: 140.0, 100: 200.0},
    },
    "SE": {
        60: {2: 40.0, 10: 68.0, 25: 90.0, 100: 128.0},
        120: {2: 52.0, 10: 85.0, 25: 112.0, 100: 158.0},
        1440: {2: 55.0, 10: 90.0, 25: 125.0, 100: 185.0},
    },
}

_IDF_NATIONAL: dict[int, dict[int, float]] = {
    60: {2: 40.0, 10: 65.0, 25: 88.0, 100: 125.0},
    120: {2: 52.0, 10: 82.0, 25: 110.0, 100: 155.0},
    1440: {2: 55.0, 10: 90.0, 25: 120.0, 100: 180.0},
}

SUPPORTED_TR = (2, 10, 25, 100)
SUPPORTED_DURATIONS = (60, 120, 1440)
DEFAULT_DURATION_MIN = 60

_IDF_OVERRIDES_CACHE: dict[str, dict[str, Any]] | None = None


def _idf_override_dir() -> Path:
    """Diretório de curvas IDF oficiais — `IDF_DIR` ou `backend/data/idf` (20h.4)."""
    env_dir = os.environ.get("IDF_DIR")
    if env_dir:
        return Path(env_dir)
    # services/ -> app/ -> backend/ -> backend/data/idf
    return Path(__file__).resolve().parents[2] / "data" / "idf"


def _parse_override_curvas(raw_curvas: dict[str, Any]) -> dict[int, dict[int, float]]:
    parsed: dict[int, dict[int, float]] = {}
    for dur_key, tr_map in (raw_curvas or {}).items():
        try:
            dur = int(dur_key)
        except (TypeError, ValueError):
            continue
        by_tr: dict[int, float] = {}
        for tr_key, mm in (tr_map or {}).items():
            try:
                by_tr[int(tr_key)] = float(mm)
            except (TypeError, ValueError):
                continue
        if by_tr:
            parsed[dur] = by_tr
    return parsed


def _load_idf_overrides() -> dict[str, dict[str, Any]]:
    """Lê `*.json` do diretório de overrides IDF e monta cache por `codigo_ibge`."""
    overrides: dict[str, dict[str, Any]] = {}
    idf_dir = _idf_override_dir()
    if not idf_dir.is_dir():
        return overrides
    for path in sorted(idf_dir.glob("*.json")):
        code = path.stem.zfill(7)[:7]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        curvas = _parse_override_curvas(data.get("curvas") or {})
        if not curvas:
            continue
        overrides[code] = {
            "fonte": data.get("fonte") or f"idf_oficial_{code}",
            "qualidade": data.get("qualidade") or "Oficial",
            "referencia": data.get("referencia"),
            "curvas": curvas,
        }
    return overrides


def _idf_overrides() -> dict[str, dict[str, Any]]:
    global _IDF_OVERRIDES_CACHE
    if _IDF_OVERRIDES_CACHE is None:
        _IDF_OVERRIDES_CACHE = _load_idf_overrides()
    return _IDF_OVERRIDES_CACHE


def reload_idf_overrides() -> dict[str, dict[str, Any]]:
    """Força releitura do diretório de overrides IDF (útil em testes/deploy)."""
    global _IDF_OVERRIDES_CACHE
    _IDF_OVERRIDES_CACHE = _load_idf_overrides()
    return _IDF_OVERRIDES_CACHE


def _nearest_duration(duracao_min: int) -> int:
    return min(SUPPORTED_DURATIONS, key=lambda d: abs(d - int(duracao_min or DEFAULT_DURATION_MIN)))


def _lookup_mm(
    table: dict[int, dict[int, float]],
    duracao_min: int,
    tr: int,
) -> float | None:
    dur = _nearest_duration(duracao_min)
    by_tr = table.get(dur) or table.get(DEFAULT_DURATION_MIN)
    if not by_tr:
        return None
    if tr in by_tr:
        return float(by_tr[tr])
    # interpolação linear simples entre TRs vizinhos
    keys = sorted(by_tr.keys())
    if tr <= keys[0]:
        return float(by_tr[keys[0]])
    if tr >= keys[-1]:
        return float(by_tr[keys[-1]])
    for lo, hi in zip(keys, keys[1:]):
        if lo <= tr <= hi:
            t = (tr - lo) / (hi - lo)
            return round(by_tr[lo] + t * (by_tr[hi] - by_tr[lo]), 1)
    return None


def resolve_idf_precipitacao(
    codigo_ibge: str,
    periodo_retorno_anos: int,
    *,
    duracao_min: int = DEFAULT_DURATION_MIN,
    uf: str | None = None,
) -> dict[str, Any]:
    """Resolve TR + duração → lâmina mm e metadados de procedência."""
    code = str(codigo_ibge or "").zfill(7)[:7]
    tr = int(periodo_retorno_anos)
    if tr not in SUPPORTED_TR:
        # aceita vizinho mais próximo entre os suportados
        tr = min(SUPPORTED_TR, key=lambda x: abs(x - tr))
    dur = _nearest_duration(duracao_min)

    mm: float | None = None
    fonte = "nacional"
    qualidade = "Estimado"
    escopo = "brasil"
    referencia: str | None = None

    override = _idf_overrides().get(code)
    if override:
        mm = _lookup_mm(override["curvas"], dur, tr)
        if mm is not None:
            fonte = override["fonte"]
            qualidade = override["qualidade"]
            escopo = "municipio"
            referencia = override.get("referencia")

    if mm is None and code in _IDF_MUNICIPAL:
        mm = _lookup_mm(_IDF_MUNICIPAL[code], dur, tr)
        fonte = f"tabela_piloto_{code}"
        qualidade = "Estimado"
        escopo = "municipio"

    if mm is None and uf:
        uf_key = str(uf).upper()[:2]
        if uf_key in _IDF_UF:
            mm = _lookup_mm(_IDF_UF[uf_key], dur, tr)
            fonte = f"tabela_uf_{uf_key}"
            escopo = "uf"

    if mm is None:
        mm = _lookup_mm(_IDF_NATIONAL, dur, tr) or 120.0
        fonte = "tabela_nacional_sinidu"
        escopo = "brasil"

    intensidade = round(float(mm) * (60.0 / dur), 2)

    if qualidade == "Oficial":
        nota = (
            f"Curva IDF oficial depositada localmente ({referencia or fonte}). "
            "Substitui a tabela interna Estimado para este município (20h.4)."
        )
    else:
        nota = (
            "Curva IDF de referência operacional Sinidu+Clima "
            "(60/120 min projeto + 24 h alinhado a série APAC/INMET/extremos documentados). "
            "Substituir por curva oficial do município/ANA quando disponível."
        )

    return {
        "periodo_retorno_anos": tr,
        "duracao_min": dur,
        "precipitacao_mm": round(float(mm), 1),
        "intensidade_mm_h": intensidade,
        "fonte": fonte,
        "qualidade": qualidade,
        "escopo": escopo,
        "referencia": referencia,
        "trs_disponiveis": list(SUPPORTED_TR),
        "duracoes_disponiveis": list(SUPPORTED_DURATIONS),
        "nota": nota,
    }


def idf_curve_catalog(codigo_ibge: str, *, uf: str | None = None) -> dict[str, Any]:
    """Catálogo TR×duração para a UI (chips)."""
    code = str(codigo_ibge or "").zfill(7)[:7]
    curvas: list[dict[str, Any]] = []
    for dur in SUPPORTED_DURATIONS:
        for tr in SUPPORTED_TR:
            resolved = resolve_idf_precipitacao(code, tr, duracao_min=dur, uf=uf)
            curvas.append(
                {
                    "periodo_retorno_anos": tr,
                    "duracao_min": dur,
                    "precipitacao_mm": resolved["precipitacao_mm"],
                    "intensidade_mm_h": resolved["intensidade_mm_h"],
                    "label": f"TR{tr} · {dur} min",
                }
            )
    sample = resolve_idf_precipitacao(code, 100, duracao_min=DEFAULT_DURATION_MIN, uf=uf)
    return {
        "codigo_ibge": code,
        "uf": uf,
        "fonte": sample["fonte"],
        "qualidade": sample["qualidade"],
        "escopo": sample["escopo"],
        "referencia": sample.get("referencia"),
        "nota": sample["nota"],
        "curvas": curvas,
        "default_duracao_min": DEFAULT_DURATION_MIN,
    }
