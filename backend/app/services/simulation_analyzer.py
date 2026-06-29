"""Análise interpretativa de simulações — LLM (Ollama/API) com fallback determinístico."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.orm import Session

from app.models import Municipio
from app.services.hydro_simulator import build_bairro_risk_context

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Análise de apoio à decisão territorial. Não substitui estudo hidrológico, "
    "laudo geotécnico ou plano de contingência oficial."
)


def _deterministic_analysis(
    simulation: dict[str, Any],
    risk_context: list[dict[str, Any]],
    muni: Municipio,
) -> dict[str, Any]:
    scenario = simulation.get("scenario_type", "Unknown")
    input_val = simulation.get("input_value", 0)
    bairros = simulation.get("affected_bairros", [])
    area = simulation.get("affected_area_km2", 0)
    pop = simulation.get("affected_population", 0)
    meta = simulation.get("simulation_meta") or {}

    top_risk = sorted(risk_context, key=lambda x: x.get("composite_risk", 0), reverse=True)[:5]
    findings = [
        f"Cenário {scenario}: parâmetro de entrada {input_val}.",
        f"Área estimada atingida: {area} km²; população exposta: {pop:,} hab.".replace(",", "."),
    ]
    if meta.get("dem_source"):
        findings.append(f"Modelo espacial: {meta.get('method', 'dem_pluvial_proxy')} com {meta.get('dem_source')}.")
    if meta.get("max_depth_m"):
        findings.append(f"Profundidade máxima simulada: {meta.get('max_depth_m')} m.")
    if bairros:
        findings.append(f"Bairros intersectados: {', '.join(bairros[:8])}{'…' if len(bairros) > 8 else ''}.")

    actions = []
    if scenario == "ExtremeRainfall":
        actions = [
            "Acionar monitoramento CEMADEN e Defesa Civil nos bairros de maior IRI.",
            "Inspecionar pontos de alagamento crônico e galerias pluviais.",
            "Restringir ocupação temporária em faixas de profundidade crítica (> 80 cm).",
        ]
    elif scenario == "DrainageDeficit":
        actions = [
            "Priorizar limpeza de bocas de lobo e microdrenagem nos bairros de IRI elevado.",
            "Simular rotas alternativas de evacuação para UBS/escolas em zona de risco.",
        ]
    else:
        actions = ["Validar resultados com equipe técnica municipal e dados de campo."]

    gaps = []
    if not meta.get("dem_available"):
        gaps.append("DEM SRTM indisponível — mancha baseada em heurística hidrográfica.")
    if not risk_context:
        gaps.append("Índices IVC/IRI por bairro não calculados.")

    narrative = (
        f"## Análise territorial — {muni.nome}/{muni.uf}\n\n"
        f"Simulação **{scenario}** com intensidade **{input_val}**. "
        f"A mancha estimada atinge **{area} km²** e expõe cerca de **{pop:,}** pessoas "
        f"em **{len(bairros)}** bairro(s).\n\n"
    ).replace(",", ".")
    if top_risk:
        narrative += "### Bairros prioritários (IVC × IRI)\n"
        for row in top_risk:
            narrative += (
                f"- **{row['bairro']}**: IVC {row.get('ivc', '—')}, IRI {row.get('iri', '—')} — "
                f"{row.get('rationale', '')}\n"
            )

    return {
        "narrative_md": narrative,
        "key_findings": findings,
        "bairros_prioritarios": [
            {
                "nome": r["bairro"],
                "ivc": r.get("ivc"),
                "iri": r.get("iri"),
                "rationale": r.get("rationale", ""),
            }
            for r in top_risk
        ],
        "suggested_actions": actions,
        "data_gaps": gaps,
        "confidence": "media" if meta.get("dem_available") else "baixa",
        "ai_provider": "deterministic",
        "ai_model": None,
        "disclaimer": DISCLAIMER,
    }


def _parse_llm_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return None


def _llm_analysis(
    simulation: dict[str, Any],
    risk_context: list[dict[str, Any]],
    muni: Municipio,
    ai_provider: str | None,
    ai_model: str | None,
    ai_api_key: str | None,
) -> dict[str, Any] | None:
    payload = {
        "municipio": {"nome": muni.nome, "uf": muni.uf, "codigo_ibge": muni.codigo_ibge},
        "simulation": {
            "scenario_type": simulation.get("scenario_type"),
            "input_value": simulation.get("input_value"),
            "affected_area_km2": simulation.get("affected_area_km2"),
            "affected_population": simulation.get("affected_population"),
            "affected_bairros": simulation.get("affected_bairros"),
            "simulation_meta": simulation.get("simulation_meta"),
        },
        "bairros_risco": risk_context[:12],
    }
    system = (
        "Você é analista de risco climático do Sinidu+Clima (MCID). "
        "Use SOMENTE os dados JSON fornecidos; não invente números. "
        "Responda APENAS com JSON válido (sem markdown externo) contendo: "
        "narrative_md (string markdown em pt-BR), key_findings (array de strings), "
        "bairros_prioritarios (array {nome, ivc, iri, rationale}), "
        "suggested_actions (array), data_gaps (array), confidence (alta|media|baixa)."
    )
    user = f"Dados da simulação:\n```json\n{json.dumps(payload, ensure_ascii=False, indent=2)}\n```"
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    try:
        if ai_provider and ai_provider.lower() not in ("ollama", "none", ""):
            from rag.providers.registry import get_chat_provider

            provider = get_chat_provider(ai_provider, ai_api_key)
            raw = provider.chat(messages, model=ai_model, temperature=0.15)
            provider_id = ai_provider
        else:
            from rag.ollama_client import ollama_client

            if not ollama_client.health():
                return None
            raw = ollama_client.chat(messages, model=ai_model, temperature=0.15)
            provider_id = "ollama"

        parsed = _parse_llm_json(raw)
        if not parsed:
            return None
        parsed.setdefault("disclaimer", DISCLAIMER)
        parsed["ai_provider"] = provider_id
        parsed["ai_model"] = ai_model
        return parsed
    except Exception as exc:
        logger.warning("LLM simulation analysis failed: %s", exc)
        return None


def analyze_simulation(
    db: Session,
    muni: Municipio,
    simulation: dict[str, Any],
    *,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
    use_ai: bool = True,
) -> dict[str, Any]:
    risk_context = simulation.get("risk_context")
    if not risk_context:
        risk_context = build_bairro_risk_context(db, muni.id)

    if use_ai:
        llm = _llm_analysis(simulation, risk_context, muni, ai_provider, ai_model, ai_api_key)
        if llm:
            llm["risk_context"] = risk_context
            return llm

    result = _deterministic_analysis(simulation, risk_context, muni)
    result["risk_context"] = risk_context
    return result
