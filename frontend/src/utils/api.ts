/** Base da API — em homolog/proxy (HTTPS :443) usa same-origin; em dev :3000 aponta para :8000. */
export function getApiBaseUrl(): string {
  const env = process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '');
  if (typeof window === 'undefined') {
    return env || 'http://localhost:8000';
  }
  // Override explícito (ex.: demo em LAN com IP fixo)
  if (env && !env.includes('localhost')) {
    return env;
  }
  // Frontend direto na porta 3000 — API no mesmo host :8000
  // (localhost no seu Mac; IP da LAN no notebook do colega — evita apontar para o PC dele)
  if (window.location.port === '3000') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  // Proxy nginx (HTTPS/HTTP na borda) — same-origin
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

async function apiFetch(
  input: RequestInfo | URL,
  init?: RequestInit & { priority?: 'high' | 'low' | 'auto' },
): Promise<Response> {
  const headers = {
    ...authHeaders(),
    ...(init?.headers as Record<string, string> | undefined),
  };
  const { priority, ...rest } = init || {};
  const res = await fetch(input, {
    cache: 'no-store',
    ...rest,
    headers,
    // Chromium: prioriza malha do mapa sobre o painel executivo.
    ...(priority ? { priority } : {}),
  } as RequestInit);
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
    setup_hint?: string | null;
    fallback_active?: boolean;
  };
  batch_coverage?: {
    municipios_total: number;
    com_diagnostico: number;
    com_relatorio: number;
    sem_diagnostico: { codigo_ibge: string; nome: string; uf: string }[];
    sem_relatorio: { codigo_ibge: string; nome: string; uf: string }[];
    diagnosticos_ok: boolean;
    relatorios_ok: boolean;
  };
  ctm?: {
    total_alvo: number;
    fontes_cadastradas: number;
    sem_fonte: number;
    importado_prefeitura: number;
    malha_operacional: number;
    lacuna_municipios: number;
    progress_label: string;
    escopo_label: string;
  };
  homologation?: {
    score_pct: number;
    ready_for_demo?: boolean;
    ready_for_sso_test: boolean;
    ready_for_production: boolean;
    govbr_required?: boolean;
    note?: string;
    pending_count: number;
    checklist_doc: string;
    next_steps: string[];
    items: Array<{
      id: string;
      label: string;
      status: 'ok' | 'warn' | 'fail' | 'na';
      detail: string;
      group: string;
    }>;
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
  pib_total_mil_reais?: number | null;
  pib_ano?: number | null;
  pib_serie?: Array<{ ano: number; valor_mil_reais: number }> | null;
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
  idh?: number | null;
  idh_ano?: number | null;
  idh_fonte?: string | null;
  idh_qualidade?: string | null;
  atlas_uf_context?: {
    uf_sigla: string;
    uf_nome: string;
    referencia_ano: number;
    atividades_economicas: number;
    produtos: number;
    matrizes: string[];
    fonte: string;
    escopo: string;
    qualidade: string;
    portal_url: string;
    descricao: string;
    kpis?: Array<{ label: string; valor: string; hint?: string }>;
  } | null;
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
    pct_area_municipal?: number | null;
    qualidade_dado?: string;
  }[];
  estimated_timeline: {
    ano: number;
    temperatura_media: number;
    area_urbanizada_km2: number;
    pct_area_municipal?: number | null;
    qualidade_dado: string;
  }[];
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
  from_cache?: boolean;
}

export interface BairroLstCompareRow {
  bairro: string;
  lst_observada_c?: number | null;
  temp_simulada_c: number;
  delta_c?: number | null;
  faixa_calor?: string | null;
}

export interface HeatLstComparison {
  disponivel: boolean;
  municipio: string;
  uf: string;
  codigo_ibge: string;
  lst_fonte: string;
  lst_periodo: string;
  lst_mediana_c?: number | null;
  lst_max_c?: number | null;
  lst_min_c?: number | null;
  sim_temp_max_c?: number | null;
  sim_temp_mediana_c?: number | null;
  sim_delta_t_max_c?: number | null;
  divergencia_mediana_c?: number | null;
  amostras_validas: number;
  amostras_total: number;
  bairros: BairroLstCompareRow[];
  narrativa: string;
  limites_metodologicos: string[];
}

export interface SimulationJobProgress {
  job_id: string;
  type?: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  progress: number;
  stage?: string;
  stage_label?: string;
  error?: string | null;
  result?: SimulationOutput;
  comparison?: RainfallComparison;
  from_cache?: boolean;
}

