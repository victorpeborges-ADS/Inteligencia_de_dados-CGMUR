-- Censo 2022 — déficits domiciliares por setor censitário (Fase 16b.3)
ALTER TABLE setores_censitarios
    ADD COLUMN IF NOT EXISTS deficits_censo_json JSONB,
    ADD COLUMN IF NOT EXISTS deficits_censo_fonte VARCHAR(80),
    ADD COLUMN IF NOT EXISTS deficits_censo_atualizado_em TIMESTAMPTZ;
