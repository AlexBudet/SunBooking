# appl/services/backup_dump.py
"""Backup immediato di un database dal pannello owner (pulsante "💾 Backup").

Perche' un dump scritto in Python e non pg_dump
------------------------------------------------
Il pannello gira sulla web app Azure (immagine PYTHON|3.13), dove pg_dump non e'
garantito, e anche se ci fosse dovrebbe essere di versione >= al server (16):
un pg_dump piu' vecchio si rifiuta. Qui si usa solo psycopg2, che c'e' gia'.

Cosa contiene il file
---------------------
SQL in chiaro, ripristinabile con psql su un database vuoto:
  tipi ENUM, sequenze, tabelle (con default e colonne generate), proprieta'
  delle sequenze, DATI (COPY), valori delle sequenze, chiavi primarie, vincoli
  unique/check/exclude, indici, chiavi esterne.
Sono gli stessi oggetti che hanno i database dei negozi (verificato sull'indice
dei pg_dump del 13/11/2026). Come pg_dump --no-owner --no-privileges: niente
proprietari ne' permessi. Funzioni, viste, trigger, domini NON sono inclusi:
se nel database ce ne sono, il file e il pannello lo dicono.

Coerenza: tutto si legge dentro UNA transazione REPEATABLE READ, READ ONLY,
come fa pg_dump: i dati sono la fotografia di un istante, anche se nel
frattempo il negozio lavora. Il database non viene mai scritto.

Perche' in un thread
--------------------
In cloud gunicorn gira con i valori predefiniti: UN worker sincrono e timeout
di 30 secondi. Una richiesta che fa il dump bloccherebbe tutti i negozi e
verrebbe uccisa a meta'. Il dump gira quindi in un thread e finisce in un
file temporaneo compresso; la pagina chiede a che punto e' e poi scarica il
file (gzip: pochi MB, pochi secondi).
"""
import gzip
import hashlib
import os
import re
import tempfile
import threading
import time
import uuid
from datetime import datetime
from urllib.parse import urlparse

import psycopg2

try:
    from zoneinfo import ZoneInfo
    _ROMA = ZoneInfo('Europe/Rome')
except Exception:  # pragma: no cover
    _ROMA = None

# I file pronti restano sul server al massimo mezz'ora, poi si cancellano:
# contengono dati personali dei clienti.
SCADENZA_FILE_S = 30 * 60
CARTELLA = os.path.join(tempfile.gettempdir(), 'tosca_backup')

_lock = threading.Lock()
_lavori = {}   # id -> dict (vedi avvia)

_SCHEMI_DI_SISTEMA = ("'pg_catalog'", "'information_schema'", "'pg_toast'")
_FILTRO_SCHEMI = (
    "n.nspname NOT IN (%s) AND n.nspname NOT LIKE 'pg\\_temp\\_%%' "
    "AND n.nspname NOT LIKE 'pg\\_toast\\_temp\\_%%'" % ', '.join(_SCHEMI_DI_SISTEMA)
)
# Oggetti che appartengono a un'estensione (pg_stat_statements & c.): li crea
# l'estensione, non si copiano.
_NON_DI_ESTENSIONE = (
    "NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = '{cat}'::regclass "
    "AND d.objid = {oid} AND d.deptype = 'e')"
)


def _adesso_roma():
    return datetime.now(_ROMA) if _ROMA else datetime.now()


def _dsn(uri):
    """URI di SQLAlchemy -> DSN per psycopg2 (via il "+psycopg2")."""
    return re.sub(r'^postgres(ql)?(\+[a-z0-9_]+)?://', 'postgresql://', uri.strip())


def nome_database(uri):
    try:
        return (urlparse(_dsn(uri)).path or '/').strip('/').split('/')[-1] or 'database'
    except Exception:
        return 'database'


