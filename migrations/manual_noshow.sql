-- ============================================================================
-- ANNULLAMENTI E NO-SHOW (Tools > Booking Web)
--
-- business_info  : le impostazioni (tutto spento di partenza) e il testo della
--                  pagina "troppo tardi per annullare" (NULL = predefinito)
-- appuntamenti   : annullato_il  = quando il cliente ha annullato dal link
-- clienti        : prenotazioni_online_sblocco_il = sblocco a mano dalla scheda
-- Regole in appl/services/no_show.py (copiate in booking routes/no_show.py).
--
-- ⛔ Eseguire su TUTTI i database PRIMA del deploy di Tosca, del sito
-- prenotazioni e dell'aggiornamento dei .exe, collegati come Alessio:
--     suncity, sunexp3, sunbookingdb, demo1, demo2, demo3
-- I modelli leggono queste colonne in ogni query su clienti, appuntamenti e
-- business_info: un database senza le colonne = Tosca e prenotazioni ferme.
-- Idempotente: rilanciarlo non fa danni.
-- ============================================================================

-- Si puo' eseguire a negozi aperti: aggiungere una colonna con un valore fisso
-- non riscrive la tabella, la blocca solo per un istante. Se in quell'istante
-- la tabella e' occupata, invece di far aspettare chi lavora lo script si
-- ferma dopo 5 secondi con un errore: basta rilanciarlo.
SET lock_timeout = '5s';

ALTER TABLE business_info
    ADD COLUMN IF NOT EXISTS booking_annullo_blocco_attivo BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS booking_annullo_blocco_ore    INTEGER NOT NULL DEFAULT 24,
    ADD COLUMN IF NOT EXISTS booking_annullo_messaggio     TEXT NULL,
    ADD COLUMN IF NOT EXISTS booking_noshow_blocco_attivo  BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS booking_noshow_soglia         INTEGER NOT NULL DEFAULT 2,
    ADD COLUMN IF NOT EXISTS booking_noshow_mesi           INTEGER NOT NULL DEFAULT 12,
    ADD COLUMN IF NOT EXISTS booking_noshow_ore_tardivo    INTEGER NOT NULL DEFAULT 24;

ALTER TABLE appuntamenti
    ADD COLUMN IF NOT EXISTS annullato_il TIMESTAMP NULL;

ALTER TABLE clienti
    ADD COLUMN IF NOT EXISTS prenotazioni_online_sblocco_il TIMESTAMP NULL;

-- Verifica: deve rispondere con 9 righe.
SELECT table_name, column_name FROM information_schema.columns
WHERE table_schema = 'public' AND (
      (table_name = 'business_info' AND column_name IN (
          'booking_annullo_blocco_attivo', 'booking_annullo_blocco_ore', 'booking_annullo_messaggio',
          'booking_noshow_blocco_attivo', 'booking_noshow_soglia',
          'booking_noshow_mesi', 'booking_noshow_ore_tardivo'))
   OR (table_name = 'appuntamenti' AND column_name = 'annullato_il')
   OR (table_name = 'clienti' AND column_name = 'prenotazioni_online_sblocco_il'))
ORDER BY table_name, column_name;
