-- ═══════════════════════════════════════════════════════════════════════
--  PROVA GRATUITA 7 GIORNI — tabelle
--  Da eseguire connessi a "tosca_registry"  (in psql:  \c tosca_registry ).
--
--  Verifica di essere nel posto giusto prima di partire:
--      SELECT current_database(), current_user;
--      -- deve dire:  tosca_registry | Alessio
--
--  ⚠️  SOLO AGGIUNTE. Non c'e' nessun blocco di DROP e non deve essercene:
--  il registro e' condiviso fra le copie dell'applicazione, e una copia
--  vecchia che non conosce queste tabelle deve continuare a funzionare.
--  Lo script e' rieseguibile: usa IF NOT EXISTS ovunque.
--
--  Perche' le prove NON stanno nella tabella `tenant`:
--  `tenant` e' l'elenco dei negozi clienti, ed e' agganciata a billing,
--  invoice, contract. Una prova gratuita non e' un negozio: se finisse li'
--  dentro inquinerebbe il conteggio dei negozi, la fatturazione e i controlli
--  di morosita'. Vive in tabelle sue.
-- ═══════════════════════════════════════════════════════════════════════


-- ── SLOT ───────────────────────────────────────────────────────────────
-- Tre database ricreabili (demo1/demo2/demo3), montati su /s/91, /s/92,
-- /s/93. Uno slot non si cancella mai: a fine prova si svuota e si risemina.
-- Gli indici partono da 91 e non da 4 perche' il primo cliente PAGANTE deve
-- prendere idx 4: la numerazione dei negozi veri non va consumata dalle demo.
CREATE TABLE IF NOT EXISTS demo_slot (
    idx         integer PRIMARY KEY,                  -- 91, 92, 93
    db_name     varchar(50)  NOT NULL,                -- demo1, demo2, demo3
    stato       varchar(20)  NOT NULL DEFAULT 'libero',
    trial_id    integer,                              -- prova che lo occupa
    updated_at  timestamptz  NOT NULL DEFAULT now(),
    CONSTRAINT demo_slot_stato_ck CHECK (stato IN
        ('libero','occupato','da_risemina','manutenzione'))
);

INSERT INTO demo_slot (idx, db_name) VALUES
    (91, 'demo1'), (92, 'demo2'), (93, 'demo3')
ON CONFLICT (idx) DO NOTHING;


-- ── PROVE ──────────────────────────────────────────────────────────────
-- Una riga per richiesta, dalla domanda alla scadenza. Le righe in coda non
-- hanno ancora uno slot: `slot_idx` resta NULL finche' non se ne libera uno.
--
-- Il telefono e' la chiave dell'antiabuso e sta qui in due forme: come l'ha
-- scritto la persona (per richiamarla) e normalizzato a sole cifre con
-- prefisso (per confrontarlo). Senza la seconda, "333 123 4567" e
-- "+39 3331234567" sarebbero due prove diverse.
CREATE TABLE IF NOT EXISTS demo_trial (
    id             serial PRIMARY KEY,
    slot_idx       integer REFERENCES demo_slot(idx),
    stato          varchar(20)  NOT NULL DEFAULT 'in_coda',

    -- chi ha chiesto la prova
    business_name  varchar(150) NOT NULL,
    referente      varchar(120),
    email          varchar(120) NOT NULL,
    telefono       varchar(30)  NOT NULL,
    telefono_norm  varchar(20)  NOT NULL,
    ip_richiesta   varchar(45),
    user_agent     text,
    fonte          varchar(200),                      -- UTM o referrer

    -- accesso allo slot
    token_hash     varchar(64) UNIQUE,                -- SHA-256 del link
    username       varchar(80),                       -- utente creato nello slot

    -- tempi. Il cronometro dei 7 giorni parte al PRIMO ACCESSO, non
    -- all'invio del link: una prova consumata dalla posta non e' una prova.
    creata_at      timestamptz NOT NULL DEFAULT now(),
    invitata_at    timestamptz,                       -- slot assegnato
    claim_entro    timestamptz,                       -- 3 giorni per entrare
    inizio_at      timestamptz,                       -- primo accesso
    scadenza_at    timestamptz,                       -- inizio + 7 giorni
    chiusa_at      timestamptz,

    -- prova del consenso, con la versione del testo accettato: senza sapere
    -- QUALE informativa ha letto, il consenso non dimostra niente.
    privacy_versione     varchar(20),
    privacy_accettata_at timestamptz,
    termini_versione     varchar(20),
    termini_accettati_at timestamptz,

    note           text,
    CONSTRAINT demo_trial_stato_ck CHECK (stato IN
        ('in_coda','invitata','attiva','scaduta','annullata','rifiutata'))
);

CREATE INDEX IF NOT EXISTS demo_trial_stato_idx    ON demo_trial (stato);
CREATE INDEX IF NOT EXISTS demo_trial_telefono_idx ON demo_trial (telefono_norm);
CREATE INDEX IF NOT EXISTS demo_trial_scadenza_idx ON demo_trial (scadenza_at);


-- ── DEROGHE ────────────────────────────────────────────────────────────
-- La regola e' una prova per numero di cellulare. Ma due titolari possono
-- condividerlo davvero (nel progetto e' misurato: il 2,7% dei recapiti e'
-- in comune fra clienti diversi), e chi si vede rifiutare una prova che non
-- ha mai fatto se ne va. Una riga qui riapre il diritto a quel numero.
CREATE TABLE IF NOT EXISTS demo_deroga (
    telefono_norm  varchar(20) PRIMARY KEY,
    prove_extra    integer     NOT NULL DEFAULT 1,    -- quante in piu' concesse
    motivo         text,
    concessa_da    varchar(80),
    concessa_at    timestamptz NOT NULL DEFAULT now()
);


-- ── VERIFICA FINALE ────────────────────────────────────────────────────
SELECT table_name,
       (SELECT count(*) FROM information_schema.columns c
        WHERE c.table_name = t.table_name AND c.table_schema = 'public') AS colonne
FROM information_schema.tables t
WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
  AND table_name LIKE 'demo%'
ORDER BY table_name;
-- Attese 3 tabelle: demo_deroga, demo_slot, demo_trial

SELECT idx, db_name, stato FROM demo_slot ORDER BY idx;
-- Attesi 3 slot liberi: 91/demo1, 92/demo2, 93/demo3
