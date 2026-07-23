"""Catálogo de programas federais e ligação medida → financiamento (17h.3b).

Contatos institucionais públicos; elegibilidade filtrada por CAPAG sem inventar
aprovação individual.
"""

from __future__ import annotations

from typing import Any

# tipo: nao_reembolsavel | credito | orcamento_proprio | apoio_tecnico
# exige_capag_ab: True = só sugerir com CAPAG A/B (garantia da União / FGTS)
PROGRAMS: list[dict[str, Any]] = [
    {
        "id": "orcamento_proprio",
        "nome": "Orçamento próprio / LOA municipal",
        "orgao": "Prefeitura",
        "unidade": "Secretaria de Finanças / Contabilidade",
        "site": "",
        "contato": "Controle interno e LOA local",
        "elegibilidade": "Recursos ordinários do município — adequado a ações de baixo/médio custo.",
        "tipo": "orcamento_proprio",
        "exige_capag_ab": False,
        "quando_sugerir": ["Alta", "Crítica", "Média", "Baixa"],
    },
    {
        "id": "emendas",
        "nome": "Emendas parlamentares (individuais/bancada)",
        "orgao": "Congresso Nacional / executivo local",
        "unidade": "Articulação institucional do município",
        "site": "https://www.camara.leg.br/",
        "contato": "Gabinete parlamentar / assessoria de governo",
        "elegibilidade": "Depende de articulação política; útil para microdrenagem, NBS e equipamentos.",
        "tipo": "nao_reembolsavel",
        "exige_capag_ab": False,
        "quando_sugerir": ["Alta", "Crítica", "Média"],
    },
    {
        "id": "fcp",
        "nome": "FCP — Fundo de Calamidade Pública",
        "orgao": "Ministério da Fazenda",
        "unidade": "Secretaria do Tesouro Nacional (STN)",
        "site": "https://www.gov.br/tesouronacional/pt-br/assuntos/fcp",
        "contato": "Canal institucional STN / Tesouro Transparente",
        "elegibilidade": "Municípios ou estados com decreto de situação de emergência ou calamidade pública reconhecida.",
        "tipo": "nao_reembolsavel",
        "exige_capag_ab": False,
        "quando_sugerir": ["Alta", "Crítica"],
    },
    {
        "id": "fundo_clima",
        "nome": "Fundo Clima",
        "orgao": "Ministério do Meio Ambiente e Mudança do Clima (MMA)",
        "unidade": "Diretoria de Adaptação às Mudanças Climáticas",
        "site": "https://www.gov.br/mma/pt-br/assuntos/agenda-climatica/fundo-clima",
        "contato": "Ouvidoria MMA: ouvidoria@mma.gov.br",
        "elegibilidade": "Projetos de mitigação e adaptação climática com entidades executoras habilitadas.",
        "tipo": "nao_reembolsavel",
        "exige_capag_ab": False,
        "quando_sugerir": ["Alta", "Crítica", "Média"],
    },
    {
        "id": "pac_cidades",
        "nome": "PAC Seleções / PAC Cidades",
        "orgao": "Ministério das Cidades (MCid)",
        "unidade": "Secretaria Nacional de Habitação (SNH)",
        "site": "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/pro-cidades",
        "contato": "Canal MCid — https://www.gov.br/cidades",
        "elegibilidade": "Obras urbanas estruturantes; contrapartida mínima; editais vigentes.",
        "tipo": "nao_reembolsavel",
        "exige_capag_ab": False,
        "quando_sugerir": ["Alta", "Crítica", "Média"],
    },
    {
        "id": "pro_cidades",
        "nome": "Pro-Cidades (FGTS — modernização / reabilitação urbana)",
        "orgao": "Ministério das Cidades (MCid)",
        "unidade": "Programa Pro-Cidades · FGTS",
        "site": "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/pro-cidades",
        "contato": "Canal Pro-Cidades MCid",
        "elegibilidade": (
            "IN MCID nº 18/2025 + Res. CCFGTS 1.147/2026; contrapartida ≥ 5%; "
            "CAPAG A ou B para garantia da União."
        ),
        "tipo": "credito",
        "exige_capag_ab": True,
        "quando_sugerir": ["Alta", "Crítica", "Média"],
        "quando_sugerir_capag": ["A", "B"],
    },
    {
        "id": "credito_uniao",
        "nome": "Operações de crédito com garantia da União",
        "orgao": "Tesouro Nacional / STN",
        "unidade": "Coordenação CAPAG",
        "site": "https://www.tesourotransparente.gov.br/ckan/dataset/capag-municipios",
        "contato": "Tesouro Transparente — dados CAPAG oficiais",
        "elegibilidade": "Nota CAPAG A ou B; compatível com limites LRF.",
        "tipo": "credito",
        "exige_capag_ab": True,
        "quando_sugerir_capag": ["A", "B"],
    },
    {
        "id": "defesa_civil",
        "nome": "Apoio técnico e operacional — Proteção e Defesa Civil",
        "orgao": "Ministério da Integração e do Desenvolvimento Regional (MIDR)",
        "unidade": "Secretaria Nacional de Proteção e Defesa Civil (SEDEC)",
        "site": "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil",
        "contato": "Centro Nacional de Gerenciamento de Riscos e Desastres (CENAD)",
        "elegibilidade": "Articulação com planos municipais de PDC; integração S2ID/CEMADEN.",
        "tipo": "apoio_tecnico",
        "exige_capag_ab": False,
        "quando_sugerir": ["Alta", "Crítica", "Média", "Baixa"],
    },
    {
        "id": "saneamento",
        "nome": "SNIS / SINISA — saneamento e drenagem",
        "orgao": "Ministério das Cidades (MCid)",
        "unidade": "Secretaria Nacional de Saneamento Ambiental (SNSA)",
        "site": "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento",
        "contato": "Canal MCid Saneamento",
        "elegibilidade": "Planos locais de saneamento; integração com diagnóstico de drenagem urbana.",
        "tipo": "nao_reembolsavel",
        "exige_capag_ab": False,
        "quando_sugerir": ["Alta", "Crítica", "Média"],
    },
]

