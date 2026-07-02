-- STEP 4: narrativa executiva gerada por IA (Mistral)
ALTER TABLE diagnosticos_executivos
    ADD COLUMN IF NOT EXISTS narrativa_ia TEXT,
    ADD COLUMN IF NOT EXISTS narrativa_ia_meta JSONB DEFAULT '{}'::jsonb;
