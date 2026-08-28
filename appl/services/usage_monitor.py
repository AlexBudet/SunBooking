# appl/services/usage_monitor.py
"""Raccolta dei consumi di un singolo tenant, per il pannello owner.

Divisione dei compiti con azure_monitor.py: li' ci sono le metriche che solo
Azure conosce (CPU, RAM, quota storage, fatturazione e-mail), qui quelle che
l'applicazione puo' misurare da se' - e che sono la maggior parte.

Ogni funzione lavora dentro l'app context del tenant: e' il chiamante
(/owner-setup/monitor) che gira sui tenant uno per uno.

Regola di questo modulo: NON deve mai far fallire chi lo chiama. Un pannello di
monitoraggio che rompe l'applicazione che sta monitorando e' peggio di nessun
pannello. Ogni raccolta e' avvolta in un try e in caso di guaio restituisce un
dizionario con la chiave 'errore'.
"""

import threading
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import text

from appl import db
from appl.models import UsageEvent, UsageTrafficHourly


# ============================================================================
# 1. Registrazione degli invii che costano
# ============================================================================

def registra_uso(canale, tipo='altro', origine='crm', esito='ok', errore=None):
    """Scrive una riga in usage_events. Da chiamare dopo OGNI invio WhatsApp o
    e-mail, riuscito o fallito che sia: i fallimenti vanno contati anche loro,
    perche' un tentativo respinto e' comunque una chiamata all'API.

    Non solleva mai: se il monitoraggio non riesce a scrivere, l'invio e' gia'
    avvenuto e non ha senso propagare l'errore a chi stava mandando il
    messaggio. Il caso tipico e' proprio quello: connessioni esaurite.

    Non sollevare pero' non vuol dire sparire: il fallimento finisce nel log
    come WARNING. Un contatore che perde righe in silenzio e' peggio di un
    contatore assente, perche' il pannello mostra "0 messaggi" e quello zero
    sembra un dato buono. Se usage_events manca su un tenant, quella riga di
    log e' l'unico posto in cui il guasto si vede.
    """
    try:
        db.session.add(UsageEvent(
            canale=str(canale)[:20],
            tipo=str(tipo)[:40],
            origine=str(origine)[:20],
            esito='errore' if esito not in ('ok', True) else 'ok',
            errore=(str(errore)[:300] if errore else None),
        ))
        db.session.commit()
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.warning(
                "[consumi] invio %s/%s NON contato: %s", canale, tipo, str(e)[:200])
        except Exception:
            pass


# ============================================================================
# 2. Traffico HTTP
# ============================================================================
# Il conteggio vive in memoria e viene scaricato su database una volta all'ora.
# Contare ogni richiesta su tabella vorrebbe dire una INSERT per ogni click:
# si consumerebbe piu' database per misurare che per lavorare.

_traffico_lock = threading.Lock()

# UN CONTATORE PER TENANT, non uno solo. Con wsgi.py questo modulo viene
# importato una volta sola e i tenant girano tutti nello stesso processo: un
# dizionario globale sommerebbe le richieste di tutti i negozi e poi
# scriverebbe il totale nel database di quello che per caso ha fatto scattare
# lo scarico. Il traffico di ogni negozio sarebbe identico e sbagliato.
_traffico = {}   # chiave tenant -> {'ora', 'richieste', 'errori', 'ms_totali', 'ms_max'}


def _chiave_tenant():
    """Identificatore del tenant nel processo corrente.

    TENANT_IDX e' None nelle installazioni a negozio singolo (start.py): li'
    c'e' una sola app e la chiave fissa va benissimo.
    """
    try:
        return str(current_app.config.get('TENANT_IDX'))
    except Exception:
        return 'unico'


def _ora_corrente():
    return datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)


