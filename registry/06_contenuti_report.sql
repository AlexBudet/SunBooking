-- ═══════════════════════════════════════════════════════════════════════
--  CONTENUTI DEL REPORT — notizie beauty e oroscopo UGUALI PER TUTTI
--  Da eseguire connessi a "tosca_registry"  (in psql:  \c tosca_registry ).
--
--  Verifica di essere nel posto giusto prima di partire:
--      SELECT current_database(), current_user;
--      -- deve dire:  tosca_registry | Alessio
--
--  Fino a qui notizie e oroscopo stavano nel database di ogni negozio
--  (beauty_news, oroscopo_settimanale) e andavano pubblicati una volta per
--  negozio. Sono contenuti uguali per tutti: da ora stanno qui, si pubblicano
--  una volta sola e ogni negozio li legge da qui.
--  Le tabelle nei database dei negozi NON si toccano: restano come ripiego
--  (registro irraggiungibile, copia vecchia dell'app, exe dei saloni).
--
--  Ordine rispetto al deploy: indifferente. Il codice nuovo, se queste
--  tabelle non ci sono o sono vuote, mostra quello che c'e' nel negozio.
--
--  ⚠️  SOLO AGGIUNTE: una copia vecchia dell'applicazione non conosce queste
--  tabelle e continua a funzionare. Rieseguibile: usa IF NOT EXISTS.
-- ═══════════════════════════════════════════════════════════════════════


-- ── NOTIZIE ────────────────────────────────────────────────────────────
-- Stesse colonne di beauty_news. Ogni pubblicazione e' un batch nuovo
-- (scan_batch, es. 20260924T1830): il Report mostra solo l'ultimo, gli altri
-- restano come archivio (l'app ne tiene 10).
CREATE TABLE IF NOT EXISTS contenuto_news (
    id            serial        PRIMARY KEY,
    scan_batch    varchar(40)   NOT NULL,
    titolo        varchar(300)  NOT NULL,
    sintesi       text,
    categoria     varchar(50),
    fonte         varchar(200),
    url           varchar(1000),
    data_notizia  date,
    ordine        integer       NOT NULL DEFAULT 0,
    created_at    timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contenuto_news_batch_ix ON contenuto_news (scan_batch);


-- ── OROSCOPO ───────────────────────────────────────────────────────────
-- Stesse colonne di oroscopo_settimanale. Simbolo e periodo dei segni sono
-- fissi e stanno nel codice (appl/contenuti_report.py). L'app tiene 8 batch.
CREATE TABLE IF NOT EXISTS contenuto_oroscopo (
    id          serial       PRIMARY KEY,
    scan_batch  varchar(40)  NOT NULL,
    segno       varchar(30)  NOT NULL,
    testo       text         NOT NULL,
    ordine      integer      NOT NULL DEFAULT 0,
    created_at  timestamptz  NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS contenuto_oroscopo_batch_ix ON contenuto_oroscopo (scan_batch);


-- ── VERIFICA FINALE ────────────────────────────────────────────────────
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN ('contenuto_news', 'contenuto_oroscopo')
ORDER BY table_name;
-- Attese 2 righe:  contenuto_news | contenuto_oroscopo

SELECT (SELECT count(*) FROM contenuto_news)     AS notizie,
       (SELECT count(*) FROM contenuto_oroscopo) AS oroscopo;
-- Atteso alla prima esecuzione:  0 | 0  (si riempiono dalla pagina Contenuti Report)
