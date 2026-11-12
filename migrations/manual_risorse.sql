-- ============================================================================
-- RISORSE: postazioni, cabine, macchinari condivisi fra piu' servizi.
--
-- risorse          = quante ce ne sono in negozio (es. "Postazione Mani" 4)
-- servizio_risorse = quali risorse usa un servizio e con che TETTO
--                    (es. "Manicure classica" -> "Postazione Mani", tetto 2)
-- Regole in appl/services/risorse.py. Un servizio senza righe qui funziona
-- come prima: nessun vincolo.
--
-- Eseguire UNA VOLTA su ogni database, collegati come Alessio, PRIMA del
-- deploy di Tosca e del sito prenotazioni:
--     suncity, sunexp3, sunbookingdb, demo1, demo2, demo3
-- Idempotente: rilanciarlo non fa danni.
--
-- Le stesse tabelle sono definite dai modelli Risorsa e ServizioRisorsa
-- (appl/models.py di SunBooking e di booking): se Tosca in negozio parte con la
-- versione nuova prima di questo script, le crea lui identiche e lo script poi
-- non fa niente. Finche' le tabelle non ci sono, Tosca e il sito prenotazioni
-- funzionano come prima (le risorse semplicemente non compaiono).
-- ============================================================================

-- Si puo' eseguire a negozi aperti. L'unico contatto con una tabella esistente
-- e' il collegamento a "servizi": per un istante blocca il SALVATAGGIO di
-- modifiche ai servizi (le letture no). Se in quell'istante qualcuno sta
-- salvando un servizio, invece di aspettare lo script si ferma dopo 5 secondi
-- con un errore: basta rilanciarlo.
SET lock_timeout = '5s';

CREATE TABLE IF NOT EXISTS risorse (
    id          SERIAL PRIMARY KEY,
    nome        VARCHAR(60) NOT NULL,
    quantita    INTEGER NOT NULL DEFAULT 1,
    is_deleted  BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT ck_risorse_quantita CHECK (quantita >= 1)
);

CREATE TABLE IF NOT EXISTS servizio_risorse (
    service_id  INTEGER NOT NULL REFERENCES servizi(id) ON DELETE CASCADE,
    risorsa_id  INTEGER NOT NULL REFERENCES risorse(id) ON DELETE CASCADE,
    quantita    INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (service_id, risorsa_id),
    CONSTRAINT ck_servizio_risorse_quantita CHECK (quantita >= 1)
);

CREATE INDEX IF NOT EXISTS ix_servizio_risorse_risorsa_id ON servizio_risorse (risorsa_id);

-- Permessi all'utente dell'app, che ha lo stesso nome del database
-- (suncity, sunexp3). Li' c'e' gia' una regola che li da' in automatico alle
-- tabelle create da Alessio: questo blocco li rende espliciti. Sui database
-- dove l'app entra come Alessio (prova, demo) un utente con quel nome non c'e'
-- e il blocco non fa niente.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = current_database()) THEN
        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON risorse, servizio_risorse TO %I',
                       current_database());
        EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE risorse_id_seq TO %I', current_database());
    END IF;
END $$;

-- Verifica: deve rispondere con 2 righe (risorse, servizio_risorse).
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public' AND table_name IN ('risorse', 'servizio_risorse')
ORDER BY table_name;
