-- Expansão Sinidu+Clima: 50 municípios prioritários + saúde + segurança
CREATE TABLE IF NOT EXISTS municipios_seed (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) UNIQUE NOT NULL,
    nome VARCHAR(120) NOT NULL,
    uf VARCHAR(2) NOT NULL,
    criterio VARCHAR(40) NOT NULL,
    decretos_emergencia INTEGER DEFAULT 0,
    score_sinidu NUMERIC(6, 3),
    status_carga VARCHAR(24) DEFAULT 'pendente',
    lacunas JSONB DEFAULT '[]'::jsonb,
    prioridade INTEGER DEFAULT 0,
    geom_fonte VARCHAR(40),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_municipios_seed_criterio ON municipios_seed(criterio);
CREATE INDEX IF NOT EXISTS idx_municipios_seed_status ON municipios_seed(status_carga);

CREATE TABLE IF NOT EXISTS estabelecimentos_saude (
    id SERIAL PRIMARY KEY,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE CASCADE,
    codigo_ibge VARCHAR(7) NOT NULL,
    cnes_codigo VARCHAR(20),
    nome VARCHAR(255) NOT NULL,
    tipo VARCHAR(40) NOT NULL,
    leitos_sus INTEGER DEFAULT 0,
    esf BOOLEAN DEFAULT FALSE,
    geom GEOMETRY(POINT, 4326),
    fonte VARCHAR(80) DEFAULT 'CNES/DataSUS',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_estab_saude_municipio ON estabelecimentos_saude(municipio_id);
CREATE INDEX IF NOT EXISTS idx_estab_saude_tipo ON estabelecimentos_saude(tipo);

CREATE TABLE IF NOT EXISTS municipios_saude (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) UNIQUE NOT NULL,
    mortalidade_causas_externas NUMERIC(10, 2),
    taxa_afogamento NUMERIC(10, 4),
    taxa_desabamento NUMERIC(10, 4),
    cobertura_esf NUMERIC(6, 3),
    ubs_count INTEGER DEFAULT 0,
    caps_count INTEGER DEFAULT 0,
    hospital_count INTEGER DEFAULT 0,
    leitos_sus_total INTEGER DEFAULT 0,
    cobertura_saude_score NUMERIC(6, 3),
    ano_ref INTEGER,
    lacunas JSONB DEFAULT '[]'::jsonb,
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS municipios_seguranca (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    mes_ref VARCHAR(7) NOT NULL,
    ocorrencias_violentas INTEGER DEFAULT 0,
    mortes_violentas INTEGER DEFAULT 0,
    roubos INTEGER DEFAULT 0,
    taxa_100k NUMERIC(10, 2),
    cobertura_seguranca_score NUMERIC(6, 3),
    fonte VARCHAR(80) DEFAULT 'SINESP/dados.gov.br',
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(codigo_ibge, mes_ref)
);

CREATE INDEX IF NOT EXISTS idx_municipios_seguranca_ibge ON municipios_seguranca(codigo_ibge);
