"""Nível do mar / storm surge para municípios costeiros (17g.1c)."""

from __future__ import annotations

from typing import Any

# Pilotos costeiros Sinidu (Recife, Aracaju)
COASTAL_IBGE = frozenset({"2611606", "2800308"})

# Elevação da cota base (m) — referência operacional IPCC AR6 / storm surge local
IPCC_NIVEL_MAR_M: dict[str, float] = {
    "atual": 0.0,
    "ssp2_45_2050": 0.30,
    "ssp2_45_2100": 0.55,
    "ssp5_85_2050": 0.45,
    "ssp5_85_2100": 0.85,
    "storm_surge": 1.20,
}

IPCC_LABELS: dict[str, str] = {
    "atual": "Atual (sem elevação)",
    "ssp2_45_2050": "SSP2-4.5 · 2050 (~+0,30 m)",
    "ssp2_45_2100": "SSP2-4.5 · 2100 (~+0,55 m)",
    "ssp5_85_2050": "SSP5-8.5 · 2050 (~+0,45 m)",
    "ssp5_85_2100": "SSP5-8.5 · 2100 (~+0,85 m)",
    "storm_surge": "Storm surge / maré meteórica (~+1,20 m)",
}


def is_coastal(codigo_ibge: str) -> bool:
    return str(codigo_ibge or "").zfill(7)[:7] in COASTAL_IBGE


def resolve_nivel_mar(
    codigo_ibge: str,
    *,
    nivel_mar_m: float | None = None,
    cenario_nivel_mar: str | None = None,
) -> dict[str, Any]:
    """Resolve offset de cota (m) para o município."""
    code = str(codigo_ibge or "").zfill(7)[:7]
    if not is_coastal(code):
        return {
            "codigo_ibge": code,
            "costeiro": False,
            "nivel_mar_m": 0.0,
            "cenario": None,
            "aplicado": False,
            "nota": "Offset de nível do mar só se aplica a municípios costeiros piloto (Recife/Aracaju).",
        }

    cenario = (cenario_nivel_mar or "").strip().lower() or None
    if cenario and cenario not in IPCC_NIVEL_MAR_M:
        cenario = None

    if nivel_mar_m is not None:
        offset = max(0.0, min(float(nivel_mar_m), 3.0))
        fonte = "manual"
        cenario_out = cenario or "manual"
    elif cenario:
        offset = float(IPCC_NIVEL_MAR_M[cenario])
        fonte = "ipcc_ar6_proxy"
        cenario_out = cenario
    else:
        offset = 0.0
        fonte = None
        cenario_out = "atual"

    return {
        "codigo_ibge": code,
        "costeiro": True,
        "nivel_mar_m": round(offset, 3),
        "cenario": cenario_out,
        "cenario_label": IPCC_LABELS.get(cenario_out or "atual", cenario_out),
        "fonte": fonte,
        "aplicado": offset > 0,
        "cenarios_disponiveis": [
            {"id": k, "label": IPCC_LABELS[k], "nivel_mar_m": v}
            for k, v in IPCC_NIVEL_MAR_M.items()
        ],
        "nota": (
            "Offset somado à cota base da mancha pluvial (proxy de SLR/storm surge). "
            "Não modela maré astronômica horária nem correntes."
        ),
    }
