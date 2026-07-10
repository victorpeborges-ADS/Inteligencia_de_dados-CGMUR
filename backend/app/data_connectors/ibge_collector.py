from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.data_connectors.base import fetch_json
from app.data_connectors.ipeadata_collector import collect_idhm_municipality

IBGE_PESQUISAS_URL = "https://servicodados.ibge.gov.br/api/v1/pesquisas"
IBGE_AGREGADOS_URL = "https://servicodados.ibge.gov.br/api/v3/agregados"


def _parse_ibge_number(value: Any) -> Optional[float]:
    if value in (None, "", "-", "..."):
        return None
    text = str(value).strip()
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _latest_numeric_value(payload: Any) -> tuple[Optional[float], Optional[int]]:
    if not payload:
        return None, None
    rows = payload if isinstance(payload, list) else [payload]
    for row in rows:
        res_list = row.get("res") or []
        if not res_list:
            continue
        values = res_list[0].get("res") or {}
        candidates = []
        for year, value in values.items():
            if not str(year).isdigit():
                continue
            parsed = _parse_ibge_number(value)
            if parsed is not None:
                candidates.append((int(year), parsed))
        if candidates:
            year, value = max(candidates, key=lambda item: item[0])
            return value, year
    return None, None


def _agregado_series(
    codigo_ibge: str,
    agregado: int,
    variavel: int,
    *,
    start_year: int = 2002,
    end_year: int = 2023,
) -> list[dict[str, Any]]:
    periodos = "|".join(str(y) for y in range(start_year, end_year + 1))
    url = f"{IBGE_AGREGADOS_URL}/{agregado}/periodos/{periodos}/variaveis/{variavel}"
    params = {"localidades": f"N6[{codigo_ibge}]"}
    cache_key = f"ibge:agregado-serie:{agregado}:{start_year}:{end_year}:{variavel}:{codigo_ibge}"
    try:
        payload = fetch_json(url, params=params, cache_key=cache_key, cache_ttl=86400)
    except Exception:
        return []
    serie_rows: list[dict[str, Any]] = []
    if not payload:
        return serie_rows
    for item in payload:
        for result in item.get("resultados", []):
            for series in result.get("series", []):
                serie = series.get("serie") or {}
                for year, value in serie.items():
                    if not str(year).isdigit() or value in (None, "", "-", "..."):
                        continue
                    parsed = _parse_ibge_number(value)
                    if parsed is None:
                        continue
                    serie_rows.append({"ano": int(year), "valor_mil_reais": round(parsed, 3)})
    serie_rows.sort(key=lambda row: row["ano"])
    return serie_rows


def _agregado_value(codigo_ibge: str, agregado: int, periodo: int, variavel: int) -> tuple[Optional[float], Optional[int]]:
    url = f"{IBGE_AGREGADOS_URL}/{agregado}/periodos/{periodo}/variaveis/{variavel}"
    params = {"localidades": f"N6[{codigo_ibge}]"}
    cache_key = f"ibge:agregado:{agregado}:{periodo}:{variavel}:{codigo_ibge}"
    try:
        payload = fetch_json(url, params=params, cache_key=cache_key, cache_ttl=86400)
    except Exception:
        return None, None
    if not payload:
        return None, None
    for item in payload:
        for result in item.get("resultados", []):
            for series in result.get("series", []):
                serie = series.get("serie") or {}
                candidates = []
                for year, value in serie.items():
                    if value in (None, "", "-", "..."):
                        continue
                    try:
                        candidates.append((int(year), float(value)))
                    except ValueError:
                        continue
                if candidates:
                    year, value = max(candidates, key=lambda entry: entry[0])
                    return value, year
    return None, None


def _pesquisa_value(codigo_ibge: str, pesquisa: int, indicador: int) -> tuple[Optional[float], Optional[int]]:
    url = f"{IBGE_PESQUISAS_URL}/{pesquisa}/indicadores/{indicador}/resultados/{codigo_ibge}"
    cache_key = f"ibge:pesquisa:{pesquisa}:{indicador}:{codigo_ibge}"
    try:
        payload = fetch_json(url, cache_key=cache_key, cache_ttl=86400)
    except Exception:
        return None, None
    return _latest_numeric_value(payload)


def collect_ibge_municipality(codigo_ibge: str) -> Dict[str, Any]:
    pop_census, pop_census_year = _agregado_value(codigo_ibge, 4709, 2022, 93)
    pop_est, pop_est_year = _pesquisa_value(codigo_ibge, 33, 29171)
    area, area_year = _pesquisa_value(codigo_ibge, 33, 29167)
    densidade, densidade_year = _pesquisa_value(codigo_ibge, 33, 29168)
    pib_serie = _agregado_series(codigo_ibge, 5938, 37)
    pib_mil_reais = None
    pib_year = None
    if pib_serie:
        latest = pib_serie[-1]
        pib_mil_reais = latest["valor_mil_reais"]
        pib_year = latest["ano"]
    else:
        pib_mil_reais, pib_year = _agregado_value(codigo_ibge, 5938, 2021, 37)

    populacao = int(pop_est or pop_census or 0)
    populacao_ano = pop_est_year or pop_census_year
    area_km2 = float(area or 0.0)
    pib_per_capita = None
    if pib_mil_reais and populacao:
        pib_per_capita = round((float(pib_mil_reais) * 1000.0) / populacao, 2)

    if not densidade and area_km2 and populacao:
        densidade = round(populacao / area_km2, 2)
        densidade_year = populacao_ano

    idhm = collect_idhm_municipality(codigo_ibge)

    return {
        "codigo_ibge": codigo_ibge,
        "populacao": populacao,
        "populacao_ano": populacao_ano,
        "area_km2": round(area_km2, 3),
        "area_ano": area_year,
        "densidade_demografica": float(densidade or 0.0),
        "densidade_ano": densidade_year,
        "pib_per_capita": pib_per_capita,
        "pib_ano": pib_year,
        "pib_total_mil_reais": pib_mil_reais,
        "pib_serie": pib_serie,
        "idh": idhm.get("idh"),
        "idh_ano": idhm.get("idh_ano"),
        "idh_fonte": idhm.get("idh_fonte"),
        "idh_qualidade": idhm.get("idh_qualidade"),
        "data_quality": "oficial" if populacao and area_km2 else "estimado",
        "fonte": "IBGE Cidades / SIDRA (população, área, PIB municipal)",
        "atualizado_em": datetime.now(timezone.utc),
        "raw_payload": {
            "pop_census": pop_census,
            "pop_census_year": pop_census_year,
            "pop_est": pop_est,
            "pop_est_year": pop_est_year,
            "pib_mil_reais": pib_mil_reais,
            "pib_year": pib_year,
            "pib_serie_len": len(pib_serie),
        },
    }
