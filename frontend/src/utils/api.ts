/** Base da API — em homolog/proxy (HTTPS :443) usa same-origin; em dev :3000 aponta para :8000. */
export function getApiBaseUrl(): string {
  const env = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '');
  if (typeof window === 'undefined') {
    return env || 'http://localhost:8000';
  }
  // Dev direto no Next (:3000) → backend em :8000, ou proxy TLS se NEXT_PUBLIC_API_URL apontar para ele
  if (window.location.port === '3000') {
    if (env && env.startsWith('https://')) return env;
    return env || 'http://localhost:8000';
  }
  // Proxy nginx (HTTPS/HTTP na borda) — evita mixed content http://localhost:8000
  if (env && !env.includes(':8000')) {
    return env;
  }
  return window.location.origin;
}

export function getWsBaseUrl(): string {
  const api = getApiBaseUrl();
  return api.replace(/^http/, 'ws');
}

const TOKEN_KEY = 'sinidu_token';
export const AUTH_REQUIRED_EVENT = 'sinidu:auth-required';

export function getStoredToken(): string | null {
  if (typeof window === 'undefined') return null;
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string | null): void {
  if (typeof window === 'undefined') return;
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getStoredToken();
  if (!token || token === 'dev') return {};
  return { Authorization: `Bearer ${token}` };
}

async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const headers = {
    ...authHeaders(),
    ...(init?.headers as Record<string, string> | undefined),
  };
  const res = await fetch(input, { ...init, headers });
  if (res.status === 401 && typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(AUTH_REQUIRED_EVENT));
  }
  return res;
}

async function httpError(res: Response, fallback: string): Promise<Error> {
  let detail = fallback;
  try {
    const body = await res.json();
    if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : fallback;
  } catch {
    /* ignore */
  }
  return new Error(`HTTP ${res.status}: ${detail}`);
}

export interface AuthStatus {
  enabled: boolean;
  roles: string[];
  multi_tenant_enabled?: boolean;
  oidc_enabled?: boolean;
  oidc_login_url?: string | null;
  password_login_enabled?: boolean;
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  username: string;
  role: string;
}

