"""Validação cruzada Sinidu × AdaptaBrasil (17g.2h).

Compara `media_adaptacao` (derivado Sinidu) com `adapta_score` persistido
(proxy MapBiomas até haver API INPE). Não inventa acordo quando dados faltam.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Municipio, MunicipioFonteExterna


def validate_against_adapta_brasil(
    db: Session,
    muni: Municipio,
    *,
    media_adaptacao: float | None,
) -> dict[str, Any]:
    """Retorna bloco `validacao_adapta_brasil` para risk-panel / simulation_meta."""
    ext = (
        db.query(MunicipioFonteExterna)
        .filter(MunicipioFonteExterna.codigo_ibge == muni.codigo_ibge)
        .first()
    )
    adapta = float(ext.adapta_score) if ext and ext.adapta_score is not None else None
    qualidade = (ext.adapta_data_quality if ext else None) or "ausente"
    indicadores = (ext.adapta_indicadores if ext else None) or {}

    base = {
        "disponivel": False,
        "fonte": "AdaptaBrasil (proxy MapBiomas / Sinidu)",
        "qualidade": qualidade,
        "adapta_score": adapta,
        "media_adaptacao_sinidu": media_adaptacao,
        "delta": None,
        "acordo": "insuficiente",
        "narrativa": "Sem score AdaptaBrasil local para cruzar com a adaptação Sinidu.",
        "limitacao": (
            "Enquanto a API oficial AdaptaBrasil/INPE não estiver integrada, "
            "o score Adapta é um proxy MapBiomas (vegetação + estabilidade da série)."
        ),
        "indicadores": indicadores,
    }

    if adapta is None or media_adaptacao is None:
        return base

    delta = round(float(media_adaptacao) - float(adapta), 3)
    abs_d = abs(delta)
    if abs_d <= 0.10:
        acordo = "alta"
        narrativa = (
            f"Adaptação Sinidu ({media_adaptacao:.2f}) alinhada ao proxy AdaptaBrasil "
            f"({adapta:.2f}) — Δ {delta:+.2f}."
        )
    elif abs_d <= 0.25:
        acordo = "media"
        narrativa = (
            f"Diferença moderada entre adaptação Sinidu ({media_adaptacao:.2f}) e "
            f"proxy AdaptaBrasil ({adapta:.2f}) — Δ {delta:+.2f}."
        )
    else:
        acordo = "baixa"
        narrativa = (
            f"Divergência relevante: Sinidu {media_adaptacao:.2f} vs proxy AdaptaBrasil "
            f"{adapta:.2f} (Δ {delta:+.2f}). Revisar cobertura vegetal e infraestrutura."
        )

    return {
        **base,
        "disponivel": True,
        "delta": delta,
        "acordo": acordo,
        "narrativa": narrativa,
    }
