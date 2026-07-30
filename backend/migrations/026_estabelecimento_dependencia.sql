-- 026: dependência administrativa em estabelecimentos de saúde
ALTER TABLE estabelecimentos_saude
  ADD COLUMN IF NOT EXISTS dependencia VARCHAR(20);

CREATE INDEX IF NOT EXISTS ix_estabelecimentos_saude_dependencia
  ON estabelecimentos_saude (dependencia);
