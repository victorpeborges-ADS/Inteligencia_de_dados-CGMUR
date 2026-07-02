-- Rastreabilidade de dados municipais (Step 1 — auditoria e honestidade)
ALTER TABLE bairros ADD COLUMN IF NOT EXISTS fonte_malha VARCHAR(40);
ALTER TABLE bairros ADD COLUMN IF NOT EXISTS fonte_socioeconomico VARCHAR(40);
ALTER TABLE bairros ADD COLUMN IF NOT EXISTS pop_censo2022 INTEGER;
ALTER TABLE bairros ADD COLUMN IF NOT EXISTS renda_media_censo2022 NUMERIC(12, 2);

ALTER TABLE setores_censitarios ADD COLUMN IF NOT EXISTS fonte_renda VARCHAR(40);

ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS score_confiabilidade VARCHAR(16);
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS malha_fonte VARCHAR(40);
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS auditoria_flags JSONB DEFAULT '{}'::jsonb;
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS auditoria_at TIMESTAMPTZ;
