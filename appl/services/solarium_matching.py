"""
Riconciliazione Solarium <-> Cassa: collega ogni seduta lampada
(SolariumSession) allo scontrino di pagamento (Receipt) piu' vicino nel
tempo, per voci con categoria "Solarium". I due campi di collegamento
(SolariumSession.client_id, SolariumSession.receipt_id) esistono gia' in
schema mai valorizzati: qui vengono popolati.

Il modulo NON tocca mai appl/routes/cassa.py: legge (sola lettura) gli
scontrini gia' committati con un loop periodico, stesso pattern fail-open
di _reconcile_loop in solarium_bridge.py, cosi' da restare completamente
disaccoppiato dal flusso di emissione scontrino/fiscale.

Il criterio di riferimento (inizio o fine seduta) e' configurabile da
/settings/solarium e salvato in un file JSON locale (nessuna modifica di
schema/models.py): la distanza effettiva usata per il match e' comunque il
minimo tra distanza da inizio e da fine, per la massima precisione; il
criterio impostato serve solo come sistema del passo in caso di parita'.
"""
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta, timezone

logger = logging.getLogger('SunBooking')

_CONFIG_DIR = os.path.join(os.getenv('LOCALAPPDATA', os.getcwd()), 'SunBooking')
_CONFIG_PATH = os.path.join(_CONFIG_DIR, 'solarium_matching.json')

# Tolleranza per il collegamento automatico: entro questi minuti da
# inizio/fine seduta, il pagamento piu' vicino viene collegato da solo.
AUTO_MATCH_TOLERANCE_MIN = 10
# Oltre questi minuti dalla fine seduta senza collegamento, la seduta compare
# nello strumento di riconciliazione manuale.
MANUAL_REVIEW_AFTER_MIN = 30
# Finestra di ricerca candidati nello strumento manuale (piu' ampia della
# tolleranza di auto-match, per recuperare pagamenti arrivati in ritardo).
CANDIDATE_WINDOW_HOURS = 6
# Non riconsiderare sedute chiuse da piu' di tanto (limita il costo del loop).
_LOOKBACK_HOURS = 24

_started = False
_lock = threading.Lock()


def get_criterio():
    """'inizio' (default, pagamento anticipato) oppure 'fine'."""
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        criterio = data.get('criterio')
        if criterio in ('inizio', 'fine'):
            return criterio
    except Exception:
        pass
    return 'inizio'


def set_criterio(value):
    if value not in ('inizio', 'fine'):
        return
    try:
        os.makedirs(_CONFIG_DIR, exist_ok=True)
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump({'criterio': value}, f)
    except Exception as e:
        logger.error("Solarium matching: impossibile salvare il criterio: %s", e)


def to_naive_local(dt):
    """Normalizza a naive locale (usata solo su SolariumSession.inizio/fine,
    mai su Receipt.created_at che e' gia' naive locale).

    BUG CORRETTO: quando il driver Postgres restituisce questi valori senza
    tzinfo, NON sono gia' ora locale - sono UTC con il tzinfo perso (stesso
    presupposto usato altrove nel progetto, es. calendar.py/solarium_bridge.py:
    "if tzinfo is None: replace(tzinfo=timezone.utc)"). Trattarli come gia'
    locali (versione precedente di questa funzione) sfalsava la finestra di
    ricerca dell'ampiezza del fuso orario, e nessun abbinamento cadeva mai
    nella tolleranza."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().replace(tzinfo=None)


def _is_solarium_voce(v):
    """Vero se la voce e' un servizio di categoria Solarium.

    La chiave 'categoria' nelle voci NON e' affidabile: in cassa.py e'
    valorizzata esplicitamente per i pagamenti di pacchetto/rata/prepagata,
    ma i due percorsi piu' comuni per Solarium - pagamento diretto di un
    singolo servizio appena erogato (blocco 'servizi_json', cassa.py righe
    389-398) e pagamento da appuntamento (blocco 'appointments_json', righe
    413-422) - costruiscono la voce SENZA la chiave 'categoria' (ne fiscale
    ne' non fiscale, il problema e' identico in entrambi i casi). Entrambi
    quei percorsi valorizzano pero' sempre 'id' con il Service.id reale:
    usato qui come fallback per risalire alla vera categoria del servizio,
    senza toccare cassa.py."""
    if not isinstance(v, dict):
        return False
    if v.get('categoria') == 'Solarium':
        return True
    if v.get('categoria'):
        return False  # categoria presente ma diversa: non e' Solarium
    service_id = v.get('id')
    if not service_id:
        return False
    from appl.models import Service, ServiceCategory
    servizio = Service.query.get(service_id)
    return bool(servizio and servizio.servizio_categoria == ServiceCategory.Solarium)


def _solarium_voci(receipt):
    voci = receipt.voci or []
    return [v for v in voci if _is_solarium_voce(v)]


def _capacity(receipt):
    """Quante sedute puo' coprire questo scontrino (n. voci Solarium: uno
    scontrino con un pacchetto da 2 sedute puo' collegarne fino a 2)."""
    return len(_solarium_voci(receipt))


