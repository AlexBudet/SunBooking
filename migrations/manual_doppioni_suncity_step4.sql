-- suncity, 19/11/2026 — doppioni step 4 (omonimi entrambi a 0 passaggi: resta la scheda piu' recente)
-- Eliminate: 202 Ambrosini · 3032 Barbaglia · 2295 Cerutti C. · 201 Creola G. · 186 Creola L. · 229 Crespi
--            30 Giustina · 2345 Lorenzini · 1001 Medina · 146 Pastore · 567 Poletti · 1802 Valsesia F.
-- Sesso M copiato dalla scheda eliminata: 490 Ambrosini Jhonny, 2699 Medina Matteo

ROLLBACK;
BEGIN;

UPDATE clienti SET cliente_sesso = 'M' WHERE id IN (490,2699);

UPDATE clienti SET is_deleted = true WHERE id IN (202,3032,2295,201,186,229,30,2345,1001,146,567,1802);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM appuntamenti WHERE client_id IN (202,3032,2295,201,186,229,30,2345,1001,146,567,1802))
  OR EXISTS (SELECT 1 FROM scontrini    WHERE cliente_id IN (202,3032,2295,201,186,229,30,2345,1001,146,567,1802))
  OR EXISTS (SELECT 1 FROM pacchetti    WHERE client_id IN (202,3032,2295,201,186,229,30,2345,1001,146,567,1802))
  OR EXISTS (SELECT 1 FROM solarium_sessions WHERE client_id IN (202,3032,2295,201,186,229,30,2345,1001,146,567,1802))
  OR (SELECT count(*) FROM clienti WHERE id IN (202,3032,2295,201,186,229,30,2345,1001,146,567,1802) AND is_deleted) <> 12
  THEN RAISE EXCEPTION 'Controllo fallito: annullato tutto';
  END IF;
END $$;

COMMIT;

SELECT id, cliente_cognome, cliente_nome, cliente_cellulare, cliente_sesso, is_deleted FROM clienti
WHERE id IN (490,1610,2659,2282,2272,1150,2218,2714,2699,207,2926,1604,202,3032,2295,201,186,229,30,2345,1001,146,567,1802)
ORDER BY cliente_cognome, cliente_nome, is_deleted;


-- ===== RIPRISTINO (solo se servisse tornare indietro) =====
-- BEGIN;
-- UPDATE clienti SET cliente_sesso = 'F' WHERE id IN (490,2699);
-- UPDATE clienti SET is_deleted = false WHERE id IN (202,3032,2295,201,186,229,30,2345,1001,146,567,1802);
-- COMMIT;
