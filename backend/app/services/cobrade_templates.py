"""Templates de ações por nível COBRADE para planos de contingência."""

from __future__ import annotations

from typing import Any

# Tipologia Sinidu → código COBRADE oficial (MDR) + rótulo
COBRADE_CODES: dict[str, dict[str, str]] = {
    "INUNDACAO": {
        "codigo": "1.2.1.0.0",
        "label": "Inundações",
        "grupo": "Desastres hidrológicos",
    },
    "DESLIZAMENTO": {
        "codigo": "1.1.3.0.0",
        "label": "Deslizamentos / movimentos de massa",
        "grupo": "Desastres geológicos",
    },
    "MULTIPLO": {
        "codigo": "1.2.1.0.0+1.1.3.0.0",
        "label": "Multi-risco (inundação + deslizamento)",
        "grupo": "Desastres hidrológicos / geológicos",
    },
}

COBRADE_ACTIONS: dict[str, dict[str, list[str]]] = {
    "INUNDACAO": {
        "VERDE": [
            "Manter monitoramento meteorológico e hidrológico.",
            "Verificar funcionamento de sirenes e canais oficiais.",
        ],
        "AMARELO": [
            "Acionar equipe de plantão da Defesa Civil.",
            "Inspecionar áreas de alagamento histórico e bocas de lobo.",
            "Comunicar escolas e UBS em zona de atenção.",
        ],
        "LARANJA": [
            "Restringir tráfego em vias de risco identificadas.",
            "Preparar abertura de pontos de apoio e abrigos.",
            "Iniciar evacuação preventiva nas zonas mapeadas.",
        ],
        "VERMELHO": [
            "Evacuação imediata das zonas vermelhas.",
            "Interditar vias alagadas; acionar Corpo de Bombeiros.",
            "Operar pontos de apoio 24h e registrar famílias acolhidas.",
        ],
    },
    "DESLIZAMENTO": {
        "VERDE": [
            "Monitorar encostas instáveis cadastradas.",
            "Manter equipes de campo em prontidão.",
        ],
        "AMARELO": [
            "Vistoriar morros e encostas com histórico de movimento.",
            "Orientar moradores sobre sinais de risco (trincas, barulhos).",
        ],
        "LARANJA": [
            "Evacuação preventiva de áreas abaixo de encostas críticas.",
            "Interditar trechos em encosta ativa.",
        ],
        "VERMELHO": [
            "Evacuação compulsória imediata.",
            "Isolar área afetada; acionar geotecnia e bombeiros.",
        ],
    },
    "MULTIPLO": {
        "VERDE": [
            "Monitoramento integrado chuva + encosta + drenagem.",
        ],
        "AMARELO": [
            "Ativar protocolo multi-risco; reunião COBRADE municipal.",
            "Checar pontos de apoio e rotas alternativas.",
        ],
        "LARANJA": [
            "Evacuação preventiva zonas inundáveis e encostas.",
            "Mobilizar todas as secretarias do plano de contingência.",
        ],
        "VERMELHO": [
            "Operação integrada Defesa Civil + Bombeiros + Saúde.",
            "Evacuação total das zonas críticas mapeadas.",
        ],
    },
}

# Contatos mínimos esperados no protocolo operacional
CONTATOS_MINIMOS = [
    {"papel": "Defesa Civil 24h", "cargo": "Plantão DC", "obrigatorio": True},
    {"papel": "Corpo de Bombeiros", "cargo": "CBM", "obrigatorio": True},
    {"papel": "SAMU / Saúde", "cargo": "Regulação", "obrigatorio": True},
    {"papel": "Prefeitura / Gabinete", "cargo": "Articulação", "obrigatorio": False},
]

