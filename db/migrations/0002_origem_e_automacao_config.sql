-- Migracao idempotente - aplicar no container ja existente (schema.sql so roda em volume novo).
-- Uso: docker exec -i sap_import_postgres psql -U sap_import -d sap_import -f - < db/migrations/0002_origem_e_automacao_config.sql

ALTER TABLE import_execucao
    ADD COLUMN IF NOT EXISTS origem TEXT NOT NULL DEFAULT 'excel_manual';

CREATE TABLE IF NOT EXISTS automacao_config (
    id             SMALLINT PRIMARY KEY DEFAULT 1,
    modo           TEXT NOT NULL DEFAULT 'manual' CHECK (modo IN ('manual', 'automatico')),
    atualizado_em  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT automacao_config_singleton CHECK (id = 1)
);

INSERT INTO automacao_config (id, modo) VALUES (1, 'manual') ON CONFLICT (id) DO NOTHING;
