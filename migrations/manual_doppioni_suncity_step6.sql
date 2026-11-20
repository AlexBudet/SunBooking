-- suncity, 19/11/2026 — doppioni step 6
-- Gia' eseguito dall'utente: eliminate le 4 schede vuote 42, 416, 1710, 3657
-- Unione: 3225 (scheda senza nome) -> 3378 Sara Azzolin

ROLLBACK;
BEGIN;

UPDATE appuntamenti SET client_id = 3378 WHERE client_id = 3225;
UPDATE scontrini SET cliente_id = 3378 WHERE cliente_id = 3225;

UPDATE clienti SET is_deleted = true WHERE id = 3225;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM appuntamenti WHERE client_id = 3225)
  OR EXISTS (SELECT 1 FROM scontrini    WHERE cliente_id = 3225)
  OR EXISTS (SELECT 1 FROM pacchetti    WHERE client_id = 3225)
  OR (SELECT count(*) FROM appuntamenti WHERE client_id = 3378) < 10
  OR (SELECT count(*) FROM scontrini    WHERE cliente_id = 3378) < 6
  OR NOT (SELECT is_deleted FROM clienti WHERE id = 3225)
  THEN RAISE EXCEPTION 'Controllo fallito: annullato tutto';
  END IF;
END $$;

COMMIT;

SELECT c.id, c.cliente_nome, c.cliente_cognome, c.is_deleted,
  (SELECT count(*) FROM appuntamenti WHERE client_id = c.id) AS app,
  (SELECT count(*) FROM scontrini WHERE cliente_id = c.id) AS scontr
FROM clienti c WHERE c.id IN (3378,3225) ORDER BY c.id;


-- ===== RIPRISTINO (solo se servisse tornare indietro) =====
-- BEGIN;
-- UPDATE appuntamenti SET client_id = 3225 WHERE id IN (2278,2279,5322,5341);
-- UPDATE scontrini SET cliente_id = 3225 WHERE id IN (2163,2164,5375);
-- UPDATE clienti SET is_deleted = false WHERE id = 3225;
-- COMMIT;