PROGRAMS_BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in PROGRAMS}

# Medida (id) → programas preferenciais (ordem = prioridade de indicação)
MEASURE_FINANCING: dict[str, list[str]] = {
    "mon_cemaden_dc": ["defesa_civil", "orcamento_proprio"],
    "microdrenagem": ["orcamento_proprio", "emendas", "saneamento"],
    "plano_contingencia": ["defesa_civil", "orcamento_proprio"],
    "capacitacao_dc": ["defesa_civil", "orcamento_proprio"],
    "revegetacao": ["fundo_clima", "emendas", "orcamento_proprio"],
    "nbs_retencao": ["pac_cidades", "pro_cidades", "fundo_clima", "saneamento", "credito_uniao"],
    "carteira_drenagem": ["pac_cidades", "pro_cidades", "saneamento", "credito_uniao"],
    "priorizar_nao_reembolsavel": ["defesa_civil", "fundo_clima", "emendas", "fcp", "orcamento_proprio"],
    "apoio_sedec": ["defesa_civil"],
    "mapeamento_expostos": ["defesa_civil", "orcamento_proprio"],
}

# Fallback por tipo_risco quando a medida não está no mapa
TIPO_RISCO_FINANCING: dict[str, list[str]] = {
    "alerta": ["defesa_civil", "orcamento_proprio"],
    "inundacao": ["saneamento", "pac_cidades", "emendas", "orcamento_proprio"],
    "contingencia": ["defesa_civil", "fcp", "orcamento_proprio"],
    "capacidade": ["defesa_civil", "orcamento_proprio"],
    "calor_escoamento": ["fundo_clima", "emendas", "orcamento_proprio"],
    "estrutural": ["pac_cidades", "pro_cidades", "saneamento", "credito_uniao"],
    "fiscal": ["emendas", "fundo_clima", "defesa_civil", "orcamento_proprio"],
    "exposicao": ["defesa_civil", "orcamento_proprio"],
}

CAPAG_RESTRITA = {"C", "D", "E"}


def _program_snapshot(prog: dict[str, Any], *, motivo: str, viabilidade: str) -> dict[str, Any]:
    return {
        "id": prog["id"],
        "nome": prog["nome"],
        "orgao": prog["orgao"],
        "unidade": prog.get("unidade") or "",
        "site": prog.get("site") or "",
        "contato": prog.get("contato") or "",
        "elegibilidade": prog.get("elegibilidade") or "",
        "tipo": prog.get("tipo") or "nao_reembolsavel",
        "motivo": motivo,
        "viabilidade": viabilidade,
    }


def _capag_blocks_program(prog: dict[str, Any], nota_capag: str | None) -> bool:
    """True se o programa de crédito não cabe na CAPAG atual."""
    capag = (nota_capag or "").upper()[:1] or None
    if not prog.get("exige_capag_ab"):
        return False
    if not capag:
        return True  # sem CAPAG → não sugerir crédito União/FGTS como viável
    return capag in CAPAG_RESTRITA or capag not in {"A", "B"}


