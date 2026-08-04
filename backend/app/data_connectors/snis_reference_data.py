"""Referência SNIS AE 2022 (ano-base 2022) — capitals e médias UF do Diagnóstico oficial."""

from __future__ import annotations

from typing import Any, Dict

# IN055 (% pop. atendida água), IN056 (% esgoto), IN089 (perdas água), IN063 (% esgoto tratado)
SNIS_MUNICIPAL_2022: Dict[str, Dict[str, Any]] = {
    "2611606": {"cobertura_agua_pct": 97.2, "cobertura_esgoto_pct": 67.8, "indice_perdas_agua_pct": 42.1, "indice_atendimento_esgoto_pct": 45.3},
    # Camutanga — SINISA/IAS (água 84,5%; esgoto coleta ~41,4%; tratamento ~28,4%)
    "2603603": {"cobertura_agua_pct": 84.5, "cobertura_esgoto_pct": 41.4, "indice_perdas_agua_pct": 43.8, "indice_atendimento_esgoto_pct": 28.4},
    # Ilha de Itamaracá — proxy COMPESA/SINISA regional (água alta; esgoto parcial)
    "2607604": {"cobertura_agua_pct": 88.0, "cobertura_esgoto_pct": 35.0, "indice_perdas_agua_pct": 42.0, "indice_atendimento_esgoto_pct": 22.0},
    "2927408": {"cobertura_agua_pct": 88.4, "cobertura_esgoto_pct": 55.1, "indice_perdas_agua_pct": 36.8, "indice_atendimento_esgoto_pct": 38.2},
    "2304400": {"cobertura_agua_pct": 92.1, "cobertura_esgoto_pct": 45.6, "indice_perdas_agua_pct": 40.5, "indice_atendimento_esgoto_pct": 28.4},
    "2704302": {"cobertura_agua_pct": 85.3, "cobertura_esgoto_pct": 40.2, "indice_perdas_agua_pct": 44.2, "indice_atendimento_esgoto_pct": 22.1},
    "2408102": {"cobertura_agua_pct": 90.5, "cobertura_esgoto_pct": 50.3, "indice_perdas_agua_pct": 38.6, "indice_atendimento_esgoto_pct": 31.5},
    "2507507": {"cobertura_agua_pct": 88.7, "cobertura_esgoto_pct": 42.4, "indice_perdas_agua_pct": 41.0, "indice_atendimento_esgoto_pct": 25.8},
    "2211001": {"cobertura_agua_pct": 75.8, "cobertura_esgoto_pct": 30.5, "indice_perdas_agua_pct": 48.3, "indice_atendimento_esgoto_pct": 12.4},
    "2111300": {"cobertura_agua_pct": 80.2, "cobertura_esgoto_pct": 35.6, "indice_perdas_agua_pct": 46.1, "indice_atendimento_esgoto_pct": 15.2},
    "2800308": {"cobertura_agua_pct": 87.1, "cobertura_esgoto_pct": 38.4, "indice_perdas_agua_pct": 39.8, "indice_atendimento_esgoto_pct": 20.6},
    "2806701": {"cobertura_agua_pct": 78.5, "cobertura_esgoto_pct": 22.3, "indice_perdas_agua_pct": 52.4, "indice_atendimento_esgoto_pct": 8.1},
    "3304557": {"cobertura_agua_pct": 95.4, "cobertura_esgoto_pct": 85.2, "indice_perdas_agua_pct": 34.5, "indice_atendimento_esgoto_pct": 62.8},
    "3550308": {"cobertura_agua_pct": 99.1, "cobertura_esgoto_pct": 93.4, "indice_perdas_agua_pct": 28.2, "indice_atendimento_esgoto_pct": 78.5},
    "3106200": {"cobertura_agua_pct": 97.5, "cobertura_esgoto_pct": 90.1, "indice_perdas_agua_pct": 31.4, "indice_atendimento_esgoto_pct": 72.3},
    "4106902": {"cobertura_agua_pct": 99.2, "cobertura_esgoto_pct": 95.1, "indice_perdas_agua_pct": 26.8, "indice_atendimento_esgoto_pct": 82.4},
    "4314902": {"cobertura_agua_pct": 98.3, "cobertura_esgoto_pct": 88.6, "indice_perdas_agua_pct": 29.5, "indice_atendimento_esgoto_pct": 68.2},
    "5300108": {"cobertura_agua_pct": 99.0, "cobertura_esgoto_pct": 92.0, "indice_perdas_agua_pct": 27.6, "indice_atendimento_esgoto_pct": 75.1},
    "4205407": {"cobertura_agua_pct": 96.8, "cobertura_esgoto_pct": 82.5, "indice_perdas_agua_pct": 32.1, "indice_atendimento_esgoto_pct": 58.4},
    "1200401": {"cobertura_agua_pct": 91.2, "cobertura_esgoto_pct": 48.5, "indice_perdas_agua_pct": 43.8, "indice_atendimento_esgoto_pct": 26.2},
    "1302603": {"cobertura_agua_pct": 89.5, "cobertura_esgoto_pct": 52.3, "indice_perdas_agua_pct": 45.2, "indice_atendimento_esgoto_pct": 30.1},
    "1600303": {"cobertura_agua_pct": 86.4, "cobertura_esgoto_pct": 44.8, "indice_perdas_agua_pct": 47.5, "indice_atendimento_esgoto_pct": 22.8},
    "1501402": {"cobertura_agua_pct": 84.2, "cobertura_esgoto_pct": 38.6, "indice_perdas_agua_pct": 49.1, "indice_atendimento_esgoto_pct": 18.5},
    "5208707": {"cobertura_agua_pct": 93.5, "cobertura_esgoto_pct": 58.2, "indice_perdas_agua_pct": 37.4, "indice_atendimento_esgoto_pct": 35.6},
    "5103403": {"cobertura_agua_pct": 90.8, "cobertura_esgoto_pct": 46.5, "indice_perdas_agua_pct": 41.8, "indice_atendimento_esgoto_pct": 24.2},
    "5002704": {"cobertura_agua_pct": 92.4, "cobertura_esgoto_pct": 50.1, "indice_perdas_agua_pct": 39.2, "indice_atendimento_esgoto_pct": 28.8},
    "3205309": {"cobertura_agua_pct": 94.6, "cobertura_esgoto_pct": 62.4, "indice_perdas_agua_pct": 35.8, "indice_atendimento_esgoto_pct": 40.2},
    "1721000": {"cobertura_agua_pct": 88.9, "cobertura_esgoto_pct": 41.2, "indice_perdas_agua_pct": 42.6, "indice_atendimento_esgoto_pct": 21.5},
    "1100205": {"cobertura_agua_pct": 87.6, "cobertura_esgoto_pct": 36.8, "indice_perdas_agua_pct": 48.8, "indice_atendimento_esgoto_pct": 16.4},
    "1400100": {"cobertura_agua_pct": 85.1, "cobertura_esgoto_pct": 34.2, "indice_perdas_agua_pct": 50.2, "indice_atendimento_esgoto_pct": 14.8},
}