export interface AuditLogEntry {
  id: number;
  username: string;
  role: string;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  codigo_ibge: string | null;
  metadata: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface SystemOverview {
  timestamp: string;
  platform: string;
  environment: string;
  auth: {
    enabled: boolean;
    multi_tenant: boolean;
    oidc_enabled: boolean;
    password_login: boolean;
    public_base_url: string;
  };
  checks: {
    database: { ok: boolean; detail: string };
    ollama: { ok: boolean; detail: string; total_vram_gb?: number; running_models?: unknown[] };
    ai_fallback: { ollama_ok: boolean; gemini_configured: boolean; fallback_available: boolean };
    oidc: { configured: boolean; reachable?: boolean | null; detail?: string | null };
    overall: string;
  };
  boot: {
    db_ready: boolean;
    migrations_applied: string[];
    integration_scheduler: boolean;
    errors: string[];
  };
  municipalities: {
    prioritarios_seed: number;
    carregados_db: number;
    piloto_ibge: string;
    piloto_nome: string;
  };
  onboarding: {
    by_status: Record<string, number>;
    pendentes: number;
    concluidos: number;
  };
  integrations: {
    total: number;
    integradas: number;
    com_falha: number;
    sources: Array<{
      source: string;
      status: string;
      records_count: number;
      last_success_at: string | null;
      error_message?: string | null;
    }>;
  };
  mapbiomas: {
    records: number;
    municipios: number;
    official_records: number;
    csv_configured: boolean;
    csv_path?: string | null;
    colecao: string;
  };
  dem: {
    prioritarios: number;
    processados: number;
    local_ou_lidar: number;
    refinado_piloto: number;
    resolucao_media_m: number | null;
    local_dem_dir: string;
    refine_pilot_enabled: boolean;
    piloto: {
      codigo_ibge: string;
      nome: string;
      dem_source?: string;
      dem_resolution_m?: number;
      vertical_accuracy_m?: number;
    } | null;
  };
  tls: {
    status: string;
    configured?: boolean;
    subject?: string;
    not_after?: string;
    days_until_expiry?: number;
    homolog_self_signed?: boolean;
    detail?: string;
  };
  scheduler: {
    running: boolean;
    jobs: Array<{ id: string; name?: string; next_run?: string | null; trigger?: string }>;
  };
  audit: {
    total_eventos: number;
    top_acoes: Array<{ action: string; count: number }>;
  };
  routing?: {
    available: boolean;
    region: string;
    covered_ufs: string[];
    supported_regions: string[];
    url: string;
    detail?: string;
  };
}

export interface RoutingStatus {
  available: boolean;
  region: string;
  covered_ufs: string[];
  supported_regions: string[];
  url: string;
  detail?: string;
}

export interface BackgroundJob {
  id: string;
  type: string;
  label: string;
  status: string;
  progress: number;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  result?: unknown;
  error?: string | null;
}

export interface ExecutiveIndicators {
  codigo_ibge: string;
  nome: string;
  uf: string;
  populacao: number;
  area_km2: number;
  cobertura_vegetal_percent: number;
  densidade_demografica: number;
  historico_desastres_count: number;
  alertas_ativos_count: number;
  renda_media_setores: number;
  renda_media_fonte: string;
  score_sinidu?: number;
  media_ivc?: number;
  media_iri?: number;
  media_adaptacao?: number;
  danos_materiais_total: number;
  populacao_fonte?: string;
  populacao_qualidade?: string;
  area_fonte?: string;
  area_qualidade?: string;
  pib_per_capita?: number;
  pib_fonte?: string;
  pib_qualidade?: string;
  nota_capag?: string;
  capag_fonte?: string;
  receita_corrente_liquida?: number;
  despesa_pessoal_pct_rcl?: number;
  divida_consolidada?: number;
  divida_consolidada_pct_rcl?: number;
  fiscal_exercicio?: number;
  siconfi_ia_url?: string;
  fiscal_fonte?: string;
  fiscal_qualidade?: string;
  selo_ibge?: string;
  selo_fiscal?: string;
  cobertura_qualidade?: string;
  alertas_qualidade?: string;
  desastres_qualidade?: string;
  renda_qualidade?: string;
  densidade_qualidade?: string;
  score_confiabilidade?: string;
  confiabilidade_geral?: string;
  malha_fonte?: string;
}

export interface IntegrationSourceStatus {
  source: string;
  status: string;
  records_count: number;
  last_success_at?: string | null;
  error_message?: string | null;
}

export interface IntegrationStatusResponse {
  sources: IntegrationSourceStatus[];
}

export interface IntegrationSyncResponse {
  summary: {
    ibge: number;
    siconfi: number;
    capag: number;
    snis: number;
    errors?: Array<{ source: string; codigo_ibge: string; error: string }>;
  };
  sources: IntegrationSourceStatus[];
}

export interface MunicipalityOption {
  id?: number;
  codigo_ibge: string;
  nome: string;
  uf: string;
  populacao?: number;
  area_km2?: number;
  criterio?: string;
  status_carga?: string;
  loaded?: boolean;
}

export interface VulnerabilityIndexResult {
  id: number;
  bairro_nome: string;
  exposicao: number;
  sensibilidade: number;
  capacidade_adaptacao: number;
  indice_vulnerabilidade: number;
}

export interface FloodRiskResult {
  id: number;
  bairro_nome: string;
  s2id_historico_score: number;
  impermeabilizacao_score: number;
  hidrografia_proximidade_score: number;
  indice_risco_inundacao: number;
}

export interface IndicesResponse {
  vulnerabilidade: VulnerabilityIndexResult[];
  inundacao: FloodRiskResult[];
}

export interface HeatIslandResult {
  bairro_nome: string;
  temperatura_superficial_celsius: number;
  anomalia_calor_celsius: number;
  intensidade_ilha: 'BAIXA' | 'MEDIA' | 'ALTA';
}

export interface HeatIslandsResponse {
  anomalies: HeatIslandResult[];
  historical_timeline: { ano: number; temperatura_media: number; area_urbanizada_km2: number }[];
  source: string;
  source_note?: string;
}

export interface OfficialUrbanClimateResponse {
  municipio: {
    codigo_ibge: string;
    nome: string;
    uf: string;
  };
  station?: {
    codigo: string;
    nome: string;
    uf: string;
    situacao: string;
    tipo: string;
    latitude: number;
    longitude: number;
    distancia_km: number;
    inicio_operacao?: string | null;
  } | null;
  historical_timeline: {
    ano: number;
    temperatura_media?: number | null;
    temperatura_qualidade?: string;
    area_urbanizada_km2?: number | null;
    qualidade_dado?: string;
  }[];
  estimated_timeline: { ano: number; temperatura_media: number; area_urbanizada_km2: number; qualidade_dado: string }[];
  source: string;
  source_note: string;
  estimated_source?: string;
  estimated_methodology?: string;
  lacunas: string[];
  temperatura_integrada?: boolean;
  temperatura_oficial?: boolean;
  mapbiomas_integrado?: boolean;
  mapbiomas_oficial?: boolean;
}

export interface RainfallComparisonDelta {
  baseline_mm: number;
  scenario_mm: number;
  affected_area_km2: number;
  affected_population: number;
  max_depth_m: number;
  flood_patches: number;
  bairros_novos: string[];
  bairros_removidos: string[];
}

export interface RainfallComparison {
  baseline: SimulationOutput;
  scenario: SimulationOutput;
  delta: RainfallComparisonDelta;
}

export interface SimulationOutput {
  scenario_type: 'Waterproofing' | 'VegetationLoss' | 'ExtremeRainfall' | 'DrainageDeficit';
  input_value: number;
  metric_impact: string;
  impact_value: number;
  affected_area_km2: number;
  affected_population: number;
  affected_bairros: string[];
  geometry: any;
  contours?: any;
  flow_paths?: any;
  simulation_meta?: {
    dem_available?: boolean;
    dem_source?: string;
    method?: string;
    iri_applied?: boolean;
    impermeability_applied?: boolean;
    flow_accumulation_applied?: boolean;
    flood_patches?: number;
    landslide_method?: string;
    landslide_zones?: number;
    contour_interval_m?: number;
    contour_count?: number;
    dem_resolution_m?: number;
    vertical_accuracy_m?: number;
    precision_note?: string;
    model_version?: string;
    twi_applied?: boolean;
    altitude_min_m?: number;
    altitude_max_m?: number;
    altitude_media_m?: number;
    declividade_media_graus?: number;
    pct_declividade_critica?: number;
    precipitation_mm?: number;
    max_depth_m?: number;
    mean_impermeability?: number;
    max_flow_accumulation?: number;
    bairros_exposicao?: { bairro: string; exposicao_pct: number; populacao_exposta: number }[];
    bairros_atingidos_count?: number;
  };
  risk_context?: BairroRiskContext[];
}

export interface BairroRiskContext {
  bairro: string;
  ivc: number;
  iri: number;
  composite_risk: number;
  rationale?: string;
  exposicao?: number;
  s2id_score?: number;
  impermeabilizacao?: number;
}

export interface SimulationAnalysis {
  narrative_md: string;
  key_findings: string[];
  bairros_prioritarios: Array<{
    nome: string;
    ivc?: number;
    iri?: number;
    rationale?: string;
  }>;
  suggested_actions: string[];
  data_gaps: string[];
  confidence: string;
  ai_provider: string;
  ai_model?: string | null;
  disclaimer: string;
  risk_context?: BairroRiskContext[];
}

export interface SimulationInterpret {
  resumo_executivo: string;
  areas_criticas: string[];
  equipamentos_em_risco: string[];
  comparacao_historica: string;
  recomendacoes_imediatas: string[];
  interpretacao_diferencial?: string | null;
  disclaimer: string;
  findings?: string[];
  metricas?: Record<string, unknown>;
  ai_provider: string;
  ai_model?: string | null;
  confidence?: string;
}

export interface SlopeInterpretation {
  codigo_ibge: string;
  area_suscetivel_km2: number;
  populacao_exposta: number;
  bairros_encosta: string[];
  nivel_suscetibilidade: string;
  interpretacao_ia: string;
  referencia_cobrade: string;
  dem_source?: string | null;
  precipitacao_mm?: number | null;
}

export interface MitigationAction {
  horizonte: string;
  acao: string;
  justificativa: string;
  proporcionalidade: string;
}

export interface MitigationEvidence {
  titulo: string;
  descricao: string;
  fonte: string;
}

export interface AnalogMunicipality {
  codigo_ibge: string;
  nome: string;
  uf: string;
  coeficiente_similaridade: number;
  fatores: Record<string, number>;
}

export interface PlanningConstraint {
  tipo: string;
  descricao: string;
  fonte: string;
}

export interface MitigationSource {
  titulo: string;
  url?: string | null;
  tipo: string;
  status: string;
  observacao?: string | null;
}

export interface MitigationPlan {
  municipio: {
    codigo_ibge: string;
    nome: string;
    uf: string;
    populacao: number;
    area_km2: number;
  };
  evento: {
    tipo: string;
    precipitacao_mm: number;
    valor_entrada?: number;
    unidade?: string;
    area_afetada_km2: number;
    populacao_afetada: number;
    bairros_atingidos: string[];
  };
  severidade: string;
  acoes_tecnicas_padrao: MitigationAction[];
  experiencias_municipais: MitigationEvidence[];
  municipios_analogos: AnalogMunicipality[];
  casos_analogos: MitigationEvidence[];
  diretrizes_plano_diretor: PlanningConstraint[];
  restricoes_plano_diretor: PlanningConstraint[];
  capacidade_investimento?: {
    nota_capag?: string | null;
    media_ivc?: number;
    despesa_pessoal_pct_rcl?: number | null;
    divida_consolidada_pct_rcl?: number | null;
    alertas: string[];
    fontes_financiamento_sugeridas: string[];
    observacao?: string;
  };
  fontes_consultadas: MitigationSource[];
  lacunas: string[];
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  sourceUrl?: string;
  ragSources?: RagSource[];
  municipalSources?: MunicipalDataSource[];
  responseTimeMs?: number;
  aiProvider?: string;
  aiModel?: string;
}

export interface RagSource {
  source: string;
  source_label: string;
  chunk_idx: number;
  content: string;
  similarity: number;
}

export interface MunicipalDataSource {
  id: string;
  label: string;
  snippet: string;
  url: string;
  tipo: string;
}

export interface MunicipalAssistantContext {
  codigo_ibge: string;
  municipio: { nome: string; uf: string };
  headline: string;
  score_sinidu?: number;
  nota_capag?: string;
  maturidade?: string;
  maturidade_score?: number;
  summary_text: string;
  sources: MunicipalDataSource[];
  suggested_questions: string[];
  tem_diagnostico: boolean;
  tem_relatorio: boolean;
}

export interface AIProviderOption {
  id: string;
  label: string;
  description: string;
  available: boolean;
  is_local: boolean;
  requires_api_key: boolean;
  default_model: string;
  models: string[];
  privacy_note: string;
}

export interface AIProvidersResponse {
  default_provider: string;
  providers: AIProviderOption[];
}

export interface AIProviderTestResponse {
  ok: boolean;
  message: string;
  response_time_ms: number;
  sample_response?: string;
}

export interface ChatResponse {
  response: string;
  suggested_layer?: string;
  coordinates?: [number, number];
  zoom?: number;
  source_url?: string;
  rag_sources?: RagSource[];
  municipal_sources?: MunicipalDataSource[];
  suggested_questions?: string[];
  response_time_ms?: number;
  ai_provider?: string;
  ai_model?: string;
}

export interface ContextualChatPayload {
  message: string;
  municipio_codigo: string;
  pagina_atual: string;
  descricao_pagina?: string;
  dados_pagina?: Record<string, unknown>;
  historico?: ChatMessage[];
  stream?: boolean;
}

export interface SuccessCaseReference {
  id: number;
  titulo?: string;
  municipio_nome?: string;
  municipio_uf?: string;
  referencia_texto: string;
  similarity?: number;
}

export interface SuccessCase {
  id: number;
  uuid?: string | null;
  titulo?: string;
  municipio_nome?: string;
  municipio_uf?: string;
  municipio: string;
  uf: string;
  populacao_aprox?: number | null;
  regiao?: string | null;
  tipo_intervencao?: string | null;
  problema_original?: string;
  solucao_implementada?: string;
  resultado_mensuravel?: string | null;
  problema: string;
  solucao: string;
  resultado?: string | null;
  custo_estimado_reais?: number | null;
  programa_financiador?: string | null;
  ano_implementacao?: number | null;
  fonte_referencia?: string | null;
  tags?: string[];
  imagem_url?: string | null;
  relevance_score?: number;
  similarity?: number;
  created_at?: string | null;
}

export interface CaseSearchFilters {
  query: string;
  municipio_codigo?: string;
  top_k?: number;
  regiao?: string;
  tipo_intervencao?: string;
  faixa_populacao?: string;
  programa_financiador?: string;
}

export interface CaseSearchResponse {
  items: SuccessCase[];
  total: number;
  search_mode: string;
}

export interface CaseAdaptationResult {
  caso: SuccessCase;
  municipio: { codigo_ibge: string; nome: string; uf: string; populacao?: number; regiao?: string };
  adaptacao_ia: string;
  custo_estimado_adaptado_reais?: number;
  ai_provider: string;
  pergunta_sugerida: string;
}

export interface CaseFilterOptions {
  regioes: string[];
  tipos_intervencao: string[];
  programas_financiadores: string[];
  faixas_populacao: string[];
}

export interface DiagnosticArea {
  bairro: string;
  score_sinidu: number;
  indice_vulnerabilidade: number;
  indice_risco_inundacao: number;
  capacidade_adaptacao: number;
  score_componentes?: {
    vulnerabilidade_pct: number;
    inundacao_pct: number;
    deficit_adaptacao_pct: number;
  };
  score_explicacao?: string;
  acao_recomendada: string;
  coordinates: [number, number];
}

export interface NarrativeStep {
  title: string;
  description: string;
  layers: string[];
  focus: [number, number];
  zoom: number;
}

export interface WorkshopDiagnostic {
  municipio: {
    nome: string;
    uf: string;
    codigo_ibge: string;
    populacao: number;
    area_km2: number;
  };
  headline: string;
  score_formula: string;
  critical_areas: DiagnosticArea[];
  ranking: DiagnosticArea[];
  recommended_layers: string[];
  opportunities: string[];
  narrative_steps: NarrativeStep[];
}

export interface MunicipalityComparisonRow {
  codigo_ibge: string;
  nome: string;
  uf: string;
  populacao: number;
  area_km2: number;
  densidade_demografica: number;
  renda_media_setores: number;
  cobertura_vegetal_percent: number;
  alertas_ativos_count: number;
  historico_desastres_count: number;
  danos_materiais_total: number;
  score_sinidu: number;
  media_ivc: number;
  media_iri: number;
  media_adaptacao: number;
}

export interface MunicipalityComparison {
  codigos: string[];
  metricas: string[];
  qualidade_dado: string;
  municipios: MunicipalityComparisonRow[];
}

export interface SocioeconomicRankingRow {
  bairro: string;
  renda_media: number;
  populacao_estimada: number;
  setores: number;
  classe_renda: string;
}

export interface SocioeconomicRanking {
  codigo_ibge: string;
  nome: string;
  renda_municipal_media: number;
  pib_per_capita_ibge: number | null;
  classificacao: string;
  limiares: { p33: number; p66: number };
  mais_ricos: SocioeconomicRankingRow[];
  mais_pobres: SocioeconomicRankingRow[];
  metodo: string;
  fonte: string;
}

export interface TerrainStats {
  altitude_min_m: number;
  altitude_max_m: number;
  altitude_media_m: number;
  declividade_media_graus: number;
  area_critica_ha: number;
  pct_declividade_critica: number;
  pct_area_baixa_elevacao: number;
  suscetibilidade_alta_pct: number;
}

export interface TerrainMesh {
  width: number;
  height: number;
  bounds: [number, number, number, number];
  heights: number[];
  colors: number[];
}

export interface TerrainConfig {
  codigo_ibge: string;
  nome?: string;
  uf?: string;
  bounds: [number, number, number, number];
  elevation_url: string;
  texture_url: string;
  mesh_url: string;
  flow_paths_url: string;
  elevation_decoder: {
    rScaler: number;
    gScaler: number;
    bScaler: number;
    offset: number;
  };
  image_size?: [number, number];
  stats?: TerrainStats;
  dem_source?: string;
  data_reference?: string;
  default_exaggeration?: number;
  terrain_available?: boolean;
}

export interface SlopeAnalysis {
  codigo_ibge: string;
  area_critica_ha: number;
  populacao_exposta: number;
  bairros_criticos: Array<{ nome: string; pct_area_critica: number }>;
  suscetibilidade_alta_pct: number;
  dem_source: string;
  data_reference: string;
}

export interface DataCatalogBase {
  id: string;
  nome: string;
  grupo: string;
  camada?: string | null;
  status: 'Integrado' | 'Estimado' | 'Em integracao' | 'Ausente';
  score: number;
  recomendacao: string;
  ultima_sync?: string | null;
  registros?: number;
  requisito?: string | null;
  impacto_confiabilidade?: number | null;
  impacto_confiabilidade_label?: string | null;
  integravel_etl?: boolean;
  dificuldade?: string;
  impacto_score_pts?: number;
}

export interface LacunaRankingItem {
  rank: number;
  id: string;
  nome: string;
  status: string;
  impacto_estimado: number;
  impacto_label: string;
  dificuldade: string;
  requisito?: string;
}

export interface MaturityDetail {
  maturidade_percentual: number;
  radar: { eixo: string; valor: number }[];
  timeline: { anterior: number; atual: number; delta: number; label: string };
  projecao: { percentual: number; fontes_alvo: string[]; label: string };
  explicacao_ia: string;
  lacunas_ranking: LacunaRankingItem[];
}

export interface FonteImpactAnalysis {
  fonte_id: string;
  fonte_nome: string;
  status_atual: string;
  campos_score: string[];
  impacto_confiabilidade: number;
  impacto_score_estimado: number;
  dificuldade: string;
  requisito: string;
  explicacao_ia: string;
  ai_provider?: string;
}

export interface CatalogRefreshJob {
  id: string;
  status: string;
  progress: number;
  result?: {
    progress?: number;
    sources?: { fonte_id: string; nome: string; status: string; detail?: string }[];
    done?: number;
    total?: number;
  };
  error?: string | null;
}

export interface DataCoverage {
  municipio: {
    codigo_ibge: string;
    nome: string;
    uf: string;
  };
  maturidade_percentual: number;
  classificacao: 'Alta' | 'Media' | 'Baixa';
  bases: DataCatalogBase[];
  lacunas_prioritarias: DataCatalogBase[];
  lacunas_ranking?: LacunaRankingItem[];
  maturity_detail?: MaturityDetail;
  resumo: string;
}

export interface DataCatalogNational {
  total_municipios: number;
  media_maturidade_percentual: number;
  classificacao: 'Alta' | 'Media' | 'Baixa';
  bases: Array<{
    id: string;
    nome: string;
    integrado_pct: number;
    totals: Record<string, number>;
  }>;
  lacunas_frequentes: Array<{ id: string; nome: string; municipios: number }>;
  municipios: Array<{
    codigo_ibge: string;
    nome: string;
    uf: string;
    maturidade_percentual: number;
    onboarding_status: string;
    lacunas_count: number;
  }>;
  resumo: string;
}

export interface MunicipalReportRecord {
  id: number;
  municipio_id: number;
  codigo_ibge: string;
  nome_arquivo: string;
  tamanho_bytes: number;
  status: string;
  gerado_em: string;
  download_url: string;
}

export interface ReportJobProgress {
  job_id: string;
  status: string;
  progress: number;
  stage?: string;
  stage_label?: string;
  report_id?: number;
  download_url?: string;
  error?: string | null;
  async?: boolean;
}

export interface ExecutiveDiagnostic {
  id: number;
  municipio_id: number;
  codigo_ibge: string;
  versao: number;
  status: string;
  headline: string;
  conteudo: Record<string, unknown>;
  narrativa_md: string;
  narrativa_ia?: string | null;
  narrativa_ia_meta?: {
    ai_provider?: string;
    ai_model?: string;
    disclaimer?: string;
    paragrafos?: string[];
  } | null;
  origem: string;
  gerado_em: string | null;
  nome_arquivo?: string | null;
  tamanho_bytes?: number | null;
  download_url?: string | null;
}

export interface PresentationPayload {
  municipio: { nome: string; uf: string; codigo_ibge: string; populacao?: number };
  score: number;
  severidade: string;
  ivc?: number;
  iri?: number;
  data_apresentacao: string;
  narrativa: {
    texto_completo?: string | null;
    paragrafos: string[];
    contexto: string;
    prioridades: string;
    proximos_passos: string;
    disclaimer?: string;
    ai_provider?: string;
  };
  mapa: {
    layer: string;
    png_base64: string;
    legenda: { cor: string; label: string }[];
  };
  bairros_prioritarios: {
    bairro: string;
    score: number;
    populacao?: number | null;
    risco_principal: string;
  }[];
  historico_desastres: {
    total_10_anos: number;
    por_ano: { ano: number; eventos: number }[];
    maior_dano: number;
    data_maior_dano?: string | null;
  };
  saude_fiscal: {
    capag?: string | null;
    capacidade_financiamento: string;
    interpretacao?: string;
    receita_corrente_liquida?: number | null;
    programas_elegiveis: { nome?: string; programa?: string }[];
  };
  plano_acao: {
    curto_prazo: { total: number; acoes: { titulo: string }[] };
    medio_prazo: { total: number; acoes: { titulo: string }[] };
    longo_prazo: { total: number; acoes: { titulo: string }[] };
  };
  pdf: { download_url?: string | null; nome_arquivo?: string | null };
  diagnostic?: ExecutiveDiagnostic;
}

export interface ExecutiveDiagnosticHistoryItem {
  id: number;
  versao: number;
  headline: string;
  origem: string;
  gerado_em: string | null;
  nome_arquivo?: string | null;
  tamanho_bytes?: number | null;
  download_url?: string | null;
}

export interface ActionPlanItem {
  id: string;
  titulo: string;
  descricao: string;
  horizonte: string;
  custo: string;
  prioridade: string;
  justificativa: string;
  fonte: string;
  orgao: string;
  bairros_alvo: string[];
  casos_referencia?: SuccessCaseReference[];
}

export interface FederalProgramSuggestion {
  nome: string;
  orgao: string;
  unidade: string;
  site: string;
  contato: string;
  elegibilidade: string;
  motivo: string;
}

export interface MunicipalActionPlan {
  id?: number;
  municipio_id?: number;
  codigo_ibge: string;
  versao?: number;
  diagnostic_id?: number | null;
  status?: string;
  severidade: string;
  score_sinidu: number;
  headline: string;
  origem?: string;
  gerado_em?: string | null;
  acoes_curto_prazo: ActionPlanItem[];
  acoes_medio_prazo: ActionPlanItem[];
  acoes_longo_prazo: ActionPlanItem[];
  total_acoes: number;
  programas_financiamento: FederalProgramSuggestion[];
  capacidade_fiscal: Record<string, unknown>;
  lacunas: string[];
  fontes_consultadas: Array<{ id: string; label: string; tipo: string }>;
  municipio: { codigo_ibge: string; nome: string; uf: string; populacao: number; area_km2: number };
  ranking_bairros?: Array<{ bairro: string; score_sinidu: number }>;
}

export interface CriticalNeighborhood {
  bairro_id: number;
  bairro_nome: string;
  risk_probability: number;
  iri: number;
  impermeabilizacao_pct: number;
}

export interface FloodRiskPrediction {
  codigo_ibge: string;
  municipio_slug: string;
  risk_probability: number;
  risk_level: string;
  confidence: string;
  threshold_mm_24h: number;
  critical_neighborhoods: CriticalNeighborhood[];
  flood_geojson: { features?: unknown[] } | null;
  model_version: string;
  model_kind?: string;
  data_quality: string;
  model_auc_roc?: number | null;
  disclaimer: string;
}

export interface ContingencyPlan {
  id: number;
  municipio_id: number;
  codigo_ibge?: string;
  municipio_nome?: string;
  cenario_tipo: string;
  nivel_alerta: string;
  zonas_evacuacao: any[];
  rotas_fuga: any[];
  pontos_apoio: any[];
  contatos_defesa_civil: Array<{ nome: string; cargo?: string; telefone?: string; whatsapp?: string }>;
  acoes_por_nivel: Record<string, string[]>;
  status: string;
  versao: number;
  simulacao_ref?: Record<string, unknown>;
}

export interface MonitoringDashboard {
  codigo_ibge: string;
  nome_municipio?: string | null;
  uf?: string | null;
  nivel_risco_atual: string;
  cemaden_ativos: number;
  alertas_risco?: number;
  precip_24h_mm: number | null;
  precip_72h_mm: number | null;
  risk_probability: number | null;
  weather_updated_at: string | null;
  weather_disponivel?: boolean;
  timeline: MonitoringAlertItem[];
  timeline_grouped?: MonitoringTimelineGroupItem[];
  plano_ativo: ContingencyPlan | null;
}

export interface MonitoringTimelineGroupItem extends MonitoringAlertItem {
  count?: number;
  grouped?: boolean;
  titulo_display?: string;
  alert_icon?: string;
  alert_category?: string;
  latest_at?: string;
}

export interface ScenarioAnalysis {
  codigo_ibge: string;
  municipio_nome: string;
  uf?: string | null;
  interpretacao: string;
  tendencia: string;
  recomendacoes: string[];
  recomendacao_nivel: string;
  referencia_historica: string;
  proxima_revisao: string;
  updated_at: string;
  cached: boolean;
  ai_provider: string;
  inputs: Record<string, unknown>;
}

export interface MonitoringCompareResult {
  municipio_a: Record<string, unknown>;
  municipio_b: Record<string, unknown>;
  mais_critico_ibge: string;
  comparacao_ia: string;
  ai_provider: string;
}

export interface MonitoringAlertItem {
  id: number;
  tipo: string;
  nivel: string;
  titulo: string;
  mensagem?: string;
  created_at: string;
  payload?: Record<string, unknown>;
  alert_icon?: string;
  alert_category?: string;
}

export interface OnboardingStep {
  status: string;
  detail?: string;
  quality?: string;
  at?: string;
}

export interface OnboardingValidateResult {
  codigo_ibge: string;
  nome: string;
  uf: string;
  regiao?: string;
  valido: boolean;
}

export interface OnboardingStatus {
  codigo_ibge: string;
  nome: string;
  uf: string;
  criterio: string;
  municipio_id?: number | null;
  onboarding_status: string;
  status_carga: string;
  maturity_score?: number | null;
  completeness_score?: number | null;
  maturity_classificacao?: string | null;
  score_sinidu?: number | null;
  lacunas: string[];
  integration_errors: Array<{ step: string; message: string }>;
  integration_steps: Record<string, OnboardingStep>;
  populacao?: number | null;
  area_km2?: number | null;
  nota_capag?: string | null;
  geom_fonte?: string | null;
  updated_at?: string | null;
  pronto_para_uso: boolean;
}

export interface MunicipalMaturitySource {
  id: string;
  nome: string;
  grupo: string;
  status: 'OFICIAL' | 'DERIVADO' | 'ESTIMADO' | 'LACUNA';
  peso_percentual: number;
  pontos: number;
  detail: string;
  recomendacao: string;
}

export interface MunicipalMaturity {
  codigo_ibge: string;
  nome: string;
  uf: string;
  score: number;
  completeness_score: number;
  classificacao: 'Bronze' | 'Prata' | 'Ouro' | 'Platina';
  fontes: MunicipalMaturitySource[];
  fontes_faltantes: Array<{ id: string; nome: string; recomendacao: string }>;
  fontes_parciais: Array<{ id: string; nome: string; status: string; detail: string }>;
  resumo: string;
  calculado_em: string;
}

export interface MonitoringMapOverview {
  total_municipios: number;
  com_geometria: number;
  com_coordenadas: number;
  municipios: MonitoringMapItem[];
}

export interface MonitoringMapItem {
  codigo_ibge: string;
  nome: string;
  uf: string;
  nivel: string;
  cemaden_ativos?: number;
  precip_72h_mm?: number | null;
  risk_probability: number;
  lat?: number | null;
  lng?: number | null;
}

const IBGE_TO_SLUG: Record<string, string> = {
  '2611606': 'recife',
  '2927408': 'salvador',
  '4314902': 'porto_alegre',
  '2507507': 'joao_pessoa',
  '4113700': 'londrina',
};

export const api = {
  getMunicipalities: async (): Promise<MunicipalityOption[]> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/municipalities`);
    if (!res.ok) throw new Error('Failed to load municipalities');
    return res.json();
  },

  getSeedMunicipalities: async (): Promise<MunicipalityOption[]> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/seeds`);
    if (!res.ok) throw new Error('Failed to load seed municipalities');
    return res.json();
  },

  getExecutiveIndicators: async (codigoIbge?: string): Promise<ExecutiveIndicators> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/executive${qs}`);
    if (!res.ok) throw await httpError(res, 'Failed to load indicators');
    return res.json();
  },

  getIntegrationStatus: async (): Promise<IntegrationStatusResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/integrations/status`);
    if (!res.ok) throw new Error('Failed to load integration status');
    return res.json();
  },

  getLayerGeoJSON: async (layerName: string, codigoIbge?: string): Promise<any> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/layers/${layerName}${qs}`);
    if (!res.ok) throw new Error(`Failed to load layer: ${layerName}`);
    return res.json();
  },

  getLayersMeta: async (codigoIbge?: string): Promise<{
    codigo_ibge: string;
    malha_fonte?: string;
    malha_disponivel?: boolean;
    camadas_bloqueadas?: string[];
    score_confiabilidade?: string;
    confiabilidade_geral?: string;
    layers: Record<string, {
      quality: string;
      source: string;
      disponivel?: boolean;
      tooltip_estimado?: string;
      snis?: Record<string, unknown>;
    }>;
  }> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/layers/meta${qs}`);
    if (!res.ok) throw new Error('Failed to load layer metadata');
    return res.json();
  },

  getTerrainConfig: async (codigoIbge: string): Promise<TerrainConfig> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/terrain/${codigoIbge}/config`);
    if (!res.ok) throw new Error('Terreno 3D não disponível');
    return res.json();
  },

  getSlopeAnalysis: async (codigoIbge: string): Promise<SlopeAnalysis> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/terrain/slope-analysis/${codigoIbge}`);
    if (!res.ok) throw new Error('Análise de encostas indisponível');
    return res.json();
  },

  processTerrainDem: async (codigoIbge: string, force = false): Promise<{ status: string; config: TerrainConfig }> => {
    const qs = force ? '?force=true' : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/terrain/${codigoIbge}/process${qs}`, { method: 'POST' });
    if (!res.ok) throw new Error('Falha ao processar DEM');
    return res.json();
  },

  getRiskIndices: async (codigoIbge?: string): Promise<IndicesResponse> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/indices${qs}`);
    if (!res.ok) throw await httpError(res, 'Failed to load risk indices');
    return res.json();
  },

  getHeatIslands: async (codigoIbge?: string): Promise<HeatIslandsResponse> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/heat-islands${qs}`);
    if (!res.ok) throw new Error('Failed to load heat islands data');
    return res.json();
  },

  getOfficialUrbanClimate: async (codigoIbge?: string): Promise<OfficialUrbanClimateResponse> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/urban-climate-official${qs}`);
    if (!res.ok) throw new Error('Failed to load official urban climate data');
    return res.json();
  },

  getWorkshopDiagnostic: async (codigoIbge?: string): Promise<WorkshopDiagnostic> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/diagnostic${qs}`);
    if (!res.ok) throw new Error('Failed to load Sinidu+Clima diagnostic');
    return res.json();
  },

  compareMunicipalities: async (codigos: string[]): Promise<MunicipalityComparison> => {
    const qs = codigos.map((code) => code.trim()).filter(Boolean).join(',');
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/compare?codigos=${encodeURIComponent(qs)}`);
    if (!res.ok) throw new Error('Failed to compare municipalities');
    return res.json();
  },

  getSocioeconomicRanking: async (codigoIbge?: string, limit = 5): Promise<SocioeconomicRanking> => {
    const params = new URLSearchParams();
    if (codigoIbge) params.set('codigo_ibge', codigoIbge);
    params.set('limit', String(limit));
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/socioeconomic-ranking?${params}`);
    if (!res.ok) throw new Error('Failed to load socioeconomic ranking');
    return res.json();
  },

  getDataCoverage: async (codigoIbge?: string): Promise<DataCoverage> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/data-catalog/coverage${qs}`);
    if (!res.ok) throw new Error('Failed to load data coverage');
    return res.json();
  },

  getFonteImpactAnalysis: async (codigoIbge: string, fonteId: string): Promise<FonteImpactAnalysis> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/data-catalog/impact-analysis/${encodeURIComponent(codigoIbge)}/${encodeURIComponent(fonteId)}`,
    );
    if (!res.ok) throw new Error('Falha na análise de impacto');
    return res.json();
  },

  getFontePreview: async (codigoIbge: string, fonteId: string): Promise<{ registros: Record<string, unknown>[] }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/data-catalog/source-preview/${encodeURIComponent(codigoIbge)}/${encodeURIComponent(fonteId)}`,
    );
    if (!res.ok) throw new Error('Falha ao carregar preview');
    return res.json();
  },

  refreshCatalogSource: async (codigoIbge: string, fonteId: string, force = false): Promise<{ ok: boolean }> => {
    const qs = force ? '?force=true' : '';
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/data-catalog/refresh-source/${encodeURIComponent(codigoIbge)}/${encodeURIComponent(fonteId)}${qs}`,
      { method: 'POST' },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao atualizar fonte');
    }
    return res.json();
  },

  refreshAllCatalogSources: async (codigoIbge: string): Promise<{ job_id: string }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/data-catalog/refresh-all/${encodeURIComponent(codigoIbge)}`,
      { method: 'POST' },
    );
    if (!res.ok) throw new Error('Falha ao iniciar atualização em lote');
    return res.json();
  },

  getCatalogRefreshJob: async (jobId: string): Promise<CatalogRefreshJob> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/data-catalog/refresh-job/${encodeURIComponent(jobId)}`);
    if (!res.ok) throw new Error('Job não encontrado');
    return res.json();
  },

  getNationalDataCatalog: async (): Promise<DataCatalogNational> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/data-catalog/national`);
    if (!res.ok) throw await httpError(res, 'Falha ao carregar panorama nacional');
    return res.json();
  },

  getSentinelScenes: async (): Promise<any> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/sentinel-stac`);
    if (!res.ok) throw new Error('Failed to load Sentinel scenes');
    return res.json();
  },

  simulateWaterproofing: async (pct: number, codigoIbge?: string): Promise<SimulationOutput> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/waterproofing`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ taxa_impermeabilizacao_adicional: pct, codigo_ibge: codigoIbge })
    });
    if (!res.ok) throw new Error('Waterproofing simulation failed');
    return res.json();
  },

  simulateVegetationLoss: async (pct: number, codigoIbge?: string): Promise<SimulationOutput> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/vegetation-loss`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ taxa_desmatamento: pct, codigo_ibge: codigoIbge })
    });
    if (!res.ok) throw new Error('Vegetation loss simulation failed');
    return res.json();
  },

  simulateExtremeRainfall: async (mm: number, codigoIbge?: string): Promise<SimulationOutput> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/extreme-rainfall`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ precipitacao_mm: mm, codigo_ibge: codigoIbge })
    });
    if (!res.ok) throw new Error('Extreme rainfall simulation failed');
    return res.json();
  },

  compareRainfallScenarios: async (
    scenarioMm: number,
    baselineMm: number = 80,
    codigoIbge?: string,
  ): Promise<RainfallComparison> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/extreme-rainfall/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        baseline_mm: baselineMm,
        scenario_mm: scenarioMm,
        codigo_ibge: codigoIbge,
      }),
    });
    if (!res.ok) throw new Error('Rainfall comparison failed');
    return res.json();
  },

  simulateDrainageDeficit: async (pct: number, codigoIbge?: string): Promise<SimulationOutput> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/drainage-deficit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ deficit_drenagem_pct: pct, codigo_ibge: codigoIbge })
    });
    if (!res.ok) throw new Error('Drainage deficit simulation failed');
    return res.json();
  },

  analyzeSimulation: async (
    simulation: SimulationOutput,
    codigoIbge?: string,
    options?: { useAi?: boolean; aiProvider?: string; aiModel?: string; aiApiKey?: string },
  ): Promise<SimulationAnalysis> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: codigoIbge,
        simulation,
        use_ai: options?.useAi ?? true,
        ai_provider: options?.aiProvider,
        ai_model: options?.aiModel,
        ai_api_key: options?.aiApiKey,
      }),
    });
    if (!res.ok) throw new Error('Simulation analysis failed');
    return res.json();
  },

  interpretSimulation: async (
    payload: {
      municipio_codigo: string;
      tipo_simulacao: 'chuva' | 'asfalto' | 'vegetacao' | 'drenagem';
      parametro_atual: number;
      parametro_referencia?: number;
      resultado_simulacao: SimulationOutput;
      resultado_referencia?: SimulationOutput;
      comparacao_delta?: RainfallComparison['delta'];
    },
  ): Promise<SimulationInterpret> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/interpret`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ...payload,
        use_ai: true,
      }),
    });
    if (!res.ok) throw new Error('Falha na interpretação da simulação');
    return res.json();
  },

  getSlopeInterpretation: async (codigoIbge: string, precipitacaoMm = 80): Promise<SlopeInterpretation> => {
    const params = new URLSearchParams({ precipitacao_mm: String(precipitacaoMm) });
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/simulations/slope-interpretation/${encodeURIComponent(codigoIbge)}?${params}`,
    );
    if (!res.ok) throw new Error('Falha na interpretação de encostas');
    return res.json();
  },

  exportSimulationGeojson: async (
    simulation: SimulationOutput,
    codigoIbge?: string,
    comparisonDelta?: RainfallComparison['delta'],
  ): Promise<{ download_url: string; nome_arquivo: string }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/export/geojson`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: codigoIbge,
        simulation,
        comparison_delta: comparisonDelta ?? null,
      }),
    });
    if (!res.ok) throw new Error('Exportação GeoJSON falhou');
    return res.json();
  },

  exportSimulationPdf: async (
    simulation: SimulationOutput,
    codigoIbge?: string,
    options?: {
      comparisonDelta?: RainfallComparison['delta'];
      analysis?: SimulationAnalysis | SimulationInterpret;
    },
  ): Promise<{ download_url: string; nome_arquivo: string }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/export/pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: codigoIbge,
        simulation,
        comparison_delta: options?.comparisonDelta ?? null,
        analysis: options?.analysis ?? null,
      }),
    });
    if (!res.ok) throw new Error('Exportação PDF falhou');
    return res.json();
  },

  generateMitigationPlan: async (scenarioType: SimulationOutput['scenario_type'], inputValue: number, codigoIbge?: string): Promise<MitigationPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/mitigation-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario_type: scenarioType, input_value: inputValue, codigo_ibge: codigoIbge })
    });
    if (!res.ok) throw new Error('Mitigation plan generation failed');
    return res.json();
  },

  generateRainfallMitigationPlan: async (mm: number, codigoIbge?: string): Promise<MitigationPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/extreme-rainfall/mitigation-plan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ precipitacao_mm: mm, codigo_ibge: codigoIbge })
    });
    if (!res.ok) throw new Error('Mitigation plan generation failed');
    return res.json();
  },

  chatAssistant: async (
    message: string,
    history: ChatMessage[],
    codigoIbge?: string,
    aiProvider?: string,
    aiModel?: string,
    aiApiKey?: string,
  ): Promise<ChatResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/assistant/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        history,
        codigo_ibge: codigoIbge,
        ai_provider: aiProvider,
        ai_model: aiModel,
        ai_api_key: aiApiKey || undefined,
      })
    });
    if (!res.ok) throw new Error('Chat communication failed');
    return res.json();
  },

  chatContextualAssistantStream: async (
    payload: ContextualChatPayload,
    onToken: (fullText: string) => void,
  ): Promise<string> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/assistant/chat-contextual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify({ ...payload, stream: true }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha no agente contextual');
    }
    if (!res.body) throw new Error('Streaming indisponível');

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let full = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith('data:')) continue;
        try {
          const evt = JSON.parse(line.slice(5).trim()) as {
            type?: string;
            content?: string;
            response?: string;
          };
          if (evt.type === 'token' && evt.content) {
            full += evt.content;
            onToken(full);
          } else if (evt.type === 'done' && evt.response) {
            full = evt.response;
            onToken(full);
          } else if (evt.type === 'error') {
            throw new Error(evt.content || 'Erro no agente');
          }
        } catch (e) {
          if (e instanceof Error && e.message !== 'Erro no agente') {
            /* ignore parse noise */
          } else {
            throw e;
          }
        }
      }
    }
    return full.trim();
  },

  chatContextualAssistant: async (payload: ContextualChatPayload): Promise<ChatResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/assistant/chat-contextual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...payload, stream: false }),
    });
    if (!res.ok) throw new Error('Falha no agente contextual');
    return res.json();
  },

  getMunicipalAssistantContext: async (codigoIbge: string): Promise<MunicipalAssistantContext> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/assistant/municipal/${encodeURIComponent(codigoIbge)}/context`);
    if (!res.ok) throw new Error('Falha ao carregar contexto municipal');
    return res.json();
  },

  generateActionPlan: async (codigoIbge: string): Promise<MunicipalActionPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/action-plan/generate/${encodeURIComponent(codigoIbge)}`, { method: 'POST' });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao gerar plano de ação');
    }
    return res.json();
  },

  getActionPlan: async (codigoIbge: string): Promise<MunicipalActionPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/action-plan/${encodeURIComponent(codigoIbge)}`);
    if (!res.ok) throw new Error('Nenhum plano de ação disponível');
    return res.json();
  },

  getAIProviders: async (): Promise<AIProvidersResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/assistant/providers`);
    if (!res.ok) throw new Error('Failed to load AI providers');
    return res.json();
  },

  getAIProvidersStatus: async (apiKeys: Record<string, string>): Promise<AIProvidersResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/assistant/providers/status`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_keys: apiKeys }),
    });
    if (!res.ok) throw new Error('Failed to load AI provider status');
    return res.json();
  },

  testAIProvider: async (
    aiProvider: string,
    aiApiKey?: string,
    aiModel?: string,
  ): Promise<AIProviderTestResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/assistant/providers/test`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ai_provider: aiProvider,
        ai_api_key: aiApiKey || undefined,
        ai_model: aiModel,
      }),
    });
    if (!res.ok) throw new Error('Provider test failed');
    return res.json();
  },

  searchCases: async (query: string): Promise<SuccessCase[]> => {
    const res = await api.searchCasesSemantic({ query, top_k: 10 });
    return res.items;
  },

  searchCasesSemantic: async (filters: CaseSearchFilters): Promise<CaseSearchResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/cases/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        top_k: 5,
        ...filters,
      }),
    });
    if (!res.ok) throw new Error('Cases search failed');
    return res.json();
  },

  getCaseFilters: async (): Promise<CaseFilterOptions> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/cases/filters`);
    if (!res.ok) throw new Error('Case filters failed');
    return res.json();
  },

  getCaseDetail: async (caseId: number): Promise<SuccessCase> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/cases/${caseId}`);
    if (!res.ok) throw new Error('Case detail failed');
    return res.json();
  },

  adaptCaseForMunicipio: async (caseId: number, codigoIbge: string): Promise<CaseAdaptationResult> => {
    const qs = `?codigo_ibge=${encodeURIComponent(codigoIbge)}`;
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/cases/${caseId}/adapt${qs}`, { method: 'POST' });
    if (!res.ok) throw new Error('Case adaptation failed');
    return res.json();
  },

  generateMunicipalReport: async (codigoIbge: string, force = false): Promise<MunicipalReportRecord> => {
    const qs = force ? '?force=true' : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/reports/municipal/codigo/${encodeURIComponent(codigoIbge)}${qs}`, { method: 'POST' });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao gerar relatório PDF');
    }
    return res.json();
  },

  generateCompletoReport: async (
    codigoIbge: string,
    force = false,
    asyncMode = true,
  ): Promise<ReportJobProgress | MunicipalReportRecord> => {
    const params = new URLSearchParams();
    params.set('async', String(asyncMode));
    if (force) params.set('force', 'true');
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/reports/municipal/codigo/${encodeURIComponent(codigoIbge)}/completo?${params}`,
      { method: 'POST' },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao gerar relatório completo');
    }
    return res.json();
  },

  getReportJobProgress: async (jobId: string): Promise<ReportJobProgress> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/reports/${encodeURIComponent(jobId)}/progresso`);
    if (!res.ok) throw new Error('Falha ao consultar progresso do relatório');
    return res.json();
  },

  getMunicipalReportHistory: async (codigoIbge: string): Promise<MunicipalReportRecord[]> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/reports/municipal/codigo/${encodeURIComponent(codigoIbge)}/history`);
    if (!res.ok) throw new Error('Falha ao carregar histórico de relatórios');
    return res.json();
  },

  downloadReport: async (downloadPath: string, filename = 'relatorio-sinidu-clima.pdf') => {
    const url = downloadPath.startsWith('http') ? downloadPath : `${getApiBaseUrl()}${downloadPath}`;
    const res = await apiFetch(url);
    if (!res.ok) throw new Error('Falha ao baixar relatório');
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
  },

  generateExecutiveDiagnostic: async (codigoIbge: string): Promise<ExecutiveDiagnostic> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/diagnostic/generate/${encodeURIComponent(codigoIbge)}`, { method: 'POST' });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao gerar diagnóstico executivo');
    }
    return res.json();
  },

  getExecutiveDiagnostic: async (codigoIbge: string): Promise<ExecutiveDiagnostic> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/diagnostic/${encodeURIComponent(codigoIbge)}`);
    if (!res.ok) throw new Error('Nenhum diagnóstico executivo disponível');
    return res.json();
  },

  getExecutiveDiagnosticHistory: async (codigoIbge: string): Promise<{ items: ExecutiveDiagnosticHistoryItem[] }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/diagnostic/${encodeURIComponent(codigoIbge)}/history`);
    if (!res.ok) throw new Error('Falha ao carregar histórico de diagnósticos');
    return res.json();
  },

  getPresentationData: async (codigoIbge: string): Promise<PresentationPayload> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/diagnostic/${encodeURIComponent(codigoIbge)}/presentation`);
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Apresentação indisponível — gere o diagnóstico executivo primeiro.');
    }
    return res.json();
  },

  predictFloodRisk: async (
    codigoIbge: string,
    precip24h: number,
    precip48h: number,
    precip72h: number,
  ): Promise<FloodRiskPrediction> => {
    const slug = IBGE_TO_SLUG[codigoIbge];
    if (!slug) {
      throw new Error('Análise preditiva disponível apenas para Recife, Salvador, Porto Alegre, João Pessoa e Londrina.');
    }
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/predictions/flood-risk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        municipio_id: slug,
        precip_24h: precip24h,
        precip_48h: precip48h,
        precip_72h: precip72h,
      }),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(typeof detail.detail === 'string' ? detail.detail : 'Falha na análise preditiva');
    }
    return res.json();
  },

  bootstrapFloodModels: async (): Promise<{ message: string; status: Record<string, boolean> }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/predictions/flood-risk/bootstrap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(typeof detail.detail === 'string' ? detail.detail : 'Falha ao preparar modelos ML');
    }
    return res.json();
  },

  getFloodModelStatus: async (): Promise<{ ready_count: number; total: number; models: Array<{ codigo_ibge: string; ready: boolean }> }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/predictions/flood-risk/status`);
    if (!res.ok) throw new Error('Falha ao consultar status dos modelos ML');
    return res.json();
  },

  // —— Contingência ——
  getContingencyPlans: async (codigoIbge: string): Promise<ContingencyPlan[]> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/municipio/${encodeURIComponent(codigoIbge)}`);
    if (!res.ok) throw new Error('Falha ao carregar planos');
    return res.json();
  },

  getActiveContingencyPlan: async (codigoIbge: string): Promise<ContingencyPlan | null> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/municipio/${encodeURIComponent(codigoIbge)}/ativo`);
    if (!res.ok) throw new Error('Falha ao carregar plano ativo');
    return res.json();
  },

  generateContingencyFromSimulation: async (payload: {
    codigo_ibge: string;
    cenario_tipo: string;
    risk_geojson: Record<string, unknown>;
    buffer_m?: number;
    simulacao_ref?: Record<string, unknown>;
  }): Promise<ContingencyPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/generate-from-simulation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao gerar plano');
    }
    return res.json();
  },

  saveContingencyPlan: async (planId: number, payload: Partial<ContingencyPlan>): Promise<ContingencyPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/${planId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Falha ao salvar plano');
    return res.json();
  },

  createContingencyPlan: async (payload: Partial<ContingencyPlan> & { codigo_ibge: string; cenario_tipo: string }): Promise<ContingencyPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Falha ao criar plano');
    return res.json();
  },

  activateContingencyPlan: async (planId: number): Promise<ContingencyPlan> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/${planId}/activate`, { method: 'POST' });
    if (!res.ok) throw new Error('Falha ao ativar plano');
    return res.json();
  },

  exportContingencyPdf: async (planId: number): Promise<{ download_url: string; filename: string }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/${planId}/export-pdf`, { method: 'POST' });
    if (!res.ok) throw new Error('Falha ao exportar PDF');
    return res.json();
  },

  downloadContingencyPdf: async (planId: number, filename?: string) => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/${planId}/download-pdf`);
    if (!res.ok) throw new Error('Falha ao baixar PDF');
    const blob = await res.blob();
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename || `contingencia-${planId}.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
  },

  getContingencyActionTemplates: async (cenario: string): Promise<Record<string, string[]>> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/templates/acoes?cenario_tipo=${encodeURIComponent(cenario)}`);
    if (!res.ok) throw new Error('Falha ao carregar template COBRADE');
    return res.json();
  },

  // —— Monitoramento ——
  getMonitoringDashboard: async (codigoIbge: string): Promise<MonitoringDashboard> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/monitoring/dashboard/${encodeURIComponent(codigoIbge)}`);
    if (!res.ok) throw new Error('Falha ao carregar monitoramento');
    return res.json();
  },

  getMonitoringMapOverview: async (): Promise<MonitoringMapOverview> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/monitoring/map-overview`);
    if (!res.ok) throw new Error('Falha ao carregar mapa de alertas');
    return res.json();
  },

  syncMonitoring: async (codigoIbge?: string): Promise<Record<string, unknown>> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/monitoring/sync${qs}`, { method: 'POST' });
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao sincronizar monitoramento');
    }
    return res.json();
  },

  getMonitoringAlerts: async (codigoIbge: string, hours = 24): Promise<MonitoringAlertItem[]> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/monitoring/alerts/${encodeURIComponent(codigoIbge)}?hours=${hours}`);
    if (!res.ok) throw new Error('Falha ao carregar alertas');
    return res.json();
  },

  getScenarioAnalysis: async (codigoIbge: string, force = false): Promise<ScenarioAnalysis> => {
    const qs = force ? '?force=true' : '';
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/scenario-analysis/${encodeURIComponent(codigoIbge)}${qs}`,
    );
    if (!res.ok) throw new Error('Falha na análise de cenário');
    return res.json();
  },

  getAlertInterpretation: async (codigoIbge: string, alertId: number): Promise<{ interpretacao: string }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/alert-interpretation/${encodeURIComponent(codigoIbge)}/${alertId}`,
    );
    if (!res.ok) throw new Error('Falha ao interpretar alerta');
    return res.json();
  },

  compareMonitoringMunicipalities: async (codigoA: string, codigoB: string): Promise<MonitoringCompareResult> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/compare/${encodeURIComponent(codigoA)}/${encodeURIComponent(codigoB)}`,
    );
    if (!res.ok) throw new Error('Falha na comparação');
    return res.json();
  },

  // —— Onboarding municipal ——
  listOnboardingStatus: async (): Promise<{ items: OnboardingStatus[] }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/status`);
    if (!res.ok) throw new Error('Falha ao listar onboarding');
    return res.json();
  },

  getOnboardingStatus: async (codigoIbge: string): Promise<OnboardingStatus> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/${code}`);
    if (!res.ok) throw new Error('Município não encontrado no onboarding');
    return res.json();
  },

  validateOnboarding: async (codigoIbge: string): Promise<OnboardingValidateResult> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo_ibge: code }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Código IBGE inválido');
    }
    return res.json();
  },

  runOnboarding: async (codigoIbge: string, force = false): Promise<OnboardingStatus> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo_ibge: code, force }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Falha no onboarding');
    }
    return res.json();
  },

  ensureMunicipality: async (codigoIbge: string): Promise<{
    codigo_ibge: string;
    nome: string;
    uf: string;
    municipio_id: number;
    loaded: boolean;
    already_existed?: boolean;
  }> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/ensure/${code}`, { method: 'POST' });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Falha ao carregar município no banco');
    }
    return res.json();
  },

  getMunicipalMaturity: async (codigoIbge?: string): Promise<MunicipalMaturity> => {
    const code = (codigoIbge || '2611606').replace(/\D/g, '').padStart(7, '0').slice(-7);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/maturity/${code}`);
    if (!res.ok) throw new Error('Falha ao carregar maturidade municipal');
    return res.json();
  },

  getAuthStatus: async (): Promise<AuthStatus> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/auth/status`);
    if (!res.ok) throw new Error('Falha ao verificar autenticação');
    return res.json();
  },

  login: async (username: string, password: string): Promise<LoginResult> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(typeof err.detail === 'string' ? err.detail : 'Falha no login');
    }
    const data: LoginResult = await res.json();
    setStoredToken(data.access_token);
    return data;
  },

  logout: (): void => {
    setStoredToken(null);
  },

  getMe: async (): Promise<{ username: string; role: string }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/auth/me`);
    if (!res.ok) throw new Error('Não autenticado');
    return res.json();
  },

  listAuditLog: async (params?: {
    limit?: number;
    offset?: number;
    action?: string;
    codigo_ibge?: string;
    username?: string;
  }): Promise<AuditLogEntry[]> => {
    const qs = new URLSearchParams();
    if (params?.limit != null) qs.set('limit', String(params.limit));
    if (params?.offset != null) qs.set('offset', String(params.offset));
    if (params?.action) qs.set('action', params.action);
    if (params?.codigo_ibge) qs.set('codigo_ibge', params.codigo_ibge);
    if (params?.username) qs.set('username', params.username);
    const query = qs.toString();
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/audit${query ? `?${query}` : ''}`);
    if (!res.ok) throw await httpError(res, 'Falha ao carregar auditoria');
    return res.json();
  },

  getSystemOverview: async (): Promise<SystemOverview> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/overview`);
    if (!res.ok) throw await httpError(res, 'Falha ao carregar visão do sistema');
    return res.json();
  },

  syncIntegrations: async (): Promise<IntegrationSyncResponse> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/integrations/sync`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao sincronizar integrações');
    return res.json();
  },

  getMapBiomasStatus: async (codigoIbge?: string): Promise<Record<string, unknown>> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/integrations/mapbiomas/status${qs}`);
    if (!res.ok) throw await httpError(res, 'Falha ao consultar MapBiomas');
    return res.json();
  },

  syncMapBiomas: async (codigoIbge: string, force = false): Promise<Record<string, unknown>> => {
    const qs = force ? '?force=true' : '';
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/integrations/mapbiomas/sync/${encodeURIComponent(codigoIbge)}${qs}`,
      { method: 'POST' },
    );
    if (!res.ok) throw await httpError(res, 'Falha ao sincronizar MapBiomas');
    return res.json();
  },

  syncMapBiomasBatch: async (limit = 61, force = false): Promise<Record<string, unknown>> => {
    const qs = new URLSearchParams({ limit: String(limit), force: String(force) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/integrations/mapbiomas/sync-batch?${qs}`, {
      method: 'POST',
    });
    if (!res.ok) throw await httpError(res, 'Falha no sync MapBiomas em lote');
    return res.json();
  },

  startPipelineJob: async (onboardingLimit = 61): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ onboarding_limit: String(onboardingLimit) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/pipeline?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar pipeline');
    return res.json();
  },

  startOnboardingBatchJob: async (
    limit = 61,
    status = 'pendente',
  ): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ limit: String(limit), status });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/onboarding-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar onboarding em lote');
    return res.json();
  },

  startMapBiomasBatchJob: async (
    limit = 61,
    force = false,
  ): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ limit: String(limit), force: String(force) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/mapbiomas-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar sync MapBiomas');
    return res.json();
  },

  getBackgroundJob: async (jobId: string): Promise<BackgroundJob> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/${encodeURIComponent(jobId)}`);
    if (!res.ok) throw await httpError(res, 'Job não encontrado');
    return res.json();
  },

  listBackgroundJobs: async (limit = 10): Promise<{ items: BackgroundJob[] }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs?limit=${limit}`);
    if (!res.ok) throw await httpError(res, 'Falha ao listar jobs');
    return res.json();
  },

  getRoutingStatus: async (): Promise<RoutingStatus> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/routing/status`);
    if (!res.ok) throw await httpError(res, 'Falha ao consultar OSRM');
    return res.json();
  },

  startDiagnosticsBatchJob: async (limit = 61): Promise<{ job_id: string; job: BackgroundJob }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/diagnostics-batch?limit=${limit}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar diagnósticos em lote');
    return res.json();
  },

  startReportsBatchJob: async (limit = 61, force = false): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ limit: String(limit), force: String(force) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/reports-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar PDFs em lote');
    return res.json();
  },

  startExternalSourcesBatchJob: async (limit = 61): Promise<{ job_id: string; job: BackgroundJob }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/fontes-externas-batch?limit=${limit}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao sincronizar fontes externas');
    return res.json();
  },

  startDemBatchJob: async (limit = 61, force = false): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ limit: String(limit), force: String(force) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/dem-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar batch DEM');
    return res.json();
  },

  startHomologationFullJob: async (
    onboardingLimit = 61,
    forceDem = false,
  ): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({
      onboarding_limit: String(onboardingLimit),
      force_dem: String(forceDem),
    });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/homologation-full?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar pipeline MCID completo');
    return res.json();
  },

  importLocalDem: async (
    codigoIbge: string,
    file: File,
    reprocess = true,
  ): Promise<Record<string, unknown>> => {
    const form = new FormData();
    form.append('file', file);
    const qs = reprocess ? '' : '?reprocess=false';
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/terrain/${encodeURIComponent(codigoIbge)}/import-local-dem${qs}`,
      { method: 'POST', body: form },
    );
    if (!res.ok) throw await httpError(res, 'Falha ao importar DEM local');
    return res.json();
  },

  runBatchOnboarding: async (limit = 5, status = 'pendente'): Promise<{
    requested: number;
    processed: number;
    errors: Array<{ codigo_ibge: string; error: string }>;
    items: OnboardingStatus[];
  }> => {
    const qs = new URLSearchParams({ limit: String(limit), status });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/run-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha no onboarding em lote');
    return res.json();
  },

  getOidcLoginUrl: (): string => `${getApiBaseUrl()}/api/v1/auth/oidc/login`,
};
