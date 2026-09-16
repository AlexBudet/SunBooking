-- ============================================================================
-- beauty_news: notizie dal mondo beauty / estetica / normativa / solarium,
-- pubblicate a mano dalla pagina Contenuti Report (appl/contenuti_report.py).
--
-- Eseguire UNA VOLTA su OGNI database PostgreSQL (suncity, sunexp3, sunbookingdb).
-- Idempotente: usa IF NOT EXISTS, puoi rilanciarlo senza danni.
-- ============================================================================

CREATE TABLE IF NOT EXISTS beauty_news (
    id            SERIAL PRIMARY KEY,
    scan_batch    VARCHAR(40)  NOT NULL,
    titolo        VARCHAR(300) NOT NULL,
    sintesi       TEXT,
    categoria     VARCHAR(50),
    fonte         VARCHAR(200),
    url           VARCHAR(1000),
    data_notizia  DATE,
    ordine        INTEGER DEFAULT 0,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_beauty_news_scan_batch
    ON beauty_news (scan_batch);
