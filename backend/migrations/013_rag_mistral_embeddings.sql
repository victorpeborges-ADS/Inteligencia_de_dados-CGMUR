-- Embeddings RAG via Mistral (mistral-embed, 1024 dimensões)
ALTER TABLE rag_documents DROP COLUMN IF EXISTS embedding;
ALTER TABLE rag_documents ADD COLUMN embedding vector(1024);
ALTER TABLE rag_documents ALTER COLUMN created_at SET DEFAULT NOW();
