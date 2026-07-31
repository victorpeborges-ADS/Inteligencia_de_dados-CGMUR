"""Selo canônico de previsão (20e.3) — OpenMeteo + CEMADEN + ML/heurística.

Um único objeto para Monitor, semáforo, alertas e Análise Preditiva.
"""

from __future__ import annotations

from typing import Any


def build_forecast_seal(
    *,
    risk_source: str,
    precip_forecast_mm: float | None = None,
    precip_for_risk_mm: float | None = None,
    cemaden_obs_mm: float | None = None,
    cemaden_estacoes: int | None = None,
    model_kind: str | None = None,
    production_ready: bool | None = None,
    experimental: bool = False,
) -> dict[str, Any]:
    """Contrato único de narrativa/selo de previsão.

    Campos:
      selo_qualidade — Observado | Estimado | Derivado (vocabulário 20h)
      fonte_chuva — openmeteo | cemaden_obs | misto | experimental
      risk_source — precip_curve | ml_full | experimental
      score_kind — score_heuristico_chuva | probabilidade_modelo | score_sintetico
      label_ui — texto curto do badge
      narrativa — 1 frase
      disclaimer — limites (não-laudo / não-alerta oficial)
    """
    source = str(risk_source or "precip_curve").strip().lower()
    kind = str(model_kind or "").strip().lower() or None
    synth = experimental or kind == "baseline_synthetic" or production_ready is False

    p_fc = float(precip_forecast_mm) if precip_forecast_mm is not None else None
    p_risk = float(precip_for_risk_mm) if precip_for_risk_mm is not None else p_fc
    obs = float(cemaden_obs_mm) if cemaden_obs_mm is not None else None

    used_obs = obs is not None and p_fc is not None and float(obs) > float(p_fc)

    if synth:
        fonte_chuva = "experimental"
        selo = "Estimado"
        score_kind = "score_sintetico"
        source_out = "experimental"
        label = "Sintético · Estimado"
        narrativa = (
            "Score experimental (baseline sintético) — não é probabilidade calibrada "
            "nem entra sozinho no Monitor operacional."
        )
        disclaimer = (
            "Artefato experimental. Não substitui alerta CEMADEN, Defesa Civil "
            "nem modelagem hidrodinâmica."
        )
    elif source == "ml_full":
        fonte_chuva = "cemaden_obs" if used_obs else "openmeteo"
        selo = "Derivado"
        score_kind = "probabilidade_modelo"
        source_out = "ml_full"
        label = "ML full · Derivado"
        chuva_bit = (
            f"Chuva de entrada: CEMADEN observado ({obs:.0f} mm)"
            if used_obs and obs is not None
            else "Chuva de entrada: previsão OpenMeteo"
        )
        narrativa = f"Probabilidade do modelo full. {chuva_bit}."
        disclaimer = (
            "Modelo estatístico com lastro observacional. "
            "Não substitui alerta oficial CEMADEN nem laudo de engenharia."
        )
    else:
        # Heurística de chuva (Monitor padrão)
        if used_obs and obs is not None:
            fonte_chuva = "cemaden_obs"
            selo = "Observado"
            label = "Heurística · Observado"
            narrativa = (
                f"Score heurístico de chuva com entrada CEMADEN observada "
                f"({obs:.0f} mm"
                + (f", {cemaden_estacoes} est." if cemaden_estacoes else "")
                + ") — maior que a previsão OpenMeteo."
            )
        else:
            fonte_chuva = "openmeteo"
            selo = "Estimado"
            label = "Heurística · Estimado"
            narrativa = (
                "Score heurístico de chuva a partir da previsão OpenMeteo — "
                "não é probabilidade calibrada."
            )
        score_kind = "score_heuristico_chuva"
        source_out = "precip_curve"
        disclaimer = (
            "Triagem operacional. Não é probabilidade calibrada, nem alerta oficial "
            "CEMADEN/Defesa Civil, nem laudo."
        )

    return {
        "selo_qualidade": selo,
        "fonte_chuva": fonte_chuva,
        "risk_source": source_out,
        "score_kind": score_kind,
        "label_ui": label,
        "narrativa": narrativa,
        "disclaimer": disclaimer,
        "precip_forecast_mm": round(p_fc, 1) if p_fc is not None else None,
        "precip_for_risk_mm": round(p_risk, 1) if p_risk is not None else None,
        "cemaden_obs_mm": round(obs, 1) if obs is not None else None,
        "cemaden_estacoes": cemaden_estacoes,
        "usou_chuva_observada": bool(used_obs),
        "protocol": "20e3_selo_previsao",
    }


def seal_from_weather_payload(
    raw_payload: dict[str, Any] | None,
    *,
    precip_24h_mm: float | None = None,
    risk_source: str | None = None,
) -> dict[str, Any]:
    """Reconstrói o selo a partir do cache OpenMeteo / payload já sincronizado."""
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    cached = payload.get("_selo_previsao")
    if isinstance(cached, dict) and cached.get("selo_qualidade"):
        return cached

    windows = payload.get("_precip_windows") if isinstance(payload.get("_precip_windows"), dict) else {}
    source = risk_source or payload.get("_risk_source") or "precip_curve"
    return build_forecast_seal(
        risk_source=str(source),
        precip_forecast_mm=windows.get("precip_24h", precip_24h_mm),
        precip_for_risk_mm=windows.get("precip_for_risk_mm", precip_24h_mm),
        cemaden_obs_mm=windows.get("cemaden_obs_mm"),
        cemaden_estacoes=windows.get("cemaden_estacoes"),
    )
