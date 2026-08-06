-- ============================================================================
-- Solarium: collegamento diretto seduta -> appuntamento di calendario.
--
-- Le sedute (solarium_sessions) erano gia' collegabili a scontrino
-- (receipt_id) e cliente (client_id); l'appuntamento era ricavabile solo
-- indirettamente leggendo le voci JSON dello scontrino collegato. Questa
-- colonna lo rende un collegamento diretto, per query/report piu' semplici.
--
-- ATTENZIONE alla regola ON DELETE SET NULL.
-- La prima versione di questo file creava la colonna con un semplice
-- "REFERENCES appuntamenti(id)", quindi con il default NO ACTION: PostgreSQL
-- rifiutava di cancellare un appuntamento che avesse gia' una seduta
-- registrata dal bridge Phidget. In Agenda si vedeva solo un errore 500
-- sui blocchi dei macchinari (es. lettino) usati davvero.
-- La seduta e' un fatto realmente accaduto e va conservata: quando
-- l'appuntamento sparisce deve solo restare senza riferimento, non essere
-- cancellata a cascata. Da qui SET NULL (mai CASCADE).
--
-- Eseguire UNA VOLTA sul database PostgreSQL (Azure), su ogni negozio.
-- Idempotente: si puo' rilanciare senza danni, e su un negozio che ha gia'
-- la colonna con il vincolo vecchio la corregge.
-- ============================================================================

ALTER TABLE solarium_sessions
    ADD COLUMN IF NOT EXISTS appointment_id INTEGER;

-- Il vincolo viene creato (o ricreato) qui, cosi' c'e' una sola strada sia per
-- i negozi nuovi sia per quelli che hanno gia' la colonna con la regola errata.
DO $$
DECLARE
    nome_vincolo text;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'solarium_sessions' AND column_name = 'appointment_id'
    ) THEN
        RAISE NOTICE 'solarium_sessions.appointment_id assente: niente da fare';
        RETURN;
    END IF;

    SELECT conname INTO nome_vincolo
    FROM pg_constraint
    WHERE conrelid = 'solarium_sessions'::regclass
      AND confrelid = 'appuntamenti'::regclass
      AND contype = 'f';

    IF nome_vincolo IS NOT NULL THEN
        EXECUTE format('ALTER TABLE solarium_sessions DROP CONSTRAINT %I', nome_vincolo);
        RAISE NOTICE 'rimosso vincolo %', nome_vincolo;
    END IF;

    ALTER TABLE solarium_sessions
        ADD CONSTRAINT solarium_sessions_appointment_id_fkey
        FOREIGN KEY (appointment_id) REFERENCES appuntamenti(id) ON DELETE SET NULL;
    RAISE NOTICE 'vincolo ricreato con ON DELETE SET NULL';
END $$;

-- Verifica: confdeltype deve essere 'n' (SET NULL). 'a' = NO ACTION = vecchio.
-- SELECT conname, confdeltype
-- FROM pg_constraint
-- WHERE conrelid = 'solarium_sessions'::regclass
--   AND confrelid = 'appuntamenti'::regclass;
