-- Fase 21a: arquivar previsão/alertas + tabela de verificação (não apagar série)

CREATE TABLE IF NOT EXISTS weather_forecast_archive (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    codigo_ibge VARCHAR(7) NOT NULL,
    lat NUMERIC(10, 6),
    lng NUMERIC(10, 6),
    precip_24h_mm NUMERIC(8, 2) DEFAULT 0,
    precip_72h_mm NUMERIC(8, 2) DEFAULT 0,
    risk_probability NUMERIC(5, 4) DEFAULT 0,
    raw_payload JSONB,
    fetched_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    archived_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_weather_forecast_archive_codigo_ibge ON weather_forecast_archive (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_weather_forecast_archive_fetched_at ON weather_forecast_archive (fetched_at);
CREATE INDEX IF NOT EXISTS ix_weather_forecast_archive_archived_at ON weather_forecast_archive (archived_at);

CREATE TABLE IF NOT EXISTS monitoring_alerts_archive (
    id SERIAL PRIMARY KEY,
    original_id INTEGER,
    municipio_id INTEGER,
    codigo_ibge VARCHAR(7) NOT NULL,
    tipo VARCHAR(30) NOT NULL,
    nivel VARCHAR(20) NOT NULL DEFAULT 'VERDE',
    titulo VARCHAR(255) NOT NULL,
    mensagem TEXT,
    payload JSONB,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
    expires_at TIMESTAMP WITHOUT TIME ZONE,
    archived_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_monitoring_alerts_archive_codigo_ibge ON monitoring_alerts_archive (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_monitoring_alerts_archive_created_at ON monitoring_alerts_archive (created_at);
CREATE INDEX IF NOT EXISTS ix_monitoring_alerts_archive_archived_at ON monitoring_alerts_archive (archived_at);

CREATE TABLE IF NOT EXISTS previsao_verificacao (
    id SERIAL PRIMARY KEY,
    codigo_ibge VARCHAR(7) NOT NULL,
    municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL,
    previsto_em TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    horizonte_h INTEGER NOT NULL DEFAULT 24,
    precip_24h_mm NUMERIC(8, 2),
    precip_48h_mm NUMERIC(8, 2),
    precip_72h_mm NUMERIC(8, 2),
    precip_7d_mm NUMERIC(8, 2),
    risk_score NUMERIC(5, 4) NOT NULL,
    risk_source VARCHAR(40) NOT NULL,
    score_kind VARCHAR(40),
    model_kind VARCHAR(40),
    desfecho_ocorrido BOOLEAN,
    desfecho_verificado_em TIMESTAMP WITHOUT TIME ZONE,
    desfecho_fonte VARCHAR(80),
    payload JSONB
);
CREATE INDEX IF NOT EXISTS ix_previsao_verificacao_codigo_ibge ON previsao_verificacao (codigo_ibge);
CREATE INDEX IF NOT EXISTS ix_previsao_verificacao_previsto_em ON previsao_verificacao (previsto_em);
