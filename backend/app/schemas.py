from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime

# Base GeoJSON Structure for geometry transmission
class GeoJSONGeometry(BaseModel):
    type: str
    coordinates: Any

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]

# Municipio Schemas
class MunicipioBase(BaseModel):
    codigo_ibge: str
    nome: str
    uf: str
    populacao: int
    area_km2: float

class MunicipioCreate(MunicipioBase):
    pass

class MunicipioOut(MunicipioBase):
    model_config = ConfigDict(from_attributes=True)

    id: int

# Indicator Summary for Executive Dashboard
class ExecutiveIndicators(BaseModel):
    codigo_ibge: str
    nome: str
    uf: str
    populacao: int
    area_km2: float
    cobertura_vegetal_percent: float
    densidade_demografica: float
    historico_desastres_count: int
    alertas_ativos_count: int
    renda_media_setores: float
    renda_media_fonte: str
    danos_materiais_total: float
    populacao_fonte: Optional[str] = None
    populacao_qualidade: Optional[str] = None
    area_fonte: Optional[str] = None
    area_qualidade: Optional[str] = None
    pib_per_capita: Optional[float] = None
    pib_fonte: Optional[str] = None
    pib_qualidade: Optional[str] = None
    pib_total_mil_reais: Optional[float] = None
    pib_ano: Optional[int] = None
    pib_serie: Optional[list] = None
    nota_capag: Optional[str] = None
    capag_fonte: Optional[str] = None
    receita_corrente_liquida: Optional[float] = None
    despesa_pessoal_pct_rcl: Optional[float] = None
    divida_consolidada: Optional[float] = None
    divida_consolidada_pct_rcl: Optional[float] = None
    fiscal_exercicio: Optional[int] = None
    siconfi_ia_url: Optional[str] = None
    fiscal_fonte: Optional[str] = None
    fiscal_qualidade: Optional[str] = None
    selo_ibge: Optional[str] = None
    selo_fiscal: Optional[str] = None
    cobertura_qualidade: Optional[str] = None
    alertas_qualidade: Optional[str] = None
    desastres_qualidade: Optional[str] = None
    renda_qualidade: Optional[str] = None
    densidade_qualidade: Optional[str] = None
    idh: Optional[float] = None
    idh_ano: Optional[int] = None
    idh_fonte: Optional[str] = None
    idh_qualidade: Optional[str] = None
    atlas_uf_context: Optional[dict] = None
    score_sinidu: Optional[int] = None
    media_ivc: Optional[float] = None
    media_iri: Optional[float] = None
    media_adaptacao: Optional[float] = None
    score_confiabilidade: Optional[str] = None
    confiabilidade_geral: Optional[str] = None
    malha_fonte: Optional[str] = None


class IntegrationSourceStatus(BaseModel):
    source: str
    status: str
    records_count: int
    last_success_at: Optional[str] = None
    error_message: Optional[str] = None


class IntegrationStatusResponse(BaseModel):
    sources: List[IntegrationSourceStatus]


class IntegrationSyncResponse(BaseModel):
    summary: dict
    sources: List[IntegrationSourceStatus]

# Index Values for Bairros/Setores
class VulnerabilityIndexResult(BaseModel):
    id: int
    bairro_nome: str
    exposicao: float
    sensibilidade: float
    capacidade_adaptacao: float
    indice_vulnerabilidade: float # 0.0 to 1.0

class FloodRiskResult(BaseModel):
    id: int
    bairro_nome: str
    s2id_historico_score: float
    impermeabilizacao_score: float
    hidrografia_proximidade_score: float
    indice_risco_inundacao: float # 0.0 to 1.0

class ClimateIndicesResponse(BaseModel):
    vulnerabilidade: List[VulnerabilityIndexResult]
    inundacao: List[FloodRiskResult]

# Simulation Requests
class ImpermeabilizacaoSimRequest(BaseModel):
    taxa_impermeabilizacao_adicional: float = Field(..., description="Adicional de impermeabilização de 0 a 100%")
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")

class PerdaVegetacaoSimRequest(BaseModel):
    taxa_desmatamento: float = Field(..., description="Perda de cobertura vegetal de 0 a 100%")
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")

