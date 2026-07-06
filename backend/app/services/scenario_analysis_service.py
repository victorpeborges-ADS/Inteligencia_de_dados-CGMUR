"""Análise de cenário meteorológico — Monitor Step 6."""

from __future__ import annotations

import calendar
import datetime
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models import HistoricoDesastreS2ID, MonitoringAlert, Municipio, WeatherForecastCache

logger = logging.getLogger(__name__)

CACHE_TTL = datetime.timedelta(minutes=30)
_scenario_cache: dict[str, tuple[datetime.datetime, dict[str, Any]]] = {}
_alert_interp_cache: dict[str, tuple[datetime.datetime, str]] = {}

RAIN_SEASON_MONTHS = {3, 4, 5, 6, 7, 8, 9, 10, 11}

RISK_ACTIONS: dict[str, list[str]] = {
    "VERDE": ["Monitorar normalmente. Próxima revisão automática em 1 hora."],
    "AMARELO": [
        "Verificar sistema de drenagem e bocas de lobo nos bairros de maior histórico pluvial.",
        "Ativar canal de comunicação com a Defesa Civil municipal e revisar equipes de prontidão.",
        "Orientar escolas e unidades de saúde sobre protocolos de chuva moderada.",
    ],
    "LARANJA": [
        "Defesa Civil em alerta — confirmar plantão e centro de operações.",
        "Suspender obras em encostas e vias com histórico de alagamento.",
        "Acionar sirenes/comunicação em bairros prioritários do S2ID.",
        "Pre-posicionar equipes de limpeza de galerias e bombas de recalque.",
    ],
    "VERMELHO": [
        "Ativar plano COBRADE e centro de operações de emergência.",
        "Evacuação preventiva em áreas de risco geológico mapeadas.",
        "Interditar vias submersíveis e pontos críticos de deslizamento.",
        "Comunicação contínua à população via rádio, redes e sirenes.",
    ],
}


def _cache_get(key: str) -> dict[str, Any] | None:
    row = _scenario_cache.get(key)
    if not row:
        return None
    ts, payload = row
    if datetime.datetime.utcnow() - ts > CACHE_TTL:
        _scenario_cache.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: dict[str, Any]) -> None:
    _scenario_cache[key] = (datetime.datetime.utcnow(), payload)


def _monitoring_snapshot(db: Session, codigo_ibge: str) -> dict[str, Any]:
    since = datetime.datetime.utcnow() - datetime.timedelta(hours=24)
    muni = db.query(Municipio).filter(Municipio.codigo_ibge == codigo_ibge).first()
    alerts = (
        db.query(MonitoringAlert)
        .filter(MonitoringAlert.codigo_ibge == codigo_ibge, MonitoringAlert.created_at >= since)
        .order_by(MonitoringAlert.created_at.desc())
        .all()
    )
    weather = (
        db.query(WeatherForecastCache)
        .filter(WeatherForecastCache.codigo_ibge == codigo_ibge)
        .order_by(WeatherForecastCache.fetched_at.desc())
        .first()
    )

    nivel = "VERDE"
    for a in alerts:
        if a.nivel == "VERMELHO":
            nivel = "VERMELHO"
            break
        if a.nivel == "LARANJA" and nivel != "VERMELHO":
            nivel = "LARANJA"
        elif a.nivel == "AMARELO" and nivel == "VERDE":
            nivel = "AMARELO"

    cemaden = sum(1 for a in alerts if a.tipo == "CEMADEN_ALERT")
    now = datetime.datetime.utcnow()
    mes = calendar.month_name[now.month].lower()
    mes_pt = (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    )[now.month - 1]

    historico_similar = _similar_s2id_event(db, muni)
    proxima_revisao = (now + datetime.timedelta(hours=1)).strftime("%H:%M")

    return {
        "codigo_ibge": codigo_ibge,
        "municipio_nome": muni.nome if muni else codigo_ibge,
        "uf": muni.uf if muni else None,
        "n_alertas": cemaden,
        "precip_24h": round(float(weather.precip_24h_mm), 1) if weather else 0.0,
        "precip_72h": round(float(weather.precip_72h_mm), 1) if weather else 0.0,
        "nivel_risco": nivel,
        "prob_critico": round(float(weather.risk_probability) * 100, 0) if weather else 15,
        "historico_similar": historico_similar,
        "mes": mes_pt,
        "estacao_chuvosa": now.month in RAIN_SEASON_MONTHS,
        "proxima_revisao": proxima_revisao,
    }


