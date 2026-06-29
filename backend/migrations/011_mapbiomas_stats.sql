-- Estatísticas MapBiomas por município/ano/classe (hectares)
CREATE TABLE IF NOT EXISTS mapbiomas_municipal_stats (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE CASCADE,
    ano INTEGER NOT NULL,
    classe_uso VARCHAR(80) NOT NULL,
    area_ha NUMERIC(14, 3) NOT NULL,
    colecao VARCHAR(32) DEFAULT '10.1',
    data_quality VARCHAR(24) DEFAULT 'derivado',
    fonte VARCHAR(255) DEFAULT 'MapBiomas / Sinidu+Clima',
    atualizado_em TIMESTAMP DEFAULT NOW(),
    UNIQUE (codigo_ibge, ano, classe_uso)
);

CREATE INDEX IF NOT EXISTS idx_mapbiomas_stats_ibge ON mapbiomas_municipal_stats (codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_mapbiomas_stats_muni ON mapbiomas_municipal_stats (municipio_id);