class IlhaCalorSimRequest(BaseModel):
    temperatura_pico_c: float = Field(default=34.0, description="Temperatura de pico prevista para a cidade (°C)")
    perda_vegetal_pct: float = Field(default=30.0, description="Perda adicional de vegetação (0–100%)")
    ganho_vegetal_pct: float = Field(default=0.0, description="Ganho de cobertura vegetal / arborização (0–60%)")
    impermeabilizacao_extra_pct: float = Field(default=15.0, description="Impermeabilização urbana adicional (0–50%)")
    sombreamento_pct: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Intervenção de sombreamento adicional (edifícios/toldos/dossel) — 17g.1f",
    )
    corredores_vento_pct: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Abertura de corredores de vento / espaço aberto — 17g.1f",
    )
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")

class ChuvaExtremaSimRequest(BaseModel):
    precipitacao_mm: Optional[float] = Field(
        default=None,
        ge=10,
        le=400,
        description="Precipitação estimada em mm. Opcional se periodo_retorno_anos for informado.",
    )
    periodo_retorno_anos: Optional[int] = Field(
        default=None,
        description="Período de retorno IDF (2/10/25/100 anos) — resolve lâmina via tabela municipal/UF",
    )
    duracao_min: Optional[int] = Field(
        default=60,
        ge=15,
        le=10080,
        description=(
            "Duração do evento de projeto (min) — usada na curva IDF (quando "
            "periodo_retorno_anos informado) e na física da simulação: mesma lâmina "
            "(mm) em janelas mais curtas gera intensidade (mm/h) maior e mancha mais "
            "abrupta; em janelas longas (até 10080 min = 7 dias) a chuva é mais "
            "distribuída/infiltrada. Aceita de 15 min a 7 dias."
        ),
    )
    nivel_mar_m: Optional[float] = Field(
        default=None,
        ge=0,
        le=3,
        description="Offset de nível do mar / storm surge (m) — municípios costeiros",
    )
    cenario_nivel_mar: Optional[str] = Field(
        default=None,
        description="Cenário IPCC/proxy: atual, ssp2_45_2050, ssp2_45_2100, ssp5_85_2050, ssp5_85_2100, storm_surge",
    )
    chuva_antecedente_mm: Optional[float] = Field(
        default=0,
        ge=0,
        le=500,
        description="Chuva antecedente (mm) para gatilho de deslizamento — 17g.1e",
    )
    aplicar_drenagem: Optional[bool] = Field(
        default=True,
        description="Aplicar sumidouro de microdrenagem (proxy SNIS) no balanço — 17g.1d",
    )
    drainage_capacity_mm_h: Optional[float] = Field(
        default=None,
        ge=5,
        le=60,
        description="Override manual da capacidade da rede (mm/h). Sem valor = proxy SNIS/densidade.",
    )
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")


class SolarRooftopRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    limit: int = Field(default=3500, ge=1, le=5000)


class GreenRoofMitigationRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    precipitacao_mm: float = Field(default=100.0, ge=10, le=400)
    telhado_verde_pct: float = Field(default=30.0, ge=0, le=100, description="% dos telhados convertidos em verdes")


class GreenInfraHeatRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    temperatura_pico_c: float = Field(default=36.0, ge=28, le=46)
    arborizacao_pct: float = Field(default=25.0, ge=0, le=60, description="% ganho de vegetação / parques")


class InterventionCompareRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    tipo: str = Field(default="telhado_verde", description="telhado_verde | infraverde_calor | solar")
    precipitacao_mm: float = Field(default=100.0, ge=10, le=400)
    telhado_verde_pct: float = Field(default=30.0, ge=0, le=100)
    temperatura_pico_c: float = Field(default=36.0, ge=28, le=46)
    arborizacao_pct: float = Field(default=25.0, ge=0, le=60)


class ShadowInsolationRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    hora_local: int = Field(default=14, ge=0, le=23, description="Hora local aproximada (BRT)")
    limit: int = Field(default=3500, ge=1, le=5000)


class ChuvaExtremaCompareRequest(BaseModel):
    baseline_mm: float = Field(default=80.0, description="Cenário de referência (mm)")
    scenario_mm: float = Field(..., description="Cenário alternativo (mm)")
    duracao_min: Optional[int] = Field(
        default=60,
        ge=15,
        le=10080,
        description="Duração do evento (min) aplicada a ambos os cenários — 15 min a 7 dias.",
    )
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")


class ClimateModuleRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    modo: str = Field(default="seca", description="seca | arbovirus")
    precip_72h_mm: Optional[float] = Field(default=None, ge=0, le=500)
    precip_esperada_72h_mm: Optional[float] = Field(default=25.0, ge=5, le=200)
    temperatura_media_c: Optional[float] = Field(default=None, ge=10, le=45)
    precip_7d_mm: Optional[float] = Field(default=None, ge=0, le=600)


class DrenagemSimRequest(BaseModel):
    deficit_drenagem_pct: float = Field(..., description="Déficit operacional de drenagem de 0 a 100%")
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")

# Simulation Outputs
class SimulationOutput(BaseModel):
    scenario_type: str
    input_value: float
    metric_impact: str
    impact_value: float
    affected_area_km2: float
    affected_population: int
    affected_bairros: List[str]
    geometry: GeoJSONFeatureCollection
    contours: Optional[GeoJSONFeatureCollection] = None
    flow_paths: Optional[GeoJSONFeatureCollection] = None
    simulation_meta: Optional[Dict[str, Any]] = None
    risk_context: Optional[List[Dict[str, Any]]] = None
    from_cache: Optional[bool] = None

class RainfallComparisonResponse(BaseModel):
    baseline: SimulationOutput
    scenario: SimulationOutput
    delta: Dict[str, Any]
    from_cache: Optional[bool] = None


class HeatLstCompareRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município")
    simulation: Dict[str, Any] = Field(..., description="Resultado da simulação de ilha de calor")


class BairroLstCompareRow(BaseModel):
    bairro: str
    lst_observada_c: Optional[float] = None
    temp_simulada_c: float
    delta_c: Optional[float] = None
    faixa_calor: Optional[str] = None


class HeatLstComparisonResponse(BaseModel):
    disponivel: bool
    municipio: str
    uf: str
    codigo_ibge: str
    lst_fonte: str
    lst_periodo: str
    lst_mediana_c: Optional[float] = None
    lst_max_c: Optional[float] = None
    lst_min_c: Optional[float] = None
    sim_temp_max_c: Optional[float] = None
    sim_temp_mediana_c: Optional[float] = None
    sim_delta_t_max_c: Optional[float] = None
    divergencia_mediana_c: Optional[float] = None
    amostras_validas: int = 0
    amostras_total: int = 0
    bairros: List[BairroLstCompareRow] = []
    narrativa: str
    limites_metodologicos: List[str] = []


class SimulationJobStartResponse(BaseModel):
    job_id: str
    async_mode: bool = True
    status: str = "queued"
    precipitacao_mm: Optional[float] = None
    idf: Optional[Dict[str, Any]] = None
    nivel_mar: Optional[Dict[str, Any]] = None

class SimulationAnalyzeRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    simulation: Dict[str, Any] = Field(..., description="Resultado de uma simulação (SimulationOutput)")
    use_ai: bool = Field(default=True, description="Tentar análise via LLM com fallback determinístico")
    ai_provider: Optional[str] = Field(default=None)
    ai_model: Optional[str] = Field(default=None)
    ai_api_key: Optional[str] = Field(default=None)


class SimulationExportRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None)
    simulation: Dict[str, Any] = Field(..., description="Resultado da simulação")
    comparison_delta: Optional[Dict[str, Any]] = Field(default=None, description="Delta de comparação pluvial")
    analysis: Optional[Dict[str, Any]] = Field(default=None, description="Análise interpretativa opcional")


class SimulationExportResponse(BaseModel):
    nome_arquivo: str
    tamanho_bytes: int
    download_url: str
    format: str

class BairroPrioritario(BaseModel):
    nome: str
    ivc: Optional[float] = None
    iri: Optional[float] = None
    rationale: Optional[str] = None

class SimulationAnalysisResponse(BaseModel):
    narrative_md: str
    key_findings: List[str]
    bairros_prioritarios: List[BairroPrioritario]
    suggested_actions: List[str]
    data_gaps: List[str]
    confidence: str
    ai_provider: str
    ai_model: Optional[str] = None
    disclaimer: str
    risk_context: Optional[List[Dict[str, Any]]] = None

