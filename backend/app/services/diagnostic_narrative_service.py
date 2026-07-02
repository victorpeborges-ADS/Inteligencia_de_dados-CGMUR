"""Narrativa executiva em linguagem de gestor — Sinidu+Clima Step 4."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

NARRATIVE_DISCLAIMER = (
    "Análise gerada por Sinidu+Clima IA. Use com critério — não substitui estudos técnicos oficiais."
)


def _capag_financing_desc(nota: str | None) -> str:
    mapping = {
        "A": "Alta — elegível a garantia da União sem restrições adicionais",
        "B": "Média — elegível a crédito com garantia da União, com monitoramento",
        "C": "Limitada — restrições para garantia da União; priorizar contrapartida e fontes não reembolsáveis",
        "D": "Limitada — capacidade fiscal restrita; priorizar PAC, convênios e apoio técnico federal",
    }
    if not nota:
        return "não disponível na base integrada"
    return mapping.get(nota.upper()[:1], "consultar Tesouro Transparente")


def _split_paragraphs(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    parts = re.split(r"\n\s*\n|(?=§[123])", cleaned)
    paragraphs = []
    for part in parts:
        p = re.sub(r"^§[123]\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇa-záéíóúâêôãõç\s]*?:\s*", "", part.strip(), flags=re.IGNORECASE)
        p = p.strip()
        if p:
            paragraphs.append(p)
    return paragraphs[:3]


def _build_prompt(ctx: dict[str, Any]) -> str:
    lacunas = ctx.get("lacunas") or []
    lacunas_txt = ", ".join(lacunas[:5]) if lacunas else "nenhuma crítica identificada"
    top3 = ctx.get("top3_bairros") or []
    top3_txt = ", ".join(top3) if top3 else "áreas centrais"

    return f"""Você é um analista sênior de gestão urbana do Ministério das Cidades.
Escreva um diagnóstico executivo para {ctx['municipio_nome']} em linguagem clara
para prefeitos e secretários municipais — sem jargão técnico excessivo.

DADOS DO DIAGNÓSTICO:
- Score de Risco Sinidu+Clima: {ctx['score']}/100 (severidade: {ctx['severidade']})
- Índice de Vulnerabilidade Climática (IVC): {ctx['ivc']}
- Índice de Risco de Inundação (IRI): {ctx['iri']}
- CAPAG: {ctx['capag'] or '—'} (capacidade de endividamento: {ctx['descricao_capag']})
- Bairros mais vulneráveis: {top3_txt}
- Histórico de desastres (S2ID, últimos 10 anos): {ctx['n_eventos']} eventos,
  maior dano: R$ {ctx['maior_dano_fmt']} em {ctx['data_maior_dano'] or '—'}
- Alertas CEMADEN ativos: {ctx['n_alertas']}
- Lacunas críticas de dados: {lacunas_txt}
- Ações sugeridas: {ctx['n_acoes']} ({ctx['n_curto']} imediatas, {ctx['n_medio']} médio prazo, {ctx['n_longo']} longo prazo)

Produza exatamente 3 parágrafos separados por linha em branco:
§1 CONTEXTO: Qual é a situação geral do município em termos de risco climático?
   Use o Score e compare implicitamente com o contexto nacional.
§2 PRIORIDADES: Quais são os bairros e riscos mais urgentes e por quê?
   Mencione os bairros pelo nome e explique o risco em linguagem simples.
§3 PRÓXIMOS PASSOS: Quais são as 3 ações mais importantes que o município
   pode tomar nos próximos 90 dias? Mencione fontes de financiamento disponíveis.

