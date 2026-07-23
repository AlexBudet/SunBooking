"""
Bridge Phidget 8/8/8 <-> Solarium: ascolta in tempo reale i canali digitali
collegati ai macchinari solarium (lampade) configurati in Impostazioni e
registra inizio/fine seduta su SolariumSession. Circuito chiuso = seduta
avviata, circuito riaperto = seduta conclusa (stessa logica del vecchio
programma FastAPI/Phidget22 di riferimento).

Va avviato una sola volta, in background, dall'app locale (start.py): non ha
senso lato cloud, dove non c'e' hardware collegato. Fail-open: qualunque
problema (libreria assente, hardware non collegato, canale occupato da
un'altra app) viene loggato e il resto dell'applicazione continua a
funzionare normalmente, semplicemente senza monitoraggio lampade.
"""
import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger('SunBooking')

_lock = threading.Lock()
_started = False
_channels = []  # canali DigitalInput aperti con successo (per get_status())


def start_solarium_bridge(app):
    """Legge i macchinari configurati (con canale Phidget assegnato) e apre
    una connessione persistente per ciascuno. Idempotente: le chiamate
    successive alla prima non fanno nulla."""
    global _started
    with _lock:
        if _started:
            return
        _started = True

    try:
        from appl.models import OWNER, SolariumDevice
        with app.app_context():
            owner_cfg = OWNER.query.first()
            if not owner_cfg or not owner_cfg.module_solarium_enabled:
                logger.info("Solarium: modulo non abilitato, bridge Phidget non avviato.")
                return
            devices = (SolariumDevice.query
                       .filter(SolariumDevice.is_deleted == False,
                               SolariumDevice.phidget_channel.isnot(None))
                       .all())
            device_map = {d.phidget_channel: d.id for d in devices}
    except Exception as e:
        logger.error("Solarium: impossibile leggere la configurazione macchinari: %s", e)
        return

    if not device_map:
        logger.info("Solarium: nessun macchinario con canale Phidget assegnato, bridge non avviato.")
        return

    try:
        from Phidget22.Devices.DigitalInput import DigitalInput
    except Exception as e:
        logger.error("Solarium: libreria Phidget22 non disponibile, bridge non avviato: %s", e)
        return

    for channel_num, device_id in device_map.items():
        try:
            # Ordine identico al programma di riferimento: apri prima il
            # canale, leggi lo stato iniziale, e SOLO DOPO registra l'handler
            # dei cambi di stato (in quell'ordine funziona in modo affidabile
            # anche per la transizione a spento).
            ch = DigitalInput()
            ch.setChannel(channel_num)
            ch.openWaitForAttachment(5000)
            initial_state = ch.getState()
            _on_state_change(app, device_id, channel_num, initial_state)
            ch.setOnStateChangeHandler(_make_handler(app, device_id, channel_num))
            _channels.append((ch, device_id, channel_num))
            logger.info("Solarium: canale %s collegato (device_id=%s, stato iniziale=%s).",
                        channel_num, device_id, initial_state)
        except Exception as e:
            logger.error("Solarium: impossibile collegare il canale %s (device_id=%s): %s",
                         channel_num, device_id, e)

    if _channels:
        threading.Thread(target=_reconcile_loop, args=(app,), daemon=True).start()


def _reconcile_loop(app):
    """Rete di sicurezza: ogni 5s rilegge lo stato reale di ogni canale e
    riallinea il DB. Serve se un evento di cambio stato non scatta o si perde
    (es. spegnimento non rilevato): senza questo, una seduta resterebbe
    "aperta" all'infinito e la lampada continuerebbe a risultare accesa."""
    import time
    while True:
        time.sleep(5)
        for ch, device_id, channel_num in _channels:
            try:
                if ch.getAttached():
                    _on_state_change(app, device_id, channel_num, ch.getState())
            except Exception as e:
                logger.debug("Solarium: reconcile canale %s fallito: %s", channel_num, e)


def get_status():
    """Ritorna True/False se il bridge e' attivo e almeno un canale e'
    collegato, oppure None se il bridge non e' mai partito (nessun
    macchinario configurato con canale, o modulo disabilitato) - in quel
    caso il chiamante puo' ripiegare su un test di connessione una tantum."""
    if not _channels:
        return None
    for ch, _device_id, _channel_num in _channels:
        try:
            if ch.getAttached():
                return True
        except Exception:
            pass
    return False


def _make_handler(app, device_id, channel_num):
    def handler(self, state):
        _on_state_change(app, device_id, channel_num, state)
    return handler


def _on_state_change(app, device_id, channel_num, state):
    from appl import db
    from appl.models import SolariumSession

    now = datetime.now(timezone.utc)
    try:
        with app.app_context():
            aperta = (SolariumSession.query
                      .filter_by(device_id=device_id, fine=None)
                      .order_by(SolariumSession.inizio.desc())
                      .first())
            if state:
                # Circuito chiuso: seduta avviata (se non gia' in corso).
                if not aperta:
                    db.session.add(SolariumSession(device_id=device_id, inizio=now))
                    db.session.commit()
                    logger.info("Solarium: seduta avviata (device_id=%s, canale=%s)", device_id, channel_num)
            else:
                # Circuito riaperto: seduta conclusa.
                if aperta:
                    inizio = aperta.inizio
                    if inizio.tzinfo is None:
                        inizio = inizio.replace(tzinfo=timezone.utc)
                    aperta.fine = now
                    aperta.durata_secondi = int((now - inizio).total_seconds())
                    db.session.commit()
                    logger.info("Solarium: seduta conclusa (device_id=%s, durata=%ss)",
                                device_id, aperta.durata_secondi)
    except Exception as e:
        logger.error("Solarium: errore aggiornamento sessione (device_id=%s): %s", device_id, e)