class SimulationInterpretRequest(BaseModel):
    municipio_codigo: str
    tipo_simulacao: str = Field(..., description="chuva | asfalto | vegetacao | drenagem | calor")
    parametro_atual: float
    parametro_referencia: float = Field(default=80.0)
    resultado_simulacao: Dict[str, Any]
    resultado_referencia: Optional[Dict[str, Any]] = None
    comparacao_delta: Optional[Dict[str, Any]] = None
    lst_comparison: Optional[Dict[str, Any]] = None
    use_ai: bool = True
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None

class SimulationInterpretResponse(BaseModel):
    resumo_executivo: str
    areas_criticas: List[str]
    equipamentos_em_risco: List[str]
    comparacao_historica: str
    recomendacoes_imediatas: List[str]
    interpretacao_diferencial: Optional[str] = None
    disclaimer: str
    findings: List[str] = []
    metricas: Dict[str, Any] = {}
    ai_provider: str = "deterministic"
    ai_model: Optional[str] = None
    confidence: str = "media"
    from_cache: bool = False

class SlopeInterpretationResponse(BaseModel):
    codigo_ibge: str
    area_suscetivel_km2: float
    populacao_exposta: int
    bairros_encosta: List[str]
    nivel_suscetibilidade: str
    interpretacao_ia: str
    referencia_cobrade: str
    dem_source: Optional[str] = None
    precipitacao_mm: Optional[float] = None

class MitigationPlanRequest(BaseModel):
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")
    scenario_type: str = Field(default="ExtremeRainfall", description="Tipo de cenário simulado")
    input_value: Optional[float] = Field(default=None, description="Valor de entrada do cenário")
    precipitacao_mm: Optional[float] = Field(default=None, description="Precipitação estimada em milímetros")

class MitigationSource(BaseModel):
    titulo: str
    url: Optional[str] = None
    tipo: str
    status: str
    observacao: Optional[str] = None

class MitigationEvidence(BaseModel):
    titulo: str
    descricao: str
    fonte: str

class AnalogMunicipality(BaseModel):
    codigo_ibge: str
    nome: str
    uf: str
    coeficiente_similaridade: float
    fatores: Dict[str, float]

class PlanningConstraint(BaseModel):
    tipo: str
    descricao: str
    fonte: str

class MitigationAction(BaseModel):
    horizonte: str
    acao: str
    justificativa: str
    proporcionalidade: str

class MitigationPlanResponse(BaseModel):
    municipio: Dict[str, Any]
    evento: Dict[str, Any]
    severidade: str
    acoes_tecnicas_padrao: List[MitigationAction]
    experiencias_municipais: List[MitigationEvidence]
    municipios_analogos: List[AnalogMunicipality]
    casos_analogos: List[MitigationEvidence]
    diretrizes_plano_diretor: List[PlanningConstraint]
    restricoes_plano_diretor: List[PlanningConstraint]
    capacidade_investimento: Optional[Dict[str, Any]] = None
    fontes_consultadas: List[MitigationSource]
    lacunas: List[str]

# AI Assistant Schemas
class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    codigo_ibge: Optional[str] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None

class ContextualChatRequest(BaseModel):
    message: str
    municipio_codigo: str
    pagina_atual: str
    descricao_pagina: Optional[str] = ""
    dados_pagina: Dict[str, Any] = {}
    historico: List[ChatMessage] = []
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None
    ai_api_key: Optional[str] = None
    stream: bool = True

class AIProviderTestRequest(BaseModel):
    ai_provider: str
    ai_api_key: Optional[str] = None
    ai_model: Optional[str] = None

class AIProviderTestResponse(BaseModel):
    ok: bool
    message: str
    response_time_ms: int
    sample_response: Optional[str] = None

class AIProvidersStatusRequest(BaseModel):
    api_keys: Dict[str, str] = {}

class RagSource(BaseModel):
    source: str
    source_label: str
    chunk_idx: int
    content: str
    similarity: float


class MunicipalDataSource(BaseModel):
    id: str
    label: str
    snippet: str
    url: str = ""
    tipo: str = "OFICIAL"


class MunicipalAssistantContext(BaseModel):
    codigo_ibge: str
    municipio: Dict[str, str]
    headline: str
    score_sinidu: Optional[int] = None
    nota_capag: Optional[str] = None
    maturidade: Optional[str] = None
    maturidade_score: Optional[int] = None
    summary_text: str
    sources: List[MunicipalDataSource]
    suggested_questions: List[str]
    tem_diagnostico: bool = False
    tem_relatorio: bool = False
    georedus_url: Optional[str] = None
    georedus_indicadores: List[Dict[str, Any]] = []

