-- suncity, 19/11/2026 — doppioni step 3 (cellulare diverso)
-- Correzioni step 2: sesso Cerrato 12 = F, Rampini 3557 = M
-- Eliminate (0 passaggi, mentre l'omonima ha storico o tessera):
--   2715 Bacchetta · 3090 Cerutti S. · 1297 Cirillo · 2727 Guidetti C. · 1190 Guidetti F. · 1455 Gaboli
--   1162 Perrone · 271 Piralla · 314 Soffiato · 1330 Zanetta · 571 Vicario M.
-- Sesso copiato sulle schede importate che restano: 3552 Gaboli, 3543 Guidetti F., 3567 Piralla

ROLLBACK;
BEGIN;

UPDATE clienti SET cliente_sesso = 'F' WHERE id IN (12,3552,3543,3567);
UPDATE clienti SET cliente_sesso = 'M' WHERE id = 3557;

UPDATE clienti SET is_deleted = true WHERE id IN (2715,3090,1297,2727,1190,1455,1162,271,314,1330,571);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM appuntamenti WHERE client_id IN (2715,3090,1297,2727,1190,1455,1162,271,314,1330,571))
  OR EXISTS (SELECT 1 FROM scontrini    WHERE cliente_id IN (2715,3090,1297,2727,1190,1455,1162,271,314,1330,571))
  OR EXISTS (SELECT 1 FROM pacchetti    WHERE client_id IN (2715,3090,1297,2727,1190,1455,1162,271,314,1330,571))
  OR EXISTS (SELECT 1 FROM solarium_sessions WHERE client_id IN (2715,3090,1297,2727,1190,1455,1162,271,314,1330,571))
  OR (SELECT count(*) FROM clienti WHERE id IN (2715,3090,1297,2727,1190,1455,1162,271,314,1330,571) AND is_deleted) <> 11
  THEN RAISE EXCEPTION 'Controllo fallito: annullato tutto';
  END IF;
END $$;

COMMIT;

SELECT id, cliente_cognome, cliente_nome, cliente_sesso, is_deleted FROM clienti
WHERE id IN (12,3557,3552,3543,3567,2715,3090,1297,2727,1190,1455,1162,271,314,1330,571) ORDER BY is_deleted, cliente_cognome;


-- ===== RIPRISTINO (solo se servisse tornare indietro) =====
-- BEGIN;
-- UPDATE clienti SET cliente_sesso = 'M' WHERE id = 12;
-- UPDATE clienti SET cliente_sesso = '-' WHERE id IN (3557,3552,3543,3567);
-- UPDATE clienti SET is_deleted = false WHERE id IN (2715,3090,1297,2727,1190,1455,1162,271,314,1330,571);
-- COMMIT;
