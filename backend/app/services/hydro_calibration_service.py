"""Calibração de coeficientes do motor pluvial por município (17g.2b).

Ajusta escalas de runoff / rise / river boost / IRI com base no histórico S2ID
(e opcionalmente no hit-rate da última simulação). Persistência em ficheiro
JSON por IBGE (+ Redis se disponível).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.data_connectors.cache import cache_get_json, cache_set_json
from app.models import HistoricoDesastreS2ID, Municipio

logger = logging.getLogger(__name__)

CALIB_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "hydro_calibration"
REDIS_TTL = 30 * 24 * 3600  # 30 dias

SCALE_KEYS = ("runoff_scale", "rise_scale", "river_boost_scale", "iri_scale")
SCALE_MIN, SCALE_MAX = 0.70, 1.40

# Proxy de bioma por UF (até haver bioma IBGE no modelo)
UF_BIOME_DEFAULTS: dict[str, dict[str, float]] = {
    # Amazônia — maior interceptação / resposta mais lenta
    "AM": {"runoff_scale": 0.92, "rise_scale": 0.95, "river_boost_scale": 1.05, "iri_scale": 1.0},
    "PA": {"runoff_scale": 0.92, "rise_scale": 0.95, "river_boost_scale": 1.05, "iri_scale": 1.0},
    "AC": {"runoff_scale": 0.92, "rise_scale": 0.95, "river_boost_scale": 1.05, "iri_scale": 1.0},
    "RO": {"runoff_scale": 0.92, "rise_scale": 0.95, "river_boost_scale": 1.05, "iri_scale": 1.0},
    "RR": {"runoff_scale": 0.92, "rise_scale": 0.95, "river_boost_scale": 1.05, "iri_scale": 1.0},
    "AP": {"runoff_scale": 0.92, "rise_scale": 0.95, "river_boost_scale": 1.05, "iri_scale": 1.0},
    # Semiárido — escoamento rápido em solo impermeável
    "CE": {"runoff_scale": 1.08, "rise_scale": 1.05, "river_boost_scale": 0.95, "iri_scale": 1.05},
    "RN": {"runoff_scale": 1.08, "rise_scale": 1.05, "river_boost_scale": 0.95, "iri_scale": 1.05},
    "PB": {"runoff_scale": 1.08, "rise_scale": 1.05, "river_boost_scale": 0.95, "iri_scale": 1.05},
    "PE": {"runoff_scale": 1.05, "rise_scale": 1.05, "river_boost_scale": 1.05, "iri_scale": 1.05},
    "AL": {"runoff_scale": 1.05, "rise_scale": 1.05, "river_boost_scale": 1.05, "iri_scale": 1.05},
    "SE": {"runoff_scale": 1.05, "rise_scale": 1.05, "river_boost_scale": 1.05, "iri_scale": 1.05},
    "BA": {"runoff_scale": 1.05, "rise_scale": 1.02, "river_boost_scale": 1.0, "iri_scale": 1.02},
    "PI": {"runoff_scale": 1.08, "rise_scale": 1.05, "river_boost_scale": 0.95, "iri_scale": 1.05},
}


def _ibge(code: str) -> str:
    return str(code).strip().zfill(7)[:7]


def _clamp(v: float) -> float:
    return round(max(SCALE_MIN, min(SCALE_MAX, float(v))), 3)


def default_calibration(codigo_ibge: str, uf: str | None = None) -> dict[str, Any]:
    uf_u = (uf or "").upper()[:2]
    base = {
        "codigo_ibge": _ibge(codigo_ibge),
        "runoff_scale": 1.0,
        "rise_scale": 1.0,
        "river_boost_scale": 1.0,
        "iri_scale": 1.0,
        "biome_proxy": uf_u or None,
        "source": "default",
        "version": 1,
        "hit_rate": None,
        "eventos_s2id_inundacao": None,
        "updated_at": None,
        "nota": "Coeficientes padrão do motor (sem calibração local).",
    }
    if uf_u in UF_BIOME_DEFAULTS:
        base.update(UF_BIOME_DEFAULTS[uf_u])
        base["source"] = "uf_biome_proxy"
        base["nota"] = f"Escalas iniciais por UF ({uf_u}) como proxy de bioma."
    return base


def _file_path(codigo_ibge: str) -> Path:
    return CALIB_DIR / f"{_ibge(codigo_ibge)}.json"


def _redis_key(codigo_ibge: str) -> str:
    return f"sinidu:hydro:calib:{_ibge(codigo_ibge)}"


def load_calibration(codigo_ibge: str, uf: str | None = None) -> dict[str, Any]:
    code = _ibge(codigo_ibge)
    cached = cache_get_json(_redis_key(code))
    if isinstance(cached, dict) and "rise_scale" in cached:
        return {**default_calibration(code, uf), **cached, "codigo_ibge": code}

    path = _file_path(code)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                out = {**default_calibration(code, uf), **data, "codigo_ibge": code}
                cache_set_json(_redis_key(code), out, ttl=REDIS_TTL)
                return out
        except Exception as exc:
            logger.warning("Falha ao ler calibração %s: %s", path, exc)

    return default_calibration(code, uf)


def save_calibration(payload: dict[str, Any]) -> dict[str, Any]:
    code = _ibge(str(payload.get("codigo_ibge") or ""))
    if not code or code == "0000000":
        raise ValueError("codigo_ibge inválido")
    out = {**default_calibration(code, payload.get("biome_proxy")), **payload, "codigo_ibge": code}
    for k in SCALE_KEYS:
        out[k] = _clamp(out.get(k, 1.0))
    try:
        out["version"] = max(1, int(out.get("version") or 1))
    except (TypeError, ValueError):
        out["version"] = 1
    out["updated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    out.pop("_bump_version", None)

    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    path = _file_path(code)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    cache_set_json(_redis_key(code), out, ttl=REDIS_TTL)
    return out


def calibration_cache_stamp(codigo_ibge: str, uf: str | None = None) -> str:
    c = load_calibration(codigo_ibge, uf)
    return (
        f"c{c.get('version', 1)}"
        f"r{float(c.get('rise_scale', 1)):.2f}"
        f"o{float(c.get('runoff_scale', 1)):.2f}"
    )


def _count_flood_s2id(db: Session, muni: Municipio) -> int:
    from app.services.simulation_confidence_service import _is_flood_type

    rows = (
        db.query(HistoricoDesastreS2ID)
        .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
        .all()
    )
    return sum(1 for e in rows if _is_flood_type(e.tipo_desastre) and e.geom is not None)


def auto_calibrate(
    db: Session,
    muni: Municipio,
    *,
    hit_rate: float | None = None,
    precip_mm: float = 120.0,
    run_simulation: bool = True,
) -> dict[str, Any]:
    """Ajusta escalas: prioriza hit_rate S2ID; senão usa contagem de eventos."""
    current = load_calibration(muni.codigo_ibge, getattr(muni, "uf", None))
    n_events = _count_flood_s2id(db, muni)

    hr = hit_rate
    if hr is None and run_simulation:
        try:
            from app.services.simulation_cache import run_rainfall_cached

            result = run_rainfall_cached(db, muni.id, muni.codigo_ibge, float(precip_mm))
            meta = result.get("simulation_meta") or {}
            val = meta.get("validacao_s2id") or {}
            if val.get("hit_rate") is not None:
                hr = float(val["hit_rate"])
        except Exception as exc:
            logger.warning("Auto-calibração: simulação falhou (%s) — usa contagem S2ID", exc)

    runoff = float(current.get("runoff_scale") or 1.0)
    rise = float(current.get("rise_scale") or 1.0)
    river = float(current.get("river_boost_scale") or 1.0)
    iri = float(current.get("iri_scale") or 1.0)
    source = "auto_s2id"
    nota = ""

    if hr is not None:
        if hr < 0.30:
            rise = _clamp(rise * 1.15)
            river = _clamp(river * 1.10)
            runoff = _clamp(runoff * 1.05)
            nota = f"Hit-rate S2ID {hr:.0%} baixo — ampliou mancha (rise/river)."
        elif hr > 0.75:
            rise = _clamp(rise * 0.90)
            river = _clamp(river * 0.92)
            runoff = _clamp(runoff * 0.95)
            nota = f"Hit-rate S2ID {hr:.0%} alto — reduziu mancha para evitar overfit."
        else:
            nota = f"Hit-rate S2ID {hr:.0%} na faixa alvo (30–75%) — escalas mantidas/ajustadas levemente."
            # micro-ajuste em direção a 0.5
            if hr < 0.45:
                rise = _clamp(rise * 1.05)
            elif hr > 0.60:
                rise = _clamp(rise * 0.97)
    else:
        source = "auto_s2id_count"
        if n_events >= 8:
            rise = _clamp(1.12)
            river = _clamp(1.10)
            iri = _clamp(1.05)
            nota = f"{n_events} eventos S2ID georref. — escalas um pouco mais agressivas."
        elif n_events == 0:
            rise = _clamp(0.95)
            river = _clamp(0.95)
            nota = "Sem eventos S2ID georref. — escalas conservadoras (proxy UF)."
        else:
            nota = f"{n_events} evento(s) S2ID — mantém proxy UF + leve reforço."
            rise = _clamp(max(rise, 1.05))

    out = save_calibration(
        {
            **current,
            "runoff_scale": runoff,
            "rise_scale": rise,
            "river_boost_scale": river,
            "iri_scale": iri,
            "source": source,
            "hit_rate": hr,
            "eventos_s2id_inundacao": n_events,
            "nota": nota,
            "version": int(current.get("version") or 1) + 1,
            "_bump_version": False,
        }
    )
    return out


def apply_manual_scales(
    codigo_ibge: str,
    scales: dict[str, float],
    *,
    uf: str | None = None,
    nota: str | None = None,
) -> dict[str, Any]:
    current = load_calibration(codigo_ibge, uf)
    payload = {
        **current,
        "source": "manual",
        "nota": nota or "Escalas definidas manualmente.",
        "version": int(current.get("version") or 1) + 1,
        "_bump_version": False,
    }
    for k in SCALE_KEYS:
        if k in scales and scales[k] is not None:
            payload[k] = _clamp(scales[k])
    return save_calibration(payload)