class AIProviderOption(BaseModel):
    id: str
    label: str
    description: str
    available: bool
    is_local: bool
    requires_api_key: bool
    default_model: str
    models: List[str] = []
    privacy_note: str = ""

class AIProvidersResponse(BaseModel):
    default_provider: str
    providers: List[AIProviderOption]

class ChatResponse(BaseModel):
    response: str
    suggested_layer: Optional[str] = None # e.g. "calor", "inundacao", "vulnerabilidade"
    recommended_layers: Optional[List[str]] = None  # 17h.2c — cruzamento multi-camada
    crosswalk_rationale: Optional[str] = None
    coordinates: Optional[List[float]] = None # e.g. [lat, lng]
    zoom: Optional[int] = None
    source_url: Optional[str] = None
    rag_sources: List[RagSource] = []
    municipal_sources: List[MunicipalDataSource] = []
    suggested_questions: List[str] = []
    response_time_ms: Optional[int] = None
    ai_provider: Optional[str] = None
    ai_model: Optional[str] = None

# Success Case Schemas
class CasoSucessoBase(BaseModel):
    titulo: Optional[str] = None
    municipio_nome: Optional[str] = None
    municipio_uf: Optional[str] = None
    municipio: str
    uf: str
    populacao_aprox: Optional[int] = None
    regiao: Optional[str] = None
    tipo_intervencao: Optional[str] = None
    problema_original: Optional[str] = None
    solucao_implementada: Optional[str] = None
    resultado_mensuravel: Optional[str] = None
    problema: str
    solucao: str
    resultado: Optional[str] = None
    custo_estimado_reais: Optional[int] = None
    programa_financiador: Optional[str] = None
    ano_implementacao: Optional[int] = None
    fonte_referencia: Optional[str] = None
    tags: Optional[List[str]] = None
    imagem_url: Optional[str] = None


class CasoReferenciaOut(BaseModel):
    id: int
    titulo: Optional[str] = None
    municipio_nome: Optional[str] = None
    municipio_uf: Optional[str] = None
    referencia_texto: str
    similarity: Optional[float] = None