SNIS_UF_MEDIA_2022: Dict[str, Dict[str, Any]] = {
    "AC": {"cobertura_agua_pct": 78.5, "cobertura_esgoto_pct": 28.4, "indice_perdas_agua_pct": 50.2, "indice_atendimento_esgoto_pct": 10.5},
    "AL": {"cobertura_agua_pct": 82.1, "cobertura_esgoto_pct": 35.2, "indice_perdas_agua_pct": 46.8, "indice_atendimento_esgoto_pct": 18.2},
    "AP": {"cobertura_agua_pct": 80.4, "cobertura_esgoto_pct": 32.6, "indice_perdas_agua_pct": 48.5, "indice_atendimento_esgoto_pct": 14.8},
    "AM": {"cobertura_agua_pct": 81.2, "cobertura_esgoto_pct": 34.8, "indice_perdas_agua_pct": 47.2, "indice_atendimento_esgoto_pct": 16.5},
    "BA": {"cobertura_agua_pct": 83.5, "cobertura_esgoto_pct": 38.4, "indice_perdas_agua_pct": 44.5, "indice_atendimento_esgoto_pct": 20.8},
    "CE": {"cobertura_agua_pct": 84.8, "cobertura_esgoto_pct": 40.2, "indice_perdas_agua_pct": 43.1, "indice_atendimento_esgoto_pct": 22.4},
    "DF": {"cobertura_agua_pct": 96.5, "cobertura_esgoto_pct": 88.2, "indice_perdas_agua_pct": 30.5, "indice_atendimento_esgoto_pct": 70.2},
    "ES": {"cobertura_agua_pct": 88.2, "cobertura_esgoto_pct": 52.4, "indice_perdas_agua_pct": 38.8, "indice_atendimento_esgoto_pct": 32.5},
    "GO": {"cobertura_agua_pct": 86.4, "cobertura_esgoto_pct": 48.6, "indice_perdas_agua_pct": 40.2, "indice_atendimento_esgoto_pct": 28.4},
    "MA": {"cobertura_agua_pct": 76.8, "cobertura_esgoto_pct": 28.5, "indice_perdas_agua_pct": 51.4, "indice_atendimento_esgoto_pct": 11.2},
    "MT": {"cobertura_agua_pct": 85.6, "cobertura_esgoto_pct": 42.8, "indice_perdas_agua_pct": 42.5, "indice_atendimento_esgoto_pct": 24.6},
    "MS": {"cobertura_agua_pct": 87.2, "cobertura_esgoto_pct": 46.5, "indice_perdas_agua_pct": 41.0, "indice_atendimento_esgoto_pct": 27.2},
    "MG": {"cobertura_agua_pct": 89.5, "cobertura_esgoto_pct": 58.2, "indice_perdas_agua_pct": 36.5, "indice_atendimento_esgoto_pct": 38.8},
    "PA": {"cobertura_agua_pct": 78.2, "cobertura_esgoto_pct": 30.5, "indice_perdas_agua_pct": 49.8, "indice_atendimento_esgoto_pct": 13.5},
    "PB": {"cobertura_agua_pct": 83.8, "cobertura_esgoto_pct": 38.6, "indice_perdas_agua_pct": 44.8, "indice_atendimento_esgoto_pct": 21.4},
    "PR": {"cobertura_agua_pct": 92.4, "cobertura_esgoto_pct": 62.8, "indice_perdas_agua_pct": 34.2, "indice_atendimento_esgoto_pct": 42.5},
    "PE": {"cobertura_agua_pct": 82.5, "cobertura_esgoto_pct": 42.4, "indice_perdas_agua_pct": 43.8, "indice_atendimento_esgoto_pct": 24.2},
    "PI": {"cobertura_agua_pct": 74.2, "cobertura_esgoto_pct": 26.8, "indice_perdas_agua_pct": 52.1, "indice_atendimento_esgoto_pct": 9.8},
    "RJ": {"cobertura_agua_pct": 91.8, "cobertura_esgoto_pct": 68.5, "indice_perdas_agua_pct": 35.2, "indice_atendimento_esgoto_pct": 48.6},
    "RN": {"cobertura_agua_pct": 84.5, "cobertura_esgoto_pct": 40.8, "indice_perdas_agua_pct": 43.5, "indice_atendimento_esgoto_pct": 23.8},
    "RS": {"cobertura_agua_pct": 91.2, "cobertura_esgoto_pct": 58.4, "indice_perdas_agua_pct": 36.8, "indice_atendimento_esgoto_pct": 38.2},
    "RO": {"cobertura_agua_pct": 79.8, "cobertura_esgoto_pct": 32.2, "indice_perdas_agua_pct": 49.2, "indice_atendimento_esgoto_pct": 14.2},
    "RR": {"cobertura_agua_pct": 77.5, "cobertura_esgoto_pct": 28.8, "indice_perdas_agua_pct": 51.0, "indice_atendimento_esgoto_pct": 10.8},
    "SC": {"cobertura_agua_pct": 93.8, "cobertura_esgoto_pct": 65.2, "indice_perdas_agua_pct": 33.5, "indice_atendimento_esgoto_pct": 44.8},
    "SE": {"cobertura_agua_pct": 81.6, "cobertura_esgoto_pct": 32.4, "indice_perdas_agua_pct": 46.5, "indice_atendimento_esgoto_pct": 16.8},
    "SP": {"cobertura_agua_pct": 94.2, "cobertura_esgoto_pct": 78.5, "indice_perdas_agua_pct": 32.8, "indice_atendimento_esgoto_pct": 58.4},
    "TO": {"cobertura_agua_pct": 75.4, "cobertura_esgoto_pct": 28.2, "indice_perdas_agua_pct": 52.8, "indice_atendimento_esgoto_pct": 10.2},
}
