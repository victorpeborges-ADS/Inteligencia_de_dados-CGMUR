'use client';

import { useEffect, useState } from 'react';
import { api, DataCoverage, ExecutiveDiagnostic, ExecutiveDiagnosticHistoryItem, ExecutiveIndicators, IndicesResponse, IntegrationStatusResponse, MunicipalActionPlan, MunicipalMaturity, MunicipalReportRecord, OfficialUrbanClimateResponse } from '@/utils/api';
import { useAppStore } from '@/stores/useAppStore';
import ActionPlanPanel from '@/components/Dashboard/ActionPlanPanel';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line, CartesianGrid, Legend } from 'recharts';
import { Users, Trees, ShieldAlert, DollarSign, Waves, FileDown, Loader2, Award, ListChecks, Landmark } from 'lucide-react';
import RotatingLoader, { PDF_DIAGNOSTIC_MESSAGES } from '@/components/UI/RotatingLoader';
import TermTooltip from '@/components/UI/TermTooltip';
import { KpiCard, PanelSection, SkeletonKpiGrid, SkeletonChart } from '@/design-system';
import ExecutiveNarrative from '@/components/Dashboard/ExecutiveNarrative';
import TerritorialRecommendations from '@/components/Dashboard/TerritorialRecommendations';

const TIER_STYLE: Record<string, { bg: string; text: string; border: string }> = {
  Platina: { bg: 'bg-slate-400/15', text: 'text-slate-200', border: 'border-slate-400/40' },
  Ouro: { bg: 'bg-amber-400/15', text: 'text-amber-300', border: 'border-amber-400/40' },
  Prata: { bg: 'bg-zinc-400/15', text: 'text-zinc-300', border: 'border-zinc-400/40' },
  Bronze: { bg: 'bg-orange-900/30', text: 'text-orange-300', border: 'border-orange-700/40' },
};

const SOURCE_STATUS_TEXT: Record<string, string> = {
  OFICIAL: 'text-emerald-300',
  DERIVADO: 'text-indigo-300',
  ESTIMADO: 'text-amber-300',
  LACUNA: 'text-rose-300',
};

const SOURCE_STATUS_STYLE: Record<string, string> = {
  OFICIAL: 'bg-emerald-500/15 text-emerald-300',
  DERIVADO: 'bg-indigo-500/15 text-indigo-300',
  ESTIMADO: 'bg-amber-500/15 text-amber-300',
  LACUNA: 'bg-rose-500/15 text-rose-300',
};

