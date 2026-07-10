"""Cache Redis/memória para interpretação IA pós-simulação."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.data_connectors.cache import cache_get_json, cache_set_json
from app.models import Municipio
from app.services.simulation_interpreter import interpret_simulation

SIMULATION_INTERPRET_CACHE_TTL = int(os.getenv("SIMULATION_INTERPRET_CACHE_TTL", str(6 * 3600)))
SIMULATION_INTERPRET_CACHE_ENABLED = os.getenv(
    "SIMULATION_INTERPRET_CACHE_ENABLED", "true"
).lower() in ("1", "true", "yes", "on")


def _fingerprint(
    resultado_simulacao: dict[str, Any],
    comparacao_delta: dict[str, Any] | None,
    lst_comparison: dict[str, Any] | None = None,
) -> str:
    meta = resultado_simulacao.get("simulation_meta") or {}
    payload = {
        "area": resultado_simulacao.get("affected_area_km2"),
        "pop": resultado_simulacao.get("affected_population"),
        "patches": meta.get("flood_patches"),
        "max_depth": meta.get("max_depth_m"),
        "max_delta_t": meta.get("max_delta_t_c"),
        "model": meta.get("model_version"),
        "delta": comparacao_delta,
        "lst_div": (lst_comparison or {}).get("divergencia_mediana_c"),
        "lst_n": (lst_comparison or {}).get("amostras_validas"),
    }
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_key(
    codigo_ibge: str,
    tipo_simulacao: str,
    parametro_atual: float,
    parametro_referencia: float,
    fingerprint: str,
    use_ai: bool,
) -> str:
    ibge = str(codigo_ibge).strip().zfill(7)[:7]
    return (
        f"sinidu:sim:interp:{ibge}:{tipo_simulacao}:{parametro_atual:.1f}:"
        f"{parametro_referencia:.1f}:{fingerprint}:ai{int(use_ai)}"
    )


def interpret_simulation_cached(
    db: Session,
    muni: Municipio,
    *,
    tipo_simulacao: Literal["chuva", "asfalto", "vegetacao", "drenagem", "calor"],
    parametro_atual: float,
    parametro_referencia: float = 80.0,
    resultado_simulacao: dict[str, Any],
    resultado_referencia: dict[str, Any] | None = None,
    comparacao_delta: dict[str, Any] | None = None,
    lst_comparison: dict[str, Any] | None = None,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
    use_ai: bool = True,
) -> dict[str, Any]:
    fp = _fingerprint(resultado_simulacao, comparacao_delta, lst_comparison)
    key = _cache_key(
        muni.codigo_ibge,
        tipo_simulacao,
        parametro_atual,
        parametro_referencia,
        fp,
        use_ai,
    )

    if SIMULATION_INTERPRET_CACHE_ENABLED:
        cached = cache_get_json(key)
        if cached and isinstance(cached, dict):
            out = dict(cached)
            out["from_cache"] = True
            return out

    result = interpret_simulation(
        db,
        muni,
        tipo_simulacao=tipo_simulacao,
        parametro_atual=parametro_atual,
        parametro_referencia=parametro_referencia,
        resultado_simulacao=resultado_simulacao,
        resultado_referencia=resultado_referencia,
        comparacao_delta=comparacao_delta,
        lst_comparison=lst_comparison,
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_api_key=ai_api_key,
        use_ai=use_ai,
    )
    payload = {**result, "from_cache": False}
    if SIMULATION_INTERPRET_CACHE_ENABLED:
        cache_set_json(key, payload, ttl=SIMULATION_INTERPRET_CACHE_TTL)
    return payload
