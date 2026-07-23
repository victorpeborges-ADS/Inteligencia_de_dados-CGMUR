"""Curvas IDF / período de retorno → lâmina (mm) — 17g.1a.

Tabelas de referência operacional para pilotos (Recife, Aracaju) e fallbacks
por UF / nacional. Qualidade "Estimado" até calibração com PDFs municipais
ou ANA/INMET. O motor hidráulico continua recebendo apenas precipitacao_mm.
"""

from __future__ import annotations

from typing import Any

# Lâmina acumulada (mm) por duração de projeto (min) e TR (anos).
# Valores típicos de projeto urbano costeiro NE — calibráveis.
_IDF_MUNICIPAL: dict[str, dict[int, dict[int, float]]] = {
    "2611606": {  # Recife-PE
        60: {2: 48.0, 10: 78.0, 25: 105.0, 100: 145.0},
        120: {2: 62.0, 10: 98.0, 25: 130.0, 100: 180.0},
    },
    "2800308": {  # Aracaju-SE
        60: {2: 42.0, 10: 70.0, 25: 95.0, 100: 132.0},
        120: {2: 55.0, 10: 88.0, 25: 118.0, 100: 165.0},
    },
}

_IDF_UF: dict[str, dict[int, dict[int, float]]] = {
    "PE": {
        60: {2: 45.0, 10: 74.0, 25: 98.0, 100: 138.0},
        120: {2: 58.0, 10: 92.0, 25: 122.0, 100: 170.0},
    },
    "SE": {
        60: {2: 40.0, 10: 68.0, 25: 90.0, 100: 128.0},
        120: {2: 52.0, 10: 85.0, 25: 112.0, 100: 158.0},
    },
}

_IDF_NATIONAL: dict[int, dict[int, float]] = {
    60: {2: 40.0, 10: 65.0, 25: 88.0, 100: 125.0},
    120: {2: 52.0, 10: 82.0, 25: 110.0, 100: 155.0},
}

SUPPORTED_TR = (2, 10, 25, 100)
SUPPORTED_DURATIONS = (60, 120)
DEFAULT_DURATION_MIN = 60


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

    if code in _IDF_MUNICIPAL:
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

    return {
        "periodo_retorno_anos": tr,
        "duracao_min": dur,
        "precipitacao_mm": round(float(mm), 1),
        "intensidade_mm_h": intensidade,
        "fonte": fonte,
        "qualidade": qualidade,
        "escopo": escopo,
        "trs_disponiveis": list(SUPPORTED_TR),
        "duracoes_disponiveis": list(SUPPORTED_DURATIONS),
        "nota": (
            "Curva IDF de referência operacional Sinidu+Clima. "
            "Substituir por curva oficial do município/ANA quando disponível."
        ),
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
        "nota": sample["nota"],
        "curvas": curvas,
        "default_duracao_min": DEFAULT_DURATION_MIN,
    }