# ---------------------------------------------------------------------------
# Scrittura
# ---------------------------------------------------------------------------
class _Uscita:
    """File gzip + SHA-256 e conteggio byte del testo NON compresso."""

    def __init__(self, percorso):
        self._gz = gzip.open(percorso, 'wb', compresslevel=6)
        self.sha = hashlib.sha256()
        self.byte = 0
        self.righe_copy = 0

    def testo(self, s):
        b = s.encode('utf-8')
        self._gz.write(b)
        self.sha.update(b)
        self.byte += len(b)

    # psycopg2.copy_expert chiama write() con bytes (oggetto non TextIOBase)
    def write(self, b):
        if isinstance(b, str):
            b = b.encode('utf-8')
        self._gz.write(b)
        self.sha.update(b)
        self.byte += len(b)
        # In COPY testo ogni riga e' una riga: gli a-capo nei valori escono come \n
        self.righe_copy += b.count(b'\n')
        return len(b)

    def chiudi(self):
        self._gz.close()


# ---------------------------------------------------------------------------
# Lettura del catalogo
# ---------------------------------------------------------------------------
def _tutti(cur, sql, args=None):
    cur.execute(sql, args)
    return cur.fetchall()


def _non_inclusi(cur):
    """Oggetti che questo dump NON copia, per dirlo invece di tacerlo."""
    voci = []
    q = {
        ('funzione', 'funzioni'): (
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE " + _FILTRO_SCHEMI + " AND " +
            _NON_DI_ESTENSIONE.format(cat='pg_proc', oid='p.oid')),
        ('vista', 'viste'): (
            "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE c.relkind IN ('v', 'm') AND " + _FILTRO_SCHEMI + " AND " +
            _NON_DI_ESTENSIONE.format(cat='pg_class', oid='c.oid')),
        ('trigger', 'trigger'): (
            "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE NOT t.tgisinternal AND " + _FILTRO_SCHEMI),
        ('dominio o tipo composto', 'domini o tipi composti'): (
            "SELECT count(*) FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
            "WHERE (t.typtype = 'd' OR (t.typtype = 'c' AND EXISTS (SELECT 1 FROM pg_class c "
            "WHERE c.oid = t.typrelid AND c.relkind = 'c'))) AND " + _FILTRO_SCHEMI + " AND " +
            _NON_DI_ESTENSIONE.format(cat='pg_type', oid='t.oid')),
        ('tabella partizionata o ereditata', 'tabelle partizionate o ereditate'): (
            "SELECT count(*) FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE " + _FILTRO_SCHEMI),
        ('politica di sicurezza per riga', 'politiche di sicurezza per riga'): (
            "SELECT count(*) FROM pg_policy pol JOIN pg_class c ON c.oid = pol.polrelid "
            "JOIN pg_namespace n ON n.oid = c.relnamespace WHERE " + _FILTRO_SCHEMI),
    }
    for (uno, tanti), sql in q.items():
        n = _tutti(cur, sql)[0][0]
        if n:
            voci.append(f'{n} {uno if n == 1 else tanti}')
    est = [r[0] for r in _tutti(cur, "SELECT extname FROM pg_extension WHERE extname <> 'plpgsql' ORDER BY 1")]
    if est:
        voci.append('estensioni da ricreare a mano: ' + ', '.join(est))
    return voci


