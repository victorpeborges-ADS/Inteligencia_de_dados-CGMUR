"""Comparador LST observada (GeoReDUS) × simulação de ilha de calor Sinidu."""

from __future__ import annotations

import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Bairro, Municipio
from app.services.georedus_lst_service import (
    LST_FONTE_LABEL,
    LST_PERIODO_LABEL,
    fetch_lst_point,
)

LIMITES_METODOLOGICOS = [
    "LST: temperatura de superfície medida por satélite (Landsat), média máxima "
    f"{LST_PERIODO_LABEL} — não é temperatura do ar nem cenário futuro.",
    "Simulação Sinidu: proxy territorial (pico previsto + ΔT por bairro) derivado de "
    "MapBiomas, densidade e IVC — não mede radiometria de superfície.",
    "A comparação é indicativa para oficinas e narrativa de gestão; não valida "
    "cientificamente o modelo nem substitui estudo microclimático de campo.",
    "Amostragem por centróide de bairro; resolução Landsat (~30 m) pode não capturar "
    "microvariações intra-bairro.",
]


def _sim_temps_by_bairro(simulation: dict[str, Any]) -> dict[str, float]:
    meta = simulation.get("simulation_meta") or {}
    out: dict[str, float] = {}
    for row in meta.get("bairros_exposicao") or []:
        nome = row.get("bairro")
        temp = row.get("temp_local_c") or row.get("temp_superficie_c")
        if nome and temp is not None:
            out[str(nome)] = round(float(temp), 1)
    if out:
        return out
    for feat in (simulation.get("geometry") or {}).get("features") or []:
        props = feat.get("properties") or {}
        if props.get("layer_type") != "heat_band":
            continue
        nome = props.get("name")
        temp = props.get("temp_surface_celsius") or props.get("temp_local_celsius")
        if nome and temp is not None:
            out[str(nome)] = round(float(temp), 1)
    return out


def _bairro_centroids(db: Session, municipio_id: int, nomes: list[str]) -> dict[str, tuple[float, float]]:
    if not nomes:
        return {}
    rows = (
        db.query(
            Bairro.nome,
            func.ST_X(func.ST_Centroid(Bairro.geom)).label("lon"),
            func.ST_Y(func.ST_Centroid(Bairro.geom)).label("lat"),
        )
        .filter(Bairro.municipio_id == municipio_id, Bairro.nome.in_(nomes))
        .all()
    )
    return {
        str(r.nome): (float(r.lon), float(r.lat))
        for r in rows
        if r.lon is not None and r.lat is not None
    }


def _fetch_lst_batch(points: dict[str, tuple[float, float]], *, max_workers: int = 6) -> dict[str, float | None]:
    results: dict[str, float | None] = {nome: None for nome in points}
    if not points:
        return results

    def _one(item: tuple[str, tuple[float, float]]) -> tuple[str, float | None]:
        nome, (lon, lat) = item
        return nome, fetch_lst_point(lon, lat)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_one, item): item[0] for item in points.items()}
        for fut in as_completed(futures):
            nome = futures[fut]
            try:
                _, val = fut.result()
                results[nome] = val
            except Exception:
                results[nome] = None
    return results


def _median(values: list[float]) -> float | None:
    return round(statistics.median(values), 1) if values else None


def _build_narrativa(
    muni: Municipio,
    *,
    lst_mediana: float | None,
    sim_mediana: float,
    divergencia: float | None,
    amostras_validas: int,
    amostras_total: int,
    pico_previsto: float | None,
) -> str:
    if amostras_validas == 0:
        return (
            f"Não foi possível obter LST observada para os bairros de {muni.nome}/{muni.uf} "
            f"({amostras_total} tentativas). A simulação Sinidu permanece válida como proxy "
            "territorial; consulte a camada LST no mapa ou o GeoReDUS para validação visual."
        )

    lst_txt = f"{lst_mediana}°C" if lst_mediana is not None else "—"
    div_txt = f"{divergencia:+.1f}°C" if divergencia is not None else "—"
    pico_txt = f"{pico_previsto}°C" if pico_previsto is not None else "cenário informado"

    return (
        f"Em {muni.nome}/{muni.uf}, a LST observada (Landsat, {LST_PERIODO_LABEL}) mediana "
        f"em {amostras_validas} bairro(s) é {lst_txt}, enquanto a simulação Sinidu projeta "
        f"mediana de {sim_mediana}°C no pico previsto ({pico_txt}). "
        f"Diferença mediana: {div_txt}. "
        "Essa divergência é esperada: a LST mede superfície em período histórico; "
        "o modelo simula onda de calor futura com ΔT territorial por impermeabilização e vegetação."
    )


