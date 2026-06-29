"""Templates de ações por nível COBRADE para planos de contingência."""

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


def default_acoes_por_nivel(cenario_tipo: str) -> dict[str, list[str]]:
    base = COBRADE_ACTIONS.get(cenario_tipo, COBRADE_ACTIONS["MULTIPLO"])
    return {nivel: list(acoes) for nivel, acoes in base.items()}
