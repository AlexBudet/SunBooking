-- =============================================================================
-- Correzione orario movimenti prepagata (erano 2 ore indietro)
-- Incolla TUTTO questo file nella finestra query e premi esegui. Una volta sola.
-- Su suncity, poi su sunexp3.
--
-- Non tocca i movimenti importati dai vecchi gestionali (hanno gia' l'ora
-- giusta): si riconoscono dalla descrizione ed escono esclusi per nome esatto.
-- Se lo rilanci per sbaglio si blocca da solo e non fa niente.
--
-- PER ANNULLARE TUTTO, se i numeri non ti tornano (un comando solo):
--   UPDATE movimenti_prepagata m SET data_movimento = b.data_movimento
--     FROM bak_20260825_orario_movimenti b WHERE b.id = m.id;
-- =============================================================================

BEGIN;

CREATE TABLE bak_20260825_orario_movimenti AS
SELECT id, data_movimento FROM movimenti_prepagata;

UPDATE movimenti_prepagata
   SET data_movimento = (data_movimento AT TIME ZONE 'UTC') AT TIME ZONE 'Europe/Rome'
 WHERE data_movimento < now()::timestamp
   AND (descrizione IS NULL OR descrizione NOT IN (
         'Saldo iniziale importato da Sun City',
         'Ricarica (storico Sun City)',
         'Seduta scalata (storico Sun City)',
         'Saldo iniziale importato da Sun Express',
         'Ricarica (storico Sun Express)',
         'Seduta scalata (storico Sun Express)'
       ));

COMMIT;

-- Esito: "corrette" = righe spostate, "lasciate_stare" = storico importato.
-- Su Sun City lasciate_stare deve essere circa 2300. Se e' 0, usa il comando
-- di annullamento qui sopra e avvisami.
SELECT count(*) FILTER (WHERE m.data_movimento <> b.data_movimento) AS corrette,
       count(*) FILTER (WHERE m.data_movimento =  b.data_movimento) AS lasciate_stare,
       count(*) AS totale,
       max(m.data_movimento) AS ultimo_movimento_adesso
FROM movimenti_prepagata m
JOIN bak_20260825_orario_movimenti b USING (id);
