-- Integração SNIS / SINISA — indicadores municipais de saneamento
CREATE TABLE IF NOT EXISTS municipios_saneamento (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL UNIQUE,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    cobertura_agua_pct NUMERIC(6, 2),
    cobertura_esgoto_pct NUMERIC(6, 2),
    indice_perdas_agua_pct NUMERIC(6, 2),
    indice_atendimento_esgoto_pct NUMERIC(6, 2),
    indice_drenagem NUMERIC(6, 2),
    ano_referencia INTEGER,
    data_quality VARCHAR(20) DEFAULT 'oficial',
    fonte VARCHAR(255),
    atualizado_em TIMESTAMPTZ,
    raw_payload TEXT
);

CREATE INDEX IF NOT EXISTS idx_municipios_saneamento_codigo ON municipios_saneamento(codigo_ibge);
