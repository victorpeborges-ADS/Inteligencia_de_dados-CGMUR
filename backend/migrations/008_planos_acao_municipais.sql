-- Etapa 9: Planos de Ação Municipal
CREATE TABLE IF NOT EXISTS planos_acao_municipais (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
    codigo_ibge VARCHAR(7) NOT NULL,
    versao INTEGER NOT NULL DEFAULT 1,
    diagnostic_id INTEGER REFERENCES diagnosticos_executivos(id) ON DELETE SET NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'concluido',
    severidade VARCHAR(24),
    headline TEXT,
    conteudo JSONB NOT NULL DEFAULT '{}',
    origem VARCHAR(24) NOT NULL DEFAULT 'manual',
    gerado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_planos_acao_municipio ON planos_acao_municipais(municipio_id);
CREATE INDEX IF NOT EXISTS idx_planos_acao_ibge ON planos_acao_municipais(codigo_ibge);
CREATE INDEX IF NOT EXISTS idx_planos_acao_gerado ON planos_acao_municipais(gerado_em DESC);