def registra_richiesta(durata_ms, status_code):
    """Contatore in memoria, chiamato da un after_request. Deve costare
    pochissimo: e' su ogni richiesta dell'applicazione.

    Ritorna il blocco dell'ora precedente quando l'ora cambia, cosi' il
    chiamante puo' scaricarlo su database. Il flush NON viene fatto qui dentro
    perche' questa funzione gira dentro il lock: scrivere su database mentre si
    tiene un lock preso da ogni richiesta significa mettere in fila tutta
    l'applicazione dietro una INSERT.
    """
    ora = _ora_corrente()
    chiave = _chiave_tenant()
    da_scaricare = None
    with _traffico_lock:
        corrente = _traffico.get(chiave)
        if corrente is None:
            corrente = {'ora': ora, 'richieste': 0, 'errori': 0, 'ms_totali': 0, 'ms_max': 0}
            _traffico[chiave] = corrente
        elif corrente['ora'] != ora:
            da_scaricare = dict(corrente)
            corrente.update({'ora': ora, 'richieste': 0, 'errori': 0,
                             'ms_totali': 0, 'ms_max': 0})
        corrente['richieste'] += 1
        if status_code >= 500:
            corrente['errori'] += 1
        ms = int(durata_ms)
        corrente['ms_totali'] += ms
        if ms > corrente['ms_max']:
            corrente['ms_max'] = ms
    return da_scaricare


def scarica_traffico(blocco):
    """UPSERT del blocco orario. In UPDATE si SOMMA invece di sovrascrivere:
    dopo un riavvio la stessa ora viene scaricata due volte da due processi
    diversi, e i due pezzi vanno sommati, non l'ultimo vince."""
    if not blocco or not blocco.get('ora') or not blocco.get('richieste'):
        return
    try:
        db.session.execute(text("""
            INSERT INTO usage_traffic_hourly (ora, richieste, errori, ms_totali, ms_max)
            VALUES (:ora, :richieste, :errori, :ms_totali, :ms_max)
            ON CONFLICT (ora) DO UPDATE SET
                richieste = usage_traffic_hourly.richieste + EXCLUDED.richieste,
                errori    = usage_traffic_hourly.errori    + EXCLUDED.errori,
                ms_totali = usage_traffic_hourly.ms_totali + EXCLUDED.ms_totali,
                ms_max    = GREATEST(usage_traffic_hourly.ms_max, EXCLUDED.ms_max)
        """), blocco)
        db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass


def traffico(giorni=7):
    """Serie oraria + medie. Include l'ora in corso, che e' ancora in memoria e
    non e' stata scaricata: senza, il pannello mostrerebbe sempre un buco
    proprio sull'ora che si sta guardando."""
    try:
        da = datetime.now(timezone.utc) - timedelta(days=giorni)
        righe = (UsageTrafficHourly.query
                 .filter(UsageTrafficHourly.ora >= da)
                 .order_by(UsageTrafficHourly.ora).all())
        serie = [{
            'ora': r.ora.isoformat(),
            'richieste': r.richieste,
            'errori': r.errori,
            'ms_medi': round(r.ms_totali / r.richieste) if r.richieste else 0,
            'ms_max': r.ms_max,
        } for r in righe]

        with _traffico_lock:
            corrente = dict(_traffico.get(_chiave_tenant()) or {})
        if corrente.get('ora') and corrente.get('richieste'):
            serie.append({
                'ora': corrente['ora'].isoformat(),
                'richieste': corrente['richieste'],
                'errori': corrente['errori'],
                'ms_medi': round(corrente['ms_totali'] / corrente['richieste']),
                'ms_max': corrente['ms_max'],
                'parziale': True,
            })

        totale = sum(s['richieste'] for s in serie)
        ore = len(serie) or 1
        return {
            'serie': serie,
            'totale': totale,
            'media_oraria': round(totale / ore, 1),
            'picco_orario': max((s['richieste'] for s in serie), default=0),
            'errori': sum(s['errori'] for s in serie),
            'giorni': giorni,
        }
    except Exception as e:
        return {'errore': str(e)[:200]}


# ============================================================================
# 3. Database
# ============================================================================