class CasoSucessoOut(CasoSucessoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    uuid: Optional[str] = None
    relevance_score: Optional[float] = None
    similarity: Optional[float] = None
    created_at: Optional[str] = None


class MunicipalReportResponse(BaseModel):
    id: int
    municipio_id: int
    codigo_ibge: str
    nome_arquivo: str
    tamanho_bytes: int
    status: str
    sha256_hash: str | None = None
    gerado_em: datetime
    download_url: str
    sei_export_url: str


class MunicipalReportHistoryItem(BaseModel):
    id: int
    municipio_id: int
    codigo_ibge: str
    nome_arquivo: str
    tamanho_bytes: int
    status: str
    sha256_hash: str | None = None
    gerado_em: datetime
    download_url: str
    sei_export_url: str


class SeiExportPackage(BaseModel):
    documento_tipo: str
    sistema_origem: str
    versao_sistema: str
    municipio: dict
    relatorio: dict
    integridade: dict
    urls: dict
    observacao: str


class FloodRiskPredictionRequest(BaseModel):
    municipio_id: str = Field(..., description="Slug do município (ex: recife) ou código IBGE")
    precip_24h: float = Field(..., ge=0, le=500)
    precip_48h: float = Field(..., ge=0, le=800)
    precip_72h: float = Field(..., ge=0, le=1000)
    precip_7d: Optional[float] = Field(
        default=None,
        ge=0,
        le=2000,
        description="Acumulado 7 dias (antecedente). Se omitido, usa precip_72h como piso — sem proxy.",
    )
    mes_do_ano: Optional[int] = Field(default=None, ge=1, le=12)


class CriticalNeighborhood(BaseModel):
    bairro_id: int
    bairro_nome: str
    risk_probability: float
    iri: float
    impermeabilizacao_pct: float


class FloodFeatureImportance(BaseModel):
    feature: str
    importance: float


class FloodDomainContribution(BaseModel):
    id: str
    label: str
    importance_share: float
    contribution: float
    contribution_pct: float
    importance_pct: float


class FloodExplanation(BaseModel):
    disponivel: bool
    method: str
    domains: list[FloodDomainContribution] = []
    top_features: list[dict] = []
    narrativa: str | None = None
    nota: str | None = None


class FloodImpactMeasure(BaseModel):
    id: Optional[str] = None
    titulo: Optional[str] = None
    custo: Optional[str] = None
    horizonte: Optional[str] = None
    prioridade: Optional[str] = None
    orgao: Optional[str] = None
    motivo: Optional[str] = None


class FloodImpactBairro(BaseModel):
    bairro_id: int
    bairro_nome: str
    risk_probability: float
    populacao_bairro: Optional[int] = None
    populacao_exposta_estimada: Optional[int] = None
    suscetibilidade_local: Optional[float] = None


class FloodImpact(BaseModel):
    disponivel: bool
    protocol: Optional[str] = None
    nivel_operacional: Optional[str] = None
    n_bairros_prioritarios: Optional[int] = None
    bairros_prioritarios: List[FloodImpactBairro] = []
    populacao_municipio: Optional[int] = None
    populacao_exposta_estimada: Optional[int] = None
    pct_populacao_exposta: Optional[float] = None
    porte: Optional[str] = None
    capag_nota: Optional[str] = None
    medidas_cabiveis: List[FloodImpactMeasure] = []
    narrativa: Optional[str] = None
    nota: Optional[str] = None
    reason: Optional[str] = None



class FloodHorizonForecast(BaseModel):
    horizon: str
    horizon_d: int
    risk_probability: float
    ci_low: Optional[float] = None
    ci_high: Optional[float] = None
    precip_24h_mm: Optional[float] = None
    uncertainty_method: Optional[str] = None


class FloodUncertainty(BaseModel):
    ci_low: float
    ci_high: float
    std: Optional[float] = None
    method: Optional[str] = None
    confidence_level: Optional[float] = None
    nota: Optional[str] = None


class FloodRiskPredictionResponse(BaseModel):
    codigo_ibge: str
    municipio_slug: str
    risk_probability: float
    risk_level: str
    confidence: str
    threshold_mm_24h: float
    mm_acima_limiar: Optional[float] = None
    top_features: Optional[List[FloodFeatureImportance]] = None
    explanation: Optional[FloodExplanation] = None
    impact: Optional[FloodImpact] = None
    horizons: Optional[List[FloodHorizonForecast]] = None
    uncertainty: Optional[FloodUncertainty] = None
    critical_neighborhoods: List[CriticalNeighborhood]
    flood_geojson: dict
    model_version: str
    model_kind: Optional[str] = None
    data_quality: str
    score_kind: Optional[str] = None
    production_ready: Optional[bool] = None
    features_used: Optional[dict] = None
    model_auc_roc: Optional[float] = None
    disclaimer: str


# 21c.4 — Canal de registro em campo (Defesa Civil)
class EventoAlagamentoCampoCreate(BaseModel):
    codigo_ibge: str
    tipo: str = Field(default="Alagamento Urbano", description="Inundação | Alagamento Urbano | Enxurrada")
    inicio_em: datetime
    fim_em: Optional[datetime] = None
    severidade: Optional[str] = Field(default="media", description="baixa | media | alta | critica")
    fenomeno: Optional[str] = Field(default="pluvial", description="pluvial | fluvial | misto")
    populacao_afetada: Optional[int] = None
    precip_acumulada_mm: Optional[float] = None
    referencia: Optional[str] = None
    lat: Optional[float] = Field(default=None, description="Usado quando geojson não é enviado")
    lng: Optional[float] = None
    geojson: Optional[Dict[str, Any]] = Field(default=None, description="Feature/geometria GeoJSON do ponto/polígono")


class EventoAlagamentoObservadoOut(BaseModel):
    id: int
    codigo_ibge: str
    tipo: str
    inicio_em: Optional[str] = None
    fim_em: Optional[str] = None
    severidade: Optional[str] = None
    fenomeno: Optional[str] = None
    fonte: str
    data_quality: str
    geometry: Optional[dict] = None
    referencia: Optional[str] = None


class EventosObservadosListResponse(BaseModel):
    codigo_ibge: str
    total: int
    eventos: List[Dict[str, Any]]