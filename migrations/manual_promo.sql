-- ============================================================================
-- PROMO DEI SERVIZI: condizioni impostate dall'ingranaggio in Tools > Servizi
--
-- servizi.promo_regole : periodo, giorni, fasce orarie, criterio, sconto e
--                        cosa succede fuori promo (JSON in TEXT).
--                        NULL = promo sempre valida e senza sconto, cioe'
--                        esattamente come le promo di prima.
-- Regole in appl/services/promo.py (copiate in booking routes/promo.py).
--
-- ⛔ Eseguire su TUTTI i database PRIMA del deploy di Tosca, del sito
-- prenotazioni e dell'aggiornamento dei .exe, collegati come Alessio:
--     suncity, sunexp3, sunbookingdb, demo1, demo2, demo3
-- Il modello Service legge questa colonna in ogni query sui servizi: un
-- database senza la colonna = Agenda, Cassa e prenotazioni ferme.
-- Idempotente: rilanciarlo non fa danni.
-- ============================================================================

-- Si puo' eseguire a negozi aperti: una colonna NULL senza default non
-- riscrive la tabella. Se la tabella e' occupata lo script si ferma dopo 5
-- secondi con un errore: basta rilanciarlo.
SET lock_timeout = '5s';

ALTER TABLE servizi
    ADD COLUMN IF NOT EXISTS promo_regole TEXT NULL;

-- Verifica: deve restituire una riga con data_type = text
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'servizi' AND column_name = 'promo_regole';
