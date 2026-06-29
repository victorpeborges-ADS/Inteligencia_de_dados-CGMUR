CREATE TABLE IF NOT EXISTS relatorios_municipais (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER NOT NULL REFERENCES municipios(id) ON DELETE CASCADE,
    codigo_ibge VARCHAR(7) NOT NULL,
    nome_arquivo VARCHAR(255) NOT NULL,
    caminho_arquivo VARCHAR(512) NOT NULL,
    tamanho_bytes INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'concluido',
    erro_mensagem TEXT,
    gerado_em TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_relatorios_municipio_id ON relatorios_municipais(municipio_id);
CREATE INDEX IF NOT EXISTS idx_relatorios_codigo_ibge ON relatorios_municipais(codigo_ibge);
