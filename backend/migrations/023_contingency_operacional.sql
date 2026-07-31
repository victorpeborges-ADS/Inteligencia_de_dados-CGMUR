-- 17h.3c — Contingência operacional reforçada (recursos + protocolo de campo)

ALTER TABLE contingency_plans
    ADD COLUMN IF NOT EXISTS recursos_operacionais JSONB NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE contingency_plans
    ADD COLUMN IF NOT EXISTS protocolo_campo JSONB NOT NULL DEFAULT '{}'::jsonb;

ALTER TABLE contingency_plans
    ADD COLUMN IF NOT EXISTS cobrade_codigo VARCHAR(32);
