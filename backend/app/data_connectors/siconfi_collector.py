from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from app.data_connectors.base import fetch_json
from app.data_connectors.constants import (
    SICONFI_BASE_URL,
    SICONFI_EXERCICIO,
    SICONFI_RGF_PERIODO,
    SICONFI_RREO_PERIODO,
)

PREFERRED_COLUMNS = (
    "ATÉ O BIMESTRE (a)",
    "ATÉ O BIMESTRE",
    "NO BIMESTRE (b)",
    "PREVISÃO ATUALIZADA",
    "PREVISÃO INICIAL",
)

RREO_ACCOUNT_MAP = {
    "receita_corrente_liquida": (
        "ReceitaCorrenteLiquida",
        "ReceitasCorrentesLiquidas",
        "ReceitasCorrentesLiquidasExcetoTransferenciasEFUNDEB",
    ),
    "pessoal": ("PessoalEEncargosSociais",),
    "resultado_primario": (
        "ResultadoPrimarioComRPPSAcimaDaLinha",
        "ResultadoPrimario",
    ),
    "divida_consolidada": ("DividaConsolidada", "DividaConsolidadaLiquida"),
}

FUNCTION_EXPENSE_MAP = {
    "exec_saude": ("ServicosEAtividadesReferentesASaude",),
    "exec_habitacao": ("Habitacao", "Urbanismo"),
    "exec_saneamento": ("Saneamento",),
    "exec_meio_ambiente": ("GestaoAmbiental", "MeioAmbiente"),
    "exec_defesa_civil": ("DefesaCivil", "DefesaCivilComunicacaoSocial"),
}


def _pick_value(items: Iterable[dict], account_keys: tuple[str, ...]) -> Optional[float]:
    matches = [item for item in items if item.get("cod_conta") in account_keys]
    if not matches:
        return None
    for preferred in PREFERRED_COLUMNS:
        for item in matches:
            if item.get("coluna") == preferred:
                try:
                    return float(item.get("valor"))
                except (TypeError, ValueError):
                    continue
    try:
        return float(matches[0].get("valor"))
    except (TypeError, ValueError):
        return None


def _pick_function_expense(items: Iterable[dict], keywords: tuple[str, ...]) -> Optional[float]:
    for keyword in keywords:
        matches = [
            item for item in items
            if keyword.lower() in (item.get("cod_conta") or "").lower()
            or keyword.lower() in (item.get("conta") or "").lower()
        ]
        if not matches:
            continue
        value = _pick_value(matches, tuple({item.get("cod_conta") for item in matches if item.get("cod_conta")}))
        if value is not None:
            return value
    return None


def _fetch_demonstrativo(codigo_ibge: str, endpoint: str, tipo: str, periodo: int) -> list[dict]:
    url = f"{SICONFI_BASE_URL}/{endpoint}"
    params = {
        "id_ente": codigo_ibge,
        "an_exercicio": SICONFI_EXERCICIO,
        "nr_periodo": periodo,
        "co_tipo_demonstrativo": tipo,
    }
    cache_key = f"siconfi:{endpoint}:{codigo_ibge}:{SICONFI_EXERCICIO}:{periodo}:{tipo}"
    payload = fetch_json(url, params=params, cache_key=cache_key, cache_ttl=43200)
    if not payload:
        return []
    return payload.get("items") or []


def collect_siconfi_municipality(codigo_ibge: str) -> Dict[str, Any]:
    rreo_items = _fetch_demonstrativo(codigo_ibge, "rreo", "RREO", SICONFI_RREO_PERIODO)
    rgf_items = _fetch_demonstrativo(codigo_ibge, "rgf", "RGF", SICONFI_RGF_PERIODO)

    receita = _pick_value(rreo_items, RREO_ACCOUNT_MAP["receita_corrente_liquida"])
    pessoal = _pick_value(rreo_items, RREO_ACCOUNT_MAP["pessoal"])
    resultado = _pick_value(rreo_items, RREO_ACCOUNT_MAP["resultado_primario"])
    divida = _pick_value(rreo_items + rgf_items, RREO_ACCOUNT_MAP["divida_consolidada"])

    despesa_pessoal_pct = None
    if receita and pessoal and receita > 0:
        despesa_pessoal_pct = round((pessoal / receita) * 100, 4)

    function_values = {
        field: _pick_function_expense(rreo_items, keys)
        for field, keys in FUNCTION_EXPENSE_MAP.items()
    }

    has_data = any(value is not None for value in [receita, pessoal, resultado, divida, *function_values.values()])

    return {
        "codigo_ibge": codigo_ibge,
        "receita_corrente_liquida": receita,
        "despesa_pessoal_pct_rcl": despesa_pessoal_pct,
        "divida_consolidada": divida,
        "resultado_primario": resultado,
        **function_values,
        "exercicio": SICONFI_EXERCICIO,
        "periodo": SICONFI_RREO_PERIODO,
        "data_quality": "oficial" if has_data else "estimado",
        "fonte": "SICONFI / Tesouro Nacional (RREO/RGF)",
        "atualizado_em": datetime.now(timezone.utc),
        "raw_payload": {
            "rreo_count": len(rreo_items),
            "rgf_count": len(rgf_items),
        },
    }