export default function ExecutiveDashboard({
  codigoIbge,
  municipioLoaded,
  municipioEnsuring,
  municipioNome,
}: {
  codigoIbge?: string;
  municipioLoaded?: boolean;
  municipioEnsuring?: boolean;
  municipioNome?: string;
}) {
  const [indicators, setIndicators] = useState<ExecutiveIndicators | null>(null);
  const [indices, setIndices] = useState<IndicesResponse | null>(null);
  const [coverage, setCoverage] = useState<DataCoverage | null>(null);
  const [maturity, setMaturity] = useState<MunicipalMaturity | null>(null);
  const [officialClimate, setOfficialClimate] = useState<OfficialUrbanClimateResponse | null>(null);
  const [integrationStatus, setIntegrationStatus] = useState<IntegrationStatusResponse | null>(null);
  const [reportHistory, setReportHistory] = useState<MunicipalReportRecord[]>([]);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportError, setReportError] = useState<string | null>(null);
  const [completoLoading, setCompletoLoading] = useState(false);
  const [completoProgress, setCompletoProgress] = useState(0);
  const [completoStage, setCompletoStage] = useState('');
  const [completoError, setCompletoError] = useState<string | null>(null);
  const [pdfForceOverride, setPdfForceOverride] = useState(false);
  const [diagnostic, setDiagnostic] = useState<ExecutiveDiagnostic | null>(null);
  const [diagnosticHistory, setDiagnosticHistory] = useState<ExecutiveDiagnosticHistoryItem[]>([]);
  const [diagnosticLoading, setDiagnosticLoading] = useState(false);
  const [diagnosticError, setDiagnosticError] = useState<string | null>(null);
  const [actionPlan, setActionPlan] = useState<MunicipalActionPlan | null>(null);
  const [actionPlanLoading, setActionPlanLoading] = useState(false);
  const [actionPlanError, setActionPlanError] = useState<string | null>(null);
  const [dashboardError, setDashboardError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const reportRequest = useAppStore((s) => s.reportRequest);
  const clearReportRequest = useAppStore((s) => s.clearReportRequest);

  useEffect(() => {
    setMounted(true);
    const parseError = (err: unknown): string => {
      if (err instanceof Error) return err.message;
      return 'Erro desconhecido ao carregar dados';
    };

    const loadDashboardData = async () => {
      setLoading(true);
      setDashboardError(null);
      setIndicators(null);
      setIndices(null);
      setCoverage(null);
      setMaturity(null);
      setOfficialClimate(null);
      setIntegrationStatus(null);

      if (!codigoIbge) {
        setDashboardError('Nenhum município selecionado.');
        setLoading(false);
        return;
      }

      if (municipioEnsuring) {
        setLoading(false);
        return;
      }

      if (municipioLoaded === false) {
        setDashboardError(
          'Este município ainda não foi integrado ao banco. Abra a aba Municípios e execute o onboarding.',
        );
      }

      let onboardingWarning: string | null =
        municipioLoaded === false
          ? 'Este município ainda não foi integrado ao banco. Abra a aba Municípios e execute o onboarding.'
          : null;

      const results = await Promise.allSettled([
        api.getExecutiveIndicators(codigoIbge),
        api.getRiskIndices(codigoIbge),
        api.getDataCoverage(codigoIbge),
        api.getMunicipalMaturity(codigoIbge),
      ]);

      const labels = ['indicadores', 'índices IVC/IRI', 'cobertura de dados', 'maturidade'];
      const failures: string[] = [];

      if (results[0].status === 'fulfilled') setIndicators(results[0].value);
      else failures.push(labels[0]);

      if (results[1].status === 'fulfilled') setIndices(results[1].value);
      else failures.push(labels[1]);

      if (results[2].status === 'fulfilled') setCoverage(results[2].value);
      else failures.push(labels[2]);

      if (results[3].status === 'fulfilled') setMaturity(results[3].value);

      const firstReject = results.find((r) => r.status === 'rejected') as PromiseRejectedResult | undefined;
      const rejectMsg = firstReject ? parseError(firstReject.reason) : '';

      if (results[0].status === 'rejected') {
        if (rejectMsg.includes('401') || rejectMsg.toLowerCase().includes('autentica')) {
          setDashboardError('Sessão expirada ou acesso negado. Faça login no canto superior direito.');
        } else if (rejectMsg.includes('404') || rejectMsg.toLowerCase().includes('not found')) {
          setDashboardError(
            'Município não encontrado no banco. Vá em Municípios → Validar → Executar onboarding.',
          );
        } else {
          setDashboardError(`Não foi possível carregar os KPIs: ${rejectMsg}`);
        }
      } else if (failures.length > 0) {
        setDashboardError(onboardingWarning ?? `Alguns dados não carregaram: ${failures.join(', ')}.`);
      } else if (onboardingWarning) {
        setDashboardError(onboardingWarning);
      }

      setLoading(false);

      Promise.allSettled([
        api.getOfficialUrbanClimate(codigoIbge),
        api.getIntegrationStatus(),
      ]).then((secondary) => {
        if (secondary[0].status === 'fulfilled') setOfficialClimate(secondary[0].value);
        if (secondary[1].status === 'fulfilled') setIntegrationStatus(secondary[1].value);
      });
    };
    loadDashboardData();
  }, [codigoIbge, municipioLoaded, municipioEnsuring]);

  useEffect(() => {
    if (!codigoIbge) {
      setReportHistory([]);
      setDiagnostic(null);
      setActionPlan(null);
      return;
    }
    api.getMunicipalReportHistory(codigoIbge)
      .then(setReportHistory)
      .catch((err) => console.error('Erro ao carregar histórico de relatórios:', err));
    api.getExecutiveDiagnostic(codigoIbge)
      .then((record) => {
        setDiagnostic(record);
        return api.getExecutiveDiagnosticHistory(codigoIbge);
      })
      .then((history) => setDiagnosticHistory(history.items))
      .catch(() => {
        setDiagnostic(null);
        setDiagnosticHistory([]);
      });
    api.getActionPlan(codigoIbge)
      .then(setActionPlan)
      .catch(() => setActionPlan(null));
  }, [codigoIbge]);

  const handleGenerateReport = async (force = false) => {
    if (!codigoIbge) {
      setReportError('Município não selecionado. Recarregue a página.');
      return;
    }
    setReportLoading(true);
    setReportError(null);
    try {
      const record = await api.generateMunicipalReport(codigoIbge, force || pdfForceOverride);
      setReportHistory((prev) => [record, ...prev.filter((item) => item.id !== record.id)]);
      await api.downloadReport(record.download_url, record.nome_arquivo);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Erro ao gerar relatório';
      setReportError(msg);
      if (msg.includes('403') || msg.toLowerCase().includes('bloqueado') || msg.toLowerCase().includes('prata')) {
        setPdfForceOverride(true);
      }
    } finally {
      setReportLoading(false);
    }
  };

  const handleGenerateCompletoReport = async () => {
    if (!codigoIbge) {
      setCompletoError('Município não selecionado.');
      return;
    }
    setCompletoLoading(true);
    setCompletoError(null);
    setCompletoProgress(0);
    setCompletoStage('Iniciando…');
    try {
      const started = await api.generateCompletoReport(codigoIbge, pdfForceOverride, true);
      if (!('job_id' in started) || !started.job_id) {
        const record = started as MunicipalReportRecord;
        await api.downloadReport(record.download_url, record.nome_arquivo);
        setReportHistory((prev) => [record, ...prev]);
        return;
      }
      const jobId = started.job_id;
      for (let i = 0; i < 120; i += 1) {
        await new Promise((r) => setTimeout(r, 2000));
        const prog = await api.getReportJobProgress(jobId);
        setCompletoProgress(prog.progress || 0);
        setCompletoStage(prog.stage_label || prog.stage || 'Processando…');
        if (prog.status === 'completed' && prog.download_url) {
          setCompletoProgress(100);
          await api.downloadReport(prog.download_url, `relatorio_completo_${codigoIbge}.pdf`);
          if (prog.report_id) {
            setReportHistory((prev) => [
              {
                id: prog.report_id!,
                municipio_id: 0,
                codigo_ibge: codigoIbge,
                nome_arquivo: `relatorio_completo_${codigoIbge}.pdf`,
                tamanho_bytes: 0,
                status: 'concluido',
                gerado_em: new Date().toISOString(),
                download_url: prog.download_url!,
              },
              ...prev,
            ]);
          }
          break;
        }
        if (prog.status === 'failed') {
          throw new Error(prog.error || 'Geração do relatório completo falhou');
        }
      }
    } catch (err) {
      setCompletoError(err instanceof Error ? err.message : 'Erro ao gerar relatório completo');
    } finally {
      setCompletoLoading(false);
    }
  };

  useEffect(() => {
    if (!reportRequest || !codigoIbge) return;
    if (reportRequest === 'completo') {
      handleGenerateCompletoReport().finally(() => clearReportRequest());
    } else if (reportRequest === 'rapido') {
      handleGenerateReport().finally(() => clearReportRequest());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportRequest, codigoIbge]);

  const handleGenerateDiagnostic = async () => {
    if (!codigoIbge) {
      setDiagnosticError('Município não selecionado.');
      return;
    }
    setDiagnosticLoading(true);
    setDiagnosticError(null);
    try {
      const record = await api.generateExecutiveDiagnostic(codigoIbge);
      setDiagnostic(record);
      if (record.download_url && record.nome_arquivo) {
        await api.downloadReport(record.download_url, record.nome_arquivo);
      }
      const conteudo = record.conteudo as Record<string, unknown> | undefined;
      const ranking = (conteudo?.ranking_bairros as Array<{ bairro?: string }>) || [];
      useAppStore.getState().notifyDiagnosticGenerated({
        versao: `v${record.versao}`,
        score: typeof conteudo?.score_sinidu === 'number' ? conteudo.score_sinidu : indicators?.score_sinidu,
        prioridade: String(conteudo?.prioridade || 'Alta'),
        riscos: ranking.map((r) => r.bairro || '').filter(Boolean),
      });
      api.getExecutiveDiagnosticHistory(codigoIbge)
        .then((history) => setDiagnosticHistory(history.items))
        .catch(() => setDiagnosticHistory([]));
      api.getActionPlan(codigoIbge).then(setActionPlan).catch(() => setActionPlan(null));
    } catch (err) {
      setDiagnosticError(err instanceof Error ? err.message : 'Erro ao gerar diagnóstico');
    } finally {
      setDiagnosticLoading(false);
    }
  };

  const handleDownloadDiagnostic = async (downloadUrl?: string | null, filename?: string | null) => {
    if (!downloadUrl) {
      setDiagnosticError('PDF do diagnóstico indisponível.');
      return;
    }
    try {
      await api.downloadReport(downloadUrl, filename || 'diagnostico-executivo.pdf');
    } catch (err) {
      setDiagnosticError(err instanceof Error ? err.message : 'Erro ao baixar PDF');
    }
  };

  const handleGenerateActionPlan = async () => {
    if (!codigoIbge) {
      setActionPlanError('Município não selecionado.');
      return;
    }
    setActionPlanLoading(true);
    setActionPlanError(null);
    try {
      const plan = await api.generateActionPlan(codigoIbge);
      setActionPlan(plan);
    } catch (err) {
      setActionPlanError(err instanceof Error ? err.message : 'Erro ao gerar plano de ação');
    } finally {
      setActionPlanLoading(false);
    }
  };

  const formatReportDate = (value: string) => new Date(value).toLocaleString('pt-BR');

  const formatCurrency = (value: number) => {
    return value.toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      maximumFractionDigits: 0
    });
  };

  const formatCompactCurrency = (value: number) => {
    if (value >= 1_000_000_000) return `R$ ${(value / 1_000_000_000).toFixed(1)} bi`;
    if (value >= 1_000_000) return `R$ ${(value / 1_000_000).toFixed(1)} mi`;
    if (value >= 1_000) return `R$ ${(value / 1_000).toFixed(1)} mil`;
    return formatCurrency(value);
  };

  if (!mounted || municipioEnsuring) {
    return (
      <div className="flex flex-col gap-5 p-1">
        <RotatingLoader messages={['Carregando dados municipais…', 'Sincronizando indicadores…', 'Preparando painel executivo…']} className="text-indigo-200" />
        <SkeletonKpiGrid count={4} />
        <SkeletonChart />
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-5 p-1">
        <SkeletonKpiGrid count={4} />
        <SkeletonChart />
      </div>
    );
  }

  // Combine IVC and IRI per neighborhood for charts
  const chartData = indices?.vulnerabilidade.map((v) => {
    const flood = indices.inundacao.find((f) => f.bairro_nome === v.bairro_nome);
    return {
      name: v.bairro_nome,
      Vulnerabilidade: v.indice_vulnerabilidade,
      Inundaçao: flood ? flood.indice_risco_inundacao : 0
    };
  }) || [];

  type DashboardCard = {
    title: string;
    value: string;
    desc: string;
    icon: typeof Users;
    color: string;
    border: string;
    badge?: string;
    quality?: string;
    maturityMetrics?: MunicipalMaturity['fontes'];
  };

  const kpiQuality = (q?: string | null) => {
    const v = (q || 'lacuna').toLowerCase();
    if (v === 'oficial') return 'OFICIAL';
    if (v === 'derivado') return 'DERIVADO';
    if (v === 'estimado') return 'ESTIMADO';
    return 'LACUNA';
  };

  const prataMin = 26;
  const maturityScore = maturity?.score ?? coverage?.maturidade_percentual ?? 0;
  const pdfBlocked = maturityScore < prataMin;

  const cards: DashboardCard[] = [
    {
      title: 'População Estimada',
      value: indicators?.populacao != null ? indicators.populacao.toLocaleString('pt-BR') : '—',
      desc: `${indicators?.densidade_demografica || '—'} hab/km²`,
      badge: indicators?.selo_ibge,
      quality: kpiQuality(indicators?.populacao_qualidade),
      icon: Users,
      color: 'text-indigo-400',
      border: 'hover:border-indigo-500/50'
    },
    {
      title: 'Cobertura Vegetal',
      value: indicators?.cobertura_vegetal_percent != null
        ? `${indicators.cobertura_vegetal_percent}%`
        : '—',
      desc: 'Vegetação e floresta (MapBiomas, área municipal)',
      quality: kpiQuality(indicators?.cobertura_qualidade),
      icon: Trees,
      color: 'text-accent-emerald',
      border: 'hover:border-accent-emerald/50'
    },
    {
      title: 'Risco Territorial Ativo',
      value: indicators?.alertas_ativos_count != null ? String(indicators.alertas_ativos_count) : '—',
      desc: 'Setores monitorados CEMADEN',
      quality: kpiQuality(indicators?.alertas_qualidade),
      icon: ShieldAlert,
      color: indicators?.alertas_ativos_count ? 'text-accent-rose' : 'text-accent-amber',
      border: 'hover:border-accent-rose/50'
    },
    {
      title: 'Renda Média Mensal',
      value: indicators?.renda_media_setores != null && indicators.renda_media_setores > 0
        ? formatCurrency(indicators.renda_media_setores)
        : '—',
      desc: 'Estimativa mensal per capita (IBGE/PNAD)',
      quality: kpiQuality(indicators?.renda_qualidade),
      icon: DollarSign,
      color: 'text-yellow-400',
      border: 'hover:border-yellow-500/50'
    },
    {
      title: 'Danos em Desastres (S2ID)',
      value: indicators?.danos_materiais_total != null && indicators.danos_materiais_total > 0
        ? formatCompactCurrency(indicators.danos_materiais_total)
        : indicators?.historico_desastres_count
          ? formatCompactCurrency(indicators.danos_materiais_total ?? 0)
          : '—',
      desc: indicators?.historico_desastres_count != null
        ? `${indicators.historico_desastres_count} evento(s) registrado(s) (S2ID)`
        : 'Sem registro S2ID',
      quality: kpiQuality(indicators?.desastres_qualidade),
      icon: Waves,
      color: 'text-accent-sky',
      border: 'hover:border-accent-sky/50'
    },
    {
      title: 'Maturidade Municipal',
      value: maturity
        ? `${Math.round(maturity.score)}%`
        : coverage?.maturidade_percentual != null
          ? `${Math.round(coverage.maturidade_percentual)}%`
          : '—',
      desc: maturity
        ? `${maturity.classificacao} · ${maturity.fontes_faltantes.length} fonte(s) faltante(s)`
        : coverage
          ? `${coverage.classificacao} · ${coverage.lacunas_prioritarias.length} lacuna(s)`
          : 'Dados indisponíveis',
      quality: maturityScore >= prataMin ? 'DERIVADO' : 'LACUNA',
      maturityMetrics: maturity?.fontes,
      icon: Award,
      color: maturity?.classificacao === 'Platina' || maturity?.classificacao === 'Ouro'
        ? 'text-emerald-400'
        : maturity?.classificacao === 'Prata'
          ? 'text-amber-400'
          : 'text-orange-400',
      border: 'hover:border-indigo-500/50'
    }
  ];

  const officialClimateData = officialClimate?.historical_timeline
    ?.filter((item) => item.temperatura_media != null || item.area_urbanizada_km2 != null)
    .map((item) => ({
      ano: item.ano,
      temp: item.temperatura_media ?? null,
      area: item.area_urbanizada_km2 ?? null,
    })) || [];
  const estimatedClimateData = officialClimate?.estimated_timeline
    .map((item) => ({
      ano: item.ano,
      temp: item.temperatura_media,
      area: item.area_urbanizada_km2,
    })) || [];
  const climateChartData = officialClimateData.length > 0 ? officialClimateData : estimatedClimateData;
  const hasMapBiomasSeries = officialClimateData.some((item) => item.area != null);
  const hasTemperatureSeries = climateChartData.some((item) => item.temp != null);
  const isEstimatedClimateChart = !hasMapBiomasSeries && estimatedClimateData.length > 0;
  const tempLegendLabel = officialClimate?.temperatura_oficial
    ? 'Temp. média INMET (°C)'
    : officialClimate?.temperatura_integrada
      ? 'Temp. referência INMET (°C)'
      : isEstimatedClimateChart
        ? 'Temp. estimada (°C)'
        : 'Temp. média INMET (°C)';
  const climateYears = climateChartData.map((item) => item.ano);
  const tempValues = climateChartData.map((item) => item.temp).filter((v): v is number => v != null);
  const areaValues = climateChartData.map((item) => item.area).filter((v): v is number => v != null);
  const tempDomain: [number, number] | ['auto', 'auto'] = tempValues.length
    ? [Math.floor(Math.min(...tempValues) * 10) / 10 - 0.3, Math.ceil(Math.max(...tempValues) * 10) / 10 + 0.3]
    : [25, 30];
  const areaDomain: [number, number] | ['auto', 'auto'] = areaValues.length
    ? [Math.floor(Math.min(...areaValues) / 10) * 10, Math.ceil(Math.max(...areaValues) / 10) * 10 + 10]
    : [50, 250];

  const avgIvc = indices?.vulnerabilidade.length
    ? indices.vulnerabilidade.reduce((sum, row) => sum + row.indice_vulnerabilidade, 0) / indices.vulnerabilidade.length
    : indicators?.media_ivc ?? null;
  const avgIri = indices?.inundacao.length
    ? indices.inundacao.reduce((sum, row) => sum + row.indice_risco_inundacao, 0) / indices.inundacao.length
    : indicators?.media_iri ?? null;
  const avgAdaptacao = indices?.vulnerabilidade.length
    ? indices.vulnerabilidade.reduce((sum, row) => sum + row.capacidade_adaptacao, 0) / indices.vulnerabilidade.length
    : indicators?.media_adaptacao ?? null;
  const scoreSinidu =
    indicators?.score_sinidu ??
    (avgIvc != null && avgIri != null && avgAdaptacao != null
      ? Math.round((avgIvc * 0.45 + avgIri * 0.35 + (1 - avgAdaptacao) * 0.2) * 100)
      : null);
  const formatIndex = (value: number | null) =>
    value != null ? `${Math.round(value * 100)}` : '—';
  const alertasCard = cards.find((c) => c.title === 'Risco Territorial Ativo');
  const maturityCard = cards.find((c) => c.title === 'Maturidade Municipal');
  const secondaryCards = cards.filter((c) =>
    !['Risco Territorial Ativo', 'Maturidade Municipal'].includes(c.title),
  );

  return (
    <div className="flex flex-col gap-5 overflow-y-auto max-h-[85vh] pr-2">
      {dashboardError && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-[11px] leading-relaxed text-amber-100">
          {dashboardError}
        </div>
      )}
      {(indicators?.nome || municipioNome) && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2">
          <p className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Município em análise</p>
          <p className="text-sm font-extrabold text-zinc-100">
            {indicators?.nome || municipioNome}
            {indicators?.uf ? ` — ${indicators.uf}` : ''}
            {codigoIbge ? <span className="ml-2 text-[10px] font-mono text-zinc-500">IBGE {codigoIbge}</span> : null}
          </p>
        </div>
      )}

      <ExecutiveNarrative
        municipioNome={municipioNome}
        uf={indicators?.uf}
        codigoIbge={codigoIbge}
        indicators={indicators}
        indices={indices}
        maturity={maturity}
        diagnostic={diagnostic}
        avgIvc={avgIvc}
        avgIri={avgIri}
      />

      <TerritorialRecommendations
        indicators={indicators}
        indices={indices}
        maturity={maturity}
        diagnostic={diagnostic}
        avgIvc={avgIvc}
        avgIri={avgIri}
      />

      <PanelSection
        title="Indicadores prioritários"
        tier="primary"
        description="Leitura rápida para gestores — score territorial, risco climático e maturidade de dados"
      >
        <div className="grid grid-cols-2 gap-3">
          <KpiCard
            tier="primary"
            className="col-span-2"
            title="Score Sinidu+Clima"
            value={scoreSinidu != null ? String(Math.round(scoreSinidu)) : '—'}
            description="Prioridade territorial composta (0–100) · maior score = maior atenção"
            icon={Award}
            iconClassName="text-indigo-300"
            quality={scoreSinidu != null ? 'DERIVADO' : 'LACUNA'}
          />
          <KpiCard
            tier="primary"
            title="IVC médio municipal"
            value={formatIndex(avgIvc)}
            description={`Média entre bairros · escala 0–100 · ${indices?.vulnerabilidade.length || 0} setor(es)`}
            icon={ShieldAlert}
            iconClassName="text-rose-300"
            quality={avgIvc != null ? 'DERIVADO' : 'LACUNA'}
          />
          <KpiCard
            tier="primary"
            title="IRI médio municipal"
            value={formatIndex(avgIri)}
            description={`Risco de inundação agregado · ${indices?.inundacao.length || 0} setor(es)`}
            icon={Waves}
            iconClassName="text-sky-300"
            quality={avgIri != null ? 'DERIVADO' : 'LACUNA'}
          />
          {alertasCard && (
            <KpiCard
              tier="primary"
              title={alertasCard.title}
              value={alertasCard.value}
              description={alertasCard.desc}
              icon={alertasCard.icon}
              iconClassName={alertasCard.color}
              quality={alertasCard.quality}
            />
          )}
          {maturityCard && (
            <KpiCard
              tier="primary"
              title={maturityCard.title}
              value={maturityCard.value}
              description={maturityCard.desc}
              icon={maturityCard.icon}
              iconClassName={maturityCard.color}
              quality={maturityCard.quality}
            />
          )}
        </div>
      </PanelSection>

      <div className="rounded-xl border border-indigo-500/20 bg-indigo-950/10 p-4 opacity-95">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h4 className="text-xs font-extrabold uppercase tracking-wide text-indigo-200">Relatório territorial PDF</h4>
            <p className="mt-1 text-[10px] leading-snug text-zinc-400">
              Compila perfil municipal, risco, clima, fiscal e plano de ação para apresentação a gestores e Defesa Civil.
              {pdfBlocked && (
                <span className="mt-1 block text-amber-300/90">
                  Requer maturidade Prata (≥{prataMin}%) — atual: {Math.round(maturityScore)}%.
                </span>
              )}
            </p>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            {pdfBlocked && (
              <label className="flex items-center gap-1.5 text-[9px] text-zinc-400">
                <input
                  type="checkbox"
                  checked={pdfForceOverride}
                  onChange={(e) => setPdfForceOverride(e.target.checked)}
                  className="rounded border-zinc-600"
                />
                Override admin
              </label>
            )}
            <button
              type="button"
              onClick={() => handleGenerateReport()}
              disabled={reportLoading || completoLoading || !codigoIbge || (pdfBlocked && !pdfForceOverride)}
              className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-indigo-400/40 bg-indigo-500/15 px-3 py-2 text-[11px] font-bold text-indigo-100 transition hover:bg-indigo-500/25 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {reportLoading ? <Loader2 size={14} className="animate-spin" /> : <FileDown size={14} />}
              {reportLoading ? 'Compilando dados...' : pdfBlocked && pdfForceOverride ? 'Gerar PDF (override)' : 'Gerar Relatório PDF'}
            </button>
            <button
              type="button"
              onClick={handleGenerateCompletoReport}
              disabled={completoLoading || reportLoading || !codigoIbge || (pdfBlocked && !pdfForceOverride)}
              className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-emerald-400/40 bg-emerald-500/15 px-3 py-2 text-[11px] font-bold text-emerald-100 transition hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {completoLoading ? <Loader2 size={14} className="animate-spin" /> : <FileDown size={14} />}
              {completoLoading ? 'Relatório IA…' : 'PDF Completo (IA + gráficos)'}
            </button>
          </div>
        </div>
        {reportLoading && (
          <div className="mb-3 rounded-lg border border-indigo-800/40 bg-indigo-950/20 p-3">
            <RotatingLoader messages={PDF_DIAGNOSTIC_MESSAGES} className="text-indigo-200" />
          </div>
        )}
        {completoLoading && (
          <div className="mb-3 rounded-lg border border-emerald-800/40 bg-emerald-950/20 p-3">
            <RotatingLoader messages={PDF_DIAGNOSTIC_MESSAGES} className="mb-2 text-emerald-200" />
            <div className="mb-1 flex justify-between text-[9px] text-emerald-200">
              <span>{completoStage}</span>
              <span>{completoProgress}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-zinc-900">
              <div
                className="h-full bg-emerald-500 transition-all duration-500"
                style={{ width: `${Math.min(completoProgress, 100)}%` }}
              />
            </div>
          </div>
        )}
        {completoError && (
          <p className="mb-2 text-[10px] text-rose-300">{completoError}</p>
        )}
        {reportError && (
          <p className="mb-2 text-[10px] text-rose-300">{reportError}</p>
        )}
        {reportHistory.length > 0 && (
          <div className="overflow-hidden rounded-lg border border-zinc-800">
            <table className="w-full text-left text-[10px] text-zinc-300">
              <thead className="bg-zinc-950/80 text-[9px] uppercase tracking-wide text-zinc-500">
                <tr>
                  <th className="px-2 py-1.5">Gerado em</th>
                  <th className="px-2 py-1.5">Arquivo</th>
                  <th className="px-2 py-1.5">Tamanho</th>
                  <th className="px-2 py-1.5"></th>
                </tr>
              </thead>
              <tbody>
                {reportHistory.slice(0, 5).map((item) => (
                  <tr key={item.id} className="border-t border-zinc-800/80">
                    <td className="px-2 py-1.5">{formatReportDate(item.gerado_em)}</td>
                    <td className="px-2 py-1.5 font-mono text-[9px]">{item.nome_arquivo}</td>
                    <td className="px-2 py-1.5">{Math.round(item.tamanho_bytes / 1024)} KB</td>
                    <td className="px-2 py-1.5">
                      <button
                        type="button"
                        onClick={() => api.downloadReport(item.download_url, item.nome_arquivo)}
                        className="text-indigo-300 hover:text-indigo-100"
                      >
                        Baixar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/15 p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h4 className="text-xs font-extrabold uppercase tracking-wide text-emerald-200">Diagnóstico Executivo</h4>
            <p className="mt-1 text-[10px] leading-snug text-zinc-400">
              PDF institucional com perfil, fiscal, clima, desastres, riscos e lacunas — pronto para apresentação.
            </p>
          </div>
          <button
            type="button"
            onClick={handleGenerateDiagnostic}
            disabled={diagnosticLoading || !codigoIbge}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-emerald-400/40 bg-emerald-500/15 px-3 py-2 text-[11px] font-bold text-emerald-100 transition hover:bg-emerald-500/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {diagnosticLoading ? <Loader2 size={14} className="animate-spin" /> : <FileDown size={14} />}
            {diagnosticLoading ? 'Gerando PDF...' : 'Gerar Diagnóstico PDF'}
          </button>
        </div>
        {diagnosticLoading && (
          <div className="mb-3 rounded-lg border border-emerald-800/40 bg-emerald-950/20 p-3">
            <RotatingLoader messages={PDF_DIAGNOSTIC_MESSAGES} className="text-emerald-200" />
          </div>
        )}
        {diagnosticError && <p className="mb-2 text-[10px] text-rose-300">{diagnosticError}</p>}
        {diagnostic ? (
          <div className="space-y-3">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="text-[11px] font-semibold leading-snug text-zinc-200">{diagnostic.headline}</p>
                <p className="mt-1 text-[9px] text-zinc-500">
                  v{diagnostic.versao} · {diagnostic.origem} · {formatReportDate(diagnostic.gerado_em || '')}
                  {diagnostic.nome_arquivo ? ` · ${diagnostic.nome_arquivo}` : ''}
                  {diagnostic.tamanho_bytes ? ` · ${Math.round(diagnostic.tamanho_bytes / 1024)} KB` : ''}
                </p>
              </div>
              {diagnostic.download_url && (
                <button
                  type="button"
                  onClick={() => handleDownloadDiagnostic(diagnostic.download_url, diagnostic.nome_arquivo)}
                  className="inline-flex shrink-0 items-center gap-1 rounded border border-emerald-500/40 bg-emerald-500/10 px-2 py-1 text-[9px] font-bold text-emerald-200 hover:bg-emerald-500/20"
                >
                  <FileDown size={10} /> Baixar PDF
                </button>
              )}
            </div>
            {diagnosticHistory.length > 0 && (
              <div className="overflow-hidden rounded-lg border border-zinc-800">
                <table className="w-full text-left text-[10px] text-zinc-300">
                  <thead className="bg-zinc-950/80 text-[9px] uppercase tracking-wide text-zinc-500">
                    <tr>
                      <th className="px-2 py-1.5">Versão</th>
                      <th className="px-2 py-1.5">Gerado em</th>
                      <th className="px-2 py-1.5">Arquivo</th>
                      <th className="px-2 py-1.5"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {diagnosticHistory.slice(0, 5).map((item) => (
                      <tr key={item.id} className="border-t border-zinc-800/80">
                        <td className="px-2 py-1.5">v{item.versao}</td>
                        <td className="px-2 py-1.5">{item.gerado_em ? formatReportDate(item.gerado_em) : '—'}</td>
                        <td className="px-2 py-1.5 font-mono text-[9px]">{item.nome_arquivo || '—'}</td>
                        <td className="px-2 py-1.5">
                          {item.download_url ? (
                            <button
                              type="button"
                              onClick={() => handleDownloadDiagnostic(item.download_url, item.nome_arquivo)}
                              className="text-emerald-300 hover:text-emerald-100"
                            >
                              Baixar
                            </button>
                          ) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ) : (
          <p className="text-[10px] text-zinc-500">
            Nenhum diagnóstico salvo. Gere manualmente ou conclua o onboarding municipal.
          </p>
        )}
      </div>

      <div className="rounded-xl border border-amber-500/30 bg-amber-950/15 p-4">
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <h4 className="text-xs font-extrabold uppercase tracking-wide text-amber-200">Plano de Ação Territorial</h4>
            <p className="mt-1 text-[10px] leading-snug text-zinc-400">
              Ações por horizonte (curto, médio, longo prazo) com classificação de custo e programas federais sugeridos.
            </p>
          </div>
          <button
            type="button"
            onClick={handleGenerateActionPlan}
            disabled={actionPlanLoading || !codigoIbge}
            className="inline-flex shrink-0 items-center gap-2 rounded-lg border border-amber-400/40 bg-amber-500/15 px-3 py-2 text-[11px] font-bold text-amber-100 transition hover:bg-amber-500/25 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {actionPlanLoading ? <Loader2 size={14} className="animate-spin" /> : <ListChecks size={14} />}
            {actionPlanLoading ? 'Gerando...' : 'Gerar Plano de Ação'}
          </button>
        </div>
        {actionPlanError && <p className="mb-2 text-[10px] text-rose-300">{actionPlanError}</p>}
        {actionPlan ? (
          <ActionPlanPanel plan={actionPlan} />
        ) : (
          <p className="text-[10px] text-zinc-500">
            Nenhum plano salvo. Gere após o diagnóstico executivo ou manualmente.
          </p>
        )}
      </div>

      {/* Indicadores complementares */}
      <PanelSection title="Indicadores complementares" tier="secondary" description="Contexto demográfico, ambiental e histórico de desastres">
        <div className="grid grid-cols-2 gap-3">
          {secondaryCards.map((c) => {
            const Icon = c.icon;
            return (
              <KpiCard
                key={c.title}
                tier="secondary"
                title={c.title}
                value={c.value}
                description={c.desc}
                icon={Icon}
                iconClassName={c.color}
                quality={c.quality}
                badge={c.badge}
              />
            );
          })}
          {maturityCard?.maturityMetrics?.length ? (
            <KpiCard
              tier="secondary"
              className="col-span-2"
              title="Composição da maturidade"
              value={maturityCard.value}
              description="Detalhamento das 8 fontes integradas"
              icon={Award}
              iconClassName={maturityCard.color}
              quality={maturityCard.quality}
            >
              <div className="mt-3 border-t border-zinc-800 pt-2.5">
                <div className="grid grid-cols-2 gap-1.5">
                  {maturityCard.maturityMetrics.map((fonte) => (
                    <div
                      key={fonte.id}
                      className="flex items-center justify-between gap-1.5 rounded-md border border-zinc-800/80 bg-zinc-950/50 px-2 py-1"
                    >
                      <div className="min-w-0 flex-1">
                        <span className="block truncate text-[9px] font-semibold text-zinc-300">{fonte.nome}</span>
                        <span className={`text-[8px] font-bold uppercase ${SOURCE_STATUS_TEXT[fonte.status] || 'text-zinc-500'}`}>
                          {fonte.status}
                        </span>
                      </div>
                      <span className="shrink-0 font-mono text-[10px] font-bold text-zinc-200">
                        {fonte.pontos.toFixed(1)}
                      </span>
                    </div>
                  ))}
                </div>
                {maturity && (
                  <p className="mt-2 text-right text-[9px] font-mono text-zinc-500">
                    Total: {maturity.fontes.reduce((sum, f) => sum + f.pontos, 0).toFixed(1)} / 100
                  </p>
                )}
              </div>
            </KpiCard>
          ) : null}
        </div>
      </PanelSection>

      {indicators && (
        <div className="rounded-xl border border-border bg-card/40 p-4">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h4 className="text-xs font-extrabold uppercase tracking-wide text-zinc-200">Saúde Fiscal</h4>
            {indicators.siconfi_ia_url && (
              <a
                href={indicators.siconfi_ia_url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-bold text-sky-200 hover:bg-sky-500/20"
              >
                Ver no Siconfi.IA ↗
              </a>
            )}
          </div>

          <div className="mb-3 flex items-center gap-3">
            <span className="text-[10px] text-zinc-500"><TermTooltip term="CAPAG" /></span>
            <span className={`inline-flex h-10 w-10 items-center justify-center rounded-xl border text-lg font-black ${
              indicators.nota_capag === 'A' || indicators.nota_capag === 'B'
                ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                : indicators.nota_capag === 'C'
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-300'
                  : indicators.nota_capag === 'D'
                    ? 'border-rose-500/40 bg-rose-500/10 text-rose-300'
                    : 'border-zinc-700 bg-zinc-900 text-zinc-400'
            }`}>
              {indicators.nota_capag || '—'}
            </span>
            <div className="text-[10px] text-zinc-400">
              {indicators.selo_fiscal || 'Dados fiscais integrados via SICONFI'}
              {indicators.receita_corrente_liquida != null && (
                <p className="mt-1 text-zinc-300">RCL: {formatCompactCurrency(indicators.receita_corrente_liquida)}</p>
              )}
            </div>
          </div>

          {indicators.despesa_pessoal_pct_rcl != null && (
            <div className="mb-3">
              <div className="mb-1 flex justify-between text-[10px] text-zinc-400">
                <span>Despesa com Pessoal % RCL</span>
                <span className={indicators.despesa_pessoal_pct_rcl > 60 ? 'text-rose-300' : 'text-emerald-300'}>
                  {indicators.despesa_pessoal_pct_rcl.toFixed(1)}% / limite 60%
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-zinc-900">
                <div
                  className={`h-full rounded-full ${indicators.despesa_pessoal_pct_rcl > 60 ? 'bg-rose-500' : 'bg-emerald-500'}`}
                  style={{ width: `${Math.min(100, (indicators.despesa_pessoal_pct_rcl / 60) * 100)}%` }}
                />
              </div>
            </div>
          )}

          {indicators.divida_consolidada_pct_rcl != null && (
            <div>
              <div className="mb-1 flex justify-between text-[10px] text-zinc-400">
                <span>Dívida Consolidada % RCL</span>
                <span className={indicators.divida_consolidada_pct_rcl > 120 ? 'text-rose-300' : 'text-emerald-300'}>
                  {indicators.divida_consolidada_pct_rcl.toFixed(1)}% / limite 120%
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-zinc-900">
                <div
                  className={`h-full rounded-full ${indicators.divida_consolidada_pct_rcl > 120 ? 'bg-rose-500' : 'bg-sky-500'}`}
                  style={{ width: `${Math.min(100, (indicators.divida_consolidada_pct_rcl / 120) * 100)}%` }}
                />
              </div>
            </div>
          )}

          {!indicators.nota_capag && indicators.despesa_pessoal_pct_rcl == null && indicators.divida_consolidada_pct_rcl == null && (
            <p className="text-[10px] text-zinc-500">
              Dados fiscais ainda não sincronizados. Execute a integração SICONFI/CAPAG ou consulte diretamente o Siconfi.IA.
            </p>
          )}
        </div>
      )}

      {(indicators?.pib_per_capita != null || indicators?.pib_total_mil_reais != null || indicators?.idh != null || indicators?.atlas_uf_context) && (
        <PanelSection
          title="Contexto socioeconômico"
          tier="secondary"
          description="Indicadores municipais (IBGE/Atlas DH) e referência estadual (Atlas Econômico IPEA/RFB)"
        >
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 2xl:grid-cols-4">
            {indicators?.pib_total_mil_reais != null && (
              <KpiCard
                tier="secondary"
                title="PIB municipal"
                value={formatCompactCurrency(indicators.pib_total_mil_reais * 1000)}
                description={`Total a preços de mercado · IBGE ${indicators.pib_ano ?? 'série'}`}
                icon={DollarSign}
                iconClassName="text-emerald-300"
                quality={kpiQuality(indicators.pib_qualidade)}
              />
            )}
            {indicators?.pib_per_capita != null && (
              <KpiCard
                tier="secondary"
                title="PIB per capita"
                value={formatCurrency(indicators.pib_per_capita)}
                description={indicators.pib_fonte || 'IBGE PIB Municipal'}
                icon={DollarSign}
                iconClassName="text-emerald-400"
                quality={kpiQuality(indicators.pib_qualidade)}
              />
            )}
            {indicators?.idh != null && (
              <KpiCard
                tier="secondary"
                title="IDH Municipal"
                value={indicators.idh.toFixed(3)}
                description={`${indicators.idh_fonte || 'Atlas DH'}${indicators.idh_ano ? ` · ${indicators.idh_ano}` : ''}`}
                icon={Award}
                iconClassName="text-sky-400"
                quality={kpiQuality(indicators.idh_qualidade)}
              />
            )}
            {indicators?.atlas_uf_context && (
              <KpiCard
                tier="secondary"
                className="col-span-full sm:col-span-2"
                title={`Atlas Econômico · ${indicators.atlas_uf_context.uf_sigla}`}
                value={`${indicators.atlas_uf_context.atividades_economicas} setores`}
                description={indicators.atlas_uf_context.descricao}
                icon={Landmark}
                iconClassName="text-violet-400"
                quality="REFERÊNCIA UF"
              >
                <div className="mt-3 space-y-2 border-t border-zinc-800 pt-2.5">
                  <div className="grid grid-cols-1 gap-2 min-[420px]:grid-cols-3">
                    {(indicators.atlas_uf_context.kpis || []).map((kpi) => (
                      <div
                        key={kpi.label}
                        className="min-w-0 rounded-md border border-zinc-800/80 bg-zinc-950/50 px-2 py-1.5 text-center"
                      >
                        <span className="block text-[8px] uppercase leading-snug text-zinc-500 line-clamp-2">
                          {kpi.label}
                        </span>
                        <span className="mt-0.5 block text-[11px] font-bold text-zinc-200">{kpi.valor}</span>
                      </div>
                    ))}
                  </div>
                  <p className="text-[9px] leading-snug text-zinc-500">
                    Matrizes: {indicators.atlas_uf_context.matrizes.join(' · ')} · escopo estadual (NF-e{' '}
                    {indicators.atlas_uf_context.referencia_ano})
                  </p>
                  <a
                    href={indicators.atlas_uf_context.portal_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex rounded-full border border-violet-500/30 bg-violet-500/10 px-2 py-0.5 text-[10px] font-bold text-violet-200 hover:bg-violet-500/20"
                  >
                    Abrir Atlas Econômico IPEA ↗
                  </a>
                </div>
              </KpiCard>
            )}
          </div>
          {indicators?.pib_serie && indicators.pib_serie.length >= 3 && (
            <div className="mt-4 rounded-xl border border-zinc-800 bg-zinc-950/40 p-3">
              <h5 className="mb-2 text-[10px] font-extrabold uppercase tracking-wide text-zinc-400">
                Série histórica PIB municipal (mil R$)
              </h5>
              <div className="h-40">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={indicators.pib_serie.map((p) => ({
                      ano: String(p.ano),
                      pib: p.valor_mil_reais / 1000,
                    }))}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                    <XAxis dataKey="ano" tick={{ fill: '#71717a', fontSize: 9 }} />
                    <YAxis tick={{ fill: '#71717a', fontSize: 9 }} width={42} />
                    <Tooltip
                      formatter={(value: number) => [`R$ ${value.toFixed(1)} bi`, 'PIB']}
                      contentStyle={{ background: '#09090b', border: '1px solid #3f3f46', fontSize: 11 }}
                    />
                    <Line type="monotone" dataKey="pib" stroke="#34d399" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-1 text-[9px] text-zinc-500">
                Fonte: IBGE SIDRA agregado 5938/37 · espelhado no Ipeadata (PIB_IBGE_5938_37)
              </p>
            </div>
          )}
        </PanelSection>
      )}

      {integrationStatus && (
        <div className="rounded-xl border border-border bg-card/30 p-3">
          <h4 className="mb-2 text-[10px] font-extrabold uppercase tracking-wide text-zinc-400">Status das integrações públicas</h4>
          <div className="flex flex-wrap gap-2">
            {integrationStatus.sources.map((source) => (
              <span
                key={source.source}
                className={`rounded-full border px-2 py-0.5 text-[9px] font-bold uppercase ${
                  source.status === 'OK'
                    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                    : source.status === 'FALHA'
                      ? 'border-rose-500/30 bg-rose-500/10 text-rose-300'
                      : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                }`}
              >
                {source.source}: {source.status} ({source.records_count})
              </span>
            ))}
          </div>
        </div>
      )}

      {maturity && (
        <div className={`rounded-xl border p-4 ${TIER_STYLE[maturity.classificacao]?.border || 'border-zinc-700'} ${TIER_STYLE[maturity.classificacao]?.bg || 'bg-zinc-900/40'}`}>
          <div className="mb-3 flex items-center justify-between gap-2">
            <h4 className="flex items-center gap-2 text-xs font-extrabold uppercase tracking-wide text-zinc-200">
              <Award size={14} className={TIER_STYLE[maturity.classificacao]?.text} />
              Score de Maturidade Municipal
            </h4>
            <span className={`rounded-full border px-3 py-1 text-[11px] font-extrabold uppercase ${TIER_STYLE[maturity.classificacao]?.border} ${TIER_STYLE[maturity.classificacao]?.text}`}>
              {maturity.classificacao}
            </span>
          </div>
          <div className="mb-3 flex items-end gap-3">
            <span className="text-4xl font-black text-zinc-100">{Math.round(maturity.score)}</span>
            <span className="pb-1 text-sm text-zinc-500">/ 100</span>
            <span className="pb-1 ml-auto text-[10px] text-zinc-500">
              Completude {Math.round(maturity.completeness_score)}%
            </span>
          </div>
          <p className="mb-3 text-[10px] text-zinc-400">{maturity.resumo}</p>
          <div className="grid grid-cols-2 gap-2">
            {maturity.fontes.map((fonte) => (
              <div key={fonte.id} className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
                <div className="flex items-center justify-between gap-1">
                  <strong className="truncate text-[10px] text-zinc-200">{fonte.nome}</strong>
                  <span className={`shrink-0 rounded px-1.5 py-0.5 text-[8px] font-bold uppercase ${SOURCE_STATUS_STYLE[fonte.status] || 'bg-zinc-800 text-zinc-400'}`}>
                    {fonte.status}
                  </span>
                </div>
                <p className="mt-0.5 text-[9px] text-zinc-500">{fonte.detail || fonte.recomendacao}</p>
              </div>
            ))}
          </div>
          {maturity.fontes_faltantes.length > 0 && (
            <p className="mt-3 text-[9px] text-rose-300/80">
              Faltantes: {maturity.fontes_faltantes.map((f) => f.nome).join(' · ')}
            </p>
          )}
        </div>
      )}

      {coverage && (
        <div className="rounded-xl border border-border bg-card/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-xs font-extrabold uppercase tracking-wide text-zinc-200">Radar de Integração de Dados</h4>
            <span className="rounded-full border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 text-[10px] font-bold text-indigo-200">
              {coverage.classificacao}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            {coverage.lacunas_prioritarias.slice(0, 4).map((item) => (
              <div key={item.id} className="rounded-lg border border-zinc-800 bg-zinc-950/60 p-2">
                <div className="flex items-center justify-between gap-2">
                  <strong className="truncate text-[10px] text-zinc-200">{item.nome}</strong>
                  <span className={`shrink-0 rounded px-1.5 py-0.5 text-[8px] font-bold uppercase ${
                    item.status === 'Ausente' ? 'bg-rose-500/15 text-rose-300' : 'bg-amber-500/15 text-amber-300'
                  }`}>
                    {item.status}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-[9px] leading-snug text-zinc-500">{item.recomendacao}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recharts Graphics List */}
      <div className="flex flex-col gap-4">
        {/* Neighborhood indices comparison */}
        <div className="bg-card/40 backdrop-blur-md border border-border p-4.5 rounded-xl flex flex-col">
          <div className="mb-3">
            <h4 className="font-extrabold text-zinc-200 text-xs uppercase tracking-wide">Vulnerabilidade por Bairro</h4>
            <p className="text-[10px] text-zinc-400 mt-0.5">Comparação entre <TermTooltip term="IVC" /> e <TermTooltip term="IRI" /> (0 a 1.0)</p>
          </div>
          <div className="h-56 w-full text-[10px]">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="99%" height="100%">
                <BarChart data={chartData} margin={{ left: -20, right: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="name" stroke="#71717a" />
                  <YAxis stroke="#71717a" domain={[0, 1.0]} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }}
                    itemStyle={{ color: '#e4e4e7' }}
                  />
                  <Legend iconSize={8} />
                  <Bar dataKey="Vulnerabilidade" fill="#f43f5e" name="Vulnerabilidade (IVC)" radius={[2, 2, 0, 0]} />
                  <Bar dataKey="Inundaçao" fill="#0ea5e9" name="Risco Inundação (IRI)" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-zinc-700 bg-zinc-900/40 px-4 text-center text-[11px] text-zinc-400">
                {indices
                  ? 'Nenhum bairro com índices IVC/IRI calculados para este município.'
                  : 'Índices de vulnerabilidade indisponíveis. Verifique se o onboarding foi concluído.'}
              </div>
            )}
          </div>
        </div>

        {/* Heat Island historical trends */}
        <div className="bg-card/40 backdrop-blur-md border border-border p-4.5 rounded-xl flex flex-col">
          <div className="mb-3">
            <h4 className="font-extrabold text-zinc-200 text-xs uppercase tracking-wide">
              Uso de Solo vs Clima Urbano - {isEstimatedClimateChart ? 'Série Estimada' : hasMapBiomasSeries ? 'Fonte Oficial' : 'Parcial'}
            </h4>
            <p className="text-[10px] text-zinc-400 mt-0.5">
              {officialClimate?.station
                ? `Temperatura do ar: INMET ${officialClimate.station.nome} (${officialClimate.station.codigo}), ${officialClimate.station.distancia_km} km`
                : 'Série estimada exibida porque as fontes oficiais ainda não retornaram dados completos'}
              {climateYears.length > 0 ? ` · ${climateYears.length} anos (${climateYears[0]}–${climateYears[climateYears.length - 1]})` : ''}
            </p>
          </div>
          {climateChartData.length > 0 ? (
            <div className="h-56 w-full text-[10px]">
              <ResponsiveContainer width="99%" height="100%">
                <LineChart data={climateChartData} margin={{ left: -20, right: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                  <XAxis dataKey="ano" stroke="#71717a" />
                  <YAxis yAxisId="left" stroke="#10b981" domain={tempDomain} />
                  <YAxis yAxisId="right" orientation="right" stroke="#6366f1" domain={areaDomain} />
                  <Tooltip contentStyle={{ backgroundColor: '#18181b', border: '1px solid #27272a', borderRadius: '8px' }} />
                  <Legend iconSize={8} />
                  {hasTemperatureSeries && (
                    <Line yAxisId="left" type="monotone" dataKey="temp" stroke="#10b981" strokeWidth={2} name={tempLegendLabel} dot={{ r: 3 }} connectNulls />
                  )}
                  <Line yAxisId="right" type="monotone" dataKey="area" stroke="#6366f1" strokeWidth={2} name={isEstimatedClimateChart ? 'Área urbanizada estimada (km²)' : 'Área urbanizada MapBiomas (km²)'} dot={{ r: 3 }} connectNulls />
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 p-4 text-[10px] leading-relaxed text-zinc-400">
              Ainda não há série anual oficial retornada pela API pública do INMET para a estação selecionada. O gráfico demonstrativo foi removido para evitar interpretação indevida.
            </div>
          )}
          <p className="mt-2 rounded-lg border border-amber-500/20 bg-amber-950/10 p-2 text-[9px] leading-relaxed text-amber-200/80">
            Fonte: {isEstimatedClimateChart ? (officialClimate?.estimated_source || 'Estimativa interna Sinidu+Clima') : (officialClimate?.source || 'INMET + MapBiomas pendente')}. {isEstimatedClimateChart ? officialClimate?.estimated_methodology : officialClimate?.source_note}
            {officialClimate?.lacunas?.length ? ` Lacunas: ${officialClimate.lacunas.join(' ')}` : ''}
          </p>
        </div>
      </div>

    </div>
  );

}
