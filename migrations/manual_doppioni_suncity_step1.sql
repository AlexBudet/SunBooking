-- suncity, 19/11/2026 — doppioni step 1 (stesso nome, cognome e cellulare)
-- Unioni: 3439,3482 -> 1026 (Bussi) · 3159 -> 2712 (Fabris) · 3349 -> 1543 (Verzetti)
-- Solo eliminazione (0 passaggi): 387 (Gattone), 962 (Vicario)
-- Gia' eliminate prima dello step: 2157 (Brancato), 2077 (Donetti), 3482 (Bussi)

ROLLBACK;
BEGIN;

CREATE TEMP TABLE m(vecchio int, nuovo int) ON COMMIT DROP;
INSERT INTO m VALUES (3439,1026),(3482,1026),(3159,2712),(3349,1543);

UPDATE appuntamenti x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE scontrini x SET cliente_id = m.nuovo FROM m WHERE x.cliente_id = m.vecchio;
UPDATE pacchetti x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE solarium_sessions x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE marketing_invii x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE marketing_piano_destinatari x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE crm_error_logs x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;

UPDATE clienti SET is_deleted = true WHERE id IN (3439,3482,3159,3349,387,962);

DO $$
BEGIN
  IF (SELECT count(*) FROM appuntamenti WHERE client_id = 1026) <> 15
  OR (SELECT count(*) FROM scontrini    WHERE cliente_id = 1026) <> 15
  OR (SELECT count(*) FROM appuntamenti WHERE client_id = 2712) <> 5
  OR (SELECT count(*) FROM scontrini    WHERE cliente_id = 2712) <> 5
  OR (SELECT count(*) FROM appuntamenti WHERE client_id = 1543) <> 3
  OR (SELECT count(*) FROM scontrini    WHERE cliente_id = 1543) <> 3
  THEN RAISE EXCEPTION 'Numeri diversi dal previsto: annullato tutto';
  END IF;
END $$;

COMMIT;

SELECT c.id, c.is_deleted,
  (SELECT count(*) FROM appuntamenti WHERE client_id = c.id) AS app,
  (SELECT count(*) FROM scontrini WHERE cliente_id = c.id) AS scontr
FROM clienti c WHERE c.id IN (1026,2712,1543,3439,3482,3159,3349,387,962) ORDER BY c.id;


-- ===== RIPRISTINO (solo se servisse tornare indietro) =====
-- BEGIN;
-- UPDATE appuntamenti SET client_id = 3439 WHERE id IN (9287,9659,9830);
-- UPDATE appuntamenti SET client_id = 3482 WHERE id IN (10241,10486);
-- UPDATE appuntamenti SET client_id = 3159 WHERE id IN (676,2338,3003);
-- UPDATE appuntamenti SET client_id = 3349 WHERE id = 6935;
-- UPDATE scontrini SET cliente_id = 3439 WHERE id IN (9496,9682,9844);
-- UPDATE scontrini SET cliente_id = 3482 WHERE id IN (10263,10508);
-- UPDATE scontrini SET cliente_id = 3159 WHERE id IN (537,2187,2883);
-- UPDATE scontrini SET cliente_id = 3349 WHERE id = 7285;
-- UPDATE clienti SET is_deleted = false WHERE id IN (3439,3159,3349,387,962);
-- COMMIT;
