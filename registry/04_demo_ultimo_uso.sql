-- ═══════════════════════════════════════════════════════════════════════
--  PROVA GRATUITA — ultimo utilizzo (regola delle 48 ore)
--  Da eseguire connessi a "tosca_registry"  (in psql:  \c tosca_registry ).
--
--  Verifica di essere nel posto giusto prima di partire:
--      SELECT current_database(), current_user;
--      -- deve dire:  tosca_registry | Alessio
--
--  ⛔ VA ESEGUITO PRIMA DEL DEPLOY DELL'APP. Il codice nuovo legge la colonna
--  in ogni query su demo_trial: senza, la pagina /prova e le API del sito
--  rispondono errore finche' la colonna non c'e'.
--
--  ⚠️  SOLO AGGIUNTE, come 03_tabelle_demo.sql: una copia vecchia
--  dell'applicazione non conosce la colonna e continua a funzionare.
--  Rieseguibile: usa IF NOT EXISTS.
-- ═══════════════════════════════════════════════════════════════════════

-- Ultima volta che chi prova ha usato lo slot. Dopo 48 ore senza utilizzo la
-- prova si chiude e lo slot si risemina, anche se i sette giorni non sono
-- finiti. NULL = mai usata dopo il primo accesso: vale inizio_at.
ALTER TABLE demo_trial ADD COLUMN IF NOT EXISTS ultimo_uso_at timestamptz;


-- ── VERIFICA FINALE ────────────────────────────────────────────────────
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'demo_trial'
  AND column_name = 'ultimo_uso_at';
-- Attesa 1 riga:  ultimo_uso_at | timestamp with time zone