# Protocolo alerta → campo (SLA e canais)
PROTOCOLO_CAMPO_PADRAO: dict[str, Any] = {
    "canais": ["rádio/WhatsApp institucional", "sirene / alto-falante", "redes oficiais da prefeitura"],
    "passos": [
        {
            "ordem": 1,
            "quando": "Alerta AMARELO",
            "quem": "Plantão Defesa Civil",
            "o_que": "Confirmar alerta CEMADEN/monitor e avisar pontos de apoio.",
            "sla_minutos": 30,
        },
        {
            "ordem": 2,
            "quando": "Alerta LARANJA",
            "quem": "Coordenação DC + Obras",
            "o_que": "Abrir abrigos, restringir vias e iniciar evacuação preventiva.",
            "sla_minutos": 60,
        },
        {
            "ordem": 3,
            "quando": "Alerta VERMELHO",
            "quem": "COE municipal (DC + Bombeiros + Saúde)",
            "o_que": "Evacuação compulsória, registro de acolhidos e boletim horário.",
            "sla_minutos": 15,
        },
    ],
    "checklist_campo": [
        "Lista de famílias por zona de evacuação",
        "Capacidade atualizada dos abrigos",
        "Viaturas e kits de primeiros socorros disponíveis",
        "Canal 24h com Bombeiros e SAMU confirmado",
    ],
}


def cobrade_for_cenario(cenario_tipo: str) -> dict[str, str]:
    return COBRADE_CODES.get((cenario_tipo or "").upper(), COBRADE_CODES["MULTIPLO"])


def default_acoes_por_nivel(cenario_tipo: str) -> dict[str, list[str]]:
    base = COBRADE_ACTIONS.get(cenario_tipo.upper(), COBRADE_ACTIONS["MULTIPLO"])
    return {nivel: list(acoes) for nivel, acoes in base.items()}


def default_protocolo_campo(cenario_tipo: str) -> dict[str, Any]:
    info = cobrade_for_cenario(cenario_tipo)
    return {
        **PROTOCOLO_CAMPO_PADRAO,
        "cobrade": info,
        "contatos_minimos": CONTATOS_MINIMOS,
    }


def default_recursos_from_support(pontos_apoio: list[dict] | None) -> list[dict[str, Any]]:
    """Deriva inventário inicial a partir dos pontos de apoio (CNES/OSM)."""
    recursos: list[dict[str, Any]] = []
    leitos = 0
    abrigos = 0
    for p in pontos_apoio or []:
        tipo = str(p.get("tipo") or "").lower()
        if p.get("leitos_sus"):
            try:
                leitos += int(p["leitos_sus"] or 0)
            except (TypeError, ValueError):
                pass
        if any(k in tipo for k in ("escola", "ginasio", "abrigo", "ginásio")):
            abrigos += 1
            recursos.append(
                {
                    "tipo": "abrigo",
                    "nome": p.get("nome") or "Abrigo",
                    "quantidade": 1,
                    "capacidade_pessoas": p.get("capacidade") or 100,
                    "fonte": p.get("fonte") or "ponto_apoio",
                }
            )
    if leitos:
        recursos.insert(
            0,
            {
                "tipo": "leitos_sus",
                "nome": "Leitos SUS (CNES)",
                "quantidade": leitos,
                "capacidade_pessoas": leitos,
                "fonte": "CNES",
            },
        )
    if not recursos:
        recursos = [
            {
                "tipo": "kit_respiracao",
                "nome": "Kits de primeiros socorros (a confirmar)",
                "quantidade": 0,
                "capacidade_pessoas": None,
                "fonte": "pendente",
            },
            {
                "tipo": "viatura",
                "nome": "Viaturas Defesa Civil (a confirmar)",
                "quantidade": 0,
                "capacidade_pessoas": None,
                "fonte": "pendente",
            },
        ]
    if abrigos == 0:
        recursos.append(
            {
                "tipo": "abrigo",
                "nome": "Abrigos provisórios (definir no mapa)",
                "quantidade": 0,
                "capacidade_pessoas": None,
                "fonte": "pendente",
            }
        )
    return recursos
