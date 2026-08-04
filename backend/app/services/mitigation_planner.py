from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import requests
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Municipio, SetorCensitario, CoberturaVegetalMapBiomas, HistoricoDesastreS2ID
from app.models import MunicipioFiscal
from app.schemas import (
    AnalogMunicipality,
    MitigationAction,
    MitigationEvidence,
    MitigationSource,
    PlanningConstraint,
)
from app.seed_demo_municipalities import RENDA_REFERENCIA_MENSAL
from app.services.analytical_engine import AnalyticalEngine
from app.services.heat_simulator import run_heat_island_simulation
from app.data_connectors.mapbiomas_collector import vegetation_coverage_percent

UF_REGION = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste", "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

CLIMATE_PROFILE = {
    "2611606": "metropole_costeira_umida",
    "2927408": "metropole_costeira_umida",
    "2507507": "capital_costeira_tropical",
    "4314902": "metropole_sul_inundacao",
    "1400233": "amazonia_interior",
    "5201108": "metropole_cerrado_logistica",
    "4113700": "metropole_interior_parana",
}

PLAN_DIRECTOR_SOURCES = {
    "2611606": [
        {
            "titulo": "Plano Diretor do Recife - Lei Complementar nº 02/2021",
            "url": "https://licenciamentounificado.recife.pe.gov.br/lei-complementar-no-02-2021",
        }
    ],
    "2603603": [
        {
            "titulo": "Plano Diretor Participativo de Camutanga — legislação urbanística municipal",
            "url": "https://www.camutanga.pe.gov.br/",
        }
    ],
    "2607604": [
        {
            "titulo": "Plano Diretor de Ilha de Itamaracá — legislação urbanística municipal",
            "url": "https://www.itamaraca.pe.gov.br/",
        }
    ],
    "2927408": [
        {
            "titulo": "PDDU Salvador - Lei nº 9.069/2016",
            "url": "https://sedur.salvador.ba.gov.br/pddu-2016/18-legislacao/65-leis-pddu",
        }
    ],
    "4314902": [
        {
            "titulo": "PDDUA Porto Alegre - legislação municipal",
            "url": "https://legislacao.portoalegre.rs.gov.br/norma/36841",
        }
    ],
    "2507507": [
        {
            "titulo": "Plano Diretor Municipal de João Pessoa - legislação urbanística vigente",
            "url": "https://planodiretor.joaopessoa.pb.gov.br/legislacaovigente/",
        }
    ],
    "1400233": [
        {
            "titulo": "Portal da Transparência de Caroebe - leis municipais",
            "url": "https://transparencia.caroebe.rr.gov.br/leis-municipais/",
        }
    ],
    "5201108": [
        {
            "titulo": "Plano Diretor de Anápolis - legislação municipal",
            "url": "https://www.anapolis.go.gov.br/urbanismo/plano-diretor",
        }
    ],
    "4113700": [
        {
            "titulo": "Plano Diretor de Londrina - legislação municipal",
            "url": "https://www.londrina.pr.gov.br/plano-diretor",
        }
    ],
}

RAIN_RELATED_TYPES = {"Inundação", "Alagamento Urbano", "Deslizamento"}


