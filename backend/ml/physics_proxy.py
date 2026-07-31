"""Proxies físicos chuva→alagamento para o vetor ML (Fase 21d.8).

Liga a física (SCS-CN + balanço de rede de drenagem) ao modelo sem rodar
DEM/D8 por data de treino. Não é saída hidrodinâmica — selo Derivado.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

from app.services.drainage_capacity_service import EFICIENCIA_REDE
from app.services.scs_cn_service import scs_runoff_mm

PHYSICS_PROXY_COLUMNS = (
    "lamina_proxy_mm",
    "escoamento_excesso_mm",
    "rede_saturada_flag",
    "area_alagada_proxy_pct",
)

PHYSICS_PROXY_NOTE = (
    "Proxy físico SCS+rede (21d.8) — não é lâmina DEM nem mancha HEC-RAS; qualidade=Derivado."
)


def compute_flood_physics_proxies(
    precip_24h: float,
    *,
    curve_number: float = 85.0,
    capacidade_drenagem_mm_h: float = 18.0,
    impermeabilizacao_pct: float = 45.0,
    suscetibilidade_hand: float = 0.35,
    pct_hand_lt_5m: float = 15.0,
    duracao_chuva_h: float = 6.0,
    eficiencia_rede: float = EFICIENCIA_REDE,
) -> dict[str, float]:
    """
    Deriva 4 features dinâmicas a partir da chuva do dia + terreno.

    - lamina_proxy_mm: escoamento direto SCS (mm)
    - escoamento_excesso_mm: Q − capacidade×duração×eficiência
    - rede_saturada_flag: 1 se precip supera sumidouro da rede
    - area_alagada_proxy_pct: % proxy (excedente × impermeab. × HAND baixo)
    """
    p = max(0.0, float(precip_24h))
    cn = max(1.0, min(100.0, float(curve_number)))
    cap = max(1.0, float(capacidade_drenagem_mm_h))
    dur = max(0.5, min(24.0, float(duracao_chuva_h))) if p > 0 else 0.0
    eff = max(0.1, min(1.0, float(eficiencia_rede)))

    lamina = scs_runoff_mm(p, cn)
    sumidouro = cap * dur * eff if dur > 0 else 0.0
    excesso = max(0.0, lamina - sumidouro)
    saturada = 1.0 if (p > sumidouro + 1e-6 and p > 0) else 0.0

    u = max(0.0, min(1.0, float(impermeabilizacao_pct) / 100.0))
    hand_f = max(0.0, min(1.0, float(pct_hand_lt_5m) / 100.0))
    susc = max(0.0, min(1.0, float(suscetibilidade_hand)))
    terr_f = 0.35 + 0.35 * u + 0.15 * hand_f + 0.15 * susc
    ex_norm = 1.0 - math.exp(-excesso / 25.0) if excesso > 0 else 0.0
    area_pct = 100.0 * max(0.0, min(1.0, ex_norm * terr_f))

    return {
        "lamina_proxy_mm": round(lamina, 3),
        "escoamento_excesso_mm": round(excesso, 3),
        "rede_saturada_flag": float(saturada),
        "area_alagada_proxy_pct": round(area_pct, 2),
    }


def apply_physics_proxies_to_row(row: Mapping[str, Any]) -> dict[str, float]:
    """Aplica proxies a um dict/Series de features já montado."""
    dur = float(row.get("duracao_chuva_h") or 0.0)
    if dur <= 0 and float(row.get("precip_24h") or 0.0) > 0:
        dur = 6.0
    return compute_flood_physics_proxies(
        float(row.get("precip_24h") or 0.0),
        curve_number=float(row.get("curve_number") or 85.0),
        capacidade_drenagem_mm_h=float(row.get("capacidade_drenagem_mm_h") or 18.0),
        impermeabilizacao_pct=float(row.get("impermeabilizacao_pct") or 45.0),
        suscetibilidade_hand=float(row.get("suscetibilidade_hand") or 0.35),
        pct_hand_lt_5m=float(row.get("pct_hand_lt_5m") or 15.0),
        duracao_chuva_h=dur,
    )


def enrich_dataframe_physics_proxies(df):
    """Adiciona as 4 colunas 21d.8 a um DataFrame de treino."""
    import pandas as pd

    if df is None or len(df) == 0:
        return df
    out = df.copy()
    rows = [apply_physics_proxies_to_row(r) for r in out.to_dict(orient="records")]
    prox = pd.DataFrame(rows, index=out.index)
    for col in PHYSICS_PROXY_COLUMNS:
        out[col] = prox[col]
    return out