def metriche_database():
    """Peso del database e connessioni in uso, lette da PostgreSQL stesso.

    Le connessioni si contano su due livelli, che vengono confusi spesso e
    sono guasti diversi (lo si e' visto il 27/08/2026):
      - quelle di QUESTO database  -> quanto pesa il singolo negozio
      - quelle di TUTTO il server  -> il tetto vero, condiviso fra i tenant
    """
    dati = {}
    try:
        dati['dimensione_byte'] = db.session.execute(
            text("SELECT pg_database_size(current_database())")).scalar()

        # pg_stat_activity: un utente non superuser vede comunque TUTTE le
        # righe (solo alcune colonne gli restano nascoste), quindi il conteggio
        # e' attendibile anche senza privilegi speciali.
        r = db.session.execute(text("""
            SELECT
                count(*) FILTER (WHERE datname = current_database()) AS del_db,
                count(*)                                            AS del_server,
                count(*) FILTER (WHERE state = 'active')            AS attive,
                count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_tx
            FROM pg_stat_activity
            WHERE backend_type = 'client backend'
        """)).mappings().first()
        dati['connessioni'] = dict(r) if r else {}

        dati['max_connections'] = int(db.session.execute(
            text("SELECT current_setting('max_connections')")).scalar())

        # Quanti slot sono riservati e quindi NON utilizzabili dall'app.
        try:
            riservate = int(db.session.execute(
                text("SELECT current_setting('superuser_reserved_connections')")).scalar())
        except Exception:
            riservate = 0
        dati['connessioni_riservate'] = riservate
        dati['connessioni_disponibili'] = dati['max_connections'] - riservate

        s = db.session.execute(text("""
            SELECT xact_commit, xact_rollback, blks_hit, blks_read,
                   tup_returned, tup_fetched, deadlocks
            FROM pg_stat_database WHERE datname = current_database()
        """)).mappings().first()
        if s:
            s = dict(s)
            letture = (s.get('blks_hit') or 0) + (s.get('blks_read') or 0)
            # Percentuale di letture servite dalla RAM del server: sotto il 95%
            # su un carico come questo vuol dire che la cache non basta piu'.
            s['cache_hit_pct'] = round(100.0 * (s.get('blks_hit') or 0) / letture, 2) if letture else None
            dati['statistiche'] = s

        # Le cinque tabelle piu' grandi: serve a capire CHE COSA cresce, che e'
        # l'unica informazione utile quando lo spazio inizia a finire.
        tab = db.session.execute(text("""
            SELECT relname AS tabella, pg_total_relation_size(c.oid) AS byte
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r' AND n.nspname = 'public'
            ORDER BY pg_total_relation_size(c.oid) DESC LIMIT 5
        """)).mappings().all()
        dati['tabelle_maggiori'] = [dict(t) for t in tab]
    except Exception as e:
        dati['errore'] = str(e)[:200]
    return dati


def stato_pool():
    """Stato del pool SQLAlchemy di QUESTO tenant, in tempo reale.

    E' la metrica che e' esplosa il 27/08/2026 e l'unica che dice se il collo
    di bottiglia e' il pool dell'applicazione o gli slot del server. Non costa
    nulla: sono contatori tenuti in memoria da SQLAlchemy, nessuna query.

    Si usa db.engine e non db.get_engine(app): in Flask-SQLAlchemy 3.1 il primo
    parametro di get_engine e' bind_key, non l'applicazione, e passargli l'app
    cercherebbe un bind con quel nome. db.engine dentro un app context da' gia'
    l'engine di quel tenant, che e' esattamente quello che serve.
    """
    try:
        pool = db.engine.pool
        dimensione = pool.size()
        overflow_max = getattr(pool, '_max_overflow', 0)
        in_uso = pool.checkedout()
        return {
            'pool_size': dimensione,
            'max_overflow': overflow_max,
            'tetto': dimensione + overflow_max,
            'in_uso': in_uso,
            'disponibili': pool.checkedin(),
            'overflow_attuale': max(0, in_uso - dimensione),
            'descrizione': pool.status(),
        }
    except Exception as e:
        return {'errore': str(e)[:200]}


# ============================================================================
# 4. Invii (WhatsApp / e-mail)
# ============================================================================

