-- suncity, 19/11/2026 — doppioni step 2 (cellulare quasi uguale, in gran parte creati dall'import Sun City del 04/08/2026)
-- Unioni: 3590 -> 944 (De Ambrosi, tessera 301) · 3594 -> 312 (Vercelli, tessera 321) · 3147 -> 12 (Cerrato)
-- Eliminate (0 passaggi): 1127 Ellena · 2490 Gavinelli · 690 Mazzotta · 494 Miglio · 677 Rampini · 3067 Tacchini · 1976 Ruga
-- Correzioni sulle schede che restano: cellulare 3583 e 3592, sesso copiato dalle vecchie schede
-- Esclusi: Russo Elisa (due persone diverse), Savoini (da decidere)

ROLLBACK;
BEGIN;

CREATE TEMP TABLE m(vecchio int, nuovo int) ON COMMIT DROP;
INSERT INTO m VALUES (3590,944),(3594,312),(3147,12);

UPDATE appuntamenti x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE scontrini x SET cliente_id = m.nuovo FROM m WHERE x.cliente_id = m.vecchio;
UPDATE pacchetti x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE solarium_sessions x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE marketing_invii x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE marketing_piano_destinatari x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;
UPDATE crm_error_logs x SET client_id = m.nuovo FROM m WHERE x.client_id = m.vecchio;

UPDATE clienti SET cliente_cellulare = '032253426', cliente_sesso = 'M' WHERE id = 3583;
UPDATE clienti SET cliente_cellulare = '3391009663', cliente_sesso = 'F' WHERE id = 3592;
UPDATE clienti SET cliente_sesso = 'F' WHERE id IN (3560,3554);
UPDATE clienti SET cliente_sesso = 'M' WHERE id = 3537;

UPDATE clienti SET is_deleted = true WHERE id IN (3590,3594,3147,1127,2490,690,494,677,3067,1976);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM appuntamenti WHERE client_id IN (3590,3594,3147,1127,2490,690,494,677,3067,1976))
  OR EXISTS (SELECT 1 FROM scontrini    WHERE cliente_id IN (3590,3594,3147,1127,2490,690,494,677,3067,1976))
  OR EXISTS (SELECT 1 FROM pacchetti    WHERE client_id IN (3590,3594,3147,1127,2490,690,494,677,3067,1976))
  OR EXISTS (SELECT 1 FROM solarium_sessions WHERE client_id IN (3590,3594,3147,1127,2490,690,494,677,3067,1976))
  OR (SELECT client_id FROM pacchetti WHERE id = 301) <> 944
  OR (SELECT client_id FROM pacchetti WHERE id = 321) <> 312
  OR (SELECT count(*) FROM clienti WHERE id IN (3590,3594,3147,1127,2490,690,494,677,3067,1976) AND is_deleted) <> 10
  THEN RAISE EXCEPTION 'Controllo fallito: annullato tutto';
  END IF;
END $$;

COMMIT;

SELECT c.id, c.cliente_cognome, c.cliente_cellulare, c.cliente_sesso, c.is_deleted,
  (SELECT count(*) FROM appuntamenti WHERE client_id = c.id) AS app,
  (SELECT count(*) FROM scontrini WHERE cliente_id = c.id) AS scontr,
  (SELECT count(*) FROM pacchetti WHERE client_id = c.id) AS tessere
FROM clienti c WHERE c.id IN (12,944,312,3560,3583,3537,3592,3557,3554,3077) ORDER BY c.cliente_cognome;


-- ===== RIPRISTINO (solo se servisse tornare indietro) =====
-- BEGIN;
-- UPDATE pacchetti SET client_id = 3590 WHERE id = 301;
-- UPDATE pacchetti SET client_id = 3594 WHERE id = 321;
-- UPDATE appuntamenti SET client_id = 3147 WHERE id = 1324;
-- UPDATE scontrini SET cliente_id = 3147 WHERE id IN (387,918,1104);
-- UPDATE clienti SET cliente_cellulare = '32253426', cliente_sesso = '-' WHERE id = 3583;
-- UPDATE clienti SET cliente_cellulare = '339100663', cliente_sesso = '-' WHERE id = 3592;
-- UPDATE clienti SET cliente_sesso = '-' WHERE id IN (3560,3554,3537);
-- UPDATE clienti SET is_deleted = false WHERE id IN (3590,3594,3147,1127,2490,690,494,677,3067,1976);
-- COMMIT;
