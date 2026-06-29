-- Integração de dados oficiais IBGE / SICONFI / CAPAG
CREATE TABLE IF NOT EXISTS municipios_ibge (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL UNIQUE,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    populacao INTEGER,
    populacao_ano INTEGER,
    area_km2 NUMERIC(12, 3),
    area_ano INTEGER,
    pib_per_capita NUMERIC(14, 2),
    pib_ano INTEGER,
    idh NUMERIC(4, 3),
    idh_ano INTEGER,
    densidade_demografica NUMERIC(12, 2),
    data_quality VARCHAR(20) DEFAULT 'oficial',
    fonte VARCHAR(255),
    atualizado_em TIMESTAMPTZ,
    raw_payload TEXT
);

CREATE TABLE IF NOT EXISTS municipios_fiscal (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL UNIQUE,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    receita_corrente_liquida NUMERIC(18, 2),
    despesa_pessoal_pct_rcl NUMERIC(8, 4),
    divida_consolidada NUMERIC(18, 2),
    resultado_primario NUMERIC(18, 2),
    exec_saude NUMERIC(18, 2),
    exec_habitacao NUMERIC(18, 2),
    exec_saneamento NUMERIC(18, 2),
    exec_meio_ambiente NUMERIC(18, 2),
    exec_defesa_civil NUMERIC(18, 2),
    nota_capag VARCHAR(2),
    exercicio INTEGER,
    periodo INTEGER,
    data_quality VARCHAR(20) DEFAULT 'oficial',
    fonte VARCHAR(255),
    atualizado_em TIMESTAMPTZ,
    raw_payload TEXT
);

CREATE TABLE IF NOT EXISTS integration_runs (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    records_count INTEGER DEFAULT 0,
    last_success_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_municipios_ibge_codigo ON municipios_ibge(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_municipios_fiscal_codigo ON municipios_fiscal(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_integration_runs_source ON integration_runs(source);