def compare_heat_simulation_with_lst(
    db: Session,
    muni: Municipio,
    simulation: dict[str, Any],
    *,
    max_bairros: int = 20,
) -> dict[str, Any]:
    sim_by_bairro = _sim_temps_by_bairro(simulation)
    if not sim_by_bairro:
        return {
            "disponivel": False,
            "municipio": muni.nome,
            "uf": muni.uf,
            "codigo_ibge": muni.codigo_ibge,
            "lst_fonte": LST_FONTE_LABEL,
            "lst_periodo": LST_PERIODO_LABEL,
            "amostras_validas": 0,
            "amostras_total": 0,
            "bairros": [],
            "narrativa": "Simulação sem bairros térmicos para comparar com LST observada.",
            "limites_metodologicos": LIMITES_METODOLOGICOS,
        }

    ranked = sorted(sim_by_bairro.items(), key=lambda x: x[1], reverse=True)
    selected = [nome for nome, _ in ranked[:max_bairros]]
    centroids = _bairro_centroids(db, muni.id, selected)
    lst_values = _fetch_lst_batch(centroids)

    bairros_rows: list[dict[str, Any]] = []
    lst_obs: list[float] = []
    sim_obs: list[float] = []
    meta = simulation.get("simulation_meta") or {}
    faixa_by_bairro = {
        str(r.get("bairro")): r.get("faixa_calor")
        for r in (meta.get("bairros_exposicao") or [])
        if r.get("bairro")
    }

    for nome in selected:
        sim_temp = sim_by_bairro[nome]
        lst_temp = lst_values.get(nome)
        delta = round(sim_temp - lst_temp, 1) if lst_temp is not None else None
        if lst_temp is not None:
            lst_obs.append(lst_temp)
            sim_obs.append(sim_temp)
        bairros_rows.append({
            "bairro": nome,
            "lst_observada_c": lst_temp,
            "temp_simulada_c": sim_temp,
            "delta_c": delta,
            "faixa_calor": faixa_by_bairro.get(nome),
        })

    lst_mediana = _median(lst_obs)
    sim_mediana = _median(sim_obs) or round(statistics.median(list(sim_by_bairro.values())), 1)
    divergencia = (
        round(sim_mediana - lst_mediana, 1)
        if lst_mediana is not None and sim_mediana is not None
        else None
    )

    sim_temps_all = list(sim_by_bairro.values())
    pico_previsto = meta.get("temperatura_pico_c")

    return {
        "disponivel": len(lst_obs) > 0,
        "municipio": muni.nome,
        "uf": muni.uf,
        "codigo_ibge": muni.codigo_ibge,
        "lst_fonte": LST_FONTE_LABEL,
        "lst_periodo": LST_PERIODO_LABEL,
        "lst_mediana_c": lst_mediana,
        "lst_max_c": round(max(lst_obs), 1) if lst_obs else None,
        "lst_min_c": round(min(lst_obs), 1) if lst_obs else None,
        "sim_temp_max_c": round(max(sim_temps_all), 1),
        "sim_temp_mediana_c": sim_mediana,
        "sim_delta_t_max_c": meta.get("max_delta_t_c") or simulation.get("impact_value"),
        "divergencia_mediana_c": divergencia,
        "amostras_validas": len(lst_obs),
        "amostras_total": len(selected),
        "bairros": bairros_rows,
        "narrativa": _build_narrativa(
            muni,
            lst_mediana=lst_mediana,
            sim_mediana=sim_mediana,
            divergencia=divergencia,
            amostras_validas=len(lst_obs),
            amostras_total=len(selected),
            pico_previsto=float(pico_previsto) if pico_previsto is not None else None,
        ),
        "limites_metodologicos": LIMITES_METODOLOGICOS,
    }
