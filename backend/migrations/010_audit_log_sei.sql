CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    username VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(64),
    resource_id VARCHAR(64),
    codigo_ibge VARCHAR(7),
    metadata JSONB DEFAULT '{}',
    ip_address VARCHAR(45),
    user_agent VARCHAR(512),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_username ON audit_log(username);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_codigo_ibge ON audit_log(codigo_ibge);

ALTER TABLE relatorios_municipais
    ADD COLUMN IF NOT EXISTS sha256_hash VARCHAR(64);

CREATE INDEX IF NOT EXISTS idx_relatorios_sha256 ON relatorios_municipais(sha256_hash);
