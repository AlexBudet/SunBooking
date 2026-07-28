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

    La chiave 'categoria' nelle voci NON e' affidabile e nel percorso di
    stampa reale (cassa.js, serializzazione riga->voce al click "Stampa",
    circa righe 835-845) non e' MAI presente: la voce che finisce davvero
    in Receipt.voci ha 'servizio_id' (non 'id' - quella e' solo la chiave
    usata dal precaricamento server-side della pagina, che e' un payload
    diverso, non quello effettivamente stampato). Qui si risale alla vera
    categoria tramite 'servizio_id' -> Service.servizio_categoria, senza
    toccare cassa.py/cassa.js. Tenuto anche 'id' come fallback residuo per
    eventuali altri percorsi che lo usassero."""
    if not isinstance(v, dict):
        return False
    if v.get('categoria') == 'Solarium':
        return True
    if v.get('categoria'):
        return False  # categoria presente ma diversa: non e' Solarium
    service_id = v.get('servizio_id') or v.get('id')
    if not service_id:
        return False
    from appl.models import Service, ServiceCategory
    try:
        service_id = int(service_id)
    except (TypeError, ValueError):
        return False
    servizio = Service.query.get(service_id)
    return bool(servizio and servizio.servizio_categoria == ServiceCategory.Solarium)


def solarium_voci(receipt):
    voci = receipt.voci or []
    return [v for v in voci if _is_solarium_voce(v)]


def _voce_service_id(v):
    """Service.id della voce di scontrino, o None se non ricavabile."""
    raw = v.get('servizio_id') or v.get('id')
    if not raw:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def device_service_id(session):
    """Service di cassa associato al macchinario della seduta.

    E' il perno dell'abbinamento: senza questo, una seduta si legherebbe al
    pagamento piu' vicino nel tempo QUALUNQUE esso sia, incrociando lampade
    diverse (un Prestige pagato mentre parte la ESA finiva sulla ESA). La
    colonna SolariumDevice.service_id esiste in schema proprio per questo
    ("Collegamento al servizio di cassa per la correlazione automatica
    scontrino/seduta", models.py) e va configurata in Impostazioni >
    Solarium per ogni macchinario."""
    from appl import db
    from appl.models import SolariumDevice
    device = session.device
    if device is None and session.device_id:
        device = db.session.get(SolariumDevice, session.device_id)
    return device.service_id if device else None


def _voci_for_service(receipt, service_id):
    """Voci dello scontrino relative ESATTAMENTE al servizio del macchinario."""
    if not service_id:
        return []
    return [v for v in (receipt.voci or [])
            if isinstance(v, dict) and _voce_service_id(v) == service_id]


def _capacity(receipt, service_id):
    """Quante sedute DI QUEL MACCHINARIO puo' coprire questo scontrino: una
    per ogni voce di quel servizio (due Prestige sullo stesso scontrino
    coprono due sedute di Prestige, non una seduta di Prestige e una ESA)."""
    return len(_voci_for_service(receipt, service_id))


def _used_slots(receipt_id, service_id):
    """Sedute gia' collegate a questo scontrino PER QUEL SERVIZIO (le sedute
    di altri macchinari sullo stesso scontrino non consumano questi slot)."""
    from appl.models import SolariumSession, SolariumDevice
    return (SolariumSession.query
            .join(SolariumDevice, SolariumSession.device_id == SolariumDevice.id)
            .filter(SolariumSession.receipt_id == receipt_id,
                    SolariumDevice.service_id == service_id)
            .count())


def session_payment_status(session):
    """'collegato' = pagamento abbinato; 'appuntamento' = cliente identificato
    dall'appuntamento di calendario ma pagamento non ancora abbinato;
    'in_sospeso' = passati piu' di MANUAL_REVIEW_AFTER_MIN minuti dalla fine
    senza alcun abbinamento; 'in_attesa' = tempo per l'abbinamento automatico
    non ancora scaduto; None = seduta ancora in corso."""
    if session.receipt_id:
        return 'collegato'
    if session.appointment_id:
        return 'appuntamento'
    if session.fine is None:
        return None
    fine = session.fine
    if fine.tzinfo is None:
        fine = fine.replace(tzinfo=timezone.utc)
    minuti_da_fine = (datetime.now(timezone.utc) - fine).total_seconds() / 60
    return 'in_sospeso' if minuti_da_fine >= MANUAL_REVIEW_AFTER_MIN else 'in_attesa'


def _pick_appointment_id(receipt, service_id):
    """Sceglie, tra le voci dello scontrino RELATIVE A QUEL SERVIZIO, un
    appointment_id non ancora assegnato a un'altra seduta collegata allo
    stesso scontrino (scontrini con piu' sedute dello stesso macchinario,
    es. due Prestige per due persone). Se le voci non hanno appointment_id
    (pagamento senza prenotazione), torna None senza bloccare il
    collegamento seduta<->scontrino."""
    from appl.models import SolariumSession
    used = {s.appointment_id for s in
            SolariumSession.query.filter_by(receipt_id=receipt.id).all()
            if s.appointment_id}
    for v in _voci_for_service(receipt, service_id):
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
    """Miglior scontrino per questa seduta: DEVE contenere una voce del
    servizio associato a quel macchinario, ed essere entro la tolleranza.

    Il vincolo sul servizio non e' negoziabile: la sola vicinanza temporale
    incrocia macchinari diversi (piu' lampade partono/finiscono a pochi
    minuti l'una dall'altra). Se il macchinario non ha un servizio
    configurato, NON si abbina nulla: meglio una seduta in sospeso, da
    sistemare a mano, che un'associazione sbagliata."""
    from appl.models import Receipt

    service_id = device_service_id(session)
    if not service_id:
        logger.warning(
            "Solarium: macchinario id=%s senza servizio di cassa associato: "
            "abbinamento automatico non possibile (configuralo in "
            "Impostazioni > Solarium).", session.device_id)
        return None

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
        capacity = _capacity(r, service_id)
        if capacity == 0:
            continue  # nessuna voce di QUESTO servizio: non e' questa lampada
        if _used_slots(r.id, service_id) >= capacity:
            continue
        eff = _effective_distance(session, r.created_at)
        if eff > tolerance_sec:
            continue
        key = (eff, _preferred_distance(session, r.created_at, criterio))
        if best_key is None or key < best_key:
            best_key, best = key, r
    return best