Tom: técnico mas acessível. Direto. Sem enfeites. Máximo 400 palavras no total.
Não use markdown, bullets ou numeração — apenas os 3 parágrafos."""


def _fallback_narrative(ctx: dict[str, Any]) -> str:
    top3 = ctx.get("top3_bairros") or ["áreas centrais"]
    top3_txt = ", ".join(top3[:3])
    programas = ctx.get("programas") or ["PAC Seleções", "Convênios MCID", "Pro-Cidades"]
    prog_txt = ", ".join(programas[:3])

    p1 = (
        f"{ctx['municipio_nome']} apresenta Score Sinidu+Clima de {ctx['score']}/100, "
        f"classificado como severidade {ctx['severidade'].lower()}. "
        f"Com IVC médio {ctx['ivc']} e IRI médio {ctx['iri']}, o município está acima da média "
        f"de exposição a eventos climáticos urbanos observada em municípios brasileiros de porte similar."
    )
    p2 = (
        f"As prioridades territoriais concentram-se em {top3_txt}, onde a combinação de vulnerabilidade "
        f"socioambiental e risco de inundação exige resposta imediata da Defesa Civil e das secretarias de obras. "
        f"Nos últimos 10 anos foram registrados {ctx['n_eventos']} eventos no S2ID, "
        f"com {ctx['n_alertas']} alertas CEMADEN ativos no monitoramento atual."
    )
    p3 = (
        f"Nos próximos 90 dias, recomenda-se: (1) articular protocolo de alerta com CEMADEN; "
        f"(2) desobstruir microdrenagem nos bairros críticos; "
        f"(3) estruturar carteira de obras alinhada ao CAPAG {ctx['capag'] or '—'}. "
        f"Fontes elegíveis incluem {prog_txt}."
    )
    return f"{p1}\n\n{p2}\n\n{p3}"


def build_narrative_context(
    muni_name: str,
    muni_uf: str,
    *,
    snapshot: dict[str, Any],
    sections: dict[str, Any],
    action_plan: dict[str, Any],
    severidade: str,
) -> dict[str, Any]:
    fiscal = sections.get("situacao_fiscal") or {}
    climatica = sections.get("situacao_climatica") or {}
    historico = sections.get("historico_desastres") or {}
    lacunas = sections.get("lacunas") or {}
    riscos = sections.get("principais_riscos") or {}

    eventos = historico.get("eventos") or []
    maior_dano = 0.0
    data_maior = None
    for ev in eventos:
        d = float(ev.get("danos_materiais") or 0)
        if d >= maior_dano:
            maior_dano = d
            data_maior = ev.get("data")

    top3 = [a.get("bairro") for a in (riscos.get("areas_criticas") or []) if a.get("bairro")]
    programas = [p.get("nome") or p.get("programa") for p in (action_plan.get("programas_financiamento") or [])[:3]]
    programas = [p for p in programas if p]

    n_curto = len(action_plan.get("acoes_curto_prazo") or [])
    n_medio = len(action_plan.get("acoes_medio_prazo") or [])
    n_longo = len(action_plan.get("acoes_longo_prazo") or [])

    nota_capag = fiscal.get("nota_capag_raw") or fiscal.get("nota_capag")

    return {
        "municipio_nome": f"{muni_name}/{muni_uf}",
        "score": int(snapshot.get("score_sinidu") or 0),
        "severidade": severidade,
        "ivc": snapshot.get("media_ivc"),
        "iri": snapshot.get("media_iri"),
        "capag": nota_capag,
        "descricao_capag": _capag_financing_desc(nota_capag),
        "top3_bairros": top3,
        "n_eventos": historico.get("total_10_anos") or len(eventos),
        "maior_dano_fmt": f"{maior_dano:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "data_maior_dano": data_maior,
        "n_alertas": climatica.get("alertas_ativos") or 0,
        "lacunas": lacunas.get("lacunas") or [],
        "n_acoes": action_plan.get("total_acoes") or (n_curto + n_medio + n_longo),
        "n_curto": n_curto,
        "n_medio": n_medio,
        "n_longo": n_longo,
        "programas": programas,
    }


def generate_executive_narrative(
    ctx: dict[str, Any],
    *,
    ai_provider: str | None = None,
    ai_model: str | None = None,
    ai_api_key: str | None = None,
    use_ai: bool = True,
) -> dict[str, Any]:
    """Gera narrativa IA (Mistral) ou fallback determinístico."""
    prompt = _build_prompt(ctx)
    text = None
    provider_id = "deterministic"
    model_used = None

    if use_ai:
        try:
            from rag.providers.registry import resolve_chat_provider_with_fallback

            provider = resolve_chat_provider_with_fallback(ai_provider, api_key=ai_api_key)
            if provider.is_available():
                model_used = ai_model or provider.info().default_model
                messages = [
                    {"role": "system", "content": "Você escreve diagnósticos executivos para gestores municipais brasileiros."},
                    {"role": "user", "content": prompt},
                ]
                text = (provider.chat(messages, model=model_used, temperature=0.2) or "").strip()
                provider_id = provider.id
        except Exception as exc:
            logger.warning("Narrativa IA falhou: %s", exc)

    if not text:
        text = _fallback_narrative(ctx)
        provider_id = "deterministic"

    paragraphs = _split_paragraphs(text)
    if len(paragraphs) < 3 and text:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()][:3]

    return {
        "narrativa_ia": text,
        "paragrafos": paragraphs,
        "disclaimer": NARRATIVE_DISCLAIMER,
        "ai_provider": provider_id,
        "ai_model": model_used,
    }
