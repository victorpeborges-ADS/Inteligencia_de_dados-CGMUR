-- Censo Escolar INEP — escolas com matrículas por etapa
CREATE TABLE IF NOT EXISTS escolas_inep (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
    codigo_inep VARCHAR(20) NOT NULL,
    nome VARCHAR(255) NOT NULL,
    dependencia VARCHAR(32),
    localizacao VARCHAR(16) DEFAULT 'urbana',
    ano INTEGER NOT NULL DEFAULT 2023,
    matriculas_total INTEGER DEFAULT 0,
    matriculas_infantil INTEGER DEFAULT 0,
    matriculas_fundamental INTEGER DEFAULT 0,
    matriculas_medio INTEGER DEFAULT 0,
    geom GEOMETRY(POINT, 4326),
    fonte VARCHAR(128) DEFAULT 'inep_censo_escolar',
    data_quality VARCHAR(24) DEFAULT 'oficial',
    atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_escolas_inep_muni_codigo_ano UNIQUE (municipio_id, codigo_inep, ano)
);

CREATE INDEX IF NOT EXISTS idx_escolas_inep_municipio ON escolas_inep(municipio_id);
CREATE INDEX IF NOT EXISTS idx_escolas_inep_geom ON escolas_inep USING GIST (geom);
