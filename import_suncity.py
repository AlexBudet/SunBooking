# -*- coding: utf-8 -*-
"""
IMPORT STORICO SUN CITY  ->  PostgreSQL Azure (tenant suncity / URI1)

    python import_suncity.py                 # DRY-RUN: non scrive nulla
    python import_suncity.py --esegui        # scrive davvero (una sola transazione)

REGOLE (non negoziabili, vedi prompt di import):
  - SOLO INSERT. Mai UPDATE, mai DELETE, mai ON CONFLICT DO UPDATE.
  - Cliente gia' presente  -> non si tocca NESSUN suo campo.
  - Cliente con prepagata  -> si salta del tutto, e si segnala.
  - Ogni cosa che lo script "avrebbe voluto" scrivere finisce nel log, non nel DB.

SCELTE CONCORDATE CON L'UTENTE (04/08/2026):
  1. Su Tosca non esistono prepagate reali: solo quelle di prova, gia' cancellate.
  2. Cliente id 428 (unico con apertura negativa): conta il credito, non lo storico.
     -> per lui niente movimenti storici, solo il saldo di apertura.
  3. Nessuna data di taglio: fino a oggi si e' usato solo il vecchio gestionale.
  4. Anagrafiche vuote: importate tutte, con nomi "Cliente<N> / Da assegnare<N>".
  5. Clienti con credito 0: NON importati.
  6. Movimenti: solo ultimi 12 mesi; il resto confluisce nel saldo di apertura.
"""
import argparse, os, re, sqlite3, sys
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict

SQLITE_PATH = r'C:\Program Files\SunBooking\suncity.db'
ENV_PATH = r'C:\Program Files\SunBooking\.env'
ENV_KEY = 'SQLALCHEMY_DATABASE_URI1'
MESI_INDIETRO_GIORNI = 365
OGGI = datetime.now()
LIMITE = OGGI - timedelta(days=MESI_INDIETRO_GIORNI)
LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        f'import_suncity_{OGGI:%Y%m%d_%H%M%S}.log')

_log = []
def log(msg=''):
    print(msg)
    _log.append(str(msg))

def euro(v):
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# ---------------------------------------------------------------- sorgente
MESI = {m: i for i, m in enumerate(
    ['January', 'February', 'March', 'April', 'May', 'June', 'July',
     'August', 'September', 'October', 'November', 'December'], 1)}

def parse_data(s):
    """Le date sono TEXT in DUE formati mischiati: ISO e '28 October 2024 19:48'."""
    if not s:
        return None
    s = str(s).strip()
    for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, f)
        except ValueError:
            pass
    m = re.match(r'^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?$', s)
    if m:
        g, mese, anno, hh, mm = m.groups()
        mi = MESI.get(mese.capitalize())
        if mi:
            try:
                return datetime(int(anno), mi, int(g), int(hh or 0), int(mm or 0))
            except ValueError:
                return None
    return None

def norm_tel(t):
    if not t:
        return ''
    d = re.sub(r'\D', '', str(t))
    return re.sub(r'^(0039|39)(?=\d{9,10}$)', '', d)

def tel_valido(d):
    """Utilizzabile per il match: solo cellulari italiani a 10 cifre."""
    return len(d) == 10 and d.startswith('3')

