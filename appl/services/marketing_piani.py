# appl/services/marketing_piani.py
"""Invii di marketing pianificati su piu' giorni (17/11/2026).

COSA FA. L'operatore sceglie anche centinaia di clienti in una volta (fino a
MAX_DESTINATARI); ogni giorno, dall'ora scelta, ne partono al massimo
`per_giorno`, mai oltre il limite giornaliero del negozio, finche' non li ha
raggiunti tutti. I messaggi passano dalla stessa coda dell'invio a mano
(marketing_queue): stesso ritmo di 12-20 secondi, stesso storico in
`marketing_invii`, stesso limite giornaliero.

CHI MANDA. Solo il processo cloud (GestSunBooking, wsgi.py), e solo se gira
DAVVERO su Azure (WEBSITE_SITE_NAME c'e' solo li'). L'exe del negozio e un
wsgi.py avviato a mano su un PC non spediscono mai niente da qui: montano i
negozi veri, e un avvio fatto per provare non deve poter mandare promo a
clienti veri (vedi la memoria "Mai avviare l'app per fare misure").

PERCHE' QUI LO STATO STA SU TABELLA (e la coda del marketing invece no). Un
piano dura giorni e deve sopravvivere a deploy e riavvii. Il rischio di un
invio persistente e' il doppione al riavvio; si chiude cosi':
  - ogni destinatario passa da `in_coda` a `in_invio` con un UPDATE
    condizionato e un commit PRIMA della chiamata a WhatsApp: chi trova la
    riga gia' cambiata non manda;
  - un riavvio proprio durante la chiamata lascia la riga `in_invio`: dopo
    SCADENZA_IN_INVIO diventa `non_confermato` e NON si rimanda da sola
    (meglio un messaggio in meno che uno doppio);
  - le righe `in_coda` rimaste senza coda (riavvio prima di partire) non sono
    mai partite: dopo SCADENZA_IN_CODA tornano `da_inviare`.

UNA VOLTA AL GIORNO. Il "giro di oggi" e' contato sul database (destinatari
presi oggi), non in memoria: un riavvio a meta' mattina riprende i mancanti e
non ne aggiunge altri.
"""

import os
import threading
import time as _time
from datetime import datetime, timedelta, timezone, time as dtime

from pytz import timezone as pytz_timezone
from sqlalchemy import or_, and_, func, inspect as sa_inspect

LIMITE_PREDEFINITO = 50          # limite giornaliero se il negozio non l'ha impostato
MAX_DESTINATARI = 500            # clienti in un piano solo
ORA_MIN = dtime(8, 0)            # ora di invio sceglibile: dalle 8...
ORA_MAX = dtime(19, 0)           # ...alle 19
ORA_FINE = dtime(20, 0)          # dopo le 20 il giro del giorno non comincia piu'
PAUSA_GIRO_S = 60
SCADENZA_IN_CODA = timedelta(minutes=60)
SCADENZA_IN_INVIO = timedelta(minutes=15)
MAX_TENTATIVI = 3                # per gli errori passeggeri (WhatsApp scollegato, server giu')

STATI_APERTI = ('da_inviare', 'in_coda', 'in_invio')
_TZ = pytz_timezone('Europe/Rome')
_GIORNI_EN = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


# ---------------------------------------------------------------------------
# Orari
# ---------------------------------------------------------------------------
def adesso_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def adesso_roma():
    return datetime.now(_TZ).replace(tzinfo=None)


