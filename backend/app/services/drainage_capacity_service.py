"""Capacidade de microdrenagem como sumidouro no balanço pluvial (17g.1d).

Proxy municipal (SNIS / densidade) — não inventaria galerias/bueiros.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Municipio, MunicipioSaneamento

# Faixa tipificada de capacidade efetiva da rede (mm/h) em evento de projeto ~1 h
CAPACIDADE_MIN_MM_H = 8.0
CAPACIDADE_MAX_MM_H = 50.0
EFICIENCIA_REDE = 0.85  # perdas por obstrução / manutenção


def _clamp_cap(mm_h: float) -> float:
    return max(CAPACIDADE_MIN_MM_H, min(CAPACIDADE_MAX_MM_H, float(mm_h)))


def _proxy_from_snis(row: MunicipioSaneamento | None) -> tuple[float | None, str | None]:
    if not row:
        return None, None
    if row.indice_drenagem is not None:
        idx = float(row.indice_drenagem)
        # indice tipicamente 0–100 (% atendimento / score SNIS)
        if idx > 1.5:
            idx = idx / 100.0
        idx = max(0.0, min(1.0, idx))
        return _clamp_cap(CAPACIDADE_MIN_MM_H + idx * (CAPACIDADE_MAX_MM_H - CAPACIDADE_MIN_MM_H)), "snis_indice_drenagem"

    cob_e = float(row.cobertura_esgoto_pct) if row.cobertura_esgoto_pct is not None else None
    cob_a = float(row.cobertura_agua_pct) if row.cobertura_agua_pct is not None else None
    if cob_e is None and cob_a is None:
        return None, None
    vals = [v / 100.0 if v > 1.5 else v for v in (cob_e, cob_a) if v is not None]
    mean_cov = sum(vals) / len(vals)
    mean_cov = max(0.0, min(1.0, mean_cov))
    return (
        _clamp_cap(CAPACIDADE_MIN_MM_H + mean_cov * 38.0),
        "snis_cobertura_proxy",
    )


def _proxy_from_density(muni: Municipio) -> float:
    pop = int(muni.populacao or 0)
    area = float(muni.area_km2 or 0)
    dens = (pop / area) if area > 0 else 0.0
    if dens >= 3000:
        return 22.0
    if dens >= 1000:
        return 18.0
    if dens >= 200:
        return 15.0
    return 12.0


def resolve_drainage_capacity(
    db: Session,
    muni: Municipio,
    *,
    precip_mm: float,
    drainage_capacity_mm_h: float | None = None,
    aplicar_drenagem: bool = True,
    duracao_h: float = 1.0,
) -> dict[str, Any]:
    """Resolve lâmina removida pela rede (mm) e flag de saturação."""
    code = str(muni.codigo_ibge).zfill(7)[:7]
    dur = max(0.25, min(float(duracao_h or 1.0), 6.0))
    precip = max(0.0, float(precip_mm or 0.0))

    if not aplicar_drenagem:
        return {
            "codigo_ibge": code,
            "aplicado": False,
            "capacidade_mm_h": 0.0,
            "duracao_h": dur,
            "removido_mm": 0.0,
            "saturada": False,
            "fonte": None,
            "ano_referencia_snis": None,
            "nota": "Sumidouro de rede desligado nesta simulação.",
        }

    snis = (
        db.query(MunicipioSaneamento)
        .filter(MunicipioSaneamento.codigo_ibge == code)
        .first()
    )

    if drainage_capacity_mm_h is not None:
        capacidade = _clamp_cap(float(drainage_capacity_mm_h))
        fonte = "manual"
    else:
        snis_cap, snis_fonte = _proxy_from_snis(snis)
        if snis_cap is not None:
            capacidade = snis_cap
            fonte = snis_fonte or "snis"
        else:
            capacidade = _clamp_cap(_proxy_from_density(muni))
            fonte = "densidade_proxy"

    removido = min(precip, capacidade * dur * EFICIENCIA_REDE)
    saturada = precip > (capacidade * dur * EFICIENCIA_REDE + 1e-6)

    return {
        "codigo_ibge": code,
        "aplicado": removido > 0,
        "capacidade_mm_h": round(capacidade, 2),
        "duracao_h": round(dur, 2),
        "eficiencia": EFICIENCIA_REDE,
        "removido_mm": round(removido, 2),
        "saturada": saturada,
        "fonte": fonte,
        "ano_referencia_snis": int(snis.ano_referencia) if snis and snis.ano_referencia else None,
        "nota": (
            "Proxy de capacidade da microdrenagem (SNIS/densidade) como sumidouro "
            "no balanço pluvial. Não modela inventário de galerias/bueiros nem routing de rede. "
            + (
                "Rede saturada: excedente permanece na superfície."
                if saturada
                else "Rede absorve parte da lâmina efetiva."
            )
        ),
    }


def municipal_drainage_features(db: Session, codigo_ibge: str) -> dict[str, float]:
    """Features ML municipais de drenagem (capacidade mm/h e saturação sob 40 mm/1h)."""
    code = str(codigo_ibge).zfill(7)[:7]
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == code).first()
    if not muni:
        return {"capacidade_drenagem_mm_h": 18.0, "saturacao_drenagem_40mm": 0.5}

    resolved = resolve_drainage_capacity(db, muni, precip_mm=40.0, duracao_h=1.0)
    cap = float(resolved["capacidade_mm_h"])
    # Fração saturada sob chuva de referência 40 mm/h (0 = folga, 1 = satura)
    rem = float(resolved["removido_mm"])
    sat = 0.0 if rem >= 40.0 else round(1.0 - (rem / 40.0), 3)
    return {
        "capacidade_drenagem_mm_h": round(cap, 2),
        "saturacao_drenagem_40mm": sat,
    }


def bairro_drainage_capacity_mm_h(
    municipal_mm_h: float,
    *,
    impermeabilizacao_pct: float,
    water_proximity: float = 0.0,
) -> float:
    """Espacializa capacidade municipal por bairro (21d.4).

    Mais impermeável / mais próximo d'água → capacidade efetiva menor
    (assoreamento, vazão de pico, entupimento).
    """
    base = float(municipal_mm_h)
    urban = max(0.0, min(100.0, float(impermeabilizacao_pct))) / 100.0
    water = max(0.0, min(1.0, float(water_proximity)))
    factor = 1.15 - 0.35 * urban - 0.15 * water
    return _clamp_cap(base * factor)
