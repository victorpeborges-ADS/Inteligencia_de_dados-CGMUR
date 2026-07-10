-- Exposição oficial IBGE SINGED Lab — enchentes RS 2024 (CNEFE/Censo 2022)
CREATE TABLE IF NOT EXISTS municipio_singedlab_rs (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL UNIQUE,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    escopo VARCHAR(24) NOT NULL DEFAULT 'nao_aplicavel',
    evento VARCHAR(64) NOT NULL DEFAULT 'enchentes_rs_2024',
    populacao_area_afetada INTEGER,
    domicilios_area_afetada INTEGER,
    estabelecimentos_area_afetada INTEGER,
    pct_populacao_municipio NUMERIC(6, 2),
    pct_area_municipio NUMERIC(6, 2),
    indicadores JSONB DEFAULT '{}'::jsonb,
    data_quality VARCHAR(32) NOT NULL DEFAULT 'ausente',
    fonte_url TEXT DEFAULT 'https://www.ibge.gov.br/singedlab/dados-apoio-rs.php',
    fonte_ref TEXT,
    sincronizado_em TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_singedlab_codigo_ibge ON municipio_singedlab_rs(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_singedlab_escopo ON municipio_singedlab_rs(escopo);
