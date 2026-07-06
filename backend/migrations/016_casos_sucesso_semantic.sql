-- Casos de sucesso: schema enriquecido + embedding Mistral (1024d, alinhado ao RAG)
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS uuid UUID DEFAULT gen_random_uuid();
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS titulo VARCHAR(255);
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS municipio_nome VARCHAR(100);
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS municipio_uf CHAR(2);
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS populacao_aprox INTEGER;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS regiao VARCHAR(20);
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS tipo_intervencao VARCHAR(100);
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS problema_original TEXT;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS solucao_implementada TEXT;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS resultado_mensuravel TEXT;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS custo_estimado_reais BIGINT;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS programa_financiador VARCHAR(100);
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS ano_implementacao INTEGER;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS fonte_referencia TEXT;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS tags TEXT[];
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS imagem_url TEXT;
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS embedding vector(1024);
ALTER TABLE casos_sucesso ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

UPDATE casos_sucesso SET
  municipio_nome = COALESCE(municipio_nome, municipio),
  municipio_uf = COALESCE(municipio_uf, uf),
  problema_original = COALESCE(problema_original, problema),
  solucao_implementada = COALESCE(solucao_implementada, solucao),
  resultado_mensuravel = COALESCE(resultado_mensuravel, resultado),
  titulo = COALESCE(
    titulo,
    LEFT(COALESCE(municipio, municipio_nome, '') || ' — ' || LEFT(COALESCE(problema, problema_original, ''), 100), 255)
  )
WHERE municipio IS NOT NULL OR municipio_nome IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_casos_sucesso_regiao ON casos_sucesso (regiao);
CREATE INDEX IF NOT EXISTS idx_casos_sucesso_tipo ON casos_sucesso (tipo_intervencao);
CREATE INDEX IF NOT EXISTS idx_casos_sucesso_uf ON casos_sucesso (municipio_uf);
