-- ============================================================================
-- MARKETING: invii pianificati su piu' giorni (17/11/2026).
--
-- marketing_piani             = il piano (promo, testo, foto, quanti al giorno, ora)
-- marketing_piano_destinatari = i clienti del piano, uno per riga, col loro stato
-- Regole in appl/services/marketing_piani.py.
--
-- Due tabelle NUOVE: nessuna colonna aggiunta a tabelle esistenti, quindi se
-- Tosca parte prima di questo script funziona tutto come prima e manca solo
-- la pianificazione.
--
-- Eseguire UNA VOLTA su ogni database, collegati come Alessio, PRIMA del deploy:
--     suncity, sunexp3, sunbookingdb, demo1, demo2, demo3
-- Idempotente: rilanciarlo non fa danni.
-- ============================================================================

-- Si puo' eseguire a negozi aperti. L'unico contatto con una tabella esistente
-- e' il collegamento a "clienti": per un istante blocca il SALVATAGGIO di un
-- cliente (le letture no). Se in quell'istante qualcuno lo sta salvando, lo
-- script si ferma dopo 5 secondi con un errore: basta rilanciarlo.
SET lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS marketing_piani (
    id            SERIAL PRIMARY KEY,
    nome          VARCHAR(120) NOT NULL,
    campagna      VARCHAR(60)  NOT NULL,
    testo         TEXT         NOT NULL,
    immagine      BYTEA,
    immagine_mime VARCHAR(50),
    per_giorno    INTEGER      NOT NULL,
    ora_invio     TIME         NOT NULL,
    stato         VARCHAR(20)  NOT NULL DEFAULT 'attivo',
    creato_il     TIMESTAMP    NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    creato_da     VARCHAR(100),
    chiuso_il     TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_marketing_piani_campagna ON marketing_piani (campagna);
CREATE INDEX IF NOT EXISTS ix_marketing_piani_stato    ON marketing_piani (stato);

CREATE TABLE IF NOT EXISTS marketing_piano_destinatari (
    id                  SERIAL PRIMARY KEY,
    piano_id            INTEGER NOT NULL REFERENCES marketing_piani(id) ON DELETE CASCADE,
    client_id           INTEGER NOT NULL REFERENCES clienti(id),
    ordine              INTEGER NOT NULL,
    stato               VARCHAR(20) NOT NULL DEFAULT 'da_inviare',
    motivo              VARCHAR(300),
    tentativi           INTEGER NOT NULL DEFAULT 0,
    in_coda_il          TIMESTAMP,
    ultimo_tentativo_il TIMESTAMP,
    inviato_il          TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_marketing_piano_destinatari_piano_id  ON marketing_piano_destinatari (piano_id);
CREATE INDEX IF NOT EXISTS ix_marketing_piano_destinatari_client_id ON marketing_piano_destinatari (client_id);

-- Permessi all'utente dell'app, che ha lo stesso nome del database
-- (suncity, sunexp3). Sui database dove l'app entra come Alessio (prova, demo)
-- un utente con quel nome non c'e' e il blocco non fa niente.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_database()) THEN
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON marketing_piani, marketing_piano_destinatari TO %I',
                       current_database());
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE marketing_piani_id_seq, marketing_piano_destinatari_id_seq TO %I',
                       current_database());
    END IF;
END $$;
