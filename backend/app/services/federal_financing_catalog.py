"""Catálogo de programas federais sugeridos para planos de ação — contatos institucionais públicos."""

from __future__ import annotations

from typing import Any

PROGRAMS: list[dict[str, Any]] = [
    {
        "id": "fcp",
        "nome": "FCP — Fundo de Calamidade Pública",
        "orgao": "Ministério da Fazenda",
        "unidade": "Secretaria do Tesouro Nacional (STN)",
        "site": "https://www.gov.br/tesouronacional/pt-br/assuntos/fcp",
        "contato": "Canal institucional STN / Tesouro Transparente",
        "elegibilidade": "Municípios ou estados com decreto de situação de emergência ou calamidade pública reconhecida.",
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
        "quando_sugerir": ["Alta", "Crítica", "Média"],
    },
    {
        "id": "pac_cidades",
        "nome": "PAC Seleções / PAC Cidades",
        "orgao": "Ministério das Cidades (MCid)",
        "unidade": "Secretaria Nacional de Habitação (SNH) · Programa Pro-Cidades",
        "site": "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/pro-cidades",
        "contato": "Canal Pro-Cidades MCid — https://www.gov.br/cidades",
        "elegibilidade": "Obras urbanas estruturantes; contrapartida mínima; CAPAG A ou B para garantia da União (Res. CCFGTS).",
        "quando_sugerir": ["Alta", "Crítica", "Média"],
    },
    {
        "id": "credito_uniao",
        "nome": "Operações de crédito com garantia da União",
        "orgao": "Tesouro Nacional / STN",
        "unidade": "Coordenação CAPAG",
        "site": "https://www.tesourotransparente.gov.br/ckan/dataset/capag-municipios",
        "contato": "Tesouro Transparente — dados CAPAG oficiais",
        "elegibilidade": "Nota CAPAG A ou B; compatível com limites LRF.",
        "quando_sugerir_capag": ["A", "B"],
    },
    {
        "id": "defesa_civil",
        "nome": "Apoio técnico e operacional — Proteção e Defesa Civil",
        "orgao": "Ministério da Integração e do Desenvolvimento Regional (MIDR)",
        "unidade": "Secretaria Nacional de Proteção e Defesa Civil (SEDEC)",
        "site": "https://www.gov.br/mdr/pt-br/assuntos/protecao-e-defesa-civil",
        "contato": "Centro Nacional de Gerenciamento de Riscos e Desastres (CENAD): cenad@sede.gov.br",
        "elegibilidade": "Articulação com planos municipais de PDC; integração S2ID/CEMADEN.",
        "quando_sugerir": ["Alta", "Crítica", "Média", "Baixa"],
    },
    {
        "id": "saneamento",
        "nome": "SNIS / SINISA — investimentos em saneamento e drenagem",
        "orgao": "Ministério das Cidades (MCid)",
        "unidade": "Secretaria Nacional de Saneamento Ambiental (SNSA)",
        "site": "https://www.gov.br/cidades/pt-br/acesso-a-informacao/acoes-e-programas/saneamento",
        "contato": "Canal MCid Saneamento",
        "elegibilidade": "Planos locais de saneamento; integração com diagnóstico de drenagem urbana.",
        "quando_sugerir": ["Alta", "Crítica", "Média"],
    },
]


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
        if capag and prog.get("quando_sugerir_capag") and capag in prog["quando_sugerir_capag"]:
            selected.append({**prog, "motivo": f"CAPAG {capag} compatível com este instrumento."})
            continue
        when = prog.get("quando_sugerir") or []
        if sev in when:
            selected.append({**prog, "motivo": f"Severidade do cenário: {sev}."})
        elif media_ivc >= 0.6 and sev in {"Alta", "Crítica"}:
            if prog["id"] in {"fcp", "fundo_clima", "pac_cidades"}:
                selected.append({**prog, "motivo": f"Alta vulnerabilidade climática (IVC médio {media_ivc:.2f})."})

    if not selected:
        selected.append({
            **PROGRAMS[3],
            "motivo": "Revisar elegibilidade após atualização da CAPAG e do diagnóstico de vulnerabilidade.",
        })
    return selected
