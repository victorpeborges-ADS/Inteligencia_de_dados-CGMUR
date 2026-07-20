from pydantic import BaseModel, Field
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
    id: int
    
    class Config:
        from_attributes = True

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
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")

class ChuvaExtremaSimRequest(BaseModel):
    precipitacao_mm: float = Field(..., description="Precipitação estimada em milímetros (e.g. 50 a 200)")
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")

class ChuvaExtremaCompareRequest(BaseModel):
    baseline_mm: float = Field(default=80.0, description="Cenário de referência (mm)")
    scenario_mm: float = Field(..., description="Cenário alternativo (mm)")
    codigo_ibge: Optional[str] = Field(default=None, description="Código IBGE do município selecionado")

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
    id: int
    uuid: Optional[str] = None
    relevance_score: Optional[float] = None
    similarity: Optional[float] = None
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


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


class FloodRiskPredictionResponse(BaseModel):
    codigo_ibge: str
    municipio_slug: str
    risk_probability: float
    risk_level: str
    confidence: str
    threshold_mm_24h: float
    mm_acima_limiar: Optional[float] = None
    top_features: Optional[List[FloodFeatureImportance]] = None
    critical_neighborhoods: List[CriticalNeighborhood]
    flood_geojson: dict
    model_version: str
    model_kind: Optional[str] = None
    data_quality: str
    model_auc_roc: Optional[float] = None
    disclaimer: str