def _similar_s2id_event(db: Session, muni: Municipio | None) -> dict[str, Any] | None:
    if not muni:
        return None
    row = (
        db.query(HistoricoDesastreS2ID)
        .filter(
            HistoricoDesastreS2ID.municipio_id == muni.id,
            HistoricoDesastreS2ID.tipo_desastre.ilike("%inunda%"),
        )
        .order_by(HistoricoDesastreS2ID.data_ocorrencia.desc())
        .first()
    )
    if not row:
        row = (
            db.query(HistoricoDesastreS2ID)
            .filter(HistoricoDesastreS2ID.municipio_id == muni.id)
            .order_by(HistoricoDesastreS2ID.data_ocorrencia.desc())
            .first()
        )
    if not row or not row.data_ocorrencia:
        return None
    desc = row.tipo_desastre or "desastre natural"
    if row.populacao_afetada:
        desc += f" — {row.populacao_afetada} pessoas afetadas"
    return {
        "data": row.data_ocorrencia.strftime("%m/%Y"),
        "descricao": desc,
        "label": f"Em {row.data_ocorrencia.strftime('%m/%Y')}, ocorreu: {desc}.",
    }


def _deterministic_analysis(ctx: dict[str, Any]) -> dict[str, Any]:
    nome = ctx["municipio_nome"]
    nivel = ctx["nivel_risco"]
    prob = ctx["prob_critico"]
    chuva = "sim" if ctx.get("estacao_chuvosa") else "não"

    interpretacao = (
        f"Com {ctx['n_alertas']} alertas CEMADEN e precipitação prevista de {ctx['precip_72h']}mm "
        f"nas próximas 72h, {nome} está em atenção {'moderada' if nivel == 'AMARELO' else nivel.lower()}. "
        f"A probabilidade de evento crítico estimada é {prob:.0f}% (precipitação 24h: {ctx['precip_24h']}mm)."
    )
    tendencia = (
        "Risco estável nas próximas 6h com vigilância contínua."
        if prob < 35
        else "Tendência de elevação do risco nas próximas 6h se a precipitação prevista se confirmar."
    )
    acoes = RISK_ACTIONS.get(nivel, RISK_ACTIONS["VERDE"])
    if nivel == "VERDE":
        acoes = [f"Monitorar normalmente. Próxima revisão: {ctx['proxima_revisao']}."]

    hist = ctx.get("historico_similar")
    referencia = hist["label"] if hist else "Sem evento S2ID comparável registrado para este município."

    return {
        "interpretacao": interpretacao,
        "tendencia": tendencia,
        "recomendacoes": acoes,
        "recomendacao_nivel": nivel,
        "referencia_historica": referencia,
        "proxima_revisao": ctx["proxima_revisao"],
        "estacao_chuvosa_label": chuva,
    }