def _catalogo(cur):
    """Tutto quello che serve per scrivere il DDL, letto con search_path vuoto:
    format_type, pg_get_expr & c. restituiscono nomi completi di schema."""
    schemi = [r[0] for r in _tutti(cur,
        "SELECT quote_ident(n.nspname) FROM pg_namespace n WHERE " + _FILTRO_SCHEMI +
        " AND n.nspname <> 'public' AND " + _NON_DI_ESTENSIONE.format(cat='pg_namespace', oid='n.oid') +
        " ORDER BY n.nspname")]

    enum = _tutti(cur,
        "SELECT format('%I.%I', n.nspname, t.typname), "
        "       string_agg(quote_literal(e.enumlabel), ', ' ORDER BY e.enumsortorder) "
        "FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
        "JOIN pg_enum e ON e.enumtypid = t.oid "
        "WHERE " + _FILTRO_SCHEMI + " AND " + _NON_DI_ESTENSIONE.format(cat='pg_type', oid='t.oid') +
        " GROUP BY n.nspname, t.typname ORDER BY n.nspname, t.typname")

    # Sequenze "libere" o di tipo serial (deptype 'a'); quelle delle colonne
    # IDENTITY (deptype 'i') le ricrea la colonna stessa.
    sequenze = _tutti(cur,
        "SELECT c.oid, format('%I.%I', n.nspname, c.relname), format_type(s.seqtypid, NULL), "
        "       s.seqstart, s.seqincrement, s.seqmin, s.seqmax, s.seqcache, s.seqcycle "
        "FROM pg_sequence s JOIN pg_class c ON c.oid = s.seqrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE " + _FILTRO_SCHEMI + " AND " + _NON_DI_ESTENSIONE.format(cat='pg_class', oid='c.oid') +
        " AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.classid = 'pg_class'::regclass "
        "  AND d.objid = c.oid AND d.deptype = 'i') "
        "ORDER BY n.nspname, c.relname")

    possesso = _tutti(cur,
        "SELECT format('%I.%I', ns.nspname, s.relname), format('%I.%I.%I', nt.nspname, t.relname, a.attname) "
        "FROM pg_depend d "
        "JOIN pg_class s ON s.oid = d.objid AND s.relkind = 'S' "
        "JOIN pg_namespace ns ON ns.oid = s.relnamespace "
        "JOIN pg_class t ON t.oid = d.refobjid "
        "JOIN pg_namespace nt ON nt.oid = t.relnamespace "
        "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = d.refobjsubid "
        "WHERE d.classid = 'pg_class'::regclass AND d.refclassid = 'pg_class'::regclass "
        "  AND d.deptype = 'a' AND d.refobjsubid > 0 "
        "ORDER BY 1")

    tabelle = _tutti(cur,
        "SELECT c.oid, format('%I.%I', n.nspname, c.relname), n.nspname, c.relname "
        "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relkind = 'r' AND NOT c.relispartition AND " + _FILTRO_SCHEMI + " AND " +
        _NON_DI_ESTENSIONE.format(cat='pg_class', oid='c.oid') +
        " ORDER BY n.nspname, c.relname")

    colonne = {}
    for r in _tutti(cur,
        "SELECT a.attrelid, quote_ident(a.attname), format_type(a.atttypid, a.atttypmod), "
        "       a.attnotnull, pg_get_expr(ad.adbin, ad.adrelid), a.attidentity, a.attgenerated, "
        "       CASE WHEN a.attcollation <> 0 AND a.attcollation <> t.typcollation "
        "            THEN format('%I.%I', cn.nspname, co.collname) END "
        "FROM pg_attribute a "
        "JOIN pg_class c ON c.oid = a.attrelid AND c.relkind = 'r' "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "JOIN pg_type t ON t.oid = a.atttypid "
        "LEFT JOIN pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum "
        "LEFT JOIN pg_collation co ON co.oid = a.attcollation "
        "LEFT JOIN pg_namespace cn ON cn.oid = co.collnamespace "
        "WHERE a.attnum > 0 AND NOT a.attisdropped AND " + _FILTRO_SCHEMI +
        " ORDER BY a.attrelid, a.attnum"):
        colonne.setdefault(r[0], []).append(r[1:])

    # Identity: opzioni della sequenza interna per ricrearla uguale
    identity = {}
    for r in _tutti(cur,
        "SELECT a.attrelid, quote_ident(a.attname), format('%I.%I', ns.nspname, s.relname), "
        "       sq.seqstart, sq.seqincrement, sq.seqmin, sq.seqmax, sq.seqcache, sq.seqcycle "
        "FROM pg_depend d JOIN pg_class s ON s.oid = d.objid AND s.relkind = 'S' "
        "JOIN pg_namespace ns ON ns.oid = s.relnamespace "
        "JOIN pg_sequence sq ON sq.seqrelid = s.oid "
        "JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid "
        "WHERE d.classid = 'pg_class'::regclass AND d.deptype = 'i'"):
        identity[(r[0], r[1])] = r[2:]

    # Vincoli: primari/unique/check/exclude prima, chiavi esterne alla fine.
    # contype 'n' (NOT NULL come vincolo, da PostgreSQL 18) e' gia' nella colonna.
    vincoli = _tutti(cur,
        "SELECT format('%I.%I', n.nspname, c.relname), quote_ident(co.conname), co.contype, "
        "       pg_get_constraintdef(co.oid) "
        "FROM pg_constraint co JOIN pg_class c ON c.oid = co.conrelid AND c.relkind = 'r' "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE co.contype IN ('p', 'u', 'c', 'x', 'f') AND co.conislocal AND " + _FILTRO_SCHEMI + " AND " +
        _NON_DI_ESTENSIONE.format(cat='pg_class', oid='c.oid') +
        " ORDER BY CASE co.contype WHEN 'p' THEN 0 WHEN 'u' THEN 1 WHEN 'x' THEN 2 WHEN 'c' THEN 3 ELSE 4 END, "
        "          n.nspname, c.relname, co.conname")

    # Indici che non nascono da un vincolo (quelli li ricrea l'ADD CONSTRAINT)
    indici = _tutti(cur,
        "SELECT pg_get_indexdef(i.indexrelid) "
        "FROM pg_index i JOIN pg_class c ON c.oid = i.indrelid AND c.relkind = 'r' "
        "JOIN pg_class ic ON ic.oid = i.indexrelid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE " + _FILTRO_SCHEMI + " AND " + _NON_DI_ESTENSIONE.format(cat='pg_class', oid='c.oid') +
        " AND NOT EXISTS (SELECT 1 FROM pg_constraint co WHERE co.conindid = i.indexrelid "
        "  AND co.contype IN ('p', 'u', 'x')) "
        "ORDER BY n.nspname, ic.relname")

    return {'schemi': schemi, 'enum': enum, 'sequenze': sequenze, 'possesso': possesso,
            'tabelle': tabelle, 'colonne': colonne, 'identity': identity,
            'vincoli': vincoli, 'indici': indici}