export interface SimulationOutput {
  scenario_type:
    | 'Waterproofing'
    | 'VegetationLoss'
    | 'ExtremeRainfall'
    | 'DrainageDeficit'
    | 'HeatIsland'
    | 'potencial_solar_telhado'
    | 'telhado_verde_permeabilidade'
    | 'infraestrutura_verde_calor'
    | 'comparador_intervencoes'
    | 'sombra_insolacao';
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
    uncertainty_bands?: {
      precip_delta_pct?: number;
      method?: string;
      nota?: string;
      optimistic?: { precipitacao_mm?: number; max_depth_m?: number; affected_area_km2?: number; affected_population?: number; flood_patches?: number };
      expected?: { precipitacao_mm?: number; max_depth_m?: number; affected_area_km2?: number; affected_population?: number; flood_patches?: number };
      pessimistic?: { precipitacao_mm?: number; max_depth_m?: number; affected_area_km2?: number; affected_population?: number; flood_patches?: number };
    };
    mean_impermeability?: number;
    max_flow_accumulation?: number;
    dem_hydro_conditioned?: boolean;
    dem_fill_sinks?: {
      dem_hydro_conditioned?: boolean;
      cells_filled?: number;
      fill_volume_cell_m?: number;
      method?: string;
      nota?: string;
    };
    calibration?: {
      runoff_scale?: number;
      rise_scale?: number;
      river_boost_scale?: number;
      iri_scale?: number;
      source?: string;
      version?: number;
      hit_rate?: number | null;
      nota?: string;
    };
    flood_timeline?: {
      n_steps: number;
      duration_h: number;
      peak_index: number;
      peak_max_depth_m?: number;
      method?: string;
      nota?: string;
      steps: Array<{
        t_index: number;
        t_h: number;
        factor: number;
        max_depth_m: number;
        flood_patches: number;
        fase: string;
        narrativa?: string;
      }>;
    };
    flood_timeline_features?: Array<Array<{
      type: string;
      geometry: unknown;
      properties: Record<string, unknown>;
    }>>;
    drenagem_urbana?: {
      aplicado?: boolean;
      capacidade_mm_h?: number;
      removido_mm?: number;
      saturada?: boolean;
      fonte?: string | null;
      duracao_h?: number;
      nota?: string;
    };
    sombreamento_pct?: number;
    corredores_vento_pct?: number;
    shade_factor_medio?: number;
    ventilacao_factor_medio?: number;
    modulo?: string;
    indice_municipal?: number;
    nivel?: string;
    nivel_label?: string;
    temperatura_media_c?: number;
    precip_72h_mm?: number;
    nota?: string;
    bairros_exposicao?: { bairro: string; exposicao_pct: number; populacao_exposta: number }[];
    bairros_atingidos_count?: number;
    selo_confianca?: {
      selo_qualidade: string;
      nivel_confianca: string;
      dem_source?: string | null;
      dem_resolution_m?: number | null;
      vertical_accuracy_m?: number | null;
      method?: string;
      model_version?: string;
      fatores: string[];
      interpretacao: string;
      padrao?: string;
    };
    validacao_s2id?: {
      disponivel: boolean;
      fonte: string;
      qualidade: string;
      eventos_inundacao_total: number;
      eventos_com_geometria: number;
      eventos_na_mancha: number;
      hit_rate: number | null;
      bairros_historicos: string[];
      bairros_simulados: string[];
      bairros_em_comum: string[];
      jaccard_bairros: number | null;
      acordo: string;
      narrativa: string;
      limitacao: string;
    };
    exposicao_cenario?: {
      disponivel: boolean;
      motivo?: string;
      edificios_total: number;
      edificios_expostos: number;
      por_faixa: {
        superficial?: number;
        moderada?: number;
        critica?: number;
        leve?: number;
        severa?: number;
        alta?: number;
      };
      populacao_exposta: number;
      populacao_edificios_estimada?: number;
      populacao_metodo?: string;
      escolas_expostas: { n: number; matriculas: number; nomes?: string[] };
      saude_exposta: { n: number; ubs: number; hospital: number; nomes?: string[] };
      amostra?: Array<{
        id: number;
        nome?: string | null;
        uso?: string | null;
        altura_m: number;
        depth_band?: string;
        depth_m?: number;
        heat_band?: string;
        delta_t_c?: number;
        temp_local_c?: number | null;
        slope_band?: string;
        mean_slope_deg?: number;
        populacao_estimada?: number;
      }>;
      precipitacao_mm?: number | null;
      temperatura_pico_c?: number | null;
      limitacao?: string;
    };
    exposicao_deslizamento?: {
      disponivel: boolean;
      motivo?: string;
      edificios_total: number;
      edificios_expostos: number;
      por_faixa: { moderada?: number; alta?: number; critica?: number };
      populacao_edificios_estimada?: number;
      slope_threshold_deg?: number | null;
      amostra?: Array<{
        id: number;
        nome?: string | null;
        slope_band?: string;
        mean_slope_deg?: number;
        altura_m?: number;
        populacao_estimada?: number;
      }>;
      limitacao?: string;
    };
    buildings_exposed?: { type: string; features: any[] };
    buildings_landslide?: { type: string; features: any[] };
    temperatura_pico_c?: number;
    temp_pico_local_c?: number;
    baseline_normal_c?: number;
    baseline_temp_c?: number;
    baseline_temp_fonte?: string;
    heatwave_amplification?: number;
    max_delta_t_c?: number;
    faixas_contagem?: Record<string, number>;
    ganho_vegetal_pct?: number;
    perda_vegetal_pct?: number;
    impermeabilizacao_extra_pct?: number;
    resfriamento_max_c?: number;
    resfriamento_medio_c?: number;
  };
  /** Campos extras dos cenários de mitigação (solar, telhado verde, infraverde, comparador, sombra). */
  delta?: {
    area_evitada_km2?: number;
    populacao_evitada?: number;
    resfriamento_max_c?: number;
    populacao_menos_exposta?: number;
    resumo?: string;
  };
  potencia_total_mwp?: number;
  geracao_total_mwh_ano?: number;
  edificios_avaliados?: number;
  label_antes?: string;
  label_depois?: string;
  sol?: { elevacao_graus?: number; azimute_graus?: number };
  resumo?: { sombra_media?: number };
  risk_context?: BairroRiskContext[];
  from_cache?: boolean;
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
  from_cache?: boolean;
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
  georedus_url?: string;
  georedus_indicadores?: { id: string; label: string; group: string; source: string; description: string; sinidu_layer?: string | null }[];
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
  recommended_layers?: string[];
  crosswalk_rationale?: string;
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
  status: 'Integrado' | 'Estimado' | 'Em integracao' | 'Ausente' | 'Nao aplicavel';
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
  /** 17c.3 — presente quando id === 'gemeo_digital_3d' */
  modelo_3d?: {
    lod?: string;
    maturidade_3d_pct?: number;
    por_fonte_altura?: Record<string, number>;
    por_qualidade?: Record<string, number>;
    fonte_altura_predominante?: string | null;
    especificacao?: string;
    tileset_url?: string | null;
    cityjson_url?: string | null;
    citygml_url?: string | null;
  };
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

export interface InstitutionalGapNationalRow {
  rank: number;
  fonte_id: string;
  nome: string;
  total_municipios: number;
  integrado_count: number;
  integrado_pct: number;
  lacuna_municipios: number;
  status_totals: Record<string, number>;
  etl_ready: boolean;
  impacto_score_pts?: number;
  dificuldade?: string;
  requisito?: string;
  proxy_ativo?: boolean;
  progress_label: string;
  ctm_cadastrada_count?: number;
  ctm_sem_fonte_count?: number;
  ctm_por_kind?: Record<string, number>;
  malha_operacional_count?: number;
  importado_prefeitura_count?: number;
  escopo_label?: string;
}

export interface InstitutionalGapsNational {
  total_municipios: number;
  gaps: InstitutionalGapNationalRow[];
  meta_maturidade: {
    baseline_pct: number;
    target_pct: number;
    label: string;
  };
  etl_ready_fontes: number;
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

export type ActionExecutionStatus = 'planejada' | 'em_andamento' | 'executada' | 'cancelada';

export interface ActionExecutionEntry {
  action_id: string;
  status: ActionExecutionStatus;
  nota?: string;
  responsavel?: string;
  atualizado_em?: string;
}

export interface ActionReavaliacao {
  em: string;
  score_antes?: number | null;
  score_depois?: number | null;
  delta_score?: number | null;
  nivel?: string;
  nota?: string | null;
  acao_sugerida?: string;
}

export interface ActionAcompanhamento {
  acoes?: Record<string, ActionExecutionEntry>;
  reavaliacoes?: ActionReavaliacao[];
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
  acompanhamento?: ActionAcompanhamento;
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
  mm_acima_limiar?: number;
  top_features?: Array<{ feature: string; importance: number }>;
  explanation?: {
    disponivel: boolean;
    method: string;
    domains: Array<{
      id: string;
      label: string;
      importance_share: number;
      contribution: number;
      contribution_pct: number;
      importance_pct: number;
    }>;
    top_features?: Array<{ feature: string; importance: number; domain?: string }>;
    narrativa?: string;
    nota?: string;
  } | null;
  impact?: {
    disponivel: boolean;
    nivel_operacional?: string;
    n_bairros_prioritarios?: number;
    bairros_prioritarios?: Array<{
      bairro_id: number;
      bairro_nome: string;
      risk_probability: number;
      populacao_bairro?: number | null;
      populacao_exposta_estimada?: number | null;
    }>;
    populacao_municipio?: number | null;
    populacao_exposta_estimada?: number | null;
    pct_populacao_exposta?: number | null;
    porte?: string | null;
    capag_nota?: string | null;
    medidas_cabiveis?: Array<{
      id?: string;
      titulo?: string;
      custo?: string;
      horizonte?: string;
      prioridade?: string;
      orgao?: string;
      motivo?: string;
    }>;
    narrativa?: string;
    nota?: string;
  } | null;
  horizons?: Array<{
    horizon: string;
    horizon_d: number;
    risk_probability: number;
    ci_low?: number;
    ci_high?: number;
    precip_24h_mm?: number;
    uncertainty_method?: string;
  }> | null;
  uncertainty?: {
    ci_low: number;
    ci_high: number;
    std?: number;
    method?: string;
    confidence_level?: number;
    nota?: string;
  } | null;
  critical_neighborhoods: CriticalNeighborhood[];
  flood_geojson: { features?: unknown[] } | null;
  model_version: string;
  model_kind?: string;
  data_quality: string;
  score_kind?: string | null;
  production_ready?: boolean | null;
  features_used?: Record<string, number> | null;
  model_auc_roc?: number | null;
  disclaimer: string;
}

export interface ContingencyRecurso {
  tipo: string;
  nome: string;
  quantidade?: number;
  capacidade_pessoas?: number | null;
  fonte?: string;
}

export interface ContingencyProtocoloPasso {
  ordem: number;
  quando: string;
  quem: string;
  o_que: string;
  sla_minutos?: number;
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
  recursos_operacionais?: ContingencyRecurso[];
  protocolo_campo?: {
    canais?: string[];
    passos?: ContingencyProtocoloPasso[];
    checklist_campo?: string[];
    cobrade?: { codigo?: string; label?: string; grupo?: string };
  };
  cobrade_codigo?: string | null;
  cobrade?: { codigo?: string; label?: string; grupo?: string };
  status: string;
  versao: number;
  simulacao_ref?: Record<string, unknown>;
}

export interface MonitoringAcertoPrevisoes {
  disponivel: boolean;
  codigo_ibge?: string;
  n_verificadas: number;
  n_pendentes: number;
  lookback?: number;
  acerto_pct: number | null;
  acertos?: number;
  amostra_suficiente?: boolean;
  limiar_risco?: number;
  narrativa?: string;
  nota?: string;
  protocol?: string;
}

export interface ForecastSourceSeal {
  selo_qualidade: string;
  fonte_chuva: string;
  risk_source: string;
  score_kind: string;
  label_ui: string;
  narrativa: string;
  disclaimer: string;
  precip_forecast_mm?: number | null;
  precip_for_risk_mm?: number | null;
  cemaden_obs_mm?: number | null;
  cemaden_estacoes?: number | null;
  usou_chuva_observada?: boolean;
  protocol?: string;
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
  risk_source?: string | null;
  score_kind?: string | null;
  cemaden_obs_mm?: number | null;
  cemaden_estacoes?: number | null;
  selo_previsao?: ForecastSourceSeal | null;
  weather_updated_at: string | null;
  weather_disponivel?: boolean;
  timeline: MonitoringAlertItem[];
  timeline_grouped?: MonitoringTimelineGroupItem[];
  plano_ativo: ContingencyPlan | null;
  acerto_previsoes?: MonitoringAcertoPrevisoes | null;
}

/** Overlay de sensores/alertas vivos no gêmeo 3D (17e.3). */
export type LiveSensorsGeoJSON = {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: { type: 'Point'; coordinates: [number, number] };
    properties: Record<string, unknown>;
  }>;
  meta?: {
    codigo_ibge?: string;
    municipio?: string;
    uf?: string;
    count?: number;
    cemaden_camada?: number;
    cemaden_vivo?: number;
    estacoes?: number;
    nivel_alerta?: string;
    vivo?: boolean;
    titulo_recente?: string | null;
  };
};

