from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import quote_plus

import requests
from sqlalchemy.orm import Session

from app.data_connectors.siconfi_collector import collect_siconfi_municipality

SICONFI_IA_BASE_URL = "https://siconfi-ia.tesourotransparente.gov.br"
SICONFI_IA_CHAT_CANDIDATES = (
    f"{SICONFI_IA_BASE_URL}/api/chat",
    f"{SICONFI_IA_BASE_URL}/api/v1/chat",
)

FISCAL_KEYWORDS = (
    "orcamento", "orçamento", "receita", "despesa", "pessoal", "divida", "dívida",
    "endividamento", "lrf", "capag", "transferencia", "transferência", "transferencias",
    "fpm", "icms", "saude", "saúde", "educacao", "educação", "fiscal", "siconfi",
    "rreo", "rgf", "rcl", "primario", "primário", "tesouro", "execucao", "execução",
    "habitacao", "habitação", "saneamento", "meio ambiente", "ambient", "defesa civil",
)

TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "meio_ambiente": ("meio ambiente", "ambient", "gestao ambiental", "gestão ambiental", "ecolog"),
    "saude": ("saude", "saúde", "mde saude", "hospital", "atencao basica"),
    "educacao": ("educacao", "educação", "mde", "escola", "ensino"),
    "pessoal": ("pessoal", "servidor", "folha", "encargos sociais"),
    "divida": ("divida", "dívida", "endividamento", "consolidada"),
    "receita": ("receita", "rcl", "arrecadacao", "arrecadação"),
    "transferencias": ("transferencia", "transferência", "fpm", "icms", "fundeb", "convênio", "convenio"),
    "capag": ("capag", "capacidade de pagamento"),
    "habitacao": ("habitacao", "habitação", "urbanismo", "habita"),
    "saneamento": ("saneamento", "drenagem", "esgoto", "agua", "água"),
    "defesa_civil": ("defesa civil", "protecao civil", "proteção civil"),
    "resultado": ("resultado primario", "resultado primário", "superavit", "superávit", "deficit", "déficit"),
}

LRF_LIMITE_PESSOAL = 60.0
LRF_LIMITE_DIVIDA = 120.0


def detect_fiscal_intent(query: str) -> bool:
    normalized = query.lower()
    return any(keyword in normalized for keyword in FISCAL_KEYWORDS)


def classify_fiscal_topic(query: str) -> str:
    normalized = query.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return topic
    return "geral"


def build_siconfi_ia_url(municipio_nome: str, uf: str, question: str) -> str:
    prompt = f"No município de {municipio_nome}-{uf}, {question.strip()}"
    return f"{SICONFI_IA_BASE_URL}/?q={quote_plus(prompt)}"


def _format_currency(value: Optional[float]) -> str:
    if value is None:
        return "não informado"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _lrf_status(pct: Optional[float], limit: float) -> str:
    if pct is None:
        return "sem dado oficial para comparar com o limite LRF"
    return "dentro" if pct <= limit else "acima"


def _fiscal_snapshot(db: Session, municipio) -> Dict[str, Any]:
    from app.models import MunicipioFiscal
    cached = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == municipio.codigo_ibge).first()
    live = collect_siconfi_municipality(municipio.codigo_ibge)

    def pick(field: str):
        if cached is not None:
            value = getattr(cached, field, None)
            if value is not None:
                return float(value) if field.endswith("_pct_rcl") or field.startswith("exec_") or field in {
                    "receita_corrente_liquida", "divida_consolidada", "resultado_primario", "despesa_pessoal_pct_rcl"
                } else value
        return live.get(field)

    receita = pick("receita_corrente_liquida")
    pessoal_pct = pick("despesa_pessoal_pct_rcl")
    divida = pick("divida_consolidada")
    divida_pct = round((divida / receita) * 100, 2) if divida and receita else None

    return {
        "codigo_ibge": municipio.codigo_ibge,
        "nome": municipio.nome,
        "uf": municipio.uf,
        "exercicio": (cached.exercicio if cached and cached.exercicio else live.get("exercicio")) or 2024,
        "nota_capag": (cached.nota_capag if cached and cached.nota_capag else None),
        "receita_corrente_liquida": receita,
        "despesa_pessoal_pct_rcl": pessoal_pct,
        "divida_consolidada": divida,
        "divida_consolidada_pct_rcl": divida_pct,
        "resultado_primario": pick("resultado_primario"),
        "exec_saude": pick("exec_saude"),
        "exec_habitacao": pick("exec_habitacao"),
        "exec_saneamento": pick("exec_saneamento"),
        "exec_meio_ambiente": pick("exec_meio_ambiente"),
        "exec_defesa_civil": pick("exec_defesa_civil"),
        "fonte": "SICONFI / Tesouro Nacional (RREO/RGF)",
    }


def try_siconfi_ia_fetch(question: str, timeout: int = 8) -> Optional[str]:
    payload = {"message": question, "question": question, "prompt": question}
    headers = {"User-Agent": "Sinidu+Clima/1.0", "Content-Type": "application/json"}
    for url in SICONFI_IA_CHAT_CANDIDATES:
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if response.status_code >= 400:
                continue
            data = response.json()
            for key in ("response", "answer", "message", "content", "text"):
                if isinstance(data, dict) and data.get(key):
                    return str(data[key]).strip()
            if isinstance(data, str) and data.strip():
                return data.strip()
        except Exception:
            continue
    return None


