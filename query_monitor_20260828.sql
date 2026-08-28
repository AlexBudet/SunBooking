-- ============================================================================
-- Pannello consumi e capienza - tabelle nuove
-- Da eseguire su OGNI tenant: suncity, sunexp3, sunbookingdb
-- Generato dai modelli in appl/models.py il 28/08/2026
-- ============================================================================
-- Nessuna tabella esistente viene toccata: sono due CREATE nuove e basta.
-- Finche' non esistono, l'applicazione continua a funzionare - il conteggio
-- fallisce in silenzio (registra_uso non solleva mai) e il pannello mostra
-- semplicemente i riquadri vuoti.

CREATE TABLE IF NOT EXISTS usage_events (
    id          SERIAL       NOT NULL,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    canale      VARCHAR(20)  NOT NULL,
    tipo        VARCHAR(40)  NOT NULL,
    origine     VARCHAR(20)  NOT NULL,
    esito       VARCHAR(10)  NOT NULL,
    errore      VARCHAR(300),
    PRIMARY KEY (id)
);

CREATE INDEX IF NOT EXISTS ix_usage_events_created_at  ON usage_events (created_at);
CREATE INDEX IF NOT EXISTS ix_usage_events_canale      ON usage_events (canale);
CREATE INDEX IF NOT EXISTS ix_usage_events_esito       ON usage_events (esito);
CREATE INDEX IF NOT EXISTS ix_usage_events_canale_data ON usage_events (canale, created_at);


CREATE TABLE IF NOT EXISTS usage_traffic_hourly (
    id         SERIAL   NOT NULL,
    ora        TIMESTAMP WITH TIME ZONE NOT NULL,
    richieste  INTEGER  NOT NULL DEFAULT 0,
    errori     INTEGER  NOT NULL DEFAULT 0,
    ms_totali  BIGINT   NOT NULL DEFAULT 0,
    ms_max     INTEGER  NOT NULL DEFAULT 0,
    PRIMARY KEY (id)
);

-- L'indice UNICO su `ora` non e' un vezzo: lo scarico orario e' una INSERT ...
-- ON CONFLICT (ora), e ON CONFLICT ha bisogno di un vincolo unico su quella
-- colonna. Senza questo indice il conteggio del traffico fallisce a ogni ora.
CREATE UNIQUE INDEX IF NOT EXISTS ix_usage_traffic_hourly_ora
    ON usage_traffic_hourly (ora);


-- ============================================================================
-- Verifica (attesi: 2 tabelle, 5 indici)
-- ============================================================================
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('usage_events', 'usage_traffic_hourly')
ORDER BY table_name;

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'public' AND tablename IN ('usage_events', 'usage_traffic_hourly')
ORDER BY indexname;