def leggi_sorgente():
    con = sqlite3.connect(f'file:{SQLITE_PATH}?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    clienti = [dict(r) for r in con.execute('SELECT * FROM cliente ORDER BY id')]
    movimenti = defaultdict(list)
    for tab, tipo in (('ricarica', 'ricarica'), ('seduta', 'utilizzo')):
        for r in con.execute(f'SELECT cliente_id, importo, data FROM "{tab}"'):
            d = parse_data(r['data'])
            if d is None:
                continue
            movimenti[r['cliente_id']].append(
                {'tipo': tipo, 'importo': euro(r['importo'] or 0), 'data': d})
    con.close()
    for lista in movimenti.values():
        lista.sort(key=lambda m: m['data'])
    return clienti, movimenti

# ---------------------------------------------------------------- destinazione
def leggi_uri():
    if not os.path.exists(ENV_PATH):
        sys.exit(f'.env non trovato in {ENV_PATH}')
    for riga in open(ENV_PATH, encoding='utf-8'):
        riga = riga.strip()
        if riga.startswith(ENV_KEY + '='):
            uri = riga.split('=', 1)[1].strip().strip('"').strip("'")
            # Nel .env la URI e' in formato SQLAlchemy (postgresql+psycopg2://...):
            # psycopg2 vuole lo schema puro, altrimenti "invalid dsn".
            return re.sub(r'^postgresql\+\w+://', 'postgresql://', uri)
    sys.exit(f'{ENV_KEY} non presente nel .env')

# ---------------------------------------------------------------- piano
def costruisci_piano(clienti, movimenti, esistenti_tel, tessere_usate, clienti_con_prepagata):
    """Decide cosa fare per ogni cliente. Non tocca il database."""
    piano, saltati = [], []
    progressivo_anonimo = 0

    for c in clienti:
        cid = c['id']
        credito = euro(c['credito'] or 0)
        nome = (c['nome'] or '').strip()
        cognome = (c['cognome'] or '').strip()
        tel = norm_tel(c['telefono'])

        if credito <= 0:
            saltati.append((cid, 'credito zero o negativo', f'credito={credito}'))
            continue

        if str(cid) in tessere_usate:
            saltati.append((cid, 'numero_tessera GIA ASSEGNATO su Tosca',
                            f'tessera={cid} -> import saltato per sicurezza'))
            continue

        # --- anagrafica ---
        anonimo = not (nome or cognome)
        if anonimo:
            progressivo_anonimo += 1
            nome = f'Cliente{progressivo_anonimo}'
            cognome = f'Da assegnare{progressivo_anonimo}'
            tel_finale = f'SUNCITY-{cid}'      # placeholder deterministico = idempotente
        else:
            tel_finale = c['telefono'] or f'SUNCITY-{cid}'

        # --- match col cliente gia' presente su Tosca ---
        client_id_tosca = None
        if tel and tel_valido(tel):
            client_id_tosca = esistenti_tel.get(tel)
        elif anonimo:
            client_id_tosca = esistenti_tel.get(f'SUNCITY-{cid}')

        if client_id_tosca and client_id_tosca in clienti_con_prepagata:
            saltati.append((cid, 'cliente gia presente CON prepagata',
                            f'client_id={client_id_tosca} -> non tocco nulla'))
            continue

        # --- movimenti: solo ultimi 12 mesi ---
        tutti = movimenti.get(cid, [])
        recenti = [m for m in tutti if m['data'] >= LIMITE]
        netto_recenti = sum((m['importo'] if m['tipo'] == 'ricarica' else -m['importo'])
                            for m in recenti) or euro(0)
        apertura = euro(credito - netto_recenti)

        note_apertura = ''
        if apertura < 0:
            # Lo storico direbbe piu' credito di quello reale: vince il credito.
            # Si rinuncia al dettaglio e si scrive un'unica riga di apertura.
            recenti = []
            apertura = credito
            note_apertura = ('storico scartato: incoerente col credito reale '
                             '(apertura sarebbe stata negativa)')

        piano.append({
            'suncity_id': cid, 'nome': nome, 'cognome': cognome,
            'telefono': tel_finale, 'anonimo': anonimo,
            'client_id_tosca': client_id_tosca, 'credito': credito,
            'apertura': apertura, 'movimenti': recenti,
            'scartati': len(tutti) - len(recenti), 'note': note_apertura,
        })
    return piano, saltati

def righe_movimenti(voce):
    """Rigioca i movimenti in ordine e calcola saldo_dopo. L'ultimo DEVE dare il credito."""
    righe = []
    saldo = euro(0)
    primo = voce['movimenti'][0]['data'] if voce['movimenti'] else OGGI
    if voce['apertura'] != 0:
        saldo = voce['apertura']
        righe.append({'tipo': 'ricarica', 'importo': abs(voce['apertura']),
                      'saldo': saldo, 'data': primo - timedelta(seconds=1),
                      'descr': 'Saldo iniziale importato da Sun City'})
    for m in voce['movimenti']:
        saldo = euro(saldo + (m['importo'] if m['tipo'] == 'ricarica' else -m['importo']))
        righe.append({'tipo': m['tipo'], 'importo': m['importo'], 'saldo': saldo,
                      'data': m['data'],
                      'descr': 'Ricarica (storico Sun City)' if m['tipo'] == 'ricarica'
                               else 'Seduta scalata (storico Sun City)'})
    return righe, saldo

# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--esegui', action='store_true',
                    help='scrive davvero sul database (senza, e sola simulazione)')
    args = ap.parse_args()

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor, execute_values
    except ImportError:
        sys.exit('psycopg2 non disponibile in questo interprete Python.')

    log('=' * 78)
    log(f'IMPORT SUN CITY -> Tosca   {"ESECUZIONE REALE" if args.esegui else "DRY-RUN (nessuna scrittura)"}')
    log(f'{OGGI:%d/%m/%Y %H:%M}   movimenti importati dal {LIMITE:%d/%m/%Y}')
    log('=' * 78)

    clienti, movimenti = leggi_sorgente()
    log(f'\nSorgente: {len(clienti)} clienti, '
        f'{sum(len(v) for v in movimenti.values())} movimenti con data valida')

    conn = psycopg2.connect(leggi_uri())
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # --- fotografia della destinazione (sola lettura) ---
    cur.execute("""
        SELECT id, regexp_replace(regexp_replace(COALESCE(cliente_cellulare,''),'\\D','','g'),
               '^(0039|39)(?=\\d{9,10}$)','') AS tel
        FROM clienti WHERE is_deleted = false""")
    esistenti_tel = {r['tel']: r['id'] for r in cur.fetchall() if r['tel']}
    cur.execute("SELECT numero_tessera FROM pacchetti WHERE numero_tessera IS NOT NULL")
    tessere_usate = {str(r['numero_tessera']) for r in cur.fetchall()}
    cur.execute("SELECT DISTINCT client_id FROM pacchetti WHERE tipo = 'prepagata'")
    clienti_con_prepagata = {r['client_id'] for r in cur.fetchall()}
    log(f'Destinazione: {len(esistenti_tel)} clienti con cellulare, '
        f'{len(tessere_usate)} tessere gia assegnate, '
        f'{len(clienti_con_prepagata)} clienti con prepagata')

    piano, saltati = costruisci_piano(clienti, movimenti, esistenti_tel,
                                      tessere_usate, clienti_con_prepagata)

    nuovi = [v for v in piano if not v['client_id_tosca']]
    esistenti = [v for v in piano if v['client_id_tosca']]
    tot_mov = sum(len(righe_movimenti(v)[0]) for v in piano)

    log('\n' + '-' * 78)
    log('PIANO')
    log('-' * 78)
    log(f'  carte prepagate da creare ......... {len(piano)}')
    log(f'     di cui clienti NUOVI ........... {len(nuovi)}')
    log(f'     di cui clienti GIA PRESENTI .... {len(esistenti)}  (anagrafica non toccata)')
    log(f'     di cui anagrafiche anonime ..... {sum(1 for v in piano if v["anonimo"])}')
    log(f'  movimenti da creare ............... {tot_mov}')
    log(f'  credito totale importato .......... EUR {sum(v["credito"] for v in piano)}')
    log(f'  clienti saltati ................... {len(saltati)}')

    if saltati:
        log('\n  Dettaglio saltati:')
        for cid, motivo, extra in saltati:
            log(f'     suncity id={cid:<5} {motivo:<45} {extra}')

    incoerenti = [v for v in piano if v['note']]
    if incoerenti:
        log('\n  Clienti con storico scartato (credito preservato):')
        for v in incoerenti:
            log(f'     suncity id={v["suncity_id"]:<5} credito={v["credito"]}  {v["note"]}')

    if esistenti:
        log('\n  Clienti GIA PRESENTI su Tosca: si aggiunge solo la carta, '
            'nessun campo anagrafico viene toccato.')
        for v in esistenti[:40]:
            log(f'     suncity id={v["suncity_id"]:<5} -> client_id={v["client_id_tosca"]:<6} '
                f'{v["nome"]} {v["cognome"]}  credito={v["credito"]}')
        if len(esistenti) > 40:
            log(f'     ... e altri {len(esistenti) - 40}')

    # --- verifica di coerenza PRIMA di scrivere ---
    log('\n' + '-' * 78)
    log('VERIFICA: ultimo saldo_dopo == credito_residuo, per ogni carta')
    log('-' * 78)
    errori = []
    for v in piano:
        _, finale = righe_movimenti(v)
        if finale != v['credito']:
            errori.append((v['suncity_id'], finale, v['credito']))
    if errori:
        log(f'  !! {len(errori)} carte NON quadrano:')
        for cid, f, c in errori[:20]:
            log(f'     suncity id={cid}  replay={f}  credito={c}')
        log('  Import interrotto: nessuna scrittura.')
        conn.rollback(); conn.close(); scrivi_log(); sys.exit(1)
    log(f'  OK: tutte le {len(piano)} carte chiudono esattamente sul credito.')

    if not args.esegui:
        log('\n' + '=' * 78)
        log('DRY-RUN: nessuna riga scritta. Per eseguire davvero:')
        log('   1) FAI IL BACKUP DEL DATABASE suncity')
        log('   2) python import_suncity.py --esegui')
        log('=' * 78)
        conn.rollback(); conn.close(); scrivi_log(); return

    # --- scrittura, tutta in una transazione ---
    log('\n' + '-' * 78)
    log('SCRITTURA')
    log('-' * 78)
    creati_cli = creati_pac = creati_mov = 0
    movimenti_da_inserire = []
    try:
        for v in piano:
            client_id = v['client_id_tosca']
            if not client_id:
                cur.execute("""INSERT INTO clienti
                    (cliente_nome, cliente_cognome, cliente_cellulare, cliente_sesso, is_deleted, note)
                    VALUES (%s,%s,%s,'-',false,%s) RETURNING id""",
                    (v['nome'], v['cognome'], v['telefono'],
                     f'Importato da Sun City (id {v["suncity_id"]})'))
                client_id = cur.fetchone()['id']
                creati_cli += 1

            cur.execute("""INSERT INTO pacchetti
                (client_id, nome, tipo, status, data_sottoscrizione, costo_totale_lordo,
                 credito_iniziale, credito_residuo, numero_tessera, history)
                VALUES (%s,%s,'prepagata','Attivo',%s,%s,%s,%s,%s,%s) RETURNING id""",
                (client_id, f'Carta Prepagata {v["suncity_id"]}', OGGI.date(),
                 v['credito'], v['credito'], v['credito'], str(v['suncity_id']),
                 f'[{{"ts": "{OGGI.isoformat()}", "azione": "Importata da Sun City"}}]'))
            pacchetto_id = cur.fetchone()['id']
            creati_pac += 1

            righe, _ = righe_movimenti(v)
            for r in righe:
                movimenti_da_inserire.append(
                    (pacchetto_id, r['data'], r['tipo'], r['importo'], r['saldo'], r['descr']))

            fatti = creati_pac
            if fatti % 50 == 0:
                print(f'    ... {fatti}/{len(piano)} carte preparate')

        # I movimenti si inseriscono in blocco: 2300 andate e ritorno verso Azure
        # diventano poche chiamate, e l'import passa da minuti a secondi.
        if movimenti_da_inserire:
            execute_values(cur, """INSERT INTO movimenti_prepagata
                (pacchetto_id, data_movimento, tipo_movimento, importo, saldo_dopo, descrizione)
                VALUES %s""", movimenti_da_inserire, page_size=500)
            creati_mov = len(movimenti_da_inserire)

        conn.commit()
        log(f'  clienti creati ....... {creati_cli}')
        log(f'  prepagate create ..... {creati_pac}')
        log(f'  movimenti creati ..... {creati_mov}')
        log('  COMMIT eseguito.')
    except Exception as e:
        conn.rollback()
        log(f'  ERRORE: {e}')
        log('  ROLLBACK eseguito: il database e rimasto come prima.')
        conn.close(); scrivi_log(); sys.exit(1)

    # --- checksum finali ---
    cur.execute("""SELECT COUNT(*) n, COALESCE(SUM(credito_residuo),0) s
                   FROM pacchetti WHERE tipo='prepagata' AND status='Attivo'""")
    r = cur.fetchone()
    log('\n' + '-' * 78)
    log('CHECKSUM')
    log('-' * 78)
    log(f'  atteso da sorgente ... {len(piano)} carte, EUR {sum(v["credito"] for v in piano)}')
    log(f'  presente su Tosca .... {r["n"]} carte, EUR {r["s"]}')
    conn.close()
    scrivi_log()

def scrivi_log():
    """Il log NON deve mai far fallire lo script dopo un commit riuscito:
    se C:\\Program Files non e' scrivibile (VS Code non elevato) si ripiega
    sulla cartella temporanea dell'utente."""
    percorsi = [LOG_PATH, os.path.join(os.environ.get('TEMP', '.'),
                                       os.path.basename(LOG_PATH))]
    for p in percorsi:
        try:
            with open(p, 'w', encoding='utf-8') as f:
                f.write('\n'.join(_log))
            print(f'\nLog scritto in: {p}')
            return
        except OSError as e:
            print(f'\nLog non scrivibile in {p} ({e})')
    print('Log non salvato su file: sopra hai comunque tutto l\'output.')

if __name__ == '__main__':
    main()
