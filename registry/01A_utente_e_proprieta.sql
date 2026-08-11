-- ═══════════════════════════════════════════════════════════════════════
--  REGISTRO CENTRALE — controllo prima di creare le tabelle
--
--  Nessun utente dedicato: si usa lo stesso con cui si accede già a
--  suncity, sunexp3 e sunbookingdb.
--
--  ►► ESEGUIRE CONNESSI A  tosca_registry  ◄◄
-- ═══════════════════════════════════════════════════════════════════════


-- ── 1. Sono nel database giusto, con l'utente giusto? ──────────────────
SELECT current_database() AS database_corrente,
       current_user       AS utente_corrente;
-- Atteso:  tosca_registry | Alessio
--
-- Se il database è un altro, nell'estensione PostgreSQL di VS Code:
--   Ctrl+Shift+P -> "PostgreSQL: Change Connection"
-- L'estensione lega la connessione alla FINESTRA dell'editor, non a quella
-- selezionata nell'albero: è l'errore facile da fare.


-- ── 2. Il database e lo schema sono miei? ─────────────────────────────
SELECT pg_get_userbyid(datdba) AS proprietario_db
FROM pg_database WHERE datname = current_database();

SELECT pg_get_userbyid(nspowner) AS proprietario_schema
FROM pg_namespace WHERE nspname = 'public';
-- Entrambe devono rispondere: Alessio


-- ── 3. Posso scrivere? ────────────────────────────────────────────────
-- Se questa passa senza errori, 02_tabelle_registry.sql passerà.
CREATE TABLE _prova_permessi (id integer);
DROP TABLE _prova_permessi;


-- ── 4. Il database è vuoto? ───────────────────────────────────────────
SELECT count(*) AS tabelle_presenti
FROM information_schema.tables
WHERE table_schema = 'public' AND table_type = 'BASE TABLE';
-- Atteso: 0 la prima volta. Se è 8, le tabelle ci sono già: 02 le rifà
-- comunque, ha un blocco di DROP in testa.


-- ═══════════════════════════════════════════════════════════════════════
--  Poi:  02_tabelle_registry.sql
--
--  E nel .env, la stessa stringa delle altre connessioni con il solo nome
--  del database cambiato in fondo:
--
--  REGISTRY_DATABASE_URI=postgresql://<utente>:<password>@<host>:5432/tosca_registry?sslmode=require
--
--  Il nome della variabile NON deve corrispondere a
--  SQLALCHEMY_DATABASE_URI<numero>: collect_db_pool() in wsgi.py monta come
--  tenant tutto ciò che gli assomiglia, e un registro montato come negozio
--  sarebbe un guaio.
-- ═══════════════════════════════════════════════════════════════════════