def invii(giorni=30):
    """Totali e frequenza per canale, dalla tabella usage_events.

    'da' dice da quando esistono i dati: prima dell'introduzione di
    usage_events gli invii non erano registrati da nessuna parte, e un totale
    che parte da meta' storia senza dirlo e' un totale che inganna.
    """
    try:
        da = datetime.now(timezone.utc) - timedelta(days=giorni)
        righe = db.session.execute(text("""
            SELECT canale, tipo, esito, count(*) AS n
            FROM usage_events WHERE created_at >= :da
            GROUP BY canale, tipo, esito
        """), {'da': da}).mappings().all()

        per_canale = {}
        for r in righe:
            c = per_canale.setdefault(r['canale'], {'totale': 0, 'errori': 0, 'per_tipo': {}})
            c['totale'] += r['n']
            if r['esito'] == 'errore':
                c['errori'] += r['n']
            c['per_tipo'][r['tipo']] = c['per_tipo'].get(r['tipo'], 0) + r['n']

        for c in per_canale.values():
            c['media_giornaliera'] = round(c['totale'] / giorni, 1)
            c['stima_mensile'] = round(c['totale'] / giorni * 30)

        serie = db.session.execute(text("""
            SELECT date_trunc('day', created_at) AS giorno, canale, count(*) AS n
            FROM usage_events WHERE created_at >= :da
            GROUP BY 1, 2 ORDER BY 1
        """), {'da': da}).mappings().all()

        primo = db.session.execute(
            text("SELECT min(created_at) FROM usage_events")).scalar()

        return {
            'per_canale': per_canale,
            'serie_giornaliera': [
                {'giorno': s['giorno'].date().isoformat(), 'canale': s['canale'], 'n': s['n']}
                for s in serie
            ],
            'dati_da': primo.isoformat() if primo else None,
            'giorni': giorni,
        }
    except Exception as e:
        return {'errore': str(e)[:200]}


def invii_marketing_storici():
    """Conteggio da marketing_invii, che esiste da prima ed e' l'unico storico
    disponibile. Copre solo il marketing: va mostrato a parte, non sommato ai
    dati nuovi, altrimenti nel periodo di sovrapposizione si conta due volte."""
    try:
        r = db.session.execute(text("""
            SELECT count(*) AS totale,
                   min(data_invio) AS dal,
                   max(data_invio) AS al,
                   count(*) FILTER (WHERE stato = 'errore') AS errori
            FROM marketing_invii
        """)).mappings().first()
        d = dict(r) if r else {}
        for k in ('dal', 'al'):
            if d.get(k):
                d[k] = d[k].isoformat()
        return d
    except Exception as e:
        return {'errore': str(e)[:200]}


# ============================================================================
# 5. Errori
# ============================================================================

def errori(giorni=30):
    """Errori registrati, con in evidenza quelli di connessione: sono gli unici
    che parlano di capienza e non di logica applicativa.

    Si porta dietro anche il `context` dell'occorrenza piu' recente. Un numero
    ("3 errori") non e' un'informazione su cui si possa fare qualcosa: per
    decidere serve leggere QUALI, e senza il dettaglio si finisce a rifare la
    stessa query a mano in psql ogni volta."""
    try:
        da = datetime.now(timezone.utc) - timedelta(days=giorni)
        righe = db.session.execute(text("""
            SELECT reason, count(*) AS n, max(created_at) AS ultimo,
                   (array_agg(context::text ORDER BY created_at DESC))[1] AS dettaglio
            FROM crm_error_logs WHERE created_at >= :da
            GROUP BY reason ORDER BY n DESC LIMIT 10
        """), {'da': da}).mappings().all()

        # Le due varianti dell'avviso connessioni si distinguono solo dentro il
        # campo context: separarle qui evita di rileggerlo a mano ogni volta.
        conn = db.session.execute(text("""
            SELECT context->>'origine' AS origine, count(*) AS n, max(created_at) AS ultimo
            FROM crm_error_logs
            WHERE reason = 'Connessioni al database esaurite' AND created_at >= :da
            GROUP BY 1
        """), {'da': da}).mappings().all()

        return {
            'totale': sum(r['n'] for r in righe),
            'principali': [
                {'motivo': r['reason'], 'n': r['n'], 'ultimo': r['ultimo'].isoformat(),
                 'dettaglio': (r['dettaglio'][:300] if r['dettaglio'] else None)}
                for r in righe
            ],
            'connessioni': [
                {'origine': c['origine'] or 'sconosciuta', 'n': c['n'],
                 'ultimo': c['ultimo'].isoformat()}
                for c in conn
            ],
            'giorni': giorni,
        }
    except Exception as e:
        return {'errore': str(e)[:200]}


# ============================================================================
# 6. Raccolta completa di un tenant
# ============================================================================

def raccogli(giorni=30):
    """Tutte le misure di un tenant in un colpo solo.

    Va chiamata dentro l'app context del tenant: tutte le misure sotto leggono
    da li' l'engine e la sessione giusti."""
    return {
        'database': metriche_database(),
        'pool': stato_pool(),
        'invii': invii(giorni),
        'marketing_storico': invii_marketing_storici(),
        'traffico': traffico(giorni=min(giorni, 7)),
        'errori': errori(giorni),
    }
