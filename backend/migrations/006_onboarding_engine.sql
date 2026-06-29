-- Etapa 1: Municipal Onboarding Engine — campos de status unificado

ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS municipio_id INTEGER REFERENCES municipios(id) ON DELETE SET NULL;
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS onboarding_status VARCHAR(24) DEFAULT 'pendente';
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS maturity_score NUMERIC(6, 2);
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS completeness_score NUMERIC(6, 2);
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS integration_errors JSONB DEFAULT '[]'::jsonb;
ALTER TABLE municipios_seed ADD COLUMN IF NOT EXISTS integration_steps JSONB DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS idx_municipios_seed_onboarding ON municipios_seed(onboarding_status);

UPDATE municipios_seed
SET onboarding_status = COALESCE(
    CASE status_carga
        WHEN 'carregado' THEN 'concluido'
        WHEN 'parcial' THEN 'parcial'
        ELSE 'pendente'
    END,
    'pendente'
)
WHERE onboarding_status IS NULL OR onboarding_status = 'pendente';
