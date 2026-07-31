-- Territórios tradicionais e periferias — Fase 16d.1
CREATE TABLE IF NOT EXISTS territorios_especiais (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
    tipo VARCHAR(32) NOT NULL,
    nome VARCHAR(255) NOT NULL,
    codigo_oficial VARCHAR(64),
    populacao_estimada INTEGER,
    ano INTEGER DEFAULT 2022,
    geom GEOMETRY(MULTIPOLYGON, 4326),
    fonte VARCHAR(128) DEFAULT 'bases_oficiais',
    data_quality VARCHAR(24) DEFAULT 'oficial',
    atualizado_em TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_territorio_especial_muni_tipo_nome UNIQUE (municipio_id, tipo, nome)
);

CREATE INDEX IF NOT EXISTS idx_territorios_especiais_municipio ON territorios_especiais(municipio_id);
CREATE INDEX IF NOT EXISTS idx_territorios_especiais_geom ON territorios_especiais USING GIST (geom);