def programs_for_measure(
    measure_id: str,
    *,
    tipo_risco: str | None = None,
    custo: str | None = None,
    nota_capag: str | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Programas cabíveis para uma medida, filtrados pela CAPAG."""
    ids = list(MEASURE_FINANCING.get(measure_id) or [])
    if not ids and tipo_risco:
        ids = list(TIPO_RISCO_FINANCING.get(tipo_risco) or ["orcamento_proprio"])
    if not ids:
        ids = ["orcamento_proprio", "defesa_civil"]

    # Custo baixo: priorizar orçamento próprio / apoio técnico
    if (custo or "").lower() in {"baixo", "low"} and "orcamento_proprio" not in ids:
        ids = ["orcamento_proprio", *ids]

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pid in ids:
        if pid in seen:
            continue
        seen.add(pid)
        prog = PROGRAMS_BY_ID.get(pid)
        if not prog:
            continue
        if _capag_blocks_program(prog, nota_capag):
            # Ainda informa como restrito (transparência), mas só se sobrar espaço
            continue
        capag = (nota_capag or "").upper()[:1] or None
        if prog.get("exige_capag_ab") and capag in {"A", "B"}:
            motivo = f"CAPAG {capag} compatível com garantia da União / FGTS."
            viabilidade = "compativel"
        elif prog.get("tipo") == "orcamento_proprio":
            motivo = "Independe de CAPAG — execução via LOA."
            viabilidade = "compativel"
        elif prog.get("tipo") == "apoio_tecnico":
            motivo = "Apoio técnico/operacional — sem operação de crédito."
            viabilidade = "compativel"
        else:
            motivo = "Fonte não reembolsável ou emenda — preferível sob restrição fiscal."
            viabilidade = "compativel"
            if capag in CAPAG_RESTRITA:
                motivo = f"CAPAG {capag}: priorizar não reembolsável."
                viabilidade = "preferivel"
        selected.append(_program_snapshot(prog, motivo=motivo, viabilidade=viabilidade))
        if len(selected) >= limit:
            break

    # Se CAPAG restritiva e nada sobrou, garantir ao menos orçamento + SEDEC
    if not selected:
        for pid in ("orcamento_proprio", "defesa_civil", "emendas"):
            prog = PROGRAMS_BY_ID.get(pid)
            if prog:
                selected.append(
                    _program_snapshot(
                        prog,
                        motivo="Fallback sob restrição fiscal / CAPAG ausente.",
                        viabilidade="preferivel",
                    )
                )
            if len(selected) >= limit:
                break
    return selected


def attach_financing_to_measures(
    medidas: list[dict[str, Any]],
    *,
    nota_capag: str | None,
    limit_por_medida: int = 3,
) -> list[dict[str, Any]]:
    """Anexa `fontes_financiamento` a cada medida recomendada."""
    out: list[dict[str, Any]] = []
    for m in medidas:
        fontes = programs_for_measure(
            m.get("id") or "",
            tipo_risco=m.get("tipo_risco"),
            custo=m.get("custo"),
            nota_capag=nota_capag,
            limit=limit_por_medida,
        )
        enriched = {**m, "fontes_financiamento": fontes}
        out.append(enriched)
    return out


def suggest_programs(
    *,
    severidade: str,
    nota_capag: str | None,
    media_ivc: float = 0.0,
) -> list[dict[str, Any]]:
    """Retorna programas aplicáveis sem inventar elegibilidade individual."""
    sev = severidade or "Média"
    capag = (nota_capag or "").upper()[:1]
    selected: list[dict[str, Any]] = []

    for prog in PROGRAMS:
        if prog["id"] == "orcamento_proprio":
            continue  # só aparece ligado a medidas
        if _capag_blocks_program(prog, nota_capag):
            continue
        if capag and prog.get("quando_sugerir_capag") and capag in prog["quando_sugerir_capag"]:
            selected.append({
                **{k: prog[k] for k in ("id", "nome", "orgao", "unidade", "site", "contato", "elegibilidade") if k in prog},
                "tipo": prog.get("tipo"),
                "motivo": f"CAPAG {capag} compatível com este instrumento.",
            })
            continue
        when = prog.get("quando_sugerir") or []
        if sev in when:
            selected.append({
                **{k: prog[k] for k in ("id", "nome", "orgao", "unidade", "site", "contato", "elegibilidade") if k in prog},
                "tipo": prog.get("tipo"),
                "motivo": f"Severidade do cenário: {sev}.",
            })
        elif media_ivc >= 0.6 and sev in {"Alta", "Crítica"}:
            if prog["id"] in {"fcp", "fundo_clima", "pac_cidades", "pro_cidades"}:
                selected.append({
                    **{k: prog[k] for k in ("id", "nome", "orgao", "unidade", "site", "contato", "elegibilidade") if k in prog},
                    "tipo": prog.get("tipo"),
                    "motivo": f"Alta vulnerabilidade climática (IVC médio {media_ivc:.2f}).",
                })

    if not selected:
        fallback = PROGRAMS_BY_ID["defesa_civil"]
        selected.append({
            **{k: fallback[k] for k in ("id", "nome", "orgao", "unidade", "site", "contato", "elegibilidade")},
            "tipo": fallback.get("tipo"),
            "motivo": "Revisar elegibilidade após atualização da CAPAG e do diagnóstico de vulnerabilidade.",
        })
    return selected
