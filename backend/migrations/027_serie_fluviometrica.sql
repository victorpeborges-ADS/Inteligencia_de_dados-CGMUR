-- Fase 21c.3/21d.9: série fluviométrica observada (ANA) + fenômeno pluvial/fluvial/misto

CREATE TABLE IF NOT EXISTS serie_fluviometrica_observada (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    estacao_id VARCHAR(64) NOT NULL,
    estacao_nome VARCHAR(120),
    lat NUMERIC(10, 6),
    lng NUMERIC(10, 6),
    observed_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    cota_m NUMERIC(10, 3),
    vazao_m3s NUMERIC(12, 3),
    granularidade VARCHAR(20) NOT NULL DEFAULT 'horaria',
    data_quality VARCHAR(30) NOT NULL DEFAULT 'oficial',
    fonte VARCHAR(40) NOT NULL DEFAULT 'ana',
    ingestido_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    raw_payload JSONB
);
CREATE INDEX IF NOT EXISTS ix_serie_fluvio_codigo_ibge ON serie_fluviometrica_observada (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_serie_fluvio_observed_at ON serie_fluviometrica_observada (observed_at);
CREATE INDEX IF NOT EXISTS ix_serie_fluvio_fonte ON serie_fluviometrica_observada (fonte);
CREATE INDEX IF NOT EXISTS ix_serie_fluvio_data_quality ON serie_fluviometrica_observada (data_quality);
CREATE UNIQUE INDEX IF NOT EXISTS ux_serie_fluvio_fonte_estacao_ts_muni
    ON serie_fluviometrica_observada (fonte, estacao_id, observed_at, codigo_ibge);

-- 21d.9 — separa fenômeno pluvial (chuva local) de fluvial (cheia de rio) e misto
ALTER TABLE evento_alagamento_observado
    ADD COLUMN IF NOT EXISTS fenomeno VARCHAR(20); -- pluvial | fluvial | misto

CREATE INDEX IF NOT EXISTS ix_evento_alagamento_fenomeno ON evento_alagamento_observado (fenomeno);
