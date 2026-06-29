-- Plano de contingenciamento e monitoramento semi-real-time

CREATE TABLE IF NOT EXISTS contingency_plans (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
    cenario_tipo VARCHAR(20) NOT NULL,
    nivel_alerta VARCHAR(10) NOT NULL DEFAULT 'VERDE',
    data_criacao TIMESTAMP NOT NULL DEFAULT NOW(),
    data_revisao TIMESTAMP NOT NULL DEFAULT NOW(),
    criado_por VARCHAR(120) DEFAULT 'sistema',
    zonas_evacuacao JSONB NOT NULL DEFAULT '[]'::jsonb,
    rotas_fuga JSONB NOT NULL DEFAULT '[]'::jsonb,
    pontos_apoio JSONB NOT NULL DEFAULT '[]'::jsonb,
    contatos_defesa_civil JSONB NOT NULL DEFAULT '[]'::jsonb,
    acoes_por_nivel JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(20) NOT NULL DEFAULT 'RASCUNHO',
    versao INTEGER NOT NULL DEFAULT 1,
    simulacao_ref JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contingency_plans_municipio ON contingency_plans(municipio_id);
CREATE INDEX IF NOT EXISTS idx_contingency_plans_status ON contingency_plans(status);

CREATE TABLE IF NOT EXISTS contingency_plan_revisions (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES contingency_plans(id) ON DELETE CASCADE,
    versao INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    revisado_em TIMESTAMP NOT NULL DEFAULT NOW(),
    revisado_por VARCHAR(120) DEFAULT 'sistema'
);

CREATE INDEX IF NOT EXISTS idx_contingency_revisions_plan ON contingency_plan_revisions(plan_id);

CREATE TABLE IF NOT EXISTS monitoring_alerts (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    codigo_ibge VARCHAR(7) NOT NULL,
    tipo VARCHAR(30) NOT NULL,
    nivel VARCHAR(20) NOT NULL DEFAULT 'VERDE',
    titulo VARCHAR(255) NOT NULL,
    mensagem TEXT,
    payload JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_ibge ON monitoring_alerts(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_monitoring_alerts_created ON monitoring_alerts(created_at);

CREATE TABLE IF NOT EXISTS weather_forecast_cache (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    lat NUMERIC(10, 6),
    lng NUMERIC(10, 6),
    precip_24h_mm NUMERIC(8, 2) DEFAULT 0,
    precip_72h_mm NUMERIC(8, 2) DEFAULT 0,
    risk_probability NUMERIC(5, 4) DEFAULT 0,
    raw_payload JSONB,
    fetched_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_weather_cache_ibge ON weather_forecast_cache(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_weather_cache_fetched ON weather_forecast_cache(fetched_at);
