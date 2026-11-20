-- suncity, 19/11/2026 — doppioni step 5 (gruppo C, decisioni dell'utente)
-- Unioni: 2591 -> 2599 Fontaneto (sesso M, resta l'e-mail della moglie) · 832 -> 3469 Gioira
--         3545 -> 1351 Migliavacca (tessera 124 da 6 EUR) · 182 -> 3325 Ottone
--         3425 -> 500 Valsesia Matilde · 2872 -> 2385 Vicario Mattia
-- Eliminate con la tessera (status Eliminato, come il tasto Elimina): 3556 Russo Noemi (tessera 187, 3 EUR)
--                                                                   2857 Vicario Francesca (tessera 295, 3 EUR)
-- Diverse persone, non toccate: Cominato Marco, Cerutti Michela, Gallo Giorgia

ROLLBACK;
BEGIN;

CREATE TEMP TABLE m(vecchio int, nuovo int) ON COMMIT DROP;
INSERT INTO m VALUES (2591,2599),(832,3469),(3545,1351),(182,3325),(3425,500),(2872,2385);

UPDATE appuntamenti x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE scontrini x SET cliente_id = m.nuovo FROM m WHERE x.cliente_id = m.vecchio;
UPDATE pacchetti x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE solarium_sessions x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE marketing_invii x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE marketing_piano_destinatari x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE crm_error_logs x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;

UPDATE clienti SET cliente_sesso = 'M' WHERE id = 2599;

UPDATE pacchetti SET status = 'Eliminato' WHERE id IN (187,295) AND client_id IN (3556,2857);

UPDATE clienti SET is_deleted = true WHERE id IN (2591,832,3545,182,3425,2872,3556,2857);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM appuntamenti WHERE client_id IN (2591,832,3545,182,3425,2872,3556,2857))
  OR EXISTS (SELECT 1 FROM scontrini    WHERE cliente_id IN (2591,832,3545,182,3425,2872,3556,2857))
  OR EXISTS (SELECT 1 FROM pacchetti    WHERE client_id IN (2591,832,3545,182,3425,2872))
  OR EXISTS (SELECT 1 FROM solarium_sessions WHERE client_id IN (2591,832,3545,182,3425,2872,3556,2857))
  OR (SELECT client_id FROM pacchetti WHERE id = 124) <> 1351
  OR (SELECT count(*) FROM pacchetti WHERE id IN (187,295) AND status = 'Eliminato') <> 2
  OR (SELECT count(*) FROM clienti WHERE id IN (2591,832,3545,182,3425,2872,3556,2857) AND is_deleted) <> 8
  THEN RAISE EXCEPTION 'Controllo fallito: annullato tutto';
  END IF;
END $$;

COMMIT;

SELECT c.id, c.cliente_cognome, c.cliente_nome, c.cliente_cellulare, c.cliente_sesso, c.is_deleted,
  (SELECT count(*) FROM appuntamenti WHERE client_id = c.id) AS app,
  (SELECT count(*) FROM scontrini WHERE cliente_id = c.id) AS scontr,
  (SELECT string_agg(p.status || ' ' || p.credito_residuo, ', ') FROM pacchetti p WHERE p.client_id = c.id) AS tessere
FROM clienti c WHERE c.id IN (2599,3469,1351,3325,500,2385,1268,3383,3556,2857) ORDER BY c.is_deleted, c.cliente_cognome;


-- ===== RIPRISTINO (solo se servisse tornare indietro) =====
-- BEGIN;
-- UPDATE appuntamenti SET client_id = 2591 WHERE id IN (10210,10211,12057,12058);
-- UPDATE appuntamenti SET client_id = 832  WHERE id = 10039;
-- UPDATE appuntamenti SET client_id = 182  WHERE id = 531;
-- UPDATE appuntamenti SET client_id = 3425 WHERE id IN (8928,8930,9648);
-- UPDATE appuntamenti SET client_id = 2872 WHERE id IN (522,10383);
-- UPDATE scontrini SET cliente_id = 2591 WHERE id IN (10182,11992);
-- UPDATE scontrini SET cliente_id = 832  WHERE id = 10025;
-- UPDATE scontrini SET cliente_id = 182  WHERE id = 229;
-- UPDATE scontrini SET cliente_id = 3425 WHERE id IN (9651,9652);
-- UPDATE scontrini SET cliente_id = 2872 WHERE id IN (249,10383);
-- UPDATE solarium_sessions SET client_id = 2591 WHERE id IN (1163,1164);
-- UPDATE marketing_invii SET client_id = 182 WHERE id IN (195,212);
-- UPDATE pacchetti SET client_id = 3545 WHERE id = 124;
-- UPDATE pacchetti SET status = 'Attivo' WHERE id IN (187,295);
-- UPDATE clienti SET cliente_sesso = 'F' WHERE id = 2599;
-- UPDATE clienti SET is_deleted = false WHERE id IN (2591,832,3545,182,3425,2872,3556,2857);
-- COMMIT;