class MitigationPlanner:
    @staticmethod
    def build_rainfall_plan(db: Session, municipio: Municipio, precipitacao_mm: float) -> Dict[str, Any]:
        return MitigationPlanner.build_plan(db, municipio, "ExtremeRainfall", precipitacao_mm)

    @staticmethod
    def build_plan(db: Session, municipio: Municipio, scenario_type: str, input_value: float) -> Dict[str, Any]:
        simulation = MitigationPlanner._run_simulation(db, municipio, scenario_type, input_value)
        severity = MitigationPlanner._severity(municipio, simulation, scenario_type, input_value)
        sources, directives, restrictions, source_lacunas = MitigationPlanner._consult_plan_director(municipio)
        own_events = MitigationPlanner._own_municipal_evidence(db, municipio, scenario_type)
        analogs = MitigationPlanner._analog_municipalities(db, municipio)
        cases, case_lacuna = MitigationPlanner._analog_cases_message(analogs)

        lacunas = list(source_lacunas)
        if not own_events:
            lacunas.append("Não há registros S2ID compatíveis no banco local para experiências próprias deste tipo de evento.")
        if not analogs:
            lacunas.append("Não foram encontrados municípios análogos acima do limiar mínimo de similaridade com os dados disponíveis.")
        if case_lacuna:
            lacunas.append(case_lacuna)

        capacidade = MitigationPlanner._investment_capacity(db, municipio, simulation, severity)
        slope_section = MitigationPlanner._slope_landslide_section(db, municipio)

        plan = {
            "municipio": {
                "codigo_ibge": municipio.codigo_ibge,
                "nome": municipio.nome,
                "uf": municipio.uf,
                "populacao": municipio.populacao,
                "area_km2": float(municipio.area_km2),
            },
            "evento": {
                "tipo": MitigationPlanner._event_label(scenario_type),
                "precipitacao_mm": input_value if scenario_type == "ExtremeRainfall" else 0,
                "valor_entrada": input_value,
                "unidade": MitigationPlanner._event_unit(scenario_type),
                "area_afetada_km2": simulation["affected_area_km2"],
                "populacao_afetada": simulation["affected_population"],
                "bairros_atingidos": simulation["affected_bairros"],
            },
            "severidade": severity,
            "acoes_tecnicas_padrao": MitigationPlanner._standard_actions(severity, simulation, scenario_type),
            "experiencias_municipais": own_events,
            "municipios_analogos": analogs,
            "casos_analogos": cases,
            "diretrizes_plano_diretor": directives,
            "restricoes_plano_diretor": restrictions,
            "capacidade_investimento": capacidade,
            "fontes_consultadas": sources,
            "lacunas": lacunas,
        }
        if slope_section:
            plan["risco_deslizamento"] = slope_section
            plan["acoes_tecnicas_padrao"] = list(plan["acoes_tecnicas_padrao"]) + slope_section.get("acoes", [])
        return plan

    @staticmethod
    def _slope_landslide_section(db: Session, municipio: Municipio) -> Dict[str, Any] | None:
        try:
            from app.services.dem_processor import slope_analysis

            analysis = slope_analysis(db, municipio.codigo_ibge)
        except Exception:
            return None
        if analysis.get("suscetibilidade_alta_pct", 0) <= 10:
            return None
        return {
            "suscetibilidade_alta_pct": analysis["suscetibilidade_alta_pct"],
            "area_critica_ha": analysis["area_critica_ha"],
            "populacao_exposta": analysis["populacao_exposta"],
            "bairros_criticos": analysis.get("bairros_criticos", [])[:5],
            "dem_source": analysis.get("dem_source"),
            "acoes": [
                MitigationAction(
                    titulo="Mapeamento geotécnico de encostas críticas",
                    descricao=(
                        f"Área com declividade >30°: {analysis['area_critica_ha']:.0f} ha "
                        f"({analysis['suscetibilidade_alta_pct']:.1f}% do município). "
                        "Priorizar estabilização, drenagem superficial e monitoramento com alertas."
                    ),
                    prioridade="Alta",
                    prazo="0-6 meses",
                    orgao="Defesa Civil / Secretaria de Obras",
                ),
                MitigationAction(
                    titulo="Plano de contingência para deslizamentos",
                    descricao=(
                        f"População estimada em zona de encosta crítica: "
                        f"{analysis['populacao_exposta']:,} hab. Definir rotas de evacuação 3D "
                        "e pontos seguros conforme análise SRTM."
                    ).replace(",", "."),
                    prioridade="Alta",
                    prazo="Imediato",
                    orgao="Defesa Civil",
                ),
            ],
        }

    @staticmethod
    def _investment_capacity(db: Session, municipio: Municipio, simulation: Dict[str, Any], severity: str) -> Dict[str, Any]:
        fiscal = db.query(MunicipioFiscal).filter(MunicipioFiscal.codigo_ibge == municipio.codigo_ibge).first()
        vulnerabilities = AnalyticalEngine.calculate_climate_vulnerability(db, municipio.id)
        avg_ivc = 0.0
        if vulnerabilities:
            avg_ivc = sum(item["indice_vulnerabilidade"] for item in vulnerabilities) / len(vulnerabilities)

        nota_capag = fiscal.nota_capag if fiscal and fiscal.nota_capag else None
        pessoal_pct = float(fiscal.despesa_pessoal_pct_rcl) if fiscal and fiscal.despesa_pessoal_pct_rcl is not None else None
        divida_pct = None
        if fiscal and fiscal.receita_corrente_liquida and fiscal.divida_consolidada:
            divida_pct = round((float(fiscal.divida_consolidada) / float(fiscal.receita_corrente_liquida)) * 100, 2)

        alertas = []
        if nota_capag in {"C", "D"} and avg_ivc >= 0.55:
            alertas.append(
                "ATENÇÃO: capacidade fiscal limitada para resposta a desastres diante de alta vulnerabilidade climática."
            )
        if pessoal_pct and pessoal_pct > 60:
            alertas.append("Despesa com pessoal acima do limite de referência LRF (60% da RCL).")
        if divida_pct and divida_pct > 120:
            alertas.append("Dívida consolidada acima do limite de referência LRF (120% da RCL).")

        funding_sources = []
        if severity in {"Alta", "Crítica"} or avg_ivc >= 0.6:
            funding_sources.extend([
                "FCP — Fundo de Calamidade Pública (estados/municípios em situação de emergência ou calamidade)",
                "Fundo Clima — projetos de mitigação e adaptação",
                "PAC Seleções / PAC Cidades — obras urbanas estruturantes",
            ])
        if nota_capag in {"A", "B"}:
            funding_sources.append("Operações de crédito com garantia da União (CAPAG compatível)")
        if not funding_sources:
            funding_sources.append(
                "Revisar elegibilidade federal após atualização da nota CAPAG e do grau de vulnerabilidade."
            )

        return {
            "nota_capag": nota_capag,
            "media_ivc": round(avg_ivc, 3),
            "despesa_pessoal_pct_rcl": pessoal_pct,
            "divida_consolidada_pct_rcl": divida_pct,
            "alertas": alertas,
            "fontes_financiamento_sugeridas": funding_sources,
            "observacao": (
                "Leitura cruzada entre CAPAG, limites LRF e vulnerabilidade climática do município. "
                "Não substitui parecer jurídico-contábil."
            ),
        }

    @staticmethod
    def _run_simulation(db: Session, municipio: Municipio, scenario_type: str, input_value: float) -> Dict[str, Any]:
        if scenario_type == "ExtremeRainfall":
            return AnalyticalEngine.run_chuva_extrema_simulation(db, municipio.id, input_value)
        if scenario_type == "Waterproofing":
            return AnalyticalEngine.run_impermeabilizacao_simulation(db, municipio.id, input_value)
        if scenario_type == "VegetationLoss":
            result = run_heat_island_simulation(
                db,
                municipio.id,
                perda_vegetal_pct=input_value,
                impermeabilizacao_extra_pct=0.0,
            )
            result["scenario_type"] = "VegetationLoss"
            result["input_value"] = input_value
            return result
        if scenario_type == "HeatIsland":
            return run_heat_island_simulation(
                db,
                municipio.id,
                temperatura_pico_c=input_value,
                perda_vegetal_pct=30.0,
                impermeabilizacao_extra_pct=15.0,
            )
        if scenario_type == "DrainageDeficit":
            return AnalyticalEngine.run_drenagem_simulation(db, municipio.id, input_value)
        raise ValueError(f"Unsupported scenario_type: {scenario_type}")

    @staticmethod
    def _event_label(scenario_type: str) -> str:
        return {
            "ExtremeRainfall": "Chuva extrema",
            "Waterproofing": "Aumento de impermeabilização",
            "VegetationLoss": "Perda de cobertura vegetal",
            "HeatIsland": "Ilha de calor urbana",
            "DrainageDeficit": "Déficit de drenagem",
        }.get(scenario_type, scenario_type)

    @staticmethod
    def _event_unit(scenario_type: str) -> str:
        return {
            "ExtremeRainfall": "mm",
            "Waterproofing": "% de área impermeável adicional",
            "VegetationLoss": "% de perda de cobertura verde",
            "HeatIsland": "°C de pico previsto",
            "DrainageDeficit": "% de déficit operacional de drenagem",
        }.get(scenario_type, "")

    @staticmethod
    def _severity(municipio: Municipio, simulation: Dict[str, Any], scenario_type: str, input_value: float) -> str:
        area_ratio = simulation["affected_area_km2"] / float(municipio.area_km2 or 1)
        pop_ratio = simulation["affected_population"] / float(municipio.populacao or 1)
        value_threshold = {
            "ExtremeRainfall": (80, 120, 180),
            "Waterproofing": (25, 50, 80),
            "VegetationLoss": (25, 50, 75),
            "HeatIsland": (34, 38, 42),
            "DrainageDeficit": (30, 60, 85),
        }.get(scenario_type, (25, 50, 80))
        moderate, high, critical = value_threshold
        if input_value >= critical or area_ratio >= 0.15 or pop_ratio >= 0.08:
            return "Crítica"
        if input_value >= high or area_ratio >= 0.07 or pop_ratio >= 0.03:
            return "Alta"
        if input_value >= moderate or area_ratio >= 0.03 or pop_ratio >= 0.01:
            return "Moderada"
        return "Baixa"

    @staticmethod
    def _standard_actions(severity: str, simulation: Dict[str, Any], scenario_type: str) -> List[MitigationAction]:
        affected_count = len(simulation.get("affected_bairros", []))
        proportionality = f"Dimensionar para {simulation['affected_area_km2']} km² e {affected_count} bairro(s) atingido(s)."
        if scenario_type == "Waterproofing":
            actions = [
                MitigationAction(
                    horizonte="Resposta de planejamento",
                    acao="Suspender novas impermeabilizações nas áreas atingidas até checagem de drenagem e compensação ambiental.",
                    justificativa="Medida técnica padrão para evitar aumento de escoamento superficial em áreas já sensíveis.",
                    proporcionalidade=proportionality,
                ),
                MitigationAction(
                    horizonte="Curto prazo",
                    acao="Priorizar pavimento permeável, jardins de chuva, valas de infiltração e reservatórios de detenção nos bairros afetados.",
                    justificativa="A simulação indica ampliação da mancha de inundação associada à perda de infiltração.",
                    proporcionalidade=proportionality,
                ),
            ]
            if severity in {"Alta", "Crítica"}:
                actions.append(MitigationAction(
                    horizonte="Estrutural",
                    acao="Criar regra de compensação hidrológica para novos empreendimentos e carteira de retrofit de áreas impermeáveis.",
                    justificativa="Cenários de alta abrangência exigem redução permanente do pico de vazão urbana.",
                    proporcionalidade=f"Priorizar: {', '.join(simulation.get('affected_bairros', [])[:6]) or 'não informado'}.",
                ))
            return actions

        if scenario_type in {"VegetationLoss", "HeatIsland"}:
            actions = [
                MitigationAction(
                    horizonte="Resposta de adaptação",
                    acao="Proteger remanescentes verdes e suspender supressões não essenciais nas áreas de maior exposição térmica.",
                    justificativa="Medida técnica padrão para evitar intensificação de ilha de calor e perda de serviços ecossistêmicos.",
                    proporcionalidade=proportionality,
                ),
                MitigationAction(
                    horizonte="Curto prazo",
                    acao="Implantar arborização de sombreamento, corredores verdes e revegetação de equipamentos públicos nos bairros afetados.",
                    justificativa="A simulação estima aumento térmico proporcional à perda de cobertura vegetal.",
                    proporcionalidade=f"Temperatura projetada: +{simulation['impact_value']}°C nas áreas expostas.",
                ),
            ]
            if severity in {"Alta", "Crítica"}:
                actions.append(MitigationAction(
                    horizonte="Estrutural",
                    acao="Definir meta municipal de cobertura arbórea mínima por bairro e priorizar ilhas de calor no orçamento climático.",
                    justificativa="A perda vegetal ampla exige política permanente de recuperação e manutenção da cobertura verde.",
                    proporcionalidade=f"Priorizar: {', '.join(simulation.get('affected_bairros', [])[:6]) or 'não informado'}.",
                ))
            return actions

        if scenario_type == "DrainageDeficit":
            actions = [
                MitigationAction(
                    horizonte="Resposta imediata",
                    acao="Inspecionar bocas de lobo, galerias e pontos de extravasamento nos bairros com maior pressão de drenagem.",
                    justificativa="Medida técnica padrão para reduzir falhas operacionais antes e durante eventos chuvosos.",
                    proporcionalidade=proportionality,
                ),
                MitigationAction(
                    horizonte="Curto prazo",
                    acao="Executar desobstrução programada, limpeza de canais e correção de pontos baixos com alagamento recorrente.",
                    justificativa="A simulação combina risco de inundação, área urbana e déficit informado da rede.",
                    proporcionalidade=proportionality,
                ),
            ]
            if severity in {"Alta", "Crítica"}:
                actions.append(MitigationAction(
                    horizonte="Estrutural",
                    acao="Priorizar ampliação de microdrenagem, reservação temporária e soluções baseadas na natureza nas bacias críticas.",
                    justificativa="Déficits altos exigem capacidade adicional e retenção distribuída.",
                    proporcionalidade=f"Priorizar: {', '.join(simulation.get('affected_bairros', [])[:6]) or 'não informado'}.",
                ))
            return actions

        actions = [
            MitigationAction(
                horizonte="Resposta imediata",
                acao="Ativar protocolo de monitoramento, alerta comunitário e vistoria em pontos críticos.",
                justificativa="Medida técnica padrão para reduzir exposição durante evento pluvial intenso.",
                proporcionalidade=proportionality,
            ),
            MitigationAction(
                horizonte="Curto prazo",
                acao="Priorizar limpeza de microdrenagem, inspeção de canais e rotas de acesso a equipamentos essenciais nos bairros atingidos.",
                justificativa="A abrangência simulada indica necessidade de reduzir obstruções e manter acessibilidade operacional.",
                proporcionalidade=proportionality,
            ),
        ]
        if severity in {"Alta", "Crítica"}:
            actions.append(
                MitigationAction(
                    horizonte="Estrutural",
                    acao="Preparar carteira de obras de drenagem, contenção localizada e soluções baseadas na natureza nas áreas recorrentes.",
                    justificativa="Eventos de maior abrangência exigem ação permanente, não apenas resposta emergencial.",
                    proporcionalidade=f"Priorizar bairros com interseção na mancha simulada: {', '.join(simulation.get('affected_bairros', [])[:6]) or 'não informado'}.",
                )
            )
        return actions

    @staticmethod
    def _own_municipal_evidence(db: Session, municipio: Municipio, scenario_type: str) -> List[MitigationEvidence]:
        if scenario_type in {"VegetationLoss", "HeatIsland"}:
            return []
        rows = db.query(HistoricoDesastreS2ID).filter(
            HistoricoDesastreS2ID.municipio_id == municipio.id,
            HistoricoDesastreS2ID.tipo_desastre.in_(RAIN_RELATED_TYPES),
        ).order_by(HistoricoDesastreS2ID.data_ocorrencia.desc()).limit(5).all()
        return [
            MitigationEvidence(
                titulo=f"{row.tipo_desastre} em {row.data_ocorrencia.strftime('%d/%m/%Y')}",
                descricao=(
                    f"Registro histórico com {row.populacao_afetada} pessoa(s) afetada(s) "
                    f"e danos materiais informados de R$ {float(row.danos_materiais):,.2f}."
                ),
                fonte="Registro S2ID carregado no banco local do Sinidu+Clima.",
            )
            for row in rows
        ]

    @staticmethod
    def _municipality_metrics(db: Session, municipio: Municipio) -> Dict[str, float | str]:
        avg_income = db.query(func.avg(SetorCensitario.renda_media)).filter(SetorCensitario.municipio_id == municipio.id).scalar()
        income = float(RENDA_REFERENCIA_MENSAL.get(municipio.codigo_ibge, float(avg_income or 0.0)))
        veg_percent, _ = vegetation_coverage_percent(db, municipio)
        disasters = db.query(HistoricoDesastreS2ID).filter(HistoricoDesastreS2ID.municipio_id == municipio.id).count()
        damages = db.query(func.sum(HistoricoDesastreS2ID.danos_materiais)).filter(HistoricoDesastreS2ID.municipio_id == municipio.id).scalar()
        return {
            "populacao": float(municipio.populacao or 0),
            "densidade": float(municipio.populacao or 0) / float(municipio.area_km2 or 1),
            "renda": income,
            "cobertura_vegetal": veg_percent,
            "historico_desastres": float(disasters),
            "danos": math.log1p(float(damages or 0.0)),
            "regiao": UF_REGION.get(municipio.uf, "Indefinida"),
            "clima": CLIMATE_PROFILE.get(municipio.codigo_ibge, "indefinido"),
        }

    @staticmethod
    def _analog_municipalities(db: Session, selected: Municipio) -> List[AnalogMunicipality]:
        municipalities = db.query(Municipio).all()
        metrics_by_code = {m.codigo_ibge: MitigationPlanner._municipality_metrics(db, m) for m in municipalities}
        numeric_keys = ["populacao", "densidade", "renda", "cobertura_vegetal", "historico_desastres", "danos"]
        ranges: Dict[str, Tuple[float, float]] = {}
        for key in numeric_keys:
            values = [float(metrics[key]) for metrics in metrics_by_code.values()]
            ranges[key] = (min(values), max(values))

        base = metrics_by_code[selected.codigo_ibge]
        weights = {
            "densidade": 0.20,
            "renda": 0.15,
            "populacao": 0.15,
            "cobertura_vegetal": 0.15,
            "historico_desastres": 0.08,
            "danos": 0.07,
            "regiao": 0.10,
            "clima": 0.10,
        }
        analogs: List[AnalogMunicipality] = []
        for muni in municipalities:
            if muni.codigo_ibge == selected.codigo_ibge:
                continue
            current = metrics_by_code[muni.codigo_ibge]
            factors: Dict[str, float] = {}
            for key in numeric_keys:
                lo, hi = ranges[key]
                span = hi - lo
                score = 1.0 if span == 0 else 1.0 - min(abs(float(base[key]) - float(current[key])) / span, 1.0)
                factors[key] = round(score, 2)
            factors["regiao"] = 1.0 if base["regiao"] == current["regiao"] else 0.0
            factors["clima"] = 1.0 if base["clima"] == current["clima"] else 0.0
            coefficient = sum(factors[key] * weight for key, weight in weights.items())
            if coefficient >= 0.65:
                analogs.append(
                    AnalogMunicipality(
                        codigo_ibge=muni.codigo_ibge,
                        nome=muni.nome,
                        uf=muni.uf,
                        coeficiente_similaridade=round(coefficient, 2),
                        fatores=factors,
                    )
                )
        analogs.sort(key=lambda item: item.coeficiente_similaridade, reverse=True)
        return analogs[:3]

    @staticmethod
    def _analog_cases_message(analogs: List[AnalogMunicipality]) -> Tuple[List[MitigationEvidence], str | None]:
        if not analogs:
            return [], "Não foram encontrados municípios nem casos análogos com evidência oficial suficiente para este cenário."
        return [], "Não foram encontrados casos análogos com solução e resultado verificáveis por fonte oficial nesta versão do banco."

    @staticmethod
    def _consult_plan_director(municipio: Municipio) -> Tuple[List[MitigationSource], List[PlanningConstraint], List[PlanningConstraint], List[str]]:
        sources: List[MitigationSource] = []
        directives: List[PlanningConstraint] = []
        restrictions: List[PlanningConstraint] = []
        lacunas: List[str] = []
        catalog = PLAN_DIRECTOR_SOURCES.get(municipio.codigo_ibge, [])
        if not catalog:
            lacunas.append("Não há fonte oficial cadastrada para consulta automática do Plano Diretor deste município.")
            return sources, directives, restrictions, lacunas

        for item in catalog:
            status, text_or_error = MitigationPlanner._fetch_official_text(item["url"])
            sources.append(
                MitigationSource(
                    titulo=item["titulo"],
                    url=item["url"],
                    tipo="Plano Diretor / legislação urbanística oficial",
                    status=status,
                    observacao=text_or_error[:220] if status != "consultada" else None,
                )
            )
            if status != "consultada":
                continue

            text = text_or_error.lower()
            if any(term in text for term in ["plano diretor", "pddu", "pddua"]):
                directives.append(
                    PlanningConstraint(
                        tipo="diretriz",
                        descricao="A intervenção deve ser compatibilizada com o Plano Diretor e a legislação urbanística oficial consultada.",
                        fonte=item["titulo"],
                    )
                )
            if any(term in text for term in ["zoneamento", "uso e ocupação do solo", "uso do solo"]):
                restrictions.append(
                    PlanningConstraint(
                        tipo="restricao",
                        descricao="Obras e mudanças permanentes de uso do solo dependem de verificação prévia do zoneamento e dos parâmetros urbanísticos aplicáveis.",
                        fonte=item["titulo"],
                    )
                )
            if any(term in text for term in ["zeis", "interesse social"]):
                restrictions.append(
                    PlanningConstraint(
                        tipo="restricao",
                        descricao="Intervenções em áreas de interesse social devem preservar garantias urbanísticas e habitacionais previstas na legislação local.",
                        fonte=item["titulo"],
                    )
                )

        if not directives and not restrictions:
            lacunas.append("As fontes oficiais do Plano Diretor foram localizadas, mas não houve texto legível suficiente para extrair diretrizes ou restrições específicas.")
        return sources, directives, restrictions, lacunas

    @staticmethod
    def _fetch_official_text(url: str) -> Tuple[str, str]:
        try:
            response = requests.get(url, timeout=4, headers={"User-Agent": "SiniduClima/1.0"})
            response.raise_for_status()
        except Exception as exc:
            return "indisponivel", f"Falha ao consultar fonte oficial: {exc}"

        content_type = response.headers.get("content-type", "").lower()
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            return "fonte_pdf_nao_extraida", "Fonte oficial em PDF localizada, mas não extraída automaticamente nesta versão."
        text = response.text
        if len(text.strip()) < 200:
            return "sem_texto_legivel", "Fonte oficial retornou pouco texto para análise automática."
        return "consultada", text