/** POIs críticos no gêmeo 3D (17f.3). */
export type CriticalPoisGeoJSON = {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: { type: 'Point'; coordinates: [number, number] };
    properties: Record<string, unknown>;
  }>;
  meta?: {
    codigo_ibge?: string;
    municipio?: string;
    uf?: string;
    count?: number;
    por_categoria?: {
      escola?: number;
      saude?: number;
      abrigo?: number;
      equipamento?: number;
    };
  };
};

/** Contexto urbano 3D — hidrografia/vias/curvas (17f.6). */
export type UrbanContextGeoJSON = {
  type: 'FeatureCollection';
  features: Array<{
    type: 'Feature';
    geometry: { type: string; coordinates: unknown };
    properties: Record<string, unknown>;
  }>;
  meta?: {
    codigo_ibge?: string;
    municipio?: string;
    uf?: string;
    count?: number;
    por_contexto?: {
      hidrografia?: number;
      via?: number;
      curva?: number;
    };
  };
};

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

export interface PublicAlertCanal {
  id: string;
  label: string;
  disponivel: boolean;
  status_default?: string;
  itens?: string[];
  destinos?: Array<{ nome: string; cargo?: string; telefone?: string; url: string }>;
  nota?: string;
  url_configurada?: boolean;
}

export interface PublicAlertDraft {
  codigo_ibge: string;
  nome: string;
  uf: string;
  nivel_sugerido: string;
  alerta_vivo?: {
    nivel_alerta?: string;
    vivo?: boolean;
    fonte?: string;
    titulo_recente?: string | null;
  };
  mensagem: string;
  canais: PublicAlertCanal[];
  contingency_plan_id?: number | null;
  nota?: string;
}

export interface PublicAlertDispatchResult {
  id: number;
  codigo_ibge: string;
  nome: string;
  uf: string;
  nivel: string;
  mensagem: string;
  canais: string[];
  status_por_canal: Record<string, { status?: string; [key: string]: unknown }>;
  destinos?: Array<{ nome: string; cargo?: string; telefone?: string; url: string }>;
  contingency_plan_id?: number | null;
  created_at?: string | null;
  tipo?: string;
}