def _used_slots(receipt_id):
    from appl.models import SolariumSession
    return SolariumSession.query.filter_by(receipt_id=receipt_id).count()


def session_payment_status(session):
    """'collegato' se la seduta ha gia' un pagamento associato, 'in_sospeso'
    se sono passati piu' di MANUAL_REVIEW_AFTER_MIN minuti dalla fine senza
    abbinamento, 'in_attesa' se il tempo per l'abbinamento automatico non e'
    ancora scaduto, None se la seduta e' ancora in corso (fine nulla)."""
    if session.receipt_id:
        return 'collegato'
    if session.fine is None:
        return None
    fine = session.fine
    if fine.tzinfo is None:
        fine = fine.replace(tzinfo=timezone.utc)
    minuti_da_fine = (datetime.now(timezone.utc) - fine).total_seconds() / 60
    return 'in_sospeso' if minuti_da_fine >= MANUAL_REVIEW_AFTER_MIN else 'in_attesa'


def _pick_appointment_id(receipt):
    """Sceglie, tra le voci Solarium dello scontrino, un appointment_id non
    ancora assegnato a un'altra seduta collegata allo stesso scontrino (per
    scontrini multi-seduta con voci legate ad appuntamenti diversi). Se le
    voci non hanno appointment_id (pagamento senza prenotazione), torna None
    senza bloccare il collegamento seduta<->scontrino."""
    from appl.models import SolariumSession
    used = {s.appointment_id for s in
            SolariumSession.query.filter_by(receipt_id=receipt.id).all()
            if s.appointment_id}
    for v in _solarium_voci(receipt):
        appt_id = v.get('appointment_id')
        if appt_id and appt_id not in used:
            return appt_id
    return None


def _effective_distance(session, receipt_time):
    """Distanza minima (secondi) tra il pagamento e inizio/fine seduta."""
    inizio = to_naive_local(session.inizio)
    fine = to_naive_local(session.fine)
    dists = [abs((receipt_time - inizio).total_seconds())]
    if fine is not None:
        dists.append(abs((receipt_time - fine).total_seconds()))
    return min(dists)


def _preferred_distance(session, receipt_time, criterio):
    """Distanza dall'istante preferito da impostazione, usata solo come
    tie-break tra candidati a pari distanza effettiva."""
    ref = session.fine if (criterio == 'fine' and session.fine is not None) else session.inizio
    return abs((receipt_time - to_naive_local(ref)).total_seconds())


def find_best_receipt(session, tolerance_minutes=AUTO_MATCH_TOLERANCE_MIN):
    """Miglior scontrino Solarium per questa seduta, entro la tolleranza, o
    None se nessun candidato e' abbastanza vicino / con capacita' residua."""
    from appl.models import Receipt

    criterio = get_criterio()
    inizio = to_naive_local(session.inizio)
    fine = to_naive_local(session.fine) or inizio
    window_start = min(inizio, fine) - timedelta(minutes=tolerance_minutes)
    window_end = max(inizio, fine) + timedelta(minutes=tolerance_minutes)
    tolerance_sec = tolerance_minutes * 60

    receipts = (Receipt.query
                .filter(Receipt.created_at >= window_start,
                        Receipt.created_at <= window_end)
                .all())

    best = None
    best_key = None
    for r in receipts:
        if _capacity(r) == 0:
            continue
        if _used_slots(r.id) >= _capacity(r):
            continue
        eff = _effective_distance(session, r.created_at)
        if eff > tolerance_sec:
            continue
        key = (eff, _preferred_distance(session, r.created_at, criterio))
        if best_key is None or key < best_key:
            best_key, best = key, r
    return best


