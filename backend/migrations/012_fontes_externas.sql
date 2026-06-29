-- Fontes externas estendidas (AdaptaBrasil, GeoSGB, SIRENE, Brasil MAIS)
CREATE TABLE IF NOT EXISTS municipio_fontes_externas (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL UNIQUE,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    adapta_score NUMERIC(6, 2),
    adapta_indicadores JSONB DEFAULT '{}',
    adapta_data_quality VARCHAR(24) DEFAULT 'ausente',
    geosgb_score NUMERIC(6, 2),
    geosgb_indicadores JSONB DEFAULT '{}',
    geosgb_data_quality VARCHAR(24) DEFAULT 'ausente',
    sirene_emissoes_tco2 NUMERIC(14, 2),
    sirene_indicadores JSONB DEFAULT '{}',
    sirene_data_quality VARCHAR(24) DEFAULT 'ausente',
    brasil_mais_indice NUMERIC(6, 2),
    brasil_mais_indicadores JSONB DEFAULT '{}',
    brasil_mais_data_quality VARCHAR(24) DEFAULT 'ausente',
    fonte_metodo VARCHAR(64) DEFAULT 'derivado_sinidu',
    sincronizado_em TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_mfe_codigo_ibge ON municipio_fontes_externas(codigo_ibge);
