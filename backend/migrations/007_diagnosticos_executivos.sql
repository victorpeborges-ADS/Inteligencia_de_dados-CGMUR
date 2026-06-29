-- Etapa 4: Diagnóstico Executivo Automático
CREATE TABLE IF NOT EXISTS diagnosticos_executivos (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
    codigo_ibge VARCHAR(7) NOT NULL,
    versao INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(20) NOT NULL DEFAULT 'concluido',
    headline TEXT NOT NULL,
    conteudo JSONB NOT NULL DEFAULT '{}',
    narrativa_md TEXT NOT NULL,
    origem VARCHAR(24) NOT NULL DEFAULT 'manual',
    gerado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_diagnosticos_executivos_municipio ON diagnosticos_executivos(municipio_id);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_executivos_ibge ON diagnosticos_executivos(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_diagnosticos_executivos_gerado ON diagnosticos_executivos(gerado_em DESC);
