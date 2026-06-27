-- ============================================================================
-- DGFE readings: persistenza in DB delle riconciliazioni DGFE<->corrispettivi
-- (sostituisce il vecchio log JSON su file).
--
-- Eseguire UNA VOLTA sul database PostgreSQL (Azure).
-- Idempotente: usa IF NOT EXISTS, puoi rilanciarlo senza danni.
-- ============================================================================

CREATE TABLE IF NOT EXISTS dgfe_readings (
    id               SERIAL PRIMARY KEY,
    business_info_id INTEGER NOT NULL DEFAULT 0,
    giorno           DATE    NOT NULL,
    dgfe_total       DOUBLE PRECISION,
    dgfe_count       INTEGER,
    status           VARCHAR(32),
    run_at           TIMESTAMP,
    payload          TEXT,
    updated_at       TIMESTAMP,
    CONSTRAINT uq_dgfe_readings_bi_day UNIQUE (business_info_id, giorno)
);

CREATE INDEX IF NOT EXISTS ix_dgfe_readings_giorno
    ON dgfe_readings (giorno);

CREATE INDEX IF NOT EXISTS ix_dgfe_readings_business_info_id
    ON dgfe_readings (business_info_id);