def auto_match_pending():
    """Tenta il collegamento automatico per tutte le sedute chiuse e non
    ancora collegate. Fail-open per seduta: un errore su una non blocca le
    altre."""
    from appl import db
    from appl.models import SolariumSession

    cutoff = datetime.now(timezone.utc) - timedelta(hours=_LOOKBACK_HOURS)
    sessions = (SolariumSession.query
                .filter(SolariumSession.fine.isnot(None),
                        SolariumSession.receipt_id.is_(None),
                        SolariumSession.fine >= cutoff)
                .all())

    for s in sessions:
        try:
            receipt = find_best_receipt(s)
            if receipt:
                s.receipt_id = receipt.id
                s.client_id = receipt.cliente_id
                s.appointment_id = _pick_appointment_id(receipt)
                db.session.commit()
                logger.info("Solarium: seduta %s collegata allo scontrino %s (cliente_id=%s, appointment_id=%s)",
                            s.id, receipt.id, receipt.cliente_id, s.appointment_id)
        except Exception as e:
            db.session.rollback()
            logger.error("Solarium matching: errore collegando la seduta %s: %s", s.id, e)


def _loop(app):
    while True:
        time.sleep(15)
        try:
            with app.app_context():
                auto_match_pending()
        except Exception as e:
            logger.error("Solarium matching: errore nel loop di riconciliazione: %s", e)


def start_matching_loop(app):
    """Idempotente: le chiamate successive alla prima non fanno nulla."""
    global _started
    with _lock:
        if _started:
            return
        _started = True
    threading.Thread(target=_loop, args=(app,), daemon=True).start()
    logger.info("Solarium: loop di riconciliazione pagamenti avviato.")


def list_pending_sessions():
    """Sedute chiuse da piu' di MANUAL_REVIEW_AFTER_MIN minuti, ancora senza
    scontrino collegato: da mostrare nello strumento di riconciliazione."""
    from appl.models import SolariumSession

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=MANUAL_REVIEW_AFTER_MIN)
    return (SolariumSession.query
            .filter(SolariumSession.fine.isnot(None),
                    SolariumSession.receipt_id.is_(None),
                    SolariumSession.fine <= cutoff)
            .order_by(SolariumSession.fine.desc())
            .limit(100)
            .all())


def list_candidate_receipts_for_session(session, window_hours=CANDIDATE_WINDOW_HOURS):
    """Scontrini Solarium con capacita' residua in una finestra ampia
    attorno alla seduta, ordinati per vicinanza (per la scelta manuale)."""
    from appl.models import Receipt

    inizio = to_naive_local(session.inizio)
    fine = to_naive_local(session.fine) or inizio
    window_start = min(inizio, fine) - timedelta(hours=window_hours)
    window_end = max(inizio, fine) + timedelta(hours=window_hours)

    receipts = (Receipt.query
                .filter(Receipt.created_at >= window_start,
                        Receipt.created_at <= window_end)
                .order_by(Receipt.created_at.asc())
                .all())

    candidates = []
    for r in receipts:
        if _capacity(r) == 0:
            continue
        if _used_slots(r.id) >= _capacity(r):
            continue
        eff = _effective_distance(session, r.created_at)
        candidates.append((eff, r))
    candidates.sort(key=lambda t: t[0])
    return [{'receipt': r, 'distanza_minuti': round(eff / 60, 1)} for eff, r in candidates]


def manual_link(session_id, receipt_id):
    """Collega manualmente una seduta a uno scontrino (strumento di
    riconciliazione). Ritorna (ok, errore)."""
    from appl import db
    from appl.models import SolariumSession, Receipt

    session = db.session.get(SolariumSession, session_id)
    receipt = db.session.get(Receipt, receipt_id)
    if not session or not receipt:
        return False, "Seduta o scontrino non trovato."
    if _capacity(receipt) == 0:
        return False, "Lo scontrino selezionato non contiene voci Solarium."
    if session.receipt_id == receipt.id:
        return True, None
    if _used_slots(receipt.id) >= _capacity(receipt):
        return False, "Lo scontrino selezionato ha gia' tutte le sedute collegate."

    session.receipt_id = receipt.id
    session.client_id = receipt.cliente_id
    session.appointment_id = _pick_appointment_id(receipt)
    db.session.commit()
    return True, None


def manual_unlink(session_id):
    """Rimuove il collegamento di una seduta (per correggere un abbinamento
    sbagliato)."""
    from appl import db
    from appl.models import SolariumSession

    session = db.session.get(SolariumSession, session_id)
    if not session:
        return False, "Seduta non trovata."
    session.receipt_id = None
    session.client_id = None
    session.appointment_id = None
    db.session.commit()
    return True, None
