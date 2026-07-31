-- Seed SQL: catálogo piloto (6 municípios) — gerado a partir de seeds/municipios_seed_50.yaml
-- Remove entradas fora do piloto (DB já existente) e upserta os 6.
DELETE FROM municipios_seed
WHERE codigo_ibge NOT IN (
  '2611606', '2800308', '2927408', '3550308', '3304557', '5300108'
);

INSERT INTO municipios_seed (codigo_ibge, nome, uf, criterio, decretos_emergencia, prioridade)
VALUES
  ('2611606', 'Recife', 'PE', 'capital', 32, 1),
  ('2800308', 'Aracaju', 'SE', 'capital', 17, 1),
  ('2927408', 'Salvador', 'BA', 'capital', 34, 1),
  ('3550308', 'São Paulo', 'SP', 'capital', 38, 1),
  ('3304557', 'Rio de Janeiro', 'RJ', 'capital', 41, 1),
  ('5300108', 'Brasília', 'DF', 'capital', 11, 1)
ON CONFLICT (codigo_ibge) DO UPDATE SET
  nome = EXCLUDED.nome,
  uf = EXCLUDED.uf,
  criterio = EXCLUDED.criterio,
  decretos_emergencia = EXCLUDED.decretos_emergencia,
  prioridade = EXCLUDED.prioridade,
  updated_at = NOW();
