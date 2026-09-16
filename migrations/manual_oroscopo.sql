-- ============================================================================
-- oroscopo_settimanale: oroscopo in chiave estetista, pubblicato a mano dalla
-- pagina Contenuti Report (appl/contenuti_report.py).
--
-- In tabella c'e' solo il testo per segno: simbolo e periodo dello zodiaco
-- sono dati fissi e stanno nel codice.
--
-- Eseguire UNA VOLTA su OGNI database PostgreSQL (suncity, sunexp3, sunbookingdb).
-- Idempotente: usa IF NOT EXISTS, puoi rilanciarlo senza danni.
-- ============================================================================

CREATE TABLE IF NOT EXISTS oroscopo_settimanale (
    id          SERIAL PRIMARY KEY,
    scan_batch  VARCHAR(40) NOT NULL,
    segno       VARCHAR(30) NOT NULL,
    testo       TEXT        NOT NULL,
    ordine      INTEGER DEFAULT 0,
    created_at  TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_oroscopo_settimanale_scan_batch
    ON oroscopo_settimanale (scan_batch);