def _opzioni_sequenza(tipo, start, inc, mn, mx, cache, ciclo):
    s = (f' AS {tipo}' if tipo else '') + \
        f' START WITH {start} INCREMENT BY {inc} MINVALUE {mn} MAXVALUE {mx} CACHE {cache}'
    return s + (' CYCLE' if ciclo else '')


# ---------------------------------------------------------------------------
# Dump
# ---------------------------------------------------------------------------
def esegui_dump(uri, percorso, etichetta='', avanzamento=None):
    """Scrive in `percorso` (gzip) il dump SQL del database. Ritorna un dict
    con tabelle, righe per tabella, byte e SHA-256 del testo non compresso."""
    def passo(**k):
        if avanzamento:
            avanzamento(**k)

    conn = psycopg2.connect(_dsn(uri), connect_timeout=15, application_name='tosca-backup')
    out = None
    try:
        conn.set_session(isolation_level='REPEATABLE READ', readonly=True)
        cur = conn.cursor()
        cur.execute("SET search_path = ''")
        cur.execute("SET client_encoding = 'UTF8'")
        cur.execute("SET statement_timeout = '15min'")
        cur.execute("SELECT current_setting('server_version'), current_database(), now()")
        versione, nome_db, istante = cur.fetchone()
        passo(fase='catalogo')
        non_inclusi = _non_inclusi(cur)
        cat = _catalogo(cur)

        out = _Uscita(percorso)
        w = out.testo
        quando = _adesso_roma().strftime('%d/%m/%Y %H:%M')
        w('--\n-- Backup Tosca del database "%s"%s\n' % (nome_db, f' ({etichetta})' if etichetta else ''))
        w('-- Fatto il %s dal pannello owner. Server PostgreSQL %s.\n' % (quando, versione))
        w('-- Fotografia coerente all\'istante %s (una transazione di sola lettura).\n' % istante.isoformat())
        w('--\n-- RIPRISTINO, su un database VUOTO gia\' creato:\n')
        w('--   psql -d <nuovo_db> -f <questo_file.sql>\n')
        w('-- Tutto o niente: al primo errore psql si ferma e non resta nulla a meta\'.\n')
        w('-- Senza proprietari e permessi (come pg_dump --no-owner --no-privileges).\n')
        if non_inclusi:
            w('--\n-- ATTENZIONE, NON inclusi in questo file: %s\n' % '; '.join(non_inclusi))
        w('--\n-- Contiene dati personali dei clienti: non va su GitHub ne\' in cartelle condivise.\n--\n\n')
        w('\\set ON_ERROR_STOP on\n')
        w("SET statement_timeout = 0;\nSET lock_timeout = 0;\nSET client_encoding = 'UTF8';\n"
          "SET standard_conforming_strings = on;\nSELECT pg_catalog.set_config('search_path', '', false);\n"
          "SET check_function_bodies = false;\nSET client_min_messages = warning;\n\nBEGIN;\n\n")

        for s in cat['schemi']:
            w(f'CREATE SCHEMA IF NOT EXISTS {s};\n')
        if cat['schemi']:
            w('\n')

        w('-- Tipi\n')
        for nome, etichette in cat['enum']:
            w(f'CREATE TYPE {nome} AS ENUM ({etichette});\n')

        w('\n-- Sequenze\n')
        for _oid, nome, tipo, *opz in cat['sequenze']:
            w(f'CREATE SEQUENCE {nome}{_opzioni_sequenza(tipo, *opz)};\n')

        w('\n-- Tabelle\n')
        colonne_copy = {}
        for oid, nome, _ns, _rel in cat['tabelle']:
            righe = []
            da_copiare = []
            for col, tipo, notnull, default, ident, gen, collaz in cat['colonne'].get(oid, []):
                d = f'    {col} {tipo}'
                if collaz:
                    d += f' COLLATE {collaz}'
                if gen == 's':
                    d += f' GENERATED ALWAYS AS ({default}) STORED'
                elif ident in ('a', 'd'):
                    io = cat['identity'].get((oid, col))
                    d += ' GENERATED %s AS IDENTITY' % ('ALWAYS' if ident == 'a' else 'BY DEFAULT')
                    if io:
                        d += ' (SEQUENCE NAME %s%s)' % (io[0], _opzioni_sequenza(None, *io[1:]))
                elif default is not None:
                    d += f' DEFAULT {default}'
                if notnull:
                    d += ' NOT NULL'
                righe.append(d)
                if gen != 's':
                    da_copiare.append(col)
            colonne_copy[oid] = da_copiare
            w(f'CREATE TABLE {nome} (\n' + ',\n'.join(righe) + '\n);\n\n')

        for seq, col in cat['possesso']:
            w(f'ALTER SEQUENCE {seq} OWNED BY {col};\n')

        w('\n-- Dati\n')
        conteggi = {}
        n_tab = len(cat['tabelle'])
        for i, (oid, nome, ns, rel) in enumerate(cat['tabelle'], start=1):
            passo(fase='dati', tabella=rel, indice=i, totale=n_tab)
            cols = colonne_copy.get(oid) or []
            elenco = ', '.join(cols)
            w(f'\nCOPY {nome} ({elenco}) FROM stdin;\n')
            prima = out.righe_copy
            cur.copy_expert(f'COPY {nome} ({elenco}) TO STDOUT', out)
            conteggi[f'{ns}.{rel}'] = out.righe_copy - prima
            w('\\.\n')

        w('\n-- Valori delle sequenze\n')
        for _oid, nome, *_ in cat['sequenze']:
            cur.execute(f'SELECT last_value, is_called FROM {nome}')
            v, chiamata = cur.fetchone()
            w(f"SELECT pg_catalog.setval('{nome}', {v}, {'true' if chiamata else 'false'});\n")
        for (oid, col), io in cat['identity'].items():
            cur.execute(f'SELECT last_value, is_called FROM {io[0]}')
            v, chiamata = cur.fetchone()
            w(f"SELECT pg_catalog.setval('{io[0]}', {v}, {'true' if chiamata else 'false'});\n")

        w('\n-- Vincoli\n')
        for tab, nome, tipo, defin in cat['vincoli']:
            if tipo != 'f':
                w(f'ALTER TABLE ONLY {tab} ADD CONSTRAINT {nome} {defin};\n')
        w('\n-- Indici\n')
        for defin in cat['indici']:
            w(f'{defin[0]};\n')
        w('\n-- Chiavi esterne\n')
        for tab, nome, tipo, defin in cat['vincoli']:
            if tipo == 'f':
                w(f'ALTER TABLE ONLY {tab} ADD CONSTRAINT {nome} {defin};\n')

        w('\nCOMMIT;\n\n-- Fine del backup: %d tabelle, %d righe.\n' % (n_tab, sum(conteggi.values())))
        out.chiudi()
        conn.rollback()
        return {
            'database': nome_db,
            'server': versione,
            'tabelle': n_tab,
            'righe': sum(conteggi.values()),
            'righe_per_tabella': conteggi,
            'byte_sql': out.byte,
            'sha256': out.sha.hexdigest(),
            'non_inclusi': non_inclusi,
        }
    except Exception:
        if out is not None:
            try:
                out.chiudi()
            except Exception:
                pass
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Lavori in background (uno alla volta)
# ---------------------------------------------------------------------------
def _pulisci():
    adesso = time.time()
    with _lock:
        for k in list(_lavori):
            j = _lavori[k]
            fine = j.get('finito_ts') or j['iniziato_ts']
            if adesso - fine > SCADENZA_FILE_S:
                _rimuovi_file(j)
                _lavori.pop(k, None)
    # File orfani di un riavvio precedente
    try:
        for f in os.listdir(CARTELLA):
            p = os.path.join(CARTELLA, f)
            if adesso - os.path.getmtime(p) > SCADENZA_FILE_S and not any(
                    j.get('percorso') == p for j in _lavori.values()):
                os.remove(p)
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _rimuovi_file(j):
    p = j.get('percorso')
    if p and os.path.exists(p):
        try:
            os.remove(p)
        except Exception:
            pass