def find_best_appointment(session, tolerance_minutes=AUTO_MATCH_TOLERANCE_MIN):
    """Miglior APPUNTAMENTO di calendario per questa seduta.

    Serve perche' il pagamento non e' l'unica traccia di chi ha fatto la
    seduta: l'appuntamento puo' esistere senza scontrino (non ancora
    pagato, pagato dopo, oppure seduta scalata da un pacchetto gia' saldato,
    che non genera alcun nuovo scontrino). Vale lo stesso vincolo degli
    scontrini: il servizio dell'appuntamento deve essere quello del
    macchinario, altrimenti si incrociano lampade diverse."""
    from appl.models import Appointment, SolariumSession

    service_id = device_service_id(session)
    if not service_id:
        return None

    inizio = to_naive_local(session.inizio)
    fine = to_naive_local(session.fine) or inizio
    window_start = min(inizio, fine) - timedelta(minutes=tolerance_minutes)
    window_end = max(inizio, fine) + timedelta(minutes=tolerance_minutes)
    tolerance_sec = tolerance_minutes * 60

    appuntamenti = (Appointment.query
                    .filter(Appointment.service_id == service_id,
                            Appointment.is_cancelled_by_client == False,
                            Appointment.start_time >= window_start - timedelta(hours=3),
                            Appointment.start_time <= window_end)
                    .all())

    # Un appuntamento non puo' coprire due sedute diverse.
    gia_usati = {s.appointment_id for s in
                 SolariumSession.query.filter(SolariumSession.appointment_id.isnot(None)).all()
                 if s.id != session.id}

    best = None
    best_dist = None
    for a in appuntamenti:
        if a.id in gia_usati:
            continue
        dist = _appointment_distance(session, a)
        if dist > tolerance_sec:
            continue
        if best_dist is None or dist < best_dist:
            best_dist, best = dist, a
    return best


def _naive_appointment_time(dt):
    """Appointment.start_time/end_time sono naive-locale per convenzione
    (colonna DateTime SENZA timezone, a differenza di SolariumSession che e'
    esplicitamente UTC-aware) - NON vanno convertiti con to_naive_local()
    (quello presume una sorgente UTC). Qui e' solo una difesa: se per
    disallineamento fra colonna e driver arriva comunque un tzinfo (visto in
    log: 'can't subtract offset-naive and offset-aware datetimes'), si toglie
    SENZA spostare l'orario, perche' le cifre sono gia' quelle giuste in
    locale."""
    if dt is not None and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


