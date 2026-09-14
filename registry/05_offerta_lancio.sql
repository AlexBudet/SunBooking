-- ═══════════════════════════════════════════════════════════════════════
--  OFFERTA DI LANCIO — art. 6-bis del contratto (versione 1.1)
--  Da eseguire connessi a "tosca_registry"  (in psql:  \c tosca_registry ).
--
--  Verifica di essere nel posto giusto prima di partire:
--      SELECT current_database(), current_user;
--      -- deve dire:  tosca_registry | Alessio
--
--  ⛔ VA ESEGUITO PRIMA DEL DEPLOY DELL'APP. Il codice nuovo legge la colonna
--  in ogni query su contract: senza, la creazione degli inviti e la pagina
--  /attiva del cliente rispondono errore finche' la colonna non c'e'.
--
--  ⚠️  SOLO AGGIUNTE: una copia vecchia dell'applicazione non conosce la
--  colonna e continua a funzionare. Rieseguibile: usa IF NOT EXISTS.
-- ═══════════════════════════════════════════════════════════════════════

-- true = attivazione a zero, nessun Periodo Starter, canone dal primo mese.
-- I contratti gia' presenti restano false: nessuno di loro e' un'offerta.
ALTER TABLE contract ADD COLUMN IF NOT EXISTS launch_offer boolean NOT NULL DEFAULT false;


-- ── VERIFICA FINALE ────────────────────────────────────────────────────
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'contract'
  AND column_name = 'launch_offer';
-- Attesa 1 riga:  launch_offer | boolean | NO | false

SELECT count(*) AS contratti, count(*) FILTER (WHERE launch_offer) AS con_offerta
FROM contract;
-- Atteso oggi:  contratti = 1, con_offerta = 0
