-- Fase 16d.5 — Geoportal municipal (publicação CTM / upload malha)

CREATE TABLE IF NOT EXISTS municipio_geoportal_publicacao (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    tipo VARCHAR(24) NOT NULL,
    titulo VARCHAR(120) NOT NULL DEFAULT 'Malha de bairros CTM',
    url TEXT,
    arcgis_where VARCHAR(256) DEFAULT '1=1',
    nome_campo_bairro VARCHAR(64),
    arquivo_nome VARCHAR(255),
    feature_count INTEGER,
    status VARCHAR(24) DEFAULT 'registrado',
    mensagem TEXT,
    geojson_snapshot JSONB,
    ativo BOOLEAN DEFAULT TRUE,
    publicado_em TIMESTAMP DEFAULT NOW(),
    importado_em TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_geoportal_codigo_ibge
    ON municipio_geoportal_publicacao(codigo_ibge);

CREATE INDEX IF NOT EXISTS idx_geoportal_ativo
    ON municipio_geoportal_publicacao(codigo_ibge, ativo);
