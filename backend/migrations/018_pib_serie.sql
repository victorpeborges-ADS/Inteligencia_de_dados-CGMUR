-- Série histórica de PIB municipal (IBGE agregado 5938 / variável 37)
ALTER TABLE municipios_ibge
    ADD COLUMN IF NOT EXISTS pib_total_mil_reais NUMERIC(18, 3),
    ADD COLUMN IF NOT EXISTS pib_serie JSONB DEFAULT '[]'::jsonb;