export interface PublicAlertHistoryItem {
  id: number;
  nivel: string;
  titulo: string;
  mensagem?: string;
  canais: string[];
  status_por_canal: Record<string, unknown>;
  destinos?: Array<{ nome: string; url: string }>;
  criado_por?: string;
  created_at?: string | null;
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

export interface GeoportalPublicacao {
  id: number;
  tipo: string;
  titulo: string;
  url?: string | null;
  arquivo_nome?: string | null;
  feature_count?: number | null;
  status: string;
  mensagem?: string | null;
  ativo: boolean;
  publicado_em?: string | null;
  importado_em?: string | null;
}

export interface GeoportalStatus {
  codigo_ibge: string;
  municipio: { nome: string; uf: string };
  bairros_count: number;
  malha_fonte?: string | null;
  publicacao_ativa?: GeoportalPublicacao | null;
  ctm_registry: {
    disponivel: boolean;
    nome?: string | null;
    tipo?: string | null;
    url?: string | null;
    nota?: string | null;
  };
  catalog_status: string;
  acoes_sugeridas: string[];
  formatos_aceitos: string[];
  tipos_api: string[];
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

export type RiskNivel = 'VERDE' | 'AMARELO' | 'LARANJA' | 'VERMELHO';

export interface RiskPanelComponent {
  id: string;
  nome: string;
  valor: number | null;
  escala: string;
  nivel: RiskNivel;
  label: string;
  qualidade: string;
  detalhe: string;
}

export interface RiskPanelFator {
  id: string;
  nome: string;
  valor: number | string | null;
  unidade: string;
  score: number;
  contribuicao: number;
  detalhe: string;
}

export interface RiskPanelExposicao {
  populacao: number;
  escolas: { n: number; matriculas: number };
  saude: { n: number; ubs: number; hospital: number; outros: number };
  territorios_especiais: { n: number; tipos: string[]; populacao_estimada: number };
  bairros_criticos?: number;
  limiar_score?: number;
}

export interface RiskPanelBairro {
  bairro: string;
  bairro_id?: number;
  score_sinidu: number;
  ivc: number;
  iri: number;
  nivel: RiskNivel;
  label: string;
  componentes?: Record<string, number>;
  fatores?: RiskPanelFator[];
  fatores_principais?: string[];
  exposicao?: RiskPanelExposicao;
}

export interface RiskPanelModoBaixaMaturidade {
  ativo: boolean;
  aviso: string;
  motivos: string[];
  maturidade_tier: string;
  maturidade_score: number;
  cobertura_percentual: number;
  cobertura_classificacao: string;
  onboarding_status: string;
  fontes_nacionais: string[];
}

export interface RiskPanelPerfil {
  codigo_ibge: string;
  nome: string;
  uf: string;
  populacao: number;
  porte: string;
  porte_label: string;
  capag: {
    nota: string | null;
    status?: string;
    interpretacao: string;
  };
  plano_diretor: {
    status: string;
    fontes_cadastradas: number;
    titulos?: string[];
  };
  defesa_civil: {
    sinal: string;
    tem_gasto_registrado: boolean;
    proxy?: string;
  };
  restricoes: string[];
  maturidade_tier?: string;
  maturidade_score?: number;
}

export interface RiskPanelFonteFinanciamento {
  id: string;
  nome: string;
  orgao: string;
  unidade?: string;
  site?: string;
  contato?: string;
  elegibilidade?: string;
  tipo: string;
  motivo: string;
  viabilidade: string;
}

export interface RiskPanelMedida {
  id: string;
  titulo: string;
  descricao: string;
  tipo_risco: string;
  horizonte: string;
  custo: string;
  prioridade: string;
  orgao: string;
  fonte: string;
  bairros_alvo: string[];
  motivo: string;
  fontes_financiamento?: RiskPanelFonteFinanciamento[];
}

export interface RiskPanelHotspot {
  bairro: string;
  bairro_id?: number;
  eventos_s2id: number;
  iri: number;
  na_mancha_sim_120mm?: boolean;
  prioridade: number;
  motivo: string;
}

export interface RiskPanelHotspots {
  codigo_ibge?: string;
  total: number;
  hotspots: RiskPanelHotspot[];
  nota?: string;
  criterio?: {
    min_eventos_s2id?: number;
    iri_min?: number;
    ou_na_mancha_sim_mm?: number;
  };
}

export interface RiskPanelResponse {
  codigo_ibge: string;
  nome: string;
  uf: string;
  status: RiskNivel;
  status_label: string;
  acao_sugerida: string;
  componentes: {
    score: RiskPanelComponent;
    ivc: RiskPanelComponent;
    iri: RiskPanelComponent;
    vm: RiskPanelComponent;
    alerta: RiskPanelComponent;
    ml_preditivo?: RiskPanelComponent;
  };
  modelo_risco?: {
    versao?: string;
    nome?: string;
    regra_status?: string;
    nota?: string;
  };
  bairros: RiskPanelBairro[];
  bairros_total: number;
  exposicao_resumo?: RiskPanelExposicao;
  hotspots_recorrentes?: RiskPanelHotspots;
  modo_baixa_maturidade: RiskPanelModoBaixaMaturidade;
  perfil?: RiskPanelPerfil;
  medidas_recomendadas?: RiskPanelMedida[];
  snapshot: {
    score_sinidu?: number;
    media_ivc?: number;
    media_iri?: number;
    media_adaptacao?: number;
    alertas_ativos_count?: number;
    historico_desastres_count?: number;
    populacao?: number;
  };
  validacao_adapta_brasil?: {
    disponivel: boolean;
    fonte?: string;
    qualidade?: string;
    adapta_score?: number | null;
    media_adaptacao_sinidu?: number | null;
    delta?: number | null;
    acordo?: 'alta' | 'media' | 'baixa' | 'insuficiente' | string;
    narrativa?: string;
    limitacao?: string;
  };
  ciclo: string;
  versao: string;
}

export interface MunicipalRankItem {
  posicao: number;
  codigo_ibge: string;
  nome: string;
  uf: string;
  valor: number | string | null;
  score_sinidu?: number | null;
  media_ivc?: number | null;
  media_iri?: number | null;
  media_adaptacao?: number | null;
  nota_capag?: string | null;
  populacao?: number | null;
}

export interface MunicipalRankResponse {
  criterio: string;
  criterio_label: string;
  higher_is_worse: boolean;
  format: string;
  total: number;
  uf?: string | null;
  items: MunicipalRankItem[];
  nota?: string;
  criterios_disponiveis?: string[];
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

  getLayerGeoJSON: async (
    layerName: string,
    codigoIbge?: string,
    extraParams?: Record<string, string | number | boolean>,
  ): Promise<any> => {
    const params = new URLSearchParams();
    if (codigoIbge) params.set('codigo_ibge', codigoIbge);
    if (extraParams) {
      Object.entries(extraParams).forEach(([key, value]) => {
        if (value !== '' && value != null) {
          params.set(key, String(value));
        }
      });
    }
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/layers/${layerName}${qs}`, {
      priority: 'high',
    });
    if (!res.ok) throw new Error(`Failed to load layer: ${layerName}`);
    return res.json();
  },

  getLayersTemporalOptions: async (codigoIbge?: string): Promise<import('@/config/layerTemporal').TemporalOptionsResponse> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/layers/temporal-options${qs}`);
    if (!res.ok) throw new Error('Failed to load temporal options');
    return res.json();
  },

  getRegionalOverlay: async (
    codigoIbge?: string,
    escopo: 'regiao_imediata' | 'mesorregiao' = 'regiao_imediata',
  ) => {
    const params = new URLSearchParams();
    if (codigoIbge) params.set('codigo_ibge', codigoIbge);
    params.set('escopo', escopo);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/indicators/regional-overlay?${params}`);
    if (!res.ok) throw new Error('Falha ao carregar overlay regional');
    return res.json();
  },

  getExternalRastersCatalog: async (codigoIbge?: string): Promise<{
    provider: string;
    tile_server_pattern: string;
    layers: {
      layer_id: string;
      label: string;
      quality: string;
      source: string;
      description: string;
      status: string;
      provider: string;
      min_zoom: number;
      max_zoom: number;
      unit: string;
      periodo_label: string;
      georedus_url: string;
      default_rescale: { min: number; max: number };
      rescale_bounds: { min: number; max: number };
      colormap: string;
    }[];
  }> => {
    const qs = codigoIbge ? `?codigo_ibge=${encodeURIComponent(codigoIbge)}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/map/external-rasters${qs}`);
    if (!res.ok) throw new Error('Falha ao carregar catálogo raster externo');
    return res.json();
  },

  getExternalRasterConfig: async (
    layerId: string,
    codigoIbge?: string,
    rescaleMin?: number,
    rescaleMax?: number,
    ano?: number,
  ): Promise<{
    layer_id: string;
    label: string;
    quality: string;
    source: string;
    description: string;
    tile_url_template: string;
    min_zoom: number;
    max_zoom: number;
    rescale_min: number;
    rescale_max: number;
    rescale_min_c?: number;
    rescale_max_c?: number;
    unit: string;
    colormap: string;
    attribution: string;
    georedus_url: string;
    provider: string;
    supports_point_query: boolean;
  }> => {
    const params = new URLSearchParams();
    if (codigoIbge) params.set('codigo_ibge', codigoIbge);
    if (rescaleMin != null) params.set('rescale_min', String(rescaleMin));
    if (rescaleMax != null) params.set('rescale_max', String(rescaleMax));
    if (ano != null) params.set('ano', String(ano));
    const qs = params.toString() ? `?${params.toString()}` : '';
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/map/external-rasters/${encodeURIComponent(layerId)}/config${qs}`,
    );
    if (!res.ok) throw new Error(`Falha ao carregar raster externo: ${layerId}`);
    return res.json();
  },

