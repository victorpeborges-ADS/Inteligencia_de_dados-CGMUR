-- Fase 21b/21c: chuva observada + ground truth + qualidade S2ID

ALTER TABLE historico_desastres_s2id
    ADD COLUMN IF NOT EXISTS data_quality VARCHAR(30) NOT NULL DEFAULT 'estimado';
ALTER TABLE historico_desastres_s2id
    ADD COLUMN IF NOT EXISTS fonte VARCHAR(80);
ALTER TABLE historico_desastres_s2id
    ADD COLUMN IF NOT EXISTS referencia VARCHAR(255);

CREATE INDEX IF NOT EXISTS ix_historico_desastres_s2id_data_quality
    ON historico_desastres_s2id (data_quality);

-- Pilotos curados já existentes: promover qualidade (heurística por danos != placeholder)
UPDATE historico_desastres_s2id
SET data_quality = 'oficial_curado',
    fonte = COALESCE(fonte, 's2id_curado')
WHERE data_quality = 'estimado'
  AND COALESCE(danos_materiais, 0) <> 250000
  AND municipio_id IN (
      SELECT id FROM municipios
      WHERE codigo_ibge IN ('2611606','2800308','2927408','3304557','3550308','5300108')
  );

CREATE TABLE IF NOT EXISTS serie_pluviometrica_observada (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    estacao_id VARCHAR(64) NOT NULL,
    estacao_nome VARCHAR(120),
    lat NUMERIC(10, 6),
    lng NUMERIC(10, 6),
    observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    precip_mm NUMERIC(8, 2) NOT NULL DEFAULT 0,
    granularidade VARCHAR(20) NOT NULL DEFAULT 'diaria',
    data_quality VARCHAR(30) NOT NULL DEFAULT 'reanalise',
    fonte VARCHAR(40) NOT NULL,
    ingestido_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS ix_serie_pluvio_codigo_ibge ON serie_pluviometrica_observada (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_serie_pluvio_observed_at ON serie_pluviometrica_observada (observed_at);
CREATE INDEX IF NOT EXISTS ix_serie_pluvio_fonte ON serie_pluviometrica_observada (fonte);
CREATE INDEX IF NOT EXISTS ix_serie_pluvio_data_quality ON serie_pluviometrica_observada (data_quality);
CREATE UNIQUE INDEX IF NOT EXISTS ux_serie_pluvio_fonte_estacao_ts_muni
    ON serie_pluviometrica_observada (fonte, estacao_id, observed_at, codigo_ibge);

CREATE TABLE IF NOT EXISTS evento_alagamento_observado (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    tipo VARCHAR(50) NOT NULL,
    inicio_em TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    fim_em TIMESTAMP WITHOUT TIME ZONE,
    severidade VARCHAR(20),
    populacao_afetada INTEGER,
    precip_acumulada_mm NUMERIC(8, 2),
    fonte VARCHAR(80) NOT NULL,
    data_quality VARCHAR(30) NOT NULL DEFAULT 'oficial',
    referencia VARCHAR(255),
    geom geometry(Geometry, 4326),
    criado_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    payload JSONB
);
CREATE INDEX IF NOT EXISTS ix_evento_alagamento_codigo_ibge ON evento_alagamento_observado (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_evento_alagamento_inicio_em ON evento_alagamento_observado (inicio_em);
CREATE INDEX IF NOT EXISTS ix_evento_alagamento_data_quality ON evento_alagamento_observado (data_quality);
CREATE INDEX IF NOT EXISTS ix_evento_alagamento_geom ON evento_alagamento_observado USING GIST (geom);