def _appointment_distance(session, appointment):
    """Distanza minima (secondi) tra gli estremi dell'appuntamento e quelli
    della seduta: un appuntamento delle 11:45 e una seduta partita alle
    11:46 distano 60 secondi."""
    inizio = to_naive_local(session.inizio)
    fine = to_naive_local(session.fine) or inizio
    punti_appuntamento = [_naive_appointment_time(appointment.start_time)]
    try:
        punti_appuntamento.append(_naive_appointment_time(appointment.end_time))
    except Exception:
        pass
    return min(abs((pa - ps).total_seconds())
               for pa in punti_appuntamento
               for ps in (inizio, fine))


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
                s.appointment_id = _pick_appointment_id(receipt, device_service_id(s))
                db.session.commit()
                logger.info("Solarium: seduta %s (device %s) collegata allo scontrino %s (cliente_id=%s, appointment_id=%s)",
                            s.id, s.device_id, receipt.id, receipt.cliente_id, s.appointment_id)
                continue

            # Nessuno scontrino: l'appuntamento di calendario e' comunque una
            # traccia valida di chi ha fatto la seduta (non ancora pagata,
            # pagata piu' tardi, o scalata da un pacchetto gia' saldato che
            # non genera scontrini). Collega cliente e appuntamento; il
            # pagamento potra' arrivare dopo e restera' da abbinare.
            if s.appointment_id:
                continue  # gia' identificata: si continua solo a cercarne il pagamento
            appuntamento = find_best_appointment(s)
            if appuntamento:
                s.appointment_id = appuntamento.id
                s.client_id = appuntamento.client_id
                db.session.commit()
                logger.info("Solarium: seduta %s (device %s) collegata all'appuntamento %s (cliente_id=%s, nessuno scontrino)",
                            s.id, s.device_id, appuntamento.id, appuntamento.client_id)
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
    """Scontrini candidati per la scelta manuale: SOLO quelli che contengono
    una voce del servizio di quel macchinario (stesso vincolo dell'automatico
    - proporre scontrini di altre lampade porterebbe a rifare a mano lo
    stesso errore), con capacita' residua, ordinati per vicinanza."""
    from appl.models import Receipt

    service_id = device_service_id(session)
    if not service_id:
        return []

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
        capacity = _capacity(r, service_id)
        if capacity == 0:
            continue
        if _used_slots(r.id, service_id) >= capacity:
            continue
        eff = _effective_distance(session, r.created_at)
        candidates.append((eff, r))
    candidates.sort(key=lambda t: t[0])
    return [{'receipt': r, 'distanza_minuti': round(eff / 60, 1)} for eff, r in candidates]


def list_candidate_appointments_for_session(session, window_hours=CANDIDATE_WINDOW_HOURS):
    """Appuntamenti di calendario candidati per la scelta manuale: stesso
    servizio del macchinario, non annullati, non gia' assegnati a un'altra
    seduta. Vanno proposti accanto agli scontrini perche' spesso l'unica
    traccia del cliente e' l'appuntamento (pagamento non ancora fatto o
    seduta scalata da pacchetto)."""
    from appl.models import Appointment, SolariumSession

    service_id = device_service_id(session)
    if not service_id:
        return []

    inizio = to_naive_local(session.inizio)
    fine = to_naive_local(session.fine) or inizio
    window_start = min(inizio, fine) - timedelta(hours=window_hours)
    window_end = max(inizio, fine) + timedelta(hours=window_hours)

    appuntamenti = (Appointment.query
                    .filter(Appointment.service_id == service_id,
                            Appointment.is_cancelled_by_client == False,
                            Appointment.start_time >= window_start,
                            Appointment.start_time <= window_end)
                    .order_by(Appointment.start_time.asc())
                    .all())

    gia_usati = {s.appointment_id for s in
                 SolariumSession.query.filter(SolariumSession.appointment_id.isnot(None)).all()
                 if s.id != session.id}

    candidates = []
    for a in appuntamenti:
        if a.id in gia_usati:
            continue
        candidates.append((_appointment_distance(session, a), a))
    candidates.sort(key=lambda t: t[0])
    return [{'appointment': a, 'distanza_minuti': round(d / 60, 1)} for d, a in candidates]


def manual_link_appointment(session_id, appointment_id):
    """Collega manualmente una seduta a un appuntamento di calendario
    (cliente identificato, pagamento eventualmente ancora da abbinare)."""
    from appl import db
    from appl.models import SolariumSession, Appointment

    session = db.session.get(SolariumSession, session_id)
    appuntamento = db.session.get(Appointment, appointment_id)
    if not session or not appuntamento:
        return False, "Seduta o appuntamento non trovato."

    service_id = device_service_id(session)
    if service_id and appuntamento.service_id != service_id:
        return False, "L'appuntamento non e' del servizio di questo macchinario."

    altra = (SolariumSession.query
             .filter(SolariumSession.appointment_id == appuntamento.id,
                     SolariumSession.id != session.id)
             .first())
    if altra:
        return False, "Questo appuntamento e' gia' collegato a un'altra seduta."

    session.appointment_id = appuntamento.id
    session.client_id = appuntamento.client_id
    db.session.commit()
    return True, None


def manual_link(session_id, receipt_id):
    """Collega manualmente una seduta a uno scontrino (strumento di
    riconciliazione). Ritorna (ok, errore)."""
    from appl import db
    from appl.models import SolariumSession, Receipt

    session = db.session.get(SolariumSession, session_id)
    receipt = db.session.get(Receipt, receipt_id)
    if not session or not receipt:
        return False, "Seduta o scontrino non trovato."

    service_id = device_service_id(session)
    if not service_id:
        return False, ("Il macchinario di questa seduta non ha un servizio di cassa "
                       "associato: impostalo in Impostazioni > Solarium.")
    capacity = _capacity(receipt, service_id)
    if capacity == 0:
        return False, "Lo scontrino selezionato non contiene il servizio di questo macchinario."
    if session.receipt_id == receipt.id:
        return True, None
    if _used_slots(receipt.id, service_id) >= capacity:
        return False, "Lo scontrino selezionato ha gia' tutte le sedute collegate per questo macchinario."

    session.receipt_id = receipt.id
    session.client_id = receipt.cliente_id
    session.appointment_id = _pick_appointment_id(receipt, service_id)
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
