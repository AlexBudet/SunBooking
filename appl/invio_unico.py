# appl/invio_unico.py
"""Un modulo inviato piu' volte deve creare UNA riga sola.

Nel browser il pulsante si blocca gia' al primo clic (base.html,
form[data-invio-unico]; la pagina servizi lo fa nel suo fetch). Questo e' il
controllo lato server per quando il browser non basta: doppio clic prima che
lo script giri, Invio ripetuto, pagina lenta che fa ricliccare. Il 03/11/2026
un servizio e' stato creato tre volte cosi' (Sun City, id 106-107-108).

Ogni modulo porta un campo nascosto `invio_id`, un uuid nuovo a ogni apertura
della pagina. La prima richiesta con quell'id lo prenota; le altre, anche se
arrivano mentre la prima sta ancora scrivendo nel database, lo trovano preso e
non creano niente. Se la prima non va a buon fine l'id si libera, cosi'
correggere e reinviare dallo stesso modulo funziona.

Sta in memoria del processo: basta perche' la web app gira su un'istanza sola
(e non va mai alzata) e l'exe e' un processo solo. wsgi.py monta tutti i
negozi nello stesso processo, ma gli id sono uuid: non si scontrano. Un
riavvio svuota l'elenco, e va bene: la pagina si riapre con un id nuovo.
"""
import threading
import time
import uuid

_DURATA_SECONDI = 15 * 60
_lock = threading.Lock()
_presi = {}  # invio_id -> istante (monotonic) in cui scade


def nuovo_id():
    """Id da mettere nel campo nascosto `invio_id` del modulo."""
    return uuid.uuid4().hex


def prenota(invio_id):
    """True se e' il primo invio con questo id (e da ora risulta preso),
    False se e' un doppione da scartare.

    Senza id passa sempre: una pagina aperta prima dell'aggiornamento non ha
    il campo, e non deve smettere di funzionare.
    """
    invio_id = (invio_id or '').strip()[:64]
    if not invio_id:
        return True
    adesso = time.monotonic()
    with _lock:
        for scaduto in [k for k, scade in _presi.items() if scade < adesso]:
            del _presi[scaduto]
        if invio_id in _presi:
            return False
        _presi[invio_id] = adesso + _DURATA_SECONDI
        return True


def libera(invio_id):
    """Rende di nuovo valido l'id: da chiamare quando l'invio NON ha creato
    niente (dati mancanti, errore), cosi' il reinvio dallo stesso modulo passa."""
    invio_id = (invio_id or '').strip()[:64]
    if invio_id:
        with _lock:
            _presi.pop(invio_id, None)
