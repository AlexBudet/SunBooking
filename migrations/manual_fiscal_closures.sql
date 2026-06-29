-- ============================================================================
-- fiscal_closures: registro persistente delle chiusure fiscali (Z) eseguite.
-- Una riga per ogni Z (numero Z, data/ora, giorno, totale del giorno).
--
-- Eseguire UNA VOLTA su OGNI database PostgreSQL del gestionale (Azure):
-- es. i 3 negozi -> lanciarlo su tutti e 3 i DB.
-- Idempotente: usa IF NOT EXISTS, puoi rilanciarlo senza danni.
-- ============================================================================

CREATE TABLE IF NOT EXISTS fiscal_closures (
    id               SERIAL PRIMARY KEY,
    business_info_id INTEGER NOT NULL DEFAULT 0,
    z_number         INTEGER,                 -- lastZ DOPO la chiusura (numero della Z)
    closed_at        TIMESTAMP NOT NULL,      -- quando e' stata eseguita
    giorno           DATE,                    -- giorno solare della Z
    dgfe_total       DOUBLE PRECISION,        -- totale del giorno (se noto)
    note             VARCHAR(255),
    CONSTRAINT uq_fiscal_closures_bi_z UNIQUE (business_info_id, z_number)
);

CREATE INDEX IF NOT EXISTS ix_fiscal_closures_business_info_id
    ON fiscal_closures (business_info_id);

CREATE INDEX IF NOT EXISTS ix_fiscal_closures_z_number
    ON fiscal_closures (z_number);

CREATE INDEX IF NOT EXISTS ix_fiscal_closures_giorno
    ON fiscal_closures (giorno);
