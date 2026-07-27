"""Modelo de risco unificado — ML preditivo × semáforo estrutural (Fase 21f.5).

Antes: dois sistemas paralelos
  - Semáforo: Score/IVC/IRI/VM/alerta vivo → VERDE…VERMELHO
  - ML/Monitor: risk_probability (0–1) ou heurística de chuva

Agora: o painel de risco inclui o componente `ml_preditivo` e o status
municipal é o **máximo** (mais severo) entre componentes estruturais e o ML
quando houver modelo `full` em produção. Heurística de chuva entra como
componente informativo (não eleva o semáforo sozinha além de AMARELO).

Limiares ML → nível (alinhados ao Monitor / impacto 21g.2):
  ≥ 0,75 → VERMELHO
  ≥ 0,55 → LARANJA
  ≥ 0,35 → AMARELO
  < 0,35 → VERDE
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import WeatherForecastCache
from app.services.live_alert_level import normalize_nivel

logger = logging.getLogger(__name__)

MODELO_RISCO_VERSAO = "21f.5"

ML_PROB_THRESHOLDS = (
    (0.75, "VERMELHO"),
    (0.55, "LARANJA"),
    (0.35, "AMARELO"),
    (0.0, "VERDE"),
)


def ml_prob_to_nivel(prob: float | None) -> str:
    if prob is None:
        return "VERDE"
    p = float(prob)
    for thr, nivel in ML_PROB_THRESHOLDS:
        if p >= thr:
            return nivel
    return "VERDE"


def _component_shell(
    *,
    id: str,
    nome: str,
    valor: float | None,
    nivel: str,
    qualidade: str,
    detalhe: str,
    escala: str = "0–1",
) -> dict[str, Any]:
    from app.services.risk_traffic_light_service import NIVEL_LABEL

    n = normalize_nivel(nivel)
    return {
        "id": id,
        "nome": nome,
        "valor": valor,
        "escala": escala,
        "nivel": n,
        "label": NIVEL_LABEL.get(n, n),
        "qualidade": qualidade,
        "detalhe": detalhe,
    }


def build_ml_risk_component(db: Session, codigo_ibge: str) -> dict[str, Any]:
    """Lê a última previsão do Monitor (cache) — evita retreinar/inferir a cada painel."""
    code = str(codigo_ibge).zfill(7)[:7]
    weather = (
        db.query(WeatherForecastCache)
        .filter(WeatherForecastCache.codigo_ibge == code)
        .order_by(WeatherForecastCache.fetched_at.desc())
        .first()
    )
    if not weather or weather.risk_probability is None:
        return _component_shell(
            id="ml_preditivo",
            nome="Predição ML / chuva",
            valor=None,
            nivel="VERDE",
            qualidade="Lacuna",
            detalhe="Sem previsão recente no Monitor — sincronize o clima.",
        )

    from numbers import Real

    rp = weather.risk_probability
    # int/float/Decimal — rejeita MagicMock (tem __float__→1.0) e bool
    if isinstance(rp, bool) or not isinstance(rp, Real):
        return _component_shell(
            id="ml_preditivo",
            nome="Predição ML / chuva",
            valor=None,
            nivel="VERDE",
            qualidade="Lacuna",
            detalhe="Sem previsão recente no Monitor — sincronize o clima.",
        )
    risk = float(rp)
    payload = weather.raw_payload if isinstance(weather.raw_payload, dict) else {}
    source = str(payload.get("_risk_source") or "precip_curve")
    score_kind = str(payload.get("_score_kind") or "")
    from app.services.forecast_source_seal import seal_from_weather_payload

    seal = seal_from_weather_payload(
        payload,
        precip_24h_mm=float(weather.precip_24h_mm) if weather.precip_24h_mm is not None else None,
        risk_source=source,
    )
    source = str(seal.get("risk_source") or source)

    if source == "ml_full":
        nivel = ml_prob_to_nivel(risk)
        qualidade = seal.get("selo_qualidade") or "Derivado"
        detalhe = seal.get("narrativa") or (
            f"Modelo full · P(alagamento)={risk:.0%} · "
            f"entra no status municipal (máximo com Score/IVC/IRI/alerta)."
        )
        elevates = True
    else:
        # Heurística: informa, mas só pode elevar até AMARELO (não dispara sozinha VERMELHO)
        raw_nivel = ml_prob_to_nivel(risk)
        order = ["VERDE", "AMARELO", "LARANJA", "VERMELHO"]
        nivel = raw_nivel if order.index(raw_nivel) <= order.index("AMARELO") else "AMARELO"
        qualidade = seal.get("selo_qualidade") or "Estimado"
        detalhe = seal.get("narrativa") or (
            f"Score heurístico de chuva ({risk:.0%}) — não é probabilidade calibrada; "
            f"capado em AMARELO até existir model_kind=full."
        )
        elevates = False

    comp = _component_shell(
        id="ml_preditivo",
        nome="Predição ML / chuva",
        valor=round(risk, 3),
        nivel=nivel,
        qualidade=qualidade,
        detalhe=detalhe,
    )
    comp["risk_source"] = source
    comp["score_kind"] = seal.get("score_kind") or score_kind or (
        "probabilidade_modelo" if source == "ml_full" else "score_heuristico_chuva"
    )
    comp["selo_previsao"] = seal
    comp["elevates_status"] = elevates or source == "ml_full"
    comp["fetched_at"] = weather.fetched_at.isoformat() if weather.fetched_at else None
    return comp


def modelo_risco_meta(comp_ml: dict[str, Any]) -> dict[str, Any]:
    """Bloco documental embutido na API do painel."""
    return {
        "versao": MODELO_RISCO_VERSAO,
        "nome": "Risco unificado Sinidu (estrutural × preditivo)",
        "regra_status": (
            "status = max(score, ivc, iri, vm, alerta_vivo, ml_preditivo) "
            "quando ml_preditivo.elevates_status; heurística capada em AMARELO."
        ),
        "limiares_ml": [
            {"min": 0.75, "nivel": "VERMELHO"},
            {"min": 0.55, "nivel": "LARANJA"},
            {"min": 0.35, "nivel": "AMARELO"},
            {"min": 0.0, "nivel": "VERDE"},
        ],
        "componente_ml": {
            "risk_source": comp_ml.get("risk_source"),
            "elevates_status": comp_ml.get("elevates_status"),
            "qualidade": comp_ml.get("qualidade"),
            "selo_previsao": comp_ml.get("selo_previsao"),
        },
        "nota": (
            "Não substitui alerta CEMADEN nem laudo de engenharia. "
            "Selo único 20e.3: Observado (CEMADEN) / Estimado (OpenMeteo ou sintético) / "
            "Derivado (ML full)."
        ),
    }