def _topic_answer(topic: str, snapshot: Dict[str, Any]) -> str:
    ano = snapshot["exercicio"]
    nome = snapshot["nome"]
    receita = snapshot.get("receita_corrente_liquida")
    pessoal_pct = snapshot.get("despesa_pessoal_pct_rcl")
    divida_pct = snapshot.get("divida_consolidada_pct_rcl")

    if topic == "meio_ambiente":
        valor = snapshot["exec_meio_ambiente"]
        if valor is None:
            return (
                f"Não localizei execução orçamentária de **meio ambiente** no RREO {ano} para {nome} "
                f"com os recortes disponíveis na API SICONFI."
            )
        return (
            f"A execução orçamentária vinculada a **meio ambiente/gestão ambiental** em {nome} "
            f"totalizou **{_format_currency(valor)}** no exercício de {ano}, conforme RREO."
        )

    if topic == "saude":
        valor = snapshot["exec_saude"]
        if valor is None:
            return f"Não há linha oficial de saúde disponível no recorte consultado do RREO {ano} para {nome}."
        share = f" ({round((valor / receita) * 100, 1)}% da RCL)" if receita else ""
        return f"{nome} executou **{_format_currency(valor)}** em ações de **saúde** em {ano}{share}."

    if topic == "educacao":
        return (
            f"Para percentuais constitucionais de **educação** (MDE) e detalhamento do Anexo 14, "
            f"o recorte REST atual do Sinidu+Clima ainda não extrai automaticamente todas as contas. "
            f"Consulte o comparativo completo no Siconfi.IA para {nome}."
        )

    if topic == "pessoal":
        status = _lrf_status(pessoal_pct, LRF_LIMITE_PESSOAL)
        return (
            f"A **despesa com pessoal** de {nome} representou **{pessoal_pct:.1f}% da RCL** em {ano}, "
            f"**{status}** do limite de referência de 60% da LRF."
            if pessoal_pct is not None
            else f"Não foi possível calcular a despesa com pessoal/RCL de {nome} no recorte consultado."
        )

    if topic == "divida":
        status = _lrf_status(divida_pct, LRF_LIMITE_DIVIDA)
        return (
            f"A **dívida consolidada** de {nome} equivale a **{divida_pct:.1f}% da RCL** em {ano}, "
            f"**{status}** do limite de referência de 120% da LRF."
            if divida_pct is not None
            else f"Não foi possível calcular dívida consolidada/RCL de {nome} no recorte consultado."
        )

    if topic == "capag":
        nota = snapshot.get("nota_capag")
        if not nota:
            return f"A nota **CAPAG** de {nome} não está disponível na base integrada do Sinidu+Clima."
        alert = " Restrições para garantia da União devem ser avaliadas." if nota in {"C", "D"} else ""
        return f"A nota **CAPAG** de {nome} é **{nota}**.{alert}"

    if topic == "transferencias":
        return (
            f"Transferências como **FPM** e **ICMS** podem ser detalhadas no RREO de {nome}. "
            f"No recorte REST atual, recomendo abrir a pergunta completa no Siconfi.IA para obter "
            f"a composição linha a linha das transferências correntes."
        )

    if topic == "resultado":
        valor = snapshot["resultado_primario"]
        if valor is None:
            return f"O **resultado primário** de {nome} não foi localizado no recorte consultado do RREO {ano}."
        sinal = "superávit" if valor >= 0 else "déficit"
        return f"{nome} apresentou **resultado primário** de **{_format_currency(abs(valor))}** ({sinal}) em {ano}."

    if topic in {"habitacao", "saneamento", "defesa_civil"}:
        field = f"exec_{topic}"
        valor = snapshot.get(field)
        label = topic.replace("_", " ")
        if valor is None:
            return f"Não localizei execução de **{label}** no RREO {ano} para {nome}."
        return f"{nome} executou **{_format_currency(valor)}** em **{label}** em {ano}."

    status_pessoal = _lrf_status(pessoal_pct, LRF_LIMITE_PESSOAL)
    return (
        f"O município de **{nome}** teve **receita corrente líquida** de **{_format_currency(receita)}** em {ano}. "
        f"A despesa com pessoal representou **{pessoal_pct:.1f}% da RCL**, **{status_pessoal}** do limite LRF de 60%."
        if receita and pessoal_pct is not None
        else f"Os indicadores fiscais principais de {nome} ainda não estão completos no recorte consultado."
    )


def answer_fiscal_question(db: Session, municipio, question: str) -> Dict[str, Any]:
    topic = classify_fiscal_topic(question)
    reformulated = (
        f"Considerando o município de {municipio.nome}-{municipio.uf} (IBGE {municipio.codigo_ibge}), "
        f"{question.strip().rstrip('?')}."
    )
    siconfi_ia_url = build_siconfi_ia_url(municipio.nome, municipio.uf, question)
    snapshot = _fiscal_snapshot(db, municipio)

    ia_answer = try_siconfi_ia_fetch(reformulated)
    if ia_answer:
        body = ia_answer
        source_mode = "Siconfi.IA"
    else:
        body = _topic_answer(topic, snapshot)
        source_mode = "SICONFI REST (fallback)"

    response = (
        f"### Consulta Fiscal — {municipio.nome}/{municipio.uf}\n\n"
        f"{body}\n\n"
        f"* Fonte: **{source_mode} / Tesouro Nacional**\n"
        f"* Exercício de referência: **{snapshot['exercicio']}**\n"
        f"* Explore detalhes conversacionais: [Abrir no Siconfi.IA ↗]({siconfi_ia_url})"
    )

    return {
        "response": response,
        "source_url": siconfi_ia_url,
        "topic": topic,
        "snapshot": snapshot,
        "source_mode": source_mode,
    }
