-- =============================================================================
-- Correzione dell'orario dei movimenti prepagata (2 ore indietro)
-- Da eseguire una volta su ogni tenant: suncity, sunexp3, sunbookingdb.
-- =============================================================================
--
-- IL PROBLEMA
-- La colonna movimenti_prepagata.data_movimento non aveva un default lato
-- applicazione: l'orario lo scriveva il database con func.now(), e il Postgres
-- su Azure e' impostato su UTC. Ogni movimento creato dall'app risulta quindi
-- indietro di 2 ore (ora legale) o di 1 ora (ora solare) rispetto all'orario
-- vero del negozio. E' l'orario che si vede nel tab "Ricaricabili Solarium" e
-- nella scheda della carta.
--
-- Il default e' stato corretto in appl/models.py (ora_italiana()): i movimenti
-- creati DOPO il riavvio dell'app sono gia' giusti. Questo script sistema
-- quelli gia' scritti in tabella, che il codice non puo' toccare da solo.
--
-- ATTENZIONE ALLE RIGHE IMPORTATE
-- I movimenti importati dai vecchi gestionali (import_suncity.py del 04/08/2026
-- e import_sunexpress.py del 07/08/2026) hanno gia' l'ora locale giusta, perche'
-- l'orario glielo ha scritto lo script e non il server. Vanno lasciati stare, e
-- si riconoscono dalla descrizione, che per quelle righe e' una di sei stringhe
-- fisse. Lo script le esclude per nome esatto.
--
-- ORDINE CONSIGLIATO
--   1. esegui questo script            <-- adesso
--   2. riavvia l'app
-- Se hai gia' riavviato l'app, i movimenti creati dopo il riavvio sono corretti
-- e NON vanno spostati: metti allora in _cutoff la data e ora del riavvio.
--
-- La correzione usa AT TIME ZONE, quindi gestisce da se' ora solare e ora
-- legale: le righe di gennaio si spostano di 1 ora, quelle di agosto di 2.
--
-- Rieseguire lo script per sbaglio NON fa danni: la CREATE TABLE del backup
-- fallisce perche' la tabella esiste gia', e la transazione si annulla intera.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1) Backup delle righe che stiamo per toccare (e blocco anti-doppia-esecuzione)
-- ---------------------------------------------------------------------------
CREATE TABLE bak_20260825_orario_movimenti AS
SELECT id, data_movimento
FROM movimenti_prepagata;

-- ---------------------------------------------------------------------------
-- 2) La correzione
--    _cutoff: lascia now() se NON hai ancora riavviato l'app.
--             Se l'hai gia' riavviata, sostituisci con l'ora del riavvio, es.
--             TIMESTAMP '2026-08-25 18:30:00'
-- ---------------------------------------------------------------------------
WITH _cutoff AS (SELECT now()::timestamp AS t)
UPDATE movimenti_prepagata m
   SET data_movimento = (m.data_movimento AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Rome'
  FROM _cutoff
 WHERE m.data_movimento < _cutoff.t
   AND (m.descrizione IS NULL OR m.descrizione NOT IN (
         'Saldo iniziale importato da Sun City',
         'Ricarica (storico Sun City)',
         'Seduta scalata (storico Sun City)',
         'Saldo iniziale importato da Sun Express',
         'Ricarica (storico Sun Express)',
         'Seduta scalata (storico Sun Express)'
       ));

-- ---------------------------------------------------------------------------
-- 3) Verifica PRIMA di confermare.
--    Colonna "prima" = com'era, "adesso" = come sara' dopo il COMMIT.
--    Gli ultimi movimenti devono coincidere con l'orario vero del negozio.
-- ---------------------------------------------------------------------------
SELECT m.id,
       b.data_movimento AS prima,
       m.data_movimento AS adesso,
       m.tipo_movimento,
       left(m.descrizione, 40) AS descrizione
FROM movimenti_prepagata m
JOIN bak_20260825_orario_movimenti b USING (id)
ORDER BY m.data_movimento DESC
LIMIT 15;

-- Quante righe sono state spostate e quante lasciate come stavano:
SELECT count(*) FILTER (WHERE m.data_movimento <> b.data_movimento) AS corrette,
       count(*) FILTER (WHERE m.data_movimento =  b.data_movimento) AS lasciate_stare,
       count(*) AS totale
FROM movimenti_prepagata m
JOIN bak_20260825_orario_movimenti b USING (id);

-- ---------------------------------------------------------------------------
-- 4) Se i numeri tornano:   COMMIT;
--    Se qualcosa non torna: ROLLBACK;   (non resta traccia di nulla)
-- ---------------------------------------------------------------------------
-- COMMIT;

-- =============================================================================
-- DOPO IL COMMIT
-- La tabella bak_20260825_orario_movimenti resta come rete di sicurezza.
-- Per tornare indietro:
--   UPDATE movimenti_prepagata m
--      SET data_movimento = b.data_movimento
--     FROM bak_20260825_orario_movimenti b
--    WHERE b.id = m.id;
-- Quando sei sicuro che va tutto bene (una settimana basta):
--   DROP TABLE bak_20260825_orario_movimenti;
-- =============================================================================