def inizio_oggi_utc():
    """Mezzanotte italiana di oggi, in UTC senza fuso (come le colonne)."""
    mezzanotte = _TZ.localize(datetime.combine(adesso_roma().date(), dtime(0, 0)))
    return mezzanotte.astimezone(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Le tabelle ci sono? (migrations/manual_marketing_piani.sql)
# ---------------------------------------------------------------------------
# Se Tosca parte prima dello script SQL tutto deve funzionare come prima: si
# controlla una volta e, finche' mancano, si ricontrolla ogni 5 minuti, cosi'
# dopo lo script la pianificazione si accende senza riavviare.
_tabelle = {}        # url engine -> (pronte, controllato_alle)
_tabelle_lock = threading.Lock()


def tabelle_pronte():
    from appl import db
    try:
        chiave = str(db.engine.url)
    except Exception:
        return False
    with _tabelle_lock:
        voce = _tabelle.get(chiave)
        if voce and (voce[0] or _time.monotonic() - voce[1] < 300):
            return voce[0]
    try:
        isp = sa_inspect(db.engine)
        pronte = isp.has_table('marketing_piani') and isp.has_table('marketing_piano_destinatari')
    except Exception:
        pronte = False
    with _tabelle_lock:
        _tabelle[chiave] = (pronte, _time.monotonic())
    return pronte


# ---------------------------------------------------------------------------
# Limite giornaliero
# ---------------------------------------------------------------------------
def limite_giornaliero(business_info):
    return (getattr(business_info, 'marketing_max_daily_sends', None) or LIMITE_PREDEFINITO)


def invii_oggi():
    """Gli invii riusciti di oggi: la stessa definizione di sempre del limite."""
    from datetime import date
    from appl.models import MarketingInvio
    return MarketingInvio.query.filter(
        func.date(MarketingInvio.data_invio) == date.today(),
        MarketingInvio.stato == 'inviato').count()


def in_volo_piani():
    """Messaggi dei piani gia' presi e non ancora partiti (in qualunque processo)."""
    if not tabelle_pronte():
        return 0
    from appl.models import MarketingPianoDestinatario as D
    return D.query.filter(D.stato.in_(('in_coda', 'in_invio'))).count()


def posti_liberi_oggi(chiave, business_info):
    """Quanti messaggi di marketing si possono ancora impegnare oggi: limite,
    meno i partiti, meno quelli in coda a mano in QUESTO processo, meno quelli
    dei piani gia' presi (che stanno nella coda del processo cloud)."""
    from appl.services import marketing_queue
    return (limite_giornaliero(business_info) - invii_oggi()
            - marketing_queue.in_coda(chiave, solo_manuali=True) - in_volo_piani())


def giorno_di_chiusura(business_info, giorno):
    try:
        chiusi = business_info.closing_days_list or []
    except Exception:
        chiusi = []
    return _GIORNI_EN[giorno.weekday()] in chiusi


# ---------------------------------------------------------------------------
# Lettura per la pagina e per lo storico
# ---------------------------------------------------------------------------
def pianificati_campagna(campagna):
    """{client_id: piano_id} dei clienti che hanno questa promo in un piano
    ancora aperto: per lo storico contano come "gia' inviati"."""
    if not campagna or not tabelle_pronte():
        return {}
    from appl import db
    from appl.models import MarketingPiano as P, MarketingPianoDestinatario as D
    righe = (db.session.query(D.client_id, D.piano_id)
             .join(P, P.id == D.piano_id)
             .filter(P.campagna == campagna, P.stato.in_(('attivo', 'in_pausa')),
                     D.stato.in_(STATI_APERTI))
             .all())
    return {cid: pid for cid, pid in righe}


def piani_aperti_campagna(campagna):
    if not campagna or not tabelle_pronte():
        return 0
    from appl.models import MarketingPiano as P
    return P.query.filter(P.campagna == campagna, P.stato.in_(('attivo', 'in_pausa'))).count()


def _iso(dt):
    return dt.isoformat() + 'Z' if dt else None


def prossimo_giro(piano, business_info, restanti, presi_oggi=0, posti_oggi=None):
    """Quando partira' il prossimo gruppo e quando finira' il piano (date
    italiane), contando i giorni di chiusura e quanto e' gia' partito oggi.
    Stima: il limite del negozio puo' essere consumato anche dagli invii a mano."""
    if piano.stato != 'attivo' or restanti <= 0:
        return None, None
    per_giorno = max(1, min(piano.per_giorno, limite_giornaliero(business_info)))
    ora = adesso_roma()
    giorno = ora.date()
    # Oggi ci sta ancora qualcosa? Il gruppo di oggi puo' essere gia' finito
    # (presi_oggi) o il limite del negozio gia' esaurito (posti_oggi).
    oggi = per_giorno - presi_oggi if ora.time() < ORA_FINE else 0
    if posti_oggi is not None:
        oggi = min(oggi, max(0, posti_oggi))
    giorni, coperti = [], 0
    while len(giorni) < 400 and coperti < restanti:
        if not giorno_di_chiusura(business_info, giorno):
            posti = oggi if giorno == ora.date() else per_giorno
            if posti > 0:
                giorni.append(giorno)
                coperti += posti
        giorno += timedelta(days=1)
    if not giorni:
        return None, None
    return giorni[0], giorni[-1]


def riepilogo_piani(business_info, giorni_chiusi=30):
    """I piani da mostrare nella pagina Marketing: aperti, piu' quelli chiusi
    negli ultimi `giorni_chiusi` giorni."""
    if not tabelle_pronte():
        return None
    from appl import db
    from appl.models import MarketingPiano as P, MarketingPianoDestinatario as D
    from appl.formati import data_it
    limite = adesso_utc() - timedelta(days=giorni_chiusi)
    piani = (P.query.filter(or_(P.stato.in_(('attivo', 'in_pausa')), P.chiuso_il >= limite))
             .order_by(P.id.desc()).limit(20).all())
    if not piani:
        return []
    conteggi = {}
    for pid, stato, n in (db.session.query(D.piano_id, D.stato, func.count(D.id))
                          .filter(D.piano_id.in_([p.id for p in piani]))
                          .group_by(D.piano_id, D.stato).all()):
        conteggi.setdefault(pid, {})[stato] = n
    inizio = inizio_oggi_utc()
    ids = [p.id for p in piani]
    oggi = dict(db.session.query(D.piano_id, func.count(D.id)).filter(
        D.piano_id.in_(ids), D.stato == 'inviato',
        D.inviato_il >= inizio).group_by(D.piano_id).all())
    # Presi oggi, come li conta il giro: il gruppo di oggi puo' essere gia' finito.
    presi = dict(db.session.query(D.piano_id, func.count(D.id)).filter(
        D.piano_id.in_(ids), D.in_coda_il >= inizio,
        D.stato.notin_(('da_inviare', 'annullato'))).group_by(D.piano_id).all())
    try:
        from appl.services import usage_monitor
        posti = posti_liberi_oggi(usage_monitor.chiave_tenant(), business_info)
    except Exception:
        posti = None
    out = []
    for p in piani:
        c = conteggi.get(p.id, {})
        totale = sum(c.values())
        restanti = sum(c.get(s, 0) for s in STATI_APERTI)
        # Quelli gia' in partenza escono oggi; la stima e' per i da inviare.
        in_corso = c.get('in_coda', 0) + c.get('in_invio', 0)
        primo, ultimo = prossimo_giro(p, business_info, c.get('da_inviare', 0),
                                      presi.get(p.id, 0), posti)
        if in_corso and p.stato == 'attivo':
            oggi_roma = adesso_roma().date()
            primo, ultimo = oggi_roma, ultimo or oggi_roma
        out.append({
            'id': p.id,
            'nome': p.nome,
            'campagna': p.campagna,
            'stato': p.stato,
            'per_giorno': p.per_giorno,
            'ora_invio': p.ora_invio.strftime('%H:%M'),
            'ha_foto': bool(p.immagine_mime),
            'creato_il': _iso(p.creato_il),
            'creato_da': p.creato_da,
            'chiuso_il': _iso(p.chiuso_il),
            'totale': totale,
            'inviati': c.get('inviato', 0),
            'inviati_oggi': oggi.get(p.id, 0),
            'da_inviare': c.get('da_inviare', 0),
            'in_corso': c.get('in_coda', 0) + c.get('in_invio', 0),
            'errori': c.get('errore', 0),
            'saltati': c.get('saltato', 0),
            'annullati': c.get('annullato', 0),
            'non_confermati': c.get('non_confermato', 0),
            'prossimo_giorno': data_it(primo) if primo else None,
            'prossimo_oggi': bool(primo and primo == adesso_roma().date()),
            'ultimo_giorno': data_it(ultimo) if ultimo else None,
        })
    return out


def dettaglio_problemi(piano_id, limite=200):
    """Chi non ha ricevuto il messaggio e perche' (errori, saltati, non confermati)."""
    from appl import db
    from appl.models import MarketingPianoDestinatario as D, Client
    righe = (db.session.query(D.stato, D.motivo, D.ultimo_tentativo_il, D.tentativi,
                              Client.cliente_nome, Client.cliente_cognome, Client.cliente_cellulare)
             .join(Client, Client.id == D.client_id)
             .filter(D.piano_id == piano_id, D.stato.in_(('errore', 'saltato', 'non_confermato')))
             .order_by(D.ultimo_tentativo_il.desc().nullslast(), D.id)
             .limit(limite).all())
    return [{
        'stato': r.stato, 'motivo': r.motivo, 'quando': _iso(r.ultimo_tentativo_il),
        'tentativi': r.tentativi,
        'nome': ((r.cliente_nome or '') + ' ' + (r.cliente_cognome or '')).strip(),
        'cellulare': r.cliente_cellulare,
    } for r in righe]


# ---------------------------------------------------------------------------
# Creazione e comandi
# ---------------------------------------------------------------------------
def crea_piano(nome, campagna, testo, immagine, immagine_mime, per_giorno, ora_invio,
               client_ids, creato_da):
    from appl import db
    from appl.models import MarketingPiano, MarketingPianoDestinatario
    piano = MarketingPiano(nome=nome[:120], campagna=campagna, testo=testo,
                           immagine=immagine, immagine_mime=immagine_mime if immagine else None,
                           per_giorno=per_giorno, ora_invio=ora_invio, stato='attivo',
                           creato_il=adesso_utc(), creato_da=(creato_da or None))
    db.session.add(piano)
    db.session.flush()
    db.session.bulk_insert_mappings(MarketingPianoDestinatario, [
        {'piano_id': piano.id, 'client_id': cid, 'ordine': i, 'stato': 'da_inviare', 'tentativi': 0}
        for i, cid in enumerate(client_ids)])
    db.session.commit()
    return piano


def _libera_in_coda(piano_id, motivo=None):
    """Le righe gia' prese per oggi e non ancora partite tornano da inviare,
    riprendibili anche oggi: dopo "Riprendi" il giro continua. Dopo un WhatsApp
    scollegato invece il piano si ferma fino al giorno dopo, ma per un'altra
    via: la riga del tentativo fallito (vedi il controllo in giro())."""
    from appl.models import MarketingPianoDestinatario as D
    valori = {'stato': 'da_inviare', 'in_coda_il': None}
    if motivo:
        valori['motivo'] = motivo
    return D.query.filter(D.piano_id == piano_id, D.stato == 'in_coda').update(
        valori, synchronize_session=False)


def cambia_stato(piano_id, azione):
    """pausa | riprendi | annulla. Ritorna (ok, messaggio)."""
    from appl import db
    from appl.models import MarketingPiano, MarketingPianoDestinatario as D
    piano = db.session.get(MarketingPiano, piano_id)
    if piano is None:
        return False, 'Piano non trovato'
    if piano.stato in ('annullato', 'completato'):
        return False, 'Il piano è già chiuso'
    if azione == 'pausa':
        if piano.stato != 'attivo':
            return False, 'Il piano è già in pausa'
        piano.stato = 'in_pausa'
        _libera_in_coda(piano.id)
    elif azione == 'riprendi':
        if piano.stato != 'in_pausa':
            return False, 'Il piano non è in pausa'
        piano.stato = 'attivo'
    elif azione == 'annulla':
        _libera_in_coda(piano.id)
        D.query.filter(D.piano_id == piano.id, D.stato == 'da_inviare').update(
            {'stato': 'annullato', 'motivo': 'Piano annullato'}, synchronize_session=False)
        piano.stato = 'annullato'
        piano.chiuso_il = adesso_utc()
    else:
        return False, 'Azione non valida'
    db.session.commit()
    return True, None


# ---------------------------------------------------------------------------
# Agganci alla coda (chiamati da marketing_queue._lavora, nel thread)
# ---------------------------------------------------------------------------
def ancora_da_mandare(messaggio):
    """Controllo veloce PRIMA di aspettare il turno: un messaggio di un piano
    messo in pausa o annullato non deve far aspettare 12-20 secondi a vuoto."""
    dest_id = messaggio.get('piano_dest_id')
    if not dest_id:
        return True
    from appl import db
    from appl.models import MarketingPiano as P, MarketingPianoDestinatario as D
    riga = (db.session.query(D.stato, P.stato).join(P, P.id == D.piano_id)
            .filter(D.id == dest_id).first())
    db.session.rollback()     # niente transazione aperta durante l'attesa
    return bool(riga and riga[0] == 'in_coda' and riga[1] == 'attivo')


def prima_dell_invio(messaggio):
    """Subito prima della chiamata a WhatsApp: segna la riga `in_invio` e
    conferma. Se la riga non e' piu' `in_coda` (piano in pausa o annullato da
    un altro operatore, o gia' presa) non si manda. True = manda."""
    dest_id = messaggio.get('piano_dest_id')
    if not dest_id:
        return True
    from appl import db
    from appl.models import MarketingPiano as P, MarketingPianoDestinatario as D
    attivi = db.session.query(P.id).filter(P.stato == 'attivo')
    n = D.query.filter(D.id == dest_id, D.stato == 'in_coda', D.piano_id.in_(attivi)).update(
        {'stato': 'in_invio', 'ultimo_tentativo_il': adesso_utc(),
         'tentativi': D.tentativi + 1}, synchronize_session=False)
    db.session.commit()
    return n == 1


def _errore_passeggero(errore):
    """WhatsApp scollegato o servizio giu': si riprova il giorno dopo. Gli
    altri errori (numero non su WhatsApp, richiesta rifiutata) sono definitivi."""
    e = (errore or '').lower()
    return ('disconnected_account' in e or 'http 401' in e or 'http 5' in e
            or 'http 429' in e or 'timeout' in e)


def dopo_l_invio(messaggio, riuscito, errore):
    """Nella STESSA transazione della riga di marketing_invii (il commit lo fa
    chi chiama): o sono vere tutte e due, o nessuna."""
    dest_id = messaggio.get('piano_dest_id')
    if not dest_id:
        return
    from appl import db
    from appl.models import MarketingPianoDestinatario as D
    riga = db.session.get(D, dest_id)
    if riga is None:
        return
    adesso = adesso_utc()
    if riuscito:
        riga.stato, riga.inviato_il, riga.motivo = 'inviato', adesso, None
        return
    from appl.services.whatsapp_errori import spiega_errore
    if _errore_passeggero(errore) and (riga.tentativi or 0) < MAX_TENTATIVI:
        riga.stato = 'da_inviare'
        riga.motivo = ('WhatsApp scollegato: riprovo il prossimo giorno di invio'
                       if 'disconnected' in (errore or '').lower() or 'http 401' in (errore or '').lower()
                       else 'WhatsApp non ha risposto: riprovo il prossimo giorno di invio')
        if 'disconnected' in (errore or '').lower() or 'http 401' in (errore or '').lower():
            # Account scollegato: gli altri del giro di oggi fallirebbero tutti.
            # Si ferma il giro e si riprende il prossimo giorno.
            _libera_in_coda(riga.piano_id, motivo='Giro fermato: WhatsApp scollegato')
        return
    riga.stato = 'errore'
    riga.motivo = (spiega_errore(errore, messaggio.get('numero'), breve=True)
                   or (errore or 'errore sconosciuto'))[:300]


def dopo_eccezione(app, messaggio, errore):
    """L'invio e' finito in un'eccezione (rete, database): non si sa se il
    messaggio e' arrivato. La riga resta senza esito certo e non si rimanda."""
    dest_id = messaggio.get('piano_dest_id')
    if not dest_id:
        return
    try:
        with app.app_context():
            from appl import db
            from appl.models import MarketingPianoDestinatario as D
            D.query.filter(D.id == dest_id, D.stato == 'in_invio').update(
                {'stato': 'non_confermato',
                 'motivo': ('Invio interrotto (%s): non so se è arrivato, '
                            'non viene rimandato da solo' % (errore or 'errore'))[:300]},
                synchronize_session=False)
            db.session.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Il giro (solo processo cloud)
# ---------------------------------------------------------------------------
def _pulizia(chiave):
    """Righe rimaste a meta' da un riavvio (vedi docstring del modulo).
    Scrive solo se trova qualcosa."""
    from appl import db
    from appl.models import MarketingPianoDestinatario as D
    from appl.services import marketing_queue
    nostri = marketing_queue.ids_piano(chiave)
    adesso = adesso_utc()
    ferme_coda = D.query.filter(D.stato == 'in_coda', D.in_coda_il < adesso - SCADENZA_IN_CODA)
    ferme_invio = D.query.filter(D.stato == 'in_invio',
                                 D.ultimo_tentativo_il < adesso - SCADENZA_IN_INVIO)
    if nostri:
        ferme_coda = ferme_coda.filter(~D.id.in_(nostri))
        ferme_invio = ferme_invio.filter(~D.id.in_(nostri))
    scritto = False
    if ferme_coda.first() is not None:
        # Mai partiti: si possono riprendere anche oggi (in_coda_il azzerato).
        ferme_coda.update({'stato': 'da_inviare', 'in_coda_il': None}, synchronize_session=False)
        scritto = True
    if ferme_invio.first() is not None:
        ferme_invio.update({'stato': 'non_confermato',
                            'motivo': 'Server riavviato durante l\'invio: non so se è arrivato, '
                                      'non viene rimandato da solo'}, synchronize_session=False)
        scritto = True
    if scritto:
        db.session.commit()


def _chiudi_se_finito(piano):
    from appl import db
    from appl.models import MarketingPianoDestinatario as D
    aperti = D.query.filter(D.piano_id == piano.id, D.stato.in_(STATI_APERTI)).count()
    if aperti == 0:
        piano.stato = 'completato'
        piano.chiuso_il = adesso_utc()
        db.session.commit()
        return True
    return False


def _prendi(piano, quanti, inizio_oggi):
    """I prossimi `quanti` destinatari, in ordine. Chi e' gia' stato preso
    OGGI e poi rilasciato (pausa, WhatsApp scollegato) aspetta domani."""
    from appl.models import MarketingPianoDestinatario as D
    return (D.query.filter(D.piano_id == piano.id, D.stato == 'da_inviare',
                           or_(D.in_coda_il.is_(None), D.in_coda_il < inizio_oggi))
            .order_by(D.ordine, D.id).limit(quanti)
            .with_for_update(skip_locked=True).all())


def giro(app):
    """Un passaggio per un negozio: pulizia, poi per ogni piano attivo il
    gruppo di oggi, se e' l'ora e se c'e' posto."""
    from appl import db
    from appl.models import (BusinessInfo, Client, MarketingInvio,
                             MarketingPiano, MarketingPianoDestinatario as D)
    from appl.services import marketing_queue, usage_monitor

    with app.app_context():
        try:
            if not tabelle_pronte():
                return
            # Niente piani aperti = niente da fare, nemmeno la pulizia: un giro
            # al minuto per negozio non deve scrivere sul database a vuoto.
            if MarketingPiano.query.filter(
                    MarketingPiano.stato.in_(('attivo', 'in_pausa'))).first() is None:
                db.session.rollback()
                return
            chiave = usage_monitor.chiave_tenant()
            _pulizia(chiave)
            piani = MarketingPiano.query.filter_by(stato='attivo').order_by(MarketingPiano.id).all()
            if not piani:
                return
            bi = BusinessInfo.query.filter_by(is_deleted=False).first()
            account_id = (getattr(bi, 'unipile_account_id', None) or '').strip() if bi else ''
            dsn = (os.getenv('UNIPILE_DSN') or '').strip()
            token = (os.getenv('UNIPILE_ACCESS_TOKEN') or os.getenv('UNIPILE_API_KEY') or '').strip()
            if not bi or not account_id or not dsn or not token:
                return
            ora = adesso_roma()
            if giorno_di_chiusura(bi, ora.date()):
                return
            inizio = inizio_oggi_utc()
            from appl.routes.settings import (_marketing_dati_clienti, _marketing_componi,
                                              _normalize_phone_for_whatsapp)
            config = {'account_id': account_id, 'token': token, 'base_url': 'https://%s' % dsn}

            for piano in piani:
                if _chiudi_se_finito(piano):
                    continue
                if not (piano.ora_invio <= ora.time() < ORA_FINE):
                    continue
                # Oggi un invio e' gia' tornato indietro per un errore passeggero
                # (WhatsApp scollegato, servizio giu'): per oggi il piano si
                # ferma. Senza, ogni giro prenderebbe il gruppo dopo, che
                # fallirebbe allo stesso modo, e si consumerebbe la lista intera.
                if D.query.filter(D.piano_id == piano.id, D.stato == 'da_inviare',
                                  D.ultimo_tentativo_il >= inizio).first() is not None:
                    continue
                presi_oggi = D.query.filter(
                    D.piano_id == piano.id, D.in_coda_il >= inizio,
                    D.stato.notin_(('da_inviare', 'annullato'))).count()
                quanti = min(piano.per_giorno - presi_oggi, posti_liberi_oggi(chiave, bi))
                if quanti <= 0:
                    continue
                righe = _prendi(piano, quanti, inizio)
                if not righe:
                    db.session.rollback()
                    continue

                clienti = {c.id: c for c in Client.query.filter(
                    Client.id.in_([r.client_id for r in righe])).all()}
                # Chi ha gia' ricevuto la promo (anche a mano, dopo la creazione del piano)
                gia = {cid for (cid,) in db.session.query(MarketingInvio.client_id).filter(
                    MarketingInvio.campagna == piano.campagna,
                    MarketingInvio.stato == 'inviato',
                    MarketingInvio.azzerato_il.is_(None),
                    MarketingInvio.client_id.in_(list(clienti))).distinct()}
                gia |= marketing_queue.in_coda_campagna(chiave, piano.campagna)
                validi = [clienti[r.client_id] for r in righe
                          if r.client_id in clienti and not clienti[r.client_id].is_deleted]
                dati = {d['id']: d for d in _marketing_dati_clienti(validi)} if validi else {}
                foto = ({'dati': bytes(piano.immagine), 'mime': piano.immagine_mime, 'nome': 'promo.jpg'}
                        if piano.immagine_mime and piano.immagine else None)
                centro = bi.business_name or 'Centro'
                adesso = adesso_utc()
                messaggi = []
                for r in righe:
                    c = clienti.get(r.client_id)
                    if c is None or c.is_deleted:
                        r.stato, r.motivo = 'saltato', 'Cliente eliminato'
                        continue
                    if r.client_id in gia:
                        r.stato, r.motivo = 'saltato', 'Aveva già ricevuto questa promo'
                        continue
                    numero = _normalize_phone_for_whatsapp(c.cliente_cellulare)
                    if not numero:
                        r.stato, r.motivo = 'saltato', 'Cellulare mancante o non valido'
                        continue
                    d = dati.get(c.id) or {'id': c.id, 'nome': c.cliente_nome,
                                           'cognome': c.cliente_cognome}
                    r.stato, r.in_coda_il, r.motivo = 'in_coda', adesso, None
                    messaggi.append({
                        'client_id': c.id,
                        'nome': ((d.get('nome') or '') + ' ' + (d.get('cognome') or '')).strip(),
                        'numero': numero,
                        'testo': _marketing_componi(piano.testo, d, centro),
                        'foto': foto,
                        'campagna': piano.campagna,
                        'piano_dest_id': r.id,
                    })
                db.session.commit()
                if messaggi:
                    marketing_queue.accoda(app, chiave, messaggi, config)
                    app.logger.info("[marketing-piano] piano %s: %s messaggi in coda",
                                    piano.id, len(messaggi))
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass
            app.logger.exception("[marketing-piano] giro non riuscito")


_avviato = False
_avvio_lock = threading.Lock()


def processo_che_spedisce():
    """Solo la web app su Azure. WEBSITE_SITE_NAME lo imposta App Service da
    se': su un PC (exe, wsgi.py avviato a mano, prove) non c'e'."""
    return bool(os.getenv('WEBSITE_SITE_NAME')) and os.getenv('MARKETING_PIANI_SPENTI') != '1'


def avvia_scheduler(figli, escludi=()):
    """Un thread per tutto il processo: ogni minuto un giro per negozio.
    `figli` e' il dizionario vivo idx -> app di wsgi.py (i negozi aggiunti dopo
    l'avvio entrano da soli); `escludi` gli slot della prova gratuita."""
    global _avviato
    if not processo_che_spedisce():
        return False
    with _avvio_lock:
        if _avviato:
            return True
        _avviato = True

    def lavora():
        # Un minuto di respiro all'avvio: i negozi si stanno ancora montando.
        _time.sleep(PAUSA_GIRO_S)
        while True:
            for idx, figlio in list(figli.items()):
                if idx in escludi:
                    continue
                giro(figlio)
            _time.sleep(PAUSA_GIRO_S)

    threading.Thread(target=lavora, daemon=True, name='marketing-piani').start()
    return True