def analyze_scenario(
    db: Session,
    codigo_ibge: str,
    *,
    force: bool = False,
    use_ai: bool = True,
) -> dict[str, Any]:
    cache_key = f"scenario:{codigo_ibge}"
    if not force:
        cached = _cache_get(cache_key)
        if cached:
            return {**cached, "cached": True}

    ctx = _monitoring_snapshot(db, codigo_ibge)
    analysis = _deterministic_analysis(ctx)
    ai_provider = "deterministic"

    if use_ai:
        try:
            from rag.providers.registry import resolve_chat_provider_with_fallback

            provider = resolve_chat_provider_with_fallback(None)
            if provider.is_available():
                prompt = f"""Você é um especialista em meteorologia urbana e Defesa Civil.
Analise o cenário atual de monitoramento para {ctx['municipio_nome']}.

DADOS ATUAIS:
- Alertas CEMADEN ativos: {ctx['n_alertas']}
- Precipitação últimas 24h: {ctx['precip_24h']}mm
- Precipitação acumulada 72h prevista: {ctx['precip_72h']}mm
- Nível de risco atual: {ctx['nivel_risco']}
- Probabilidade de evento crítico (modelo): {ctx['prob_critico']:.0f}%
- Histórico similar: {analysis['referencia_historica']}
- Época do ano: {ctx['mes']} (estação chuvosa: {'sim' if ctx['estacao_chuvosa'] else 'não'})

Produza JSON com chaves: interpretacao (2 frases), tendencia (1 frase), recomendacoes (lista de strings proporcional ao nível {ctx['nivel_risco']}), referencia_historica (1 frase). Sem markdown."""
                raw = provider.chat(
                    [
                        {"role": "system", "content": "Responda apenas JSON válido."},
                        {"role": "user", "content": prompt},
                    ],
                    model=provider.info().default_model,
                    temperature=0.2,
                )
                if raw:
                    import json
                    import re

                    match = re.search(r"\{.*\}", raw, re.DOTALL)
                    if match:
                        parsed = json.loads(match.group())
                        analysis["interpretacao"] = parsed.get("interpretacao") or analysis["interpretacao"]
                        analysis["tendencia"] = parsed.get("tendencia") or analysis["tendencia"]
                        if isinstance(parsed.get("recomendacoes"), list) and parsed["recomendacoes"]:
                            analysis["recomendacoes"] = [str(x) for x in parsed["recomendacoes"]]
                        if parsed.get("referencia_historica"):
                            analysis["referencia_historica"] = parsed["referencia_historica"]
                        ai_provider = provider.id
        except Exception as exc:
            logger.warning("Scenario analysis IA failed: %s", exc)

    payload = {
        **analysis,
        "codigo_ibge": codigo_ibge,
        "municipio_nome": ctx["municipio_nome"],
        "uf": ctx["uf"],
        "inputs": {
            "n_alertas": ctx["n_alertas"],
            "precip_24h_mm": ctx["precip_24h"],
            "precip_72h_mm": ctx["precip_72h"],
            "nivel_risco": ctx["nivel_risco"],
            "prob_critico_pct": ctx["prob_critico"],
        },
        "updated_at": datetime.datetime.utcnow().isoformat(),
        "cached": False,
        "ai_provider": ai_provider,
    }
    _cache_set(cache_key, payload)
    return payload


def interpret_alert(tipo: str, nivel: str, titulo: str = "", *, use_ai: bool = True) -> dict[str, Any]:
    cache_key = f"alert:{tipo}:{nivel}:{titulo[:40]}"
    row = _alert_interp_cache.get(cache_key)
    if row and datetime.datetime.utcnow() - row[0] <= CACHE_TTL:
        return {"interpretacao": row[1], "cached": True, "tipo": tipo, "nivel": nivel}

    defaults = {
        "CEMADEN_ALERT": {
            "AMARELO": "Alerta CEMADEN de nível médio: chuva ou instabilidade que exige monitoramento reforçado, sem evacuação imediata.",
            "LARANJA": "Alerta CEMADEN elevado: risco significativo de deslizamento ou inundação localizada.",
            "VERMELHO": "Alerta CEMADEN crítico: condições que podem causar danos imediatos à população.",
        },
        "RISK_THRESHOLD": {
            "LARANJA": "Limiar hidrológico atingido: precipitação prevista ou probabilidade elevada de alagamento.",
            "VERMELHO": "Limiar crítico: volume pluvial previsto compatível com evento extremo urbano.",
        },
    }
    text = defaults.get(tipo, {}).get(nivel) or f"Alerta {tipo.replace('_', ' ').lower()} — nível {nivel}."

    if use_ai and tipo == "CEMADEN_ALERT":
        try:
            from rag.providers.registry import resolve_chat_provider_with_fallback

            provider = resolve_chat_provider_with_fallback(None)
            if provider.is_available():
                prompt = f"Em 1-2 frases simples para gestores: o que significa um alerta CEMADEN {nivel}? Título: {titulo or 'Alerta CEMADEN'}"
                reply = provider.chat([{"role": "user", "content": prompt}], model=provider.info().default_model, temperature=0.2)
                if reply and reply.strip():
                    text = reply.strip()
        except Exception:
            pass

    _alert_interp_cache[cache_key] = (datetime.datetime.utcnow(), text)
    return {"interpretacao": text, "cached": False, "tipo": tipo, "nivel": nivel}