  getLstObservadaConfig: async (
    codigoIbge?: string,
    rescaleMin?: number,
    rescaleMax?: number,
    ano?: number,
  ): Promise<{
    layer_id: string;
    label: string;
    quality: string;
    source: string;
    description: string;
    tile_url_template: string;
    min_zoom: number;
    max_zoom: number;
    rescale_min_c: number;
    rescale_max_c: number;
    colormap: string;
    attribution: string;
    georedus_url: string;
  }> => {
    const cfg = await api.getExternalRasterConfig('lst_observada', codigoIbge, rescaleMin, rescaleMax, ano);
    return {
      ...cfg,
      rescale_min_c: cfg.rescale_min_c ?? cfg.rescale_min,
      rescale_max_c: cfg.rescale_max_c ?? cfg.rescale_max,
    };
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
      descricao?: string;
      count?: number;
      fontes_catalogo?: { id: string; nome: string; descricao_curta?: string }[];
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

  getRiskPanel: async (codigoIbge?: string, topBairros = 8): Promise<RiskPanelResponse> => {
    const params = new URLSearchParams();
    if (codigoIbge) params.set('codigo_ibge', codigoIbge);
    params.set('top_bairros', String(topBairros));
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/risk-panel?${params}`);
    if (!res.ok) throw await httpError(res, 'Falha ao carregar painel de risco');
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

  rankMunicipalities: async (opts: {
    criterio?: string;
    uf?: string;
    codigos?: string[];
    limit?: number;
  }): Promise<MunicipalRankResponse> => {
    const params = new URLSearchParams();
    if (opts.criterio) params.set('criterio', opts.criterio);
    if (opts.uf) params.set('uf', opts.uf);
    if (opts.codigos?.length) params.set('codigos', opts.codigos.join(','));
    if (opts.limit) params.set('limit', String(opts.limit));
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/rank?${params}`);
    if (!res.ok) throw await httpError(res, 'Falha ao ranquear municípios');
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

  getInstitutionalGapsNational: async (): Promise<InstitutionalGapsNational> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/data-catalog/institutional-gaps`);
    if (!res.ok) throw await httpError(res, 'Falha ao carregar lacunas institucionais');
    return res.json();
  },

  getCtmInventory: async (probe = false): Promise<{
    registry: {
      total_alvo: number;
      fontes_cadastradas: number;
      sem_fonte: number;
      por_kind: Record<string, number>;
    };
    resumo: string;
  }> => {
    const qs = probe ? '?probe=1' : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/data-catalog/ctm-inventory${qs}`);
    if (!res.ok) throw await httpError(res, 'Falha ao carregar inventário CTM');
    return res.json();
  },

  getSingedlabExposure: async (codigoIbge: string): Promise<Record<string, unknown>> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/data-catalog/singedlab/${encodeURIComponent(codigoIbge)}`,
    );
    if (!res.ok) throw await httpError(res, 'Falha ao carregar exposição SINGED Lab');
    return res.json();
  },

  importSingedlabCsv: async (
    file: File,
    syncDb = true,
  ): Promise<{
    filename: string;
    imported_municipios: number;
    codigos_ibge: string[];
    target_csv: string;
    sync?: { requested: number; processed: number; errors: unknown[] };
  }> => {
    const form = new FormData();
    form.append('file', file);
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/data-catalog/singedlab/import-csv?sync_db=${syncDb ? 'true' : 'false'}`,
      { method: 'POST', body: form },
    );
    if (!res.ok) throw await httpError(res, 'Falha ao importar CSV SINGED Lab');
    return res.json();
  },

  syncSingedlabAll: async (): Promise<{ requested: number; processed: number; errors: unknown[] }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/data-catalog/singedlab/sync-all`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao sincronizar SINGED Lab');
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

  simulateSolarRooftop: async (codigoIbge?: string, limit = 3500): Promise<SimulationOutput & {
    potencia_total_kwp?: number;
    potencia_total_mwp?: number;
    geracao_total_mwh_ano?: number;
    edificios_avaliados?: number;
    top_edificios?: Array<{ id: number; nome?: string; potencia_kwp: number; geracao_kwh_ano: number; area_telhado_m2: number }>;
    parametros?: Record<string, unknown>;
  }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/solar-rooftop`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo_ibge: codigoIbge, limit }),
    });
    if (!res.ok) throw new Error('Simulação de potencial solar falhou');
    return res.json();
  },

  simulateGreenRoof: async (params: {
    codigoIbge?: string;
    precipitacaoMm?: number;
    telhadoVerdePct?: number;
  }): Promise<SimulationOutput & {
    delta?: {
      area_evitada_km2?: number;
      populacao_evitada?: number;
      impermeabilidade_delta?: number;
    };
    baseline?: { affected_area_km2?: number; affected_population?: number; max_depth_m?: number };
    mitigated?: { affected_area_km2?: number; affected_population?: number; max_depth_m?: number };
    parametros?: Record<string, unknown>;
  }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/green-roof`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: params.codigoIbge,
        precipitacao_mm: params.precipitacaoMm ?? 100,
        telhado_verde_pct: params.telhadoVerdePct ?? 30,
      }),
    });
    if (!res.ok) throw new Error('Simulação de telhado verde falhou');
    return res.json();
  },

  simulateGreenInfraHeat: async (params: {
    codigoIbge?: string;
    temperaturaPicoC?: number;
    arborizacaoPct?: number;
  }): Promise<SimulationOutput & {
    delta?: { resfriamento_max_c?: number; populacao_menos_exposta?: number };
    ranking_bairros?: Array<{ bairro: string; resfriamento_c: number; delta_t_antes_c: number; delta_t_depois_c: number }>;
  }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/green-infra-heat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: params.codigoIbge,
        temperatura_pico_c: params.temperaturaPicoC ?? 36,
        arborizacao_pct: params.arborizacaoPct ?? 25,
      }),
    });
    if (!res.ok) throw new Error('Simulação infraverde × calor falhou');
    return res.json();
  },

  compareInterventions: async (params: {
    codigoIbge?: string;
    tipo?: 'telhado_verde' | 'infraverde_calor' | 'solar';
    precipitacaoMm?: number;
    telhadoVerdePct?: number;
    temperaturaPicoC?: number;
    arborizacaoPct?: number;
  }): Promise<SimulationOutput & {
    tipo?: string;
    label_antes?: string;
    label_depois?: string;
    delta?: { resumo?: string; [key: string]: unknown };
    baseline?: Record<string, unknown>;
    scenario?: Record<string, unknown>;
  }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/interventions/compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: params.codigoIbge,
        tipo: params.tipo ?? 'telhado_verde',
        precipitacao_mm: params.precipitacaoMm ?? 100,
        telhado_verde_pct: params.telhadoVerdePct ?? 30,
        temperatura_pico_c: params.temperaturaPicoC ?? 36,
        arborizacao_pct: params.arborizacaoPct ?? 25,
      }),
    });
    if (!res.ok) throw new Error('Comparador de intervenções falhou');
    return res.json();
  },

  simulateShadowInsolation: async (params: {
    codigoIbge?: string;
    horaLocal?: number;
  }): Promise<SimulationOutput & {
    sol?: { elevacao_graus?: number; azimute_graus?: number };
    resumo?: { insolacao_media?: number; sombra_media?: number; faixas?: Record<string, number> };
  }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/shadow-insolation`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: params.codigoIbge,
        hora_local: params.horaLocal ?? 14,
      }),
    });
    if (!res.ok) throw new Error('Simulação de sombra/insolação falhou');
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

  simulateHeatIsland: async (
    params: {
      temperaturaPicoC?: number;
      perdaVegetalPct?: number;
      ganhoVegetalPct?: number;
      impermeabilizacaoExtraPct?: number;
      sombreamentoPct?: number;
      corredoresVentoPct?: number;
      codigoIbge?: string;
    },
  ): Promise<SimulationOutput> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/heat-island`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        temperatura_pico_c: params.temperaturaPicoC ?? 34,
        perda_vegetal_pct: params.perdaVegetalPct ?? 0,
        ganho_vegetal_pct: params.ganhoVegetalPct ?? 0,
        impermeabilizacao_extra_pct: params.impermeabilizacaoExtraPct ?? 15,
        sombreamento_pct: params.sombreamentoPct ?? 0,
        corredores_vento_pct: params.corredoresVentoPct ?? 0,
        codigo_ibge: params.codigoIbge,
      }),
    });
    if (!res.ok) throw new Error('Heat island simulation failed');
    return res.json();
  },

  compareHeatLst: async (
    simulation: SimulationOutput,
    codigoIbge?: string,
  ): Promise<HeatLstComparison> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/heat-lst-compare`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: codigoIbge,
        simulation,
      }),
    });
    if (!res.ok) throw new Error('Falha na comparação LST × simulação');
    return res.json();
  },

  getIdfCurves: async (codigoIbge: string): Promise<{
    codigo_ibge: string;
    fonte: string;
    qualidade: string;
    default_duracao_min: number;
    curvas: Array<{
      periodo_retorno_anos: number;
      duracao_min: number;
      precipitacao_mm: number;
      intensidade_mm_h: number;
      label: string;
    }>;
  }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/simulations/idf/${encodeURIComponent(codigoIbge)}`,
    );
    if (!res.ok) throw await httpError(res, 'Falha ao carregar curvas IDF');
    return res.json();
  },

  simulateExtremeRainfall: async (
    mm: number,
    codigoIbge?: string,
    opts?: { periodoRetornoAnos?: number; duracaoMin?: number },
  ): Promise<SimulationOutput> => {
    const body: Record<string, unknown> = {
      precipitacao_mm: mm,
      codigo_ibge: codigoIbge,
    };
    if (opts?.periodoRetornoAnos != null) body.periodo_retorno_anos = opts.periodoRetornoAnos;
    if (opts?.duracaoMin != null) body.duracao_min = opts.duracaoMin;
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/extreme-rainfall`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
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

  pollSimulationJob: async (
    jobId: string,
    onProgress?: (progress: SimulationJobProgress) => void,
    intervalMs = 900,
  ): Promise<SimulationJobProgress> => {
    for (;;) {
      const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/jobs/${jobId}`);
      if (!res.ok) throw new Error('Falha ao consultar job de simulação');
      const data: SimulationJobProgress = await res.json();
      onProgress?.(data);
      if (data.status === 'completed') return data;
      if (data.status === 'failed') {
        throw new Error(data.error || 'Simulação falhou');
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  },

  getSeaLevelScenarios: async (codigoIbge: string): Promise<{
    costeiro: boolean;
    nivel_mar_m: number;
    cenarios_disponiveis?: Array<{ id: string; label: string; nivel_mar_m: number }>;
    nota?: string;
  }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/simulations/sea-level/${encodeURIComponent(codigoIbge)}`,
    );
    if (!res.ok) throw await httpError(res, 'Falha ao carregar cenários de nível do mar');
    return res.json();
  },

  getDrainageCapacity: async (
    codigoIbge: string,
    precipMm = 120,
    duracaoMin = 60,
  ): Promise<{
    capacidade_mm_h: number;
    removido_mm: number;
    saturada: boolean;
    fonte?: string | null;
    aplicado?: boolean;
    nota?: string;
  }> => {
    const params = new URLSearchParams({
      precip_mm: String(precipMm),
      duracao_min: String(duracaoMin),
    });
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/simulations/drainage-capacity/${encodeURIComponent(codigoIbge)}?${params}`,
    );
    if (!res.ok) throw await httpError(res, 'Falha ao carregar capacidade de drenagem');
    return res.json();
  },

  downloadFieldReportPdf: async (codigoIbge: string): Promise<Blob> => {
    const params = new URLSearchParams({ codigo_ibge: codigoIbge });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/analytics/risk-panel/field-report.pdf?${params}`);
    if (!res.ok) throw await httpError(res, 'Falha ao gerar ficha de campo');
    return res.blob();
  },

  simulateExtremeRainfallAsync: async (
    mm: number,
    codigoIbge?: string,
    onProgress?: (progress: SimulationJobProgress) => void,
    opts?: {
      periodoRetornoAnos?: number;
      duracaoMin?: number;
      cenarioNivelMar?: string;
      nivelMarM?: number;
      chuvaAntecedenteMm?: number;
      aplicarDrenagem?: boolean;
      drainageCapacityMmH?: number;
    },
  ): Promise<SimulationOutput> => {
    const body: Record<string, unknown> = {
      precipitacao_mm: mm,
      codigo_ibge: codigoIbge,
    };
    if (opts?.periodoRetornoAnos != null) body.periodo_retorno_anos = opts.periodoRetornoAnos;
    if (opts?.duracaoMin != null) body.duracao_min = opts.duracaoMin;
    if (opts?.cenarioNivelMar) body.cenario_nivel_mar = opts.cenarioNivelMar;
    if (opts?.nivelMarM != null) body.nivel_mar_m = opts.nivelMarM;
    if (opts?.chuvaAntecedenteMm != null) body.chuva_antecedente_mm = opts.chuvaAntecedenteMm;
    if (opts?.aplicarDrenagem != null) body.aplicar_drenagem = opts.aplicarDrenagem;
    if (opts?.drainageCapacityMmH != null) body.drainage_capacity_mm_h = opts.drainageCapacityMmH;
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/extreme-rainfall/async`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error('Extreme rainfall simulation failed');
    const { job_id } = await res.json();
    const finished = await api.pollSimulationJob(job_id, onProgress);
    if (!finished.result) throw new Error('Job concluído sem resultado');
    return finished.result;
  },

  /** Pré-aquece cache da simulação pluvial em background (não bloqueia UI). */
  prewarmExtremeRainfall: async (mm = 120, codigoIbge?: string): Promise<{ codigo_ibge: string; scheduled: unknown[] }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/extreme-rainfall/prewarm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ precipitacao_mm: mm, codigo_ibge: codigoIbge }),
      priority: 'low',
    });
    if (!res.ok) throw new Error('Falha ao agendar pré-aquecimento da simulação');
    return res.json();
  },

  compareRainfallScenariosAsync: async (
    scenarioMm: number,
    baselineMm: number = 80,
    codigoIbge?: string,
    onProgress?: (progress: SimulationJobProgress) => void,
  ): Promise<RainfallComparison> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/extreme-rainfall/compare/async`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        baseline_mm: baselineMm,
        scenario_mm: scenarioMm,
        codigo_ibge: codigoIbge,
      }),
    });
    if (!res.ok) throw new Error('Rainfall comparison failed');
    const { job_id } = await res.json();
    const finished = await api.pollSimulationJob(job_id, onProgress);
    if (!finished.comparison) throw new Error('Job concluído sem comparação');
    return finished.comparison;
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

  simulateClimateModule: async (opts: {
    codigoIbge?: string;
    modo: 'seca' | 'arbovirus';
    precip72hMm?: number;
    precipEsperada72hMm?: number;
    temperaturaMediaC?: number;
    precip7dMm?: number;
  }): Promise<SimulationOutput> => {
    const body: Record<string, unknown> = {
      codigo_ibge: opts.codigoIbge,
      modo: opts.modo,
    };
    if (opts.precip72hMm != null) body.precip_72h_mm = opts.precip72hMm;
    if (opts.precipEsperada72hMm != null) body.precip_esperada_72h_mm = opts.precipEsperada72hMm;
    if (opts.temperaturaMediaC != null) body.temperatura_media_c = opts.temperaturaMediaC;
    if (opts.precip7dMm != null) body.precip_7d_mm = opts.precip7dMm;
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/climate-modules`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw await httpError(res, 'Falha no módulo climático');
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
      tipo_simulacao: 'chuva' | 'asfalto' | 'vegetacao' | 'drenagem' | 'calor';
      parametro_atual: number;
      parametro_referencia?: number;
      resultado_simulacao: SimulationOutput;
      resultado_referencia?: SimulationOutput;
      comparacao_delta?: RainfallComparison['delta'];
      lst_comparison?: HeatLstComparison;
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

  exportSimulationKmz: async (
    simulation: SimulationOutput,
    codigoIbge?: string,
    comparisonDelta?: RainfallComparison['delta'],
  ): Promise<{ download_url: string; nome_arquivo: string }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/export/kmz`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        codigo_ibge: codigoIbge,
        simulation,
        comparison_delta: comparisonDelta ?? null,
      }),
    });
    if (!res.ok) throw await httpError(res, 'Exportação KMZ falhou');
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

  patchActionStatus: async (
    codigoIbge: string,
    actionId: string,
    payload: { status: ActionExecutionStatus; nota?: string; responsavel?: string },
  ): Promise<MunicipalActionPlan> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/action-plan/${encodeURIComponent(codigoIbge)}/acoes/${encodeURIComponent(actionId)}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao atualizar status da ação');
    }
    return res.json();
  },

  reavaliarActionPlan: async (
    codigoIbge: string,
    nota?: string,
  ): Promise<{
    plano: MunicipalActionPlan;
    reavaliacao: ActionReavaliacao;
    risk_panel_resumo: { status?: string; status_label?: string; score_sinidu?: number | null };
  }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/action-plan/${encodeURIComponent(codigoIbge)}/reavaliar`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nota }),
      },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao reavaliar risco');
    }
    return res.json();
  },

  buildMethodNote: async (payload: {
    tipo?: string;
    codigo_ibge?: string;
    simulation_meta?: Record<string, unknown>;
    format?: 'json' | 'markdown';
  }): Promise<{ titulo: string; markdown: string; secoes: Array<{ id: string; titulo: string; corpo: string }> } | string> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/simulations/method-note`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Falha ao gerar nota metodológica');
    if (payload.format === 'markdown') return res.text();
    return res.json();
  },

  getHydroCalibration: async (codigoIbge: string): Promise<{
    codigo_ibge: string;
    runoff_scale: number;
    rise_scale: number;
    river_boost_scale: number;
    iri_scale: number;
    source: string;
    version: number;
    hit_rate?: number | null;
    nota?: string;
  }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/simulations/hydro-calibration/${encodeURIComponent(codigoIbge)}`,
    );
    if (!res.ok) throw new Error('Falha ao carregar calibração');
    return res.json();
  },

  recalibrateHydro: async (
    codigoIbge: string,
    opts?: { auto?: boolean; precip_mm?: number },
  ): Promise<{
    codigo_ibge: string;
    runoff_scale: number;
    rise_scale: number;
    river_boost_scale: number;
    iri_scale: number;
    source: string;
    version: number;
    hit_rate?: number | null;
    nota?: string;
  }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/simulations/hydro-calibration/${encodeURIComponent(codigoIbge)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ auto: opts?.auto ?? true, precip_mm: opts?.precip_mm ?? 120 }),
      },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao recalibrar');
    }
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
    precip7d?: number,
  ): Promise<FloodRiskPrediction> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/predictions/flood-risk`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        municipio_id: codigoIbge,
        precip_24h: precip24h,
        precip_48h: precip48h,
        precip_72h: precip72h,
        ...(precip7d != null ? { precip_7d: precip7d } : {}),
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

  getFloodModelStatus: async (): Promise<{
    ready_count: number;
    total: number;
    note?: string;
    models: Array<{
      codigo_ibge: string;
      ready: boolean;
      model_kind?: string | null;
      auc_roc_cv?: number | null;
      threshold_mm_24h?: number | null;
    }>;
  }> => {
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

  getContingencyAlertaVivo: async (codigoIbge: string): Promise<{
    codigo_ibge: string;
    nivel_alerta: string;
    cemaden_ativos_24h: number;
    alertas_risco_24h: number;
    alertas_total_24h: number;
    camada_cemaden_count: number;
    fonte: string;
    vivo: boolean;
    titulo_recente?: string | null;
  }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/contingency/municipio/${encodeURIComponent(codigoIbge)}/alerta-vivo`,
    );
    if (!res.ok) throw new Error('Falha ao carregar alerta vivo');
    return res.json();
  },

  generateContingencyFromSimulation: async (payload: {
    codigo_ibge: string;
    cenario_tipo: string;
    risk_geojson: Record<string, unknown>;
    buffer_m?: number;
    simulacao_ref?: Record<string, unknown>;
    nivel_alerta?: string;
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

  activateContingencyPlan: async (planId: number, opts?: { confirm?: boolean }): Promise<ContingencyPlan> => {
    const confirm = opts?.confirm !== false;
    const qs = confirm ? '?confirm=true' : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/${planId}/activate${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao ativar plano');
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

  getContingencyActionTemplates: async (cenario: string): Promise<{
    acoes_por_nivel: Record<string, string[]>;
    protocolo_campo?: ContingencyPlan['protocolo_campo'];
    cobrade?: ContingencyPlan['cobrade'];
    recursos_sugeridos?: ContingencyRecurso[];
  }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/contingency/templates/acoes?cenario_tipo=${encodeURIComponent(cenario)}`);
    if (!res.ok) throw new Error('Falha ao carregar template COBRADE');
    const data = await res.json();
    if (data?.acoes_por_nivel) return data;
    return { acoes_por_nivel: data as Record<string, string[]> };
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

  getPublicAlertDraft: async (codigoIbge: string): Promise<PublicAlertDraft> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/disseminate/${encodeURIComponent(codigoIbge)}/draft`,
    );
    if (!res.ok) throw await httpError(res, 'Falha ao carregar prévia de disseminação');
    return res.json();
  },

  dispatchPublicAlert: async (
    codigoIbge: string,
    body: {
      nivel?: string;
      mensagem?: string;
      canais?: string[];
      checklist_itens?: string[];
      confirm?: boolean;
    },
  ): Promise<PublicAlertDispatchResult> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/disseminate/${encodeURIComponent(codigoIbge)}`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...body, confirm: body.confirm !== false }),
      },
    );
    if (!res.ok) throw await httpError(res, 'Falha ao disseminar aviso');
    return res.json();
  },

  getPublicAlertHistory: async (
    codigoIbge: string,
    limit = 15,
  ): Promise<{ items: PublicAlertHistoryItem[] }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/disseminate/${encodeURIComponent(codigoIbge)}/history?limit=${limit}`,
    );
    if (!res.ok) throw await httpError(res, 'Falha ao carregar histórico de disseminação');
    return res.json();
  },

  getTerrainProfile: async (
    codigoIbge: string,
    payload: {
      coordinates: [number, number][];
      samples?: number;
      water_level_m?: number | null;
    },
  ): Promise<{
    length_m: number;
    samples: number;
    elevation_min_m: number | null;
    elevation_max_m: number | null;
    water_level_m: number | null;
    points_below_water: number;
    dem_source?: string;
    points: Array<{
      distance_m: number;
      lon: number;
      lat: number;
      elevation_m: number | null;
      below_water?: boolean;
    }>;
  }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/terrain/${encodeURIComponent(codigoIbge)}/profile`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => ({}));
      throw new Error(detail.detail || 'Falha ao gerar perfil do terreno');
    }
    return res.json();
  },

  getLiveSensors3D: async (
    codigoIbge: string,
    opts?: { hours?: number; includeInmet?: boolean },
  ): Promise<LiveSensorsGeoJSON> => {
    const hours = opts?.hours ?? 24;
    const includeInmet = opts?.includeInmet !== false;
    const qs = new URLSearchParams({
      hours: String(hours),
      include_inmet: includeInmet ? 'true' : 'false',
    });
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/live-sensors/${encodeURIComponent(codigoIbge)}?${qs}`,
    );
    if (!res.ok) throw new Error('Falha ao carregar sensores vivos 3D');
    return res.json();
  },

  getCriticalPois3D: async (
    codigoIbge: string,
    opts?: { escolas?: boolean; saude?: boolean; abrigos?: boolean; equipamentos?: boolean },
  ): Promise<CriticalPoisGeoJSON> => {
    const qs = new URLSearchParams({
      escolas: opts?.escolas === false ? 'false' : 'true',
      saude: opts?.saude === false ? 'false' : 'true',
      abrigos: opts?.abrigos === false ? 'false' : 'true',
      equipamentos: opts?.equipamentos === false ? 'false' : 'true',
    });
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/critical-pois/${encodeURIComponent(codigoIbge)}?${qs}`,
    );
    if (!res.ok) throw new Error('Falha ao carregar POIs críticos 3D');
    return res.json();
  },

  getUrbanContext3D: async (
    codigoIbge: string,
    opts?: { hidrografia?: boolean; vias?: boolean; curvas?: boolean },
  ): Promise<UrbanContextGeoJSON> => {
    const qs = new URLSearchParams({
      hidrografia: opts?.hidrografia === false ? 'false' : 'true',
      vias: opts?.vias === false ? 'false' : 'true',
      curvas: opts?.curvas === false ? 'false' : 'true',
    });
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/monitoring/urban-context/${encodeURIComponent(codigoIbge)}?${qs}`,
    );
    if (!res.ok) throw new Error('Falha ao carregar contexto urbano 3D');
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

  getGeoportalStatus: async (codigoIbge: string): Promise<GeoportalStatus> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/geoportal/${code}/status`);
    if (!res.ok) throw await httpError(res, 'Falha ao carregar geoportal municipal');
    return res.json();
  },

  uploadGeoportalMesh: async (
    codigoIbge: string,
    file: File,
    titulo = 'Malha de bairros CTM',
  ): Promise<{ feature_count: number; snapshot_stored: boolean; publicacao: GeoportalPublicacao }> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const form = new FormData();
    form.append('file', file);
    form.append('titulo', titulo);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/geoportal/${code}/upload`, {
      method: 'POST',
      body: form,
    });
    if (!res.ok) throw await httpError(res, 'Falha no upload da malha CTM');
    return res.json();
  },

  registerGeoportalApi: async (
    codigoIbge: string,
    payload: {
      tipo: 'geojson_url' | 'arcgis_rest' | 'geoserver_wfs';
      url: string;
      titulo?: string;
      arcgis_where?: string;
      geoserver_type_name?: string;
    },
  ): Promise<{ publicacao: GeoportalPublicacao }> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/geoportal/${code}/register-api`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        titulo: 'Malha de bairros CTM',
        arcgis_where: '1=1',
        ...payload,
      }),
    });
    if (!res.ok) throw await httpError(res, 'Falha ao registrar API municipal');
    return res.json();
  },

  importGeoportalMesh: async (
    codigoIbge: string,
    publicacaoId?: number,
  ): Promise<{ bairros?: number; status?: string; error?: string }> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const qs = publicacaoId != null ? `?publicacao_id=${publicacaoId}` : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/geoportal/${code}/import${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao importar malha do geoportal');
    return res.json();
  },

  syncGeoportalCtmRegistry: async (
    codigoIbge: string,
    force = false,
  ): Promise<{ bairros?: number; error?: string; skipped?: boolean }> => {
    const code = codigoIbge.replace(/\D/g, '').padStart(7, '0').slice(-7);
    const qs = force ? '?force=true' : '';
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/geoportal/${code}/sync-ctm-registry${qs}`, {
      method: 'POST',
    });
    if (!res.ok) throw await httpError(res, 'Falha ao sincronizar CTM do catálogo');
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

  previewUfBootstrap: async (
    uf: string,
    limit = 50,
  ): Promise<{
    uf: string;
    total_ibge: number;
    ja_carregados: number;
    pendentes: number;
    a_processar: number;
    amostra: Array<{ codigo_ibge: string; nome: string; uf: string }>;
  }> => {
    const sigla = uf.trim().toUpperCase().slice(0, 2);
    const qs = new URLSearchParams({ limit: String(limit) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/uf/${sigla}/preview?${qs}`);
    if (!res.ok) throw await httpError(res, 'Falha ao pré-visualizar bootstrap da UF');
    return res.json();
  },

  bootstrapUf: async (
    uf: string,
    opts?: { limit?: number; skip_existing?: boolean; async_job?: boolean },
  ): Promise<Record<string, unknown>> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/onboarding/bootstrap-uf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        uf: uf.trim().toUpperCase().slice(0, 2),
        limit: opts?.limit ?? 20,
        skip_existing: opts?.skip_existing ?? true,
        async_job: opts?.async_job ?? true,
      }),
    });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar bootstrap por UF');
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

  syncMapBiomasBatch: async (limit = 6, force = false): Promise<Record<string, unknown>> => {
    const qs = new URLSearchParams({ limit: String(limit), force: String(force) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/integrations/mapbiomas/sync-batch?${qs}`, {
      method: 'POST',
    });
    if (!res.ok) throw await httpError(res, 'Falha no sync MapBiomas em lote');
    return res.json();
  },

  startPipelineJob: async (onboardingLimit = 6): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ onboarding_limit: String(onboardingLimit) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/pipeline?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar pipeline');
    return res.json();
  },

  startOnboardingBatchJob: async (
    limit = 6,
    status = 'pendente',
  ): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ limit: String(limit), status });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/onboarding-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar onboarding em lote');
    return res.json();
  },

  startMapBiomasBatchJob: async (
    limit = 6,
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

  startDiagnosticsBatchJob: async (limit = 6): Promise<{ job_id: string; job: BackgroundJob }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/diagnostics-batch?limit=${limit}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar diagnósticos em lote');
    return res.json();
  },

  startReportsBatchJob: async (
    limit = 6,
    force = false,
    codigos?: string[],
  ): Promise<{ job_id: string; job: BackgroundJob; reused?: boolean }> => {
    const qs = new URLSearchParams({ limit: String(limit), force: String(force) });
    if (codigos?.length) qs.set('codigos', codigos.join(','));
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/reports-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar PDFs em lote');
    return res.json();
  },

  prewarmAgentContext: async (codigoIbge: string): Promise<{ codigo_ibge: string; status: string }> => {
    const res = await apiFetch(
      `${getApiBaseUrl()}/api/v1/assistant/municipal/${encodeURIComponent(codigoIbge)}/prewarm`,
      { method: 'POST', priority: 'low' },
    );
    if (!res.ok) throw new Error('Falha ao pré-aquecer agente');
    return res.json();
  },

  startExternalSourcesBatchJob: async (limit = 6): Promise<{ job_id: string; job: BackgroundJob }> => {
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/fontes-externas-batch?limit=${limit}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao sincronizar fontes externas');
    return res.json();
  },

  startCtmBatchJob: async (
    force = false,
    codigos?: string[],
  ): Promise<{ job_id: string; job: BackgroundJob; reused?: boolean }> => {
    const qs = new URLSearchParams({ force: String(force) });
    if (codigos?.length) qs.set('codigos', codigos.join(','));
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/ctm-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar batch CTM');
    return res.json();
  },

  startDemBatchJob: async (limit = 6, force = false): Promise<{ job_id: string; job: BackgroundJob }> => {
    const qs = new URLSearchParams({ limit: String(limit), force: String(force) });
    const res = await apiFetch(`${getApiBaseUrl()}/api/v1/system/jobs/dem-batch?${qs}`, { method: 'POST' });
    if (!res.ok) throw await httpError(res, 'Falha ao iniciar batch DEM');
    return res.json();
  },

  startHomologationFullJob: async (
    onboardingLimit = 6,
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