def in_corso():
    with _lock:
        return next((dict(j) for j in _lavori.values() if j['stato'] == 'in_corso'), None)


def avvia(uri, etichetta, logger=None):
    """Fa partire il backup in un thread. Ritorna (lavoro, None) oppure
    (None, motivo) se ce n'e' gia' uno in corso."""
    _pulisci()
    os.makedirs(CARTELLA, exist_ok=True)
    with _lock:
        attivo = next((j for j in _lavori.values() if j['stato'] == 'in_corso'), None)
        if attivo:
            return None, f"C'e' gia' un backup in corso ({attivo['etichetta']}): aspetta che finisca."
        nome_db = nome_database(uri)
        stamp = _adesso_roma().strftime('%Y%m%d_%H%M')
        jid = uuid.uuid4().hex
        lavoro = {
            'id': jid, 'etichetta': etichetta, 'database': nome_db,
            'nome_file': f'{nome_db}_{stamp}.sql',
            'percorso': os.path.join(CARTELLA, f'{jid}.sql.gz'),
            'stato': 'in_corso', 'fase': 'connessione', 'tabella': '', 'indice': 0, 'totale': 0,
            'iniziato_ts': time.time(), 'finito_ts': None, 'errore': None, 'esito': None,
        }
        _lavori[jid] = lavoro

    def aggiorna(**k):
        with _lock:
            lavoro.update(k)

    def corri():
        try:
            esito = esegui_dump(uri, lavoro['percorso'], etichetta, avanzamento=aggiorna)
            esito['byte_gz'] = os.path.getsize(lavoro['percorso'])
            esito['secondi'] = round(time.time() - lavoro['iniziato_ts'], 1)
            aggiorna(stato='pronto', fase='pronto', esito=esito, finito_ts=time.time())
            if logger:
                logger.info("[backup] %s pronto: %d tabelle, %d righe, %d byte (gz %d) in %.1fs",
                            nome_db, esito['tabelle'], esito['righe'], esito['byte_sql'],
                            esito['byte_gz'], esito['secondi'])
        except Exception as e:
            _rimuovi_file(lavoro)
            # Il motivo va mostrato, ma senza la stringa di connessione
            msg = re.sub(r'postgres(ql)?(\+\w+)?://\S+', '<uri>', str(e)).strip() or e.__class__.__name__
            aggiorna(stato='errore', fase='errore', errore=msg[:500], finito_ts=time.time())
            if logger:
                logger.warning("[backup] %s fallito: %s", nome_db, msg, exc_info=True)

    threading.Thread(target=corri, name=f'backup-{nome_db}', daemon=True).start()
    return dict(lavoro), None


def stato(jid):
    with _lock:
        j = _lavori.get(jid)
        if not j:
            return None
        pubblico = {k: v for k, v in j.items() if k != 'percorso'}
        pubblico['secondi'] = round((j.get('finito_ts') or time.time()) - j['iniziato_ts'], 1)
        return pubblico


def file_pronto(jid):
    """(percorso, nome_file) del lavoro pronto, altrimenti None."""
    with _lock:
        j = _lavori.get(jid)
        if not j or j['stato'] != 'pronto' or not os.path.exists(j['percorso']):
            return None
        j['scaricato_ts'] = time.time()
        return j['percorso'], j['nome_file']