def alert_icon_and_category(tipo: str, titulo: str, mensagem: str = "") -> tuple[str, str]:
    blob = f"{titulo} {mensagem}".lower()
    if "desliz" in blob or "enxurr" in blob:
        return "landslide", "Deslizamento"
    if "vento" in blob:
        return "wind", "Vento"
    if tipo == "RISK_THRESHOLD" or "precip" in blob or "chuva" in blob or "hidrol" in blob:
        return "rain", "Chuva"
    return "alert", "Alerta"


def group_timeline_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Agrupa alertas idênticos (tipo+nivel+título) nas últimas 24h."""
    groups: dict[str, dict[str, Any]] = {}
    for item in entries:
        key = f"{item['tipo']}|{item['nivel']}|{item['titulo']}"
        if key not in groups:
            icon, cat = alert_icon_and_category(item["tipo"], item["titulo"], item.get("mensagem") or "")
            groups[key] = {
                **item,
                "count": 1,
                "grouped": False,
                "alert_icon": icon,
                "alert_category": cat,
                "latest_at": item["created_at"],
            }
        else:
            groups[key]["count"] += 1
            groups[key]["grouped"] = groups[key]["count"] > 1
            if item["created_at"] > groups[key]["latest_at"]:
                groups[key]["latest_at"] = item["created_at"]
                groups[key]["id"] = item["id"]
    result = sorted(groups.values(), key=lambda x: x["latest_at"], reverse=True)
    for g in result:
        if g["count"] > 1:
            g["titulo_display"] = f"{g['count']} alertas — {g['titulo']}"
        else:
            g["titulo_display"] = g["titulo"]
    return result


def compare_municipalities(db: Session, codigo_a: str, codigo_b: str, *, use_ai: bool = True) -> dict[str, Any]:
    ctx_a = _monitoring_snapshot(db, codigo_a)
    ctx_b = _monitoring_snapshot(db, codigo_b)

    risk_order = {"VERDE": 0, "AMARELO": 1, "LARANJA": 2, "VERMELHO": 3}
    more_critical = codigo_a if risk_order.get(ctx_a["nivel_risco"], 0) >= risk_order.get(ctx_b["nivel_risco"], 0) else codigo_b
    crit_ctx = ctx_a if more_critical == codigo_a else ctx_b
    other_ctx = ctx_b if more_critical == codigo_a else ctx_a

    resumo = (
        f"{crit_ctx['municipio_nome']} apresenta cenário mais crítico "
        f"({crit_ctx['nivel_risco']}, {crit_ctx['n_alertas']} alertas CEMADEN, "
        f"precip. 72h: {crit_ctx['precip_72h']}mm) que {other_ctx['municipio_nome']} "
        f"({other_ctx['nivel_risco']}, {other_ctx['n_alertas']} alertas, precip. 72h: {other_ctx['precip_72h']}mm)."
    )

    comparacao_ia = resumo
    if use_ai:
        try:
            from rag.providers.registry import resolve_chat_provider_with_fallback

            provider = resolve_chat_provider_with_fallback(None)
            if provider.is_available():
                prompt = (
                    f"Compare em 2 frases para gestores: {ctx_a['municipio_nome']} "
                    f"(risco {ctx_a['nivel_risco']}, {ctx_a['n_alertas']} alertas, precip 72h {ctx_a['precip_72h']}mm) "
                    f"vs {ctx_b['municipio_nome']} (risco {ctx_b['nivel_risco']}, {ctx_b['n_alertas']} alertas, "
                    f"precip 72h {ctx_b['precip_72h']}mm). Explique qual está mais crítico e por quê."
                )
                reply = provider.chat([{"role": "user", "content": prompt}], model=provider.info().default_model, temperature=0.2)
                if reply and reply.strip():
                    comparacao_ia = reply.strip()
        except Exception:
            pass

    return {
        "municipio_a": ctx_a,
        "municipio_b": ctx_b,
        "mais_critico_ibge": more_critical,
        "comparacao_ia": comparacao_ia,
        "ai_provider": "mistral" if comparacao_ia != resumo else "deterministic",
    }
