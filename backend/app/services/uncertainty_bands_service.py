"""Bandas de incerteza otimista/esperada/pessimista (17g.2c)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.simulation_cache import run_rainfall_cached

DEFAULT_DELTA_PCT = 15.0


def _band_summary(sim: dict[str, Any]) -> dict[str, Any]:
    meta = sim.get("simulation_meta") or {}
    return {
        "precipitacao_mm": round(float(sim.get("input_value") or 0), 1),
        "max_depth_m": round(float(meta.get("max_depth_m") or 0), 3),
        "affected_area_km2": round(float(sim.get("affected_area_km2") or 0), 3),
        "affected_population": int(sim.get("affected_population") or 0),
        "flood_patches": int(meta.get("flood_patches") or 0),
    }


def attach_uncertainty_bands(
    db: Session,
    muni_id: int,
    codigo_ibge: str,
    result: dict[str, Any],
    *,
    delta_pct: float = DEFAULT_DELTA_PCT,
) -> dict[str, Any]:
    """Anexa envelope ±delta% de precipitação ao simulation_meta (reusa cache)."""
    if not isinstance(result, dict):
        return result
    if (result.get("scenario_type") or "") != "ExtremeRainfall":
        return result

    mm = float(result.get("input_value") or 0)
    if mm <= 0:
        return result

    delta = max(5.0, min(float(delta_pct), 40.0))
    opt_mm = round(mm * (1.0 - delta / 100.0), 1)
    pes_mm = round(mm * (1.0 + delta / 100.0), 1)
    opt_mm = max(10.0, opt_mm)
    pes_mm = min(400.0, pes_mm)

    try:
        opt = run_rainfall_cached(db, muni_id, codigo_ibge, opt_mm)
        pes = run_rainfall_cached(db, muni_id, codigo_ibge, pes_mm)
    except Exception:
        return result

    out = dict(result)
    meta = dict(out.get("simulation_meta") or {})
    meta["uncertainty_bands"] = {
        "precip_delta_pct": delta,
        "method": "precip_pct_envelope",
        "optimistic": _band_summary(opt),
        "expected": _band_summary(out),
        "pessimistic": _band_summary(pes),
        "nota": (
            f"Envelope ±{delta:.0f}% na precipitação do cenário esperado. "
            "Comunica incerteza do modelo paramétrico — não é intervalo de confiança estatístico."
        ),
    }
    out["simulation_meta"] = meta
    return out
