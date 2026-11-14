from decimal import Decimal
import json
import os
import tempfile
import html, re, time as pytime
from xml.sax.saxutils import escape as _xml_escape
from flask import Blueprint, app, render_template, jsonify, request, session, abort, current_app
from appl.models import Appointment, AppointmentStatus, BusinessInfo, Operator, PrinterModel, Service, ServiceCategory, Client, Receipt, Subcategory, User, Pacchetto, PacchettoRata, PacchettoStatus, db
from appl.services.error_log import log_crm_error
from appl.services import promo as promo_mod
from appl.formati import nome_proprio
from datetime import datetime, date, timedelta
import requests
import urllib3
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import selectinload
from collections import defaultdict
from sqlalchemy.orm.attributes import flag_modified

# Disabilita warning SSL per certificati self-signed RCH Print 3.0 RT
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _rch_url(ip: str, model: str = None) -> str:
    """Costruisce URL per la stampante RCH in base al modello.
    - RCH Print 3.0 RT: HTTPS + /service.cgi
    - RCH Print F: HTTP + /service.cgi
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return f"http://{ip}/service.cgi"
    return f"https://{ip}/service.cgi"

def _rch_headers(model: str = None) -> dict:
    """Header HTTP per la stampante RCH in base al modello.
    - RCH Print 3.0 RT: application/xml + Accept obbligatorio (da specifica)
    - RCH Print F: text/xml; charset=UTF-8
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {"Content-Type": "text/xml; charset=UTF-8"}
    return {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache"
    }

def _rch_verify_ssl(model: str = None):
    """Parametro verify per requests.
    - RCH Print 3.0 RT: False (HTTPS self-signed, disabilita verifica)
    - RCH Print F: None (HTTP, parametro non necessario)
    Ritorna False per RT, None per Print F.
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return None
    return False

def _rch_chiusura_headers(model: str = None) -> dict:
    """Header speciali per la chiusura giornaliera.
    - RCH Print F: application/x-www-form-urlencoded (storicamente funzionante)
    - RCH Print 3.0 RT: application/xml (come per gli altri comandi)
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {"Content-Type": "application/x-www-form-urlencoded"}
    return {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache"
    }

def _rch_dgfe_headers(model: str = None) -> dict:
    """Header per lettura DGFE.
    - RCH Print F: text/xml; charset=iso-8859-1
    - RCH Print 3.0 RT: application/xml
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {'Content-Type': 'text/xml; charset=iso-8859-1'}
    return {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "Connection": "close",
        "Cache-Control": "no-cache"
    }

def _rch_request_kwargs(model: str = None) -> dict:
    """Keyword arguments extra per _rch_post() in base al modello.
    - RCH Print 3.0 RT: verify=False (HTTPS self-signed)
    - RCH Print F: niente (HTTP puro, nessun verify necessario)
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {}
    return {"verify": False}

def _normalize_model(model_raw) -> str:
    """Normalizza il valore printer_model a stringa canonica."""
    if model_raw is None:
        return PrinterModel.RCH_PRINT_RT.value
    if hasattr(model_raw, 'value'):
        model_raw = model_raw.value
    s = str(model_raw).strip().lower()
    if s in ('rch_print_f', 'printermodel.rch_print_f', 'print_f', 'print f'):
        return PrinterModel.RCH_PRINT_F.value
    return PrinterModel.RCH_PRINT_RT.value

def _tender_code(metodo, model=None) -> str:
    """Mappa il metodo di pagamento del CRM al comando di pagamento RCH (=T<n>).

    La tabella delle forme di pagamento differisce per modello:
    - RCH Print 3.0 RT (tabella standard di fabbrica, vedi manuale sez. 9):
        T1 contanti, T2 non riscosso, T3 assegni, T4 elettronico, T5 ticket
      => carta/POS e bonifico sono entrambi 'elettronico' (T4).
    - RCH Print F: tabella storica programmata con T2=bonifico, T3=POS.

    NB: 'bank'->T2 sulla RT 3.0 colpisce 'non riscosso' e genera errorCode 45;
    'pos'->T3 colpisce 'assegni' (non da' errore ma e' fiscalmente errato).
    """
    model = _normalize_model(model)
    metodo = (metodo or "cash").lower()
    if model == PrinterModel.RCH_PRINT_F.value:
        return {"cash": "T1", "contanti": "T1", "bank": "T2", "pos": "T3"}.get(metodo, "T1")
    # RCH Print 3.0 RT: carta/POS e bonifico sono entrambi 'elettronico' (T4)
    return {"cash": "T1", "contanti": "T1", "bank": "T4", "pos": "T4"}.get(metodo, "T1")

def _get_printer_config():
    """Ritorna (ip, model) dalla BusinessInfo corrente.
    Usa expire_all + query fresca per garantire lettura dal DB reale,
    mai dalla identity map cached di SQLAlchemy.
    """
    db.session.expire_all()
    row = db.session.execute(
        text("SELECT id, printer_ip, printer_model FROM business_info WHERE is_deleted = false ORDER BY id ASC LIMIT 1")
    ).fetchone()
    if not row:
        return None, None
    ip = (row[1] or '').strip()
    if not ip:
        return None, None
    model = _normalize_model(row[2])
    current_app.logger.debug(
        "_get_printer_config: id=%s, ip=%s, raw_model=%r, model=%s",
        row[0], ip, row[2], model
    )
    return ip, model

def _rch_parse_errcode(body: str):
    """Estrae codice errore dalla risposta RCH.
    Supporta sia <errCode> (da specifica) che <errorCode> (variante firmware).
    """
    if not body:
        return None
    m = re.search(r'<(?:errCode|errorCode)>(\d+)</(?:errCode|errorCode)>', body)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None

def _rch_is_success(resp):
    """Verifica se la risposta RCH indica successo (errCode/errorCode == 0)."""
    if resp is None:
        return False
    body = getattr(resp, 'text', '') or ''
    code = _rch_parse_errcode(body)
    if code is not None:
        return code == 0
    # Nessun codice trovato: HTTP 200 = OK presumibile
    return getattr(resp, 'status_code', 0) == 200

def _read_progressivo(url, headers, rch_kwargs, max_attempts=8, sleep_s=0.5):
    """Polla =C453/$0 (e fallback =DGFE/REG) per leggere lastDocF/lastZ.
    Ritorna (numero_progressivo, numero_z) oppure (None, None) se non leggibile.
    numero_z e' gia' incrementato di 1 (come fa il flusso esistente)."""
    for cmd in ("=C453/$0", "=DGFE/REG"):
        payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
        for _ in range(max_attempts):
            pytime.sleep(sleep_s)
            try:
                resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers,
                                     timeout=6, **rch_kwargs)
            except Exception:
                continue
            body = resp.text or ""
            m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', body) or
                     re.search(r'<C453[^>]*>(\d+)</C453>', body) or
                     re.search(r'<result>(\d+)</result>', body))
            m_z = re.search(r'<lastZ>(\d+)</lastZ>', body)
            if m_doc and m_z:
                try:
                    return int(m_doc.group(1)), int(m_z.group(1)) + 1
                except Exception:
                    pass
    return None, None


# =========================================================================
# SCONTRINO EMESSO = CONTATORE AVANZATO DI UNO. Nient'altro.
# =========================================================================
# errorCode 0 dice solo che la stampante ha ACCETTATO i comandi, non che il
# documento sia uscito. Misurato su sunexp3 e suncity (09/11/2026): 25
# scontrini registrati con numero documento 0000 (RCH bloccata che risponde
# "Z 0, Doc 0", oppure contatore fermo a 0 dopo la Z), e in TUTTI i 12 giorni
# con lettura DGFE il DGFE ha un documento in meno del registro, per lo stesso
# identico importo. Erano scontrini mai emessi, registrati come fiscali e poi
# non stornabili (il reso su un documento che non esiste viene rifiutato).
#
# Regola unica, uguale per RCH Print 3.0 RT e Print F: si legge il contatore
# (=C453/$0) PRIMA di mandare lo scontrino e lo si rilegge DOPO. Si registra
# solo se e' rimasta la stessa Z e lastDocF e' salito esattamente di uno.
# Ogni altro esito non scrive niente: lo scontrino resta "da verificare" e si
# decide con una nuova lettura del contatore, mai indovinando dagli importi.

import threading as _threading
from contextlib import contextmanager as _contextmanager
import functools as _functools

_RCH_LOCK = _threading.Lock()   # una sola registrazione per volta

# ---------------------------------------------------------------------------
# TEMPI. La stampante sta nella rete del negozio: risponde in decimi di
# secondo oppure non risponde affatto. Prima si aspettavano 120 s la risposta
# allo scontrino: sono i blocchi da 2 minuti misurati in usage_traffic_hourly
# (8 volte dal 28/08 all'11/11/2026), col cliente davanti al banco. Entro
# ~10 s l'operatrice deve sapere cosa e' successo e poter ristampare.
# ---------------------------------------------------------------------------
RCH_CONNESSIONE_S = 2.5          # se non accetta la connessione in 2,5 s non e' raggiungibile
RCH_LETTURA_S = 3.0              # risposta a una lettura di stato (=C453)
RCH_RISPOSTA_SCONTRINO_S = 7.0   # risposta allo scontrino: oltre, decide il contatore
RCH_CONFERMA_S = 3.0             # quanto si aspetta che il contatore salga dopo un "ok"
RCH_ATTESA_LIBERA_S = 3.0        # quanto aspetta una richiesta se la stampante e' impegnata
# Mai dire "non uscito" (e offrire la Ristampa) prima di tanti secondi
# dall'invio. Il manuale dice "no queue": se la RCH risponde alla lettura del
# contatore ha finito tutto quello che aveva ricevuto; questo margine copre
# solo una stampa ancora in corso. Uno scontrino normale e' confermato in <7 s.
RCH_MIN_PRIMA_DI_RISTAMPA_S = 10.0

# ---------------------------------------------------------------------------
# UNA CONVERSAZIONE ALLA VOLTA. Manuale RCH (COMANDI RCH PRINT RT 3-0.txt,
# sez. 31): "no multithreading, no queue, no comandi paralleli". Waitress
# serve piu' richieste insieme: senza lucchetto, chi ricarica la pagina e
# ristampa mentre la prima richiesta aspetta ancora la stampante apre una
# seconda conversazione in parallelo. Ogni chiamata alla RCH passa da
# _rch_post (che prende il lucchetto); le sequenze di piu' comandi lo tengono
# per tutta la durata (_rch_in_uso, _rch_esclusivo). RLock: la stessa
# richiesta lo riprende senza bloccarsi.
# ---------------------------------------------------------------------------
_RCH_BUS = _threading.RLock()


class RchOccupata(Exception):
    """La stampante e' impegnata da un'altra richiesta oltre il tempo di attesa."""


MSG_RCH_OCCUPATA = ("La stampante sta finendo un'altra operazione (uno scontrino, una "
                    "verifica o la chiusura). Riprova tra qualche secondo.")


@_contextmanager
def _rch_in_uso(attesa_s=RCH_ATTESA_LIBERA_S):
    if not _RCH_BUS.acquire(timeout=attesa_s):
        raise RchOccupata()
    try:
        yield
    finally:
        _RCH_BUS.release()


def _rch_post(url, **kwargs):
    """requests.post verso la stampante, una richiesta alla volta."""
    with _rch_in_uso():
        return requests.post(url, **kwargs)


def _rch_esclusivo(f):
    """Rotta che parla con la stampante: la tiene per tutta la sequenza di
    comandi. Se e' impegnata oltre RCH_ATTESA_LIBERA_S, RchOccupata -> 409
    (errorhandler del blueprint)."""
    @_functools.wraps(f)
    def wrapper(*args, **kwargs):
        with _rch_in_uso():
            return f(*args, **kwargs)
    return wrapper


def _rch_contatori(url, headers, rch_kwargs, timeout=(RCH_CONNESSIONE_S, RCH_LETTURA_S)):
    """Una lettura di stato (=C453/$0). Ritorna un dict con z (lastZ), doc
    (lastDocF), i segnali della meccanica e la risposta grezza, oppure None se
    la stampante non risponde o la risposta non contiene i contatori.
    Non solleva mai, salvo RchOccupata (stampante impegnata da altri)."""
    payload = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C453/$0</cmd></Service>'
    try:
        resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers,
                         timeout=timeout, **rch_kwargs)
    except RchOccupata:
        raise
    except Exception:
        return None
    return _rch_parse_contatori(resp.text or "")


def _rch_parse_contatori(body):
    """Contatori e segnali della meccanica da una risposta RCH qualsiasi
    (ogni risposta porta lo stesso blocco <Request>). None se mancano."""
    body = body or ""

    def _int(tag):
        m = re.search(rf'<{tag}>(\d+)</{tag}>', body)
        return int(m.group(1)) if m else None

    z, doc = _int('lastZ'), _int('lastDocF')
    if z is None or doc is None:
        return None
    return {
        "z": z,
        "doc": doc,
        "carta_finita": _int('paperEnd') == 1,
        "coperchio_aperto": _int('coverOpen') == 1,
        "errore_meccanico": _int('printerError') == 1,
        "occupata": _int('busy') == 1,
        "error_code": _rch_parse_errcode(body),
        "raw": body[:500],
    }


def _rch_leggi_contatori(url, headers, rch_kwargs, tentativi=2, pausa_s=0.3):
    """Come _rch_contatori, con un secondo tentativo: una stampante appena
    svegliata puo' non rispondere alla prima richiesta. Al peggio ~6 s."""
    for i in range(tentativi):
        c = _rch_contatori(url, headers, rch_kwargs)
        if c is not None:
            return c
        if i < tentativi - 1:
            pytime.sleep(pausa_s)
    return None


def _rch_contatori_bloccati(c):
    """Z 0 e documento 0 insieme: è la risposta della RCH bloccata (misurata a
    Biella il 10/10/2026 e il 09/11/2026), anche se dice errorCode 0. Una
    stampante nuova, prima della sua prima Z, risponde allo stesso modo: per
    questo non si usa per bloccare l'invio, solo per non dichiarare la
    stampante pronta."""
    return c is not None and c["z"] == 0 and c["doc"] == 0


def _rch_bloccata_prima_dell_invio(c):
    """Contatori a zero su una stampante che ha gia' una storia nel registro
    (almeno uno scontrino oltre la prima Z): non e' una stampante nuova, e'
    la RCH bloccata. Non le si manda niente: dopo il riavvio la numerazione
    torna quella vera e non ci sarebbe un termine di paragone per dire se lo
    scontrino e' uscito."""
    if not _rch_contatori_bloccati(c):
        return False
    try:
        storico = Receipt.query.filter(
            Receipt.is_fiscale == True,
            Receipt.numero_progressivo.like('____-____'),
            ~Receipt.numero_progressivo.like('0001-%'),
        ).first()
    except Exception:
        db.session.rollback()
        return False
    return storico is not None


MSG_RCH_BLOCCATA_NON_INVIATO = (
    "La stampante risponde con i contatori a zero (Z 0, documento 0): è bloccata. "
    "Lo scontrino NON è stato inviato e NON è stato registrato. Se la carta c'è, "
    "spegni e riaccendi la stampante RCH, poi premi di nuovo Stampa. "
    "(Se la stampante è nuova o appena sostituita, esegui prima una chiusura Z.)")


def _rch_pronta(c):
    """La lettura descrive una stampante che risponde in modo affidabile e non
    ha niente in corso (nessun segnale di carta, coperchio, errore, lavoro)."""
    if c is None or _rch_contatori_bloccati(c):
        return False
    if c["carta_finita"] or c["coperchio_aperto"] or c["errore_meccanico"] or c["occupata"]:
        return False
    # 2/3/4 = documento aperto (vedi rch_console_status)
    return c["error_code"] in (None, 0, 20, 99)


def _rch_esito(prima, dopo):
    """Confronta due letture. Ritorna:
    'emesso'     stessa Z, documento +1: lo scontrino e' uscito
    'non_emesso' stampante pronta e contatore fermo: non e' uscito niente
    'incerto'    la stampante risponde ma il contatore non si spiega con un
                 solo documento (Z cambiata, documento +2 o indietro)
    'attesa'     la stampante non è (ancora) in grado di dirlo"""
    if dopo is None or _rch_contatori_bloccati(dopo):
        return 'attesa'
    if dopo["z"] == prima["z"] and dopo["doc"] == prima["doc"] + 1:
        return 'emesso'
    if dopo["z"] == prima["z"] and dopo["doc"] == prima["doc"]:
        return 'non_emesso' if _rch_pronta(dopo) else 'attesa'
    return 'incerto' if _rch_pronta(dopo) else 'attesa'


def _rch_attendi_emissione(url, headers, rch_kwargs, prima, budget_s=RCH_CONFERMA_S, passo_s=0.5):
    """Rilegge il contatore finche' lo scontrino risulta emesso o finisce il
    tempo. Nel caso normale esce alla prima lettura (mezzo secondo).
    Ritorna (esito, ultima_lettura)."""
    scadenza = pytime.monotonic() + budget_s
    ultima = None
    while True:
        pytime.sleep(passo_s)
        ultima = _rch_contatori(url, headers, rch_kwargs)
        esito = _rch_esito(prima, ultima)
        if esito == 'emesso' or pytime.monotonic() >= scadenza:
            return esito, ultima


def _rch_progressivo(c):
    """Progressivo nel formato del registro: Z in corso (lastZ + 1) - documento."""
    return f"{c['z'] + 1:04d}-{c['doc']:04d}"


def _rch_messaggio_stato(c):
    """Cosa dire all'operatore guardando una lettura."""
    if c is None:
        return ("La stampante non risponde (si sta riavviando? è accesa e collegata?).")
    if c["carta_finita"]:
        return "Carta finita: cambia il rotolo."
    if c["coperchio_aperto"]:
        return "Coperchio della stampante aperto: chiudilo."
    if _rch_contatori_bloccati(c) or c["errore_meccanico"]:
        return ("Stampante bloccata. Se la carta c'è, spegni e riaccendi la stampante RCH.")
    if c["occupata"]:
        return "La stampante sta ancora lavorando..."
    if c["error_code"] in (2, 3, 4):
        return ("La stampante ha un documento aperto: chiudilo qui sotto oppure "
                "spegni e riaccendi la stampante RCH.")
    return "Stampante pronta."


def _rch_connessione_mai_aperta(exc):
    """True se la richiesta NON e' mai arrivata alla stampante (connessione
    rifiutata o non aperta in tempo): niente stampato, ristampare e' sicuro.
    Una connessione caduta a meta' invece non lo dice: lo scontrino puo' essere
    arrivato."""
    if isinstance(exc, requests.exceptions.ConnectTimeout):
        return True
    testo = str(exc)
    return any(s in testo for s in ("NewConnectionError", "Failed to establish a new connection",
                                    "Connection refused", "actively refused",
                                    "No route to host", "Network is unreachable"))


def _rch_esegui_scontrino(url, headers, rch_kwargs, payload, prima):
    """Manda lo scontrino e decide dal contatore se e' uscito. Va chiamata con
    la stampante gia' in uso (_rch_in_uso) e con il contatore letto subito prima.

    Ritorna un dict:
      esito   'emesso'        stessa Z, documento +1
              'non_arrivato'  la connessione non si e' mai aperta: niente
                              stampato, si puo' ristampare subito
              'da_verificare' la stampante puo' averlo ricevuto: decide solo una
                              nuova lettura del contatore (rch_retry)
      motivo  None | 'connessione' | 'nessuna_risposta' | 'connessione_interrotta'
              | 'risposta_errore' | 'contatore_fermo' | 'errore'
      dopo, risposta, errcode, invio_ms
    Al peggio: RCH_RISPOSTA_SCONTRINO_S + una lettura di stato."""
    out = {"esito": None, "motivo": None, "dopo": None, "risposta": "",
           "errcode": None, "invio_ms": None}
    t0 = pytime.monotonic()
    resp = None
    try:
        resp = _rch_post(url, data=payload.encode("UTF-8"), headers=headers,
                         timeout=(RCH_CONNESSIONE_S, RCH_RISPOSTA_SCONTRINO_S), **rch_kwargs)
    except RchOccupata:
        raise
    except requests.exceptions.ConnectTimeout:
        out.update(esito='non_arrivato', motivo='connessione')
    except requests.exceptions.ReadTimeout:
        out['motivo'] = 'nessuna_risposta'
    except requests.exceptions.ConnectionError as exc:
        if _rch_connessione_mai_aperta(exc):
            out.update(esito='non_arrivato', motivo='connessione')
        else:
            out['motivo'] = 'connessione_interrotta'
            out['risposta'] = str(exc)[:200]
    except Exception as exc:
        out['motivo'] = 'errore'
        out['risposta'] = str(exc)[:200]
    out['invio_ms'] = int((pytime.monotonic() - t0) * 1000)
    if out['esito'] == 'non_arrivato':
        return out

    if resp is not None:
        out['risposta'] = (resp.text or "")[:400]
        if _rch_is_success(resp):
            esito, dopo = _rch_attendi_emissione(url, headers, rch_kwargs, prima)
            out['dopo'] = dopo
            if esito == 'emesso':
                out['esito'] = 'emesso'
            else:
                out.update(esito='da_verificare', motivo='contatore_fermo')
            return out
        out['motivo'] = 'risposta_errore'
        out['errcode'] = _rch_parse_errcode(resp.text or "")

    # Nessuna risposta, o risposta d'errore: UNA lettura veloce. Se lo scontrino
    # e' uscito lo stesso si registra subito, altrimenti decide la verifica.
    dopo = _rch_contatori(url, headers, rch_kwargs)
    out['dopo'] = dopo
    out['esito'] = 'emesso' if _rch_esito(prima, dopo) == 'emesso' else 'da_verificare'
    return out


def _rch_messaggio_motivo(esecuzione):
    """Prima riga della finestra "Scontrino non confermato": cosa e' successo."""
    motivo = esecuzione.get("motivo")
    if motivo == 'nessuna_risposta':
        testo = (f"La stampante ha ricevuto lo scontrino ma non ha risposto entro "
                 f"{int(RCH_RISPOSTA_SCONTRINO_S)} secondi.")
    elif motivo == 'contatore_fermo':
        testo = "La stampante ha accettato lo scontrino, ma non risulta stampato."
    elif motivo == 'risposta_errore':
        testo = f"La stampante ha rifiutato lo scontrino (codice {esecuzione.get('errcode')})."
    elif motivo == 'connessione_interrotta':
        testo = "La connessione con la stampante si è interrotta durante l'invio."
    else:
        testo = "La stampante non ha confermato lo scontrino."
    dopo = esecuzione.get("dopo")
    if not _rch_pronta(dopo):
        testo += " " + _rch_messaggio_stato(dopo)
    return testo


def _rch_registra_pendente(key, pending, progressivo, come):
    """Registra lo scontrino di un pending che il contatore ha confermato
    uscito, con ricariche/attivazioni/rate come nel percorso diretto.
    Il pending si toglie PRIMA di scrivere: due verifiche arrivate insieme non
    lo registrano due volte (e _registra_fiscale_confermato non duplica il
    progressivo). Ritorna il risultato da dare alla cassa."""
    if RCH_PENDING.pop(key, None) is None and key in IDEMPOTENCY_STORE:
        return IDEMPOTENCY_STORE[key]
    voci = pending.get("voci", []) or []
    try:
        totale = float(pending.get("expected_total"))
    except Exception:
        totale = round(sum(float(v.get("prezzo", 0)) for v in voci), 2)
    scritto = _registra_fiscale_confermato(voci, pending.get("cliente_id"),
                                           pending.get("operatore_id"), totale, progressivo)
    if scritto:
        try:
            _applica_movimenti_incasso(pending.get("voci_richiesta") or voci)
        except Exception:
            current_app.logger.exception("movimenti carte/rate non applicati (%s)", come)
        log_crm_error(
            "Scontrino registrato dopo una mancata conferma della stampante",
            context={"idempotency_key": key, "progressivo": progressivo, "come": come,
                     "expected_total": totale, "ristampe": pending.get("ristampe", 0),
                     "secondi_dal_primo_invio": round(
                         pytime.time() - pending.get("primo_invio_ts", pending.get("created_ts", pytime.time())), 1)},
            client_id=pending.get("cliente_id"),
        )
    result = {"results": [{"message": f"Scontrino fiscale registrato (progressivo {progressivo})",
                           "is_fiscale": True}],
              "reset_voci": True}
    IDEMPOTENCY_STORE[key] = result
    return result


def _rch_risolvi_pendenti(pre):
    """UNO SCONTRINO IN SOSPESO ALLA VOLTA. Prima di mandarne uno nuovo si
    decide la sorte di quelli rimasti da verificare, con la lettura del
    contatore appena fatta (stampante gia' in uso). Ritorna None se si puo'
    procedere, altrimenti (corpo, status) da restituire al posto della stampa.
    - uscito in ritardo           -> registrato; il nuovo NON si stampa: dopo un
                                     ricarico della pagina e' spesso lo stesso
    - non uscito, stampante pronta -> scartato, si procede
    - stampante non pronta        -> non si stampa"""
    oggi = datetime.now().strftime("%Y-%m-%d")
    for key, p in sorted(list(RCH_PENDING.items()), key=lambda kv: kv[1].get("created_ts", 0)):
        prima_p = p.get("contatori_prima")
        if p.get("giorno") != oggi or not prima_p:
            RCH_PENDING.pop(key, None)
            continue
        esito = _rch_esito(prima_p, pre)
        ora = datetime.fromtimestamp(p.get("primo_invio_ts", p.get("created_ts", pytime.time()))).strftime("%H:%M")
        try:
            tot = f"{float(p.get('expected_total') or 0):.2f}".replace('.', ',')
        except Exception:
            tot = "?"
        if esito == 'emesso':
            prog = _rch_progressivo(pre)
            _rch_registra_pendente(key, p, prog, "prima di uno scontrino nuovo")
            return ({"error": (f"Lo scontrino precedente da € {tot} (ore {ora}) è uscito in "
                               f"ritardo ed è stato registrato adesso ({prog}). Se stavi "
                               f"ristampando lo stesso scontrino NON serve: togli le voci dalla "
                               f"bozza. Se è un'altra vendita, premi di nuovo Stampa."),
                     "pendente_registrato": True}, 409)
        if esito == 'non_emesso':
            if pytime.time() - p.get("created_ts", 0) < RCH_MIN_PRIMA_DI_RISTAMPA_S:
                return ({"error": "Sto ancora verificando lo scontrino precedente: "
                                  "riprova tra qualche secondo."}, 409)
            RCH_PENDING.pop(key, None)     # non uscito: scartato, la bozza e' ancora in cassa
            continue
        if esito == 'attesa':
            return ({"error": (f"C'è uno scontrino precedente da € {tot} (ore {ora}) non "
                               f"confermato e la stampante non è pronta. "
                               + _rch_messaggio_stato(pre)),
                     "pendente_in_attesa": True}, 409)
        # incerto: non si puo' attribuire il documento, lo si scarta lasciando traccia
        RCH_PENDING.pop(key, None)
        log_crm_error(
            "Scontrino da verificare scartato: contatore non spiegabile",
            context={"idempotency_key": key, "contatori_prima": prima_p,
                     "contatori_ora": {"z": pre["z"], "doc": pre["doc"]},
                     "expected_total": p.get("expected_total")},
            client_id=p.get("cliente_id"),
        )
    return None

def clean_str(s):
    # Rimuove apostrofi e caratteri HTML problematici
    return str(s).replace("'", "").replace('"', "").replace("&", "").replace(";", "").replace("<", "").replace(">", "")

cassa_bp = Blueprint('cassa', __name__)


@cassa_bp.errorhandler(RchOccupata)
def _cassa_rch_occupata(exc):
    """La stampante e' impegnata da un'altra richiesta: niente e' stato
    mandato. Piu' specifico di Exception, quindi Flask sceglie questo."""
    return jsonify({"error": MSG_RCH_OCCUPATA, "rch_occupata": True}), 409


@cassa_bp.errorhandler(Exception)
def _cassa_errore_non_gestito(exc):
    """Qualsiasi eccezione non gestita nelle route della cassa esce come JSON,
    non come pagina HTML di errore.

    Motivo: il frontend fa `await res.json()` e, se il body non e' JSON, si
    ritrova `data = null` e mostra il generico "Errore durante la stampa
    fiscale!" - che non dice nulla su cosa sia successo. Cosi' invece il
    messaggio reale arriva fino all'operatore e finisce nei log col traceback.
    Le HTTPException (404, 405, i 4xx espliciti) passano invariate.
    """
    from werkzeug.exceptions import HTTPException
    if isinstance(exc, HTTPException):
        return exc
    try:
        db.session.rollback()
    except Exception:
        pass
    current_app.logger.exception("Eccezione non gestita in una route della cassa")
    return jsonify({
        "error": f"Errore interno: {type(exc).__name__}: {exc}"
    }), 500


def _prezzo_riga_appuntamento(servizio, appuntamento):
    """Prezzo con cui la riga di un appuntamento entra in cassa: (prezzo, in_promo).

    PROMO (appl/services/promo.py): se il servizio e' spuntato PROMO, ha uno
    sconto e l'orario dell'appuntamento rientra nelle condizioni, la riga
    arriva gia' col prezzo promo, modificabile come sempre. Lo scontrino non
    cambia: la riga "Scontato del X%" la stampa gia' da sola quando il prezzo
    e' sotto il listino. In tutti gli altri casi (e se qualcosa va storto)
    resta il listino: la cassa non si ferma per una promo."""
    listino = servizio.servizio_prezzo if servizio else 0
    if not servizio or not appuntamento:
        return listino, False
    scontato = promo_mod.prezzo_scontato_servizio(servizio, appuntamento.start_time,
                                                  appuntamento._duration)
    if scontato is None:
        return listino, False
    return scontato, True


@cassa_bp.route('/cassa')
def cassa():
    current_app.logger.debug("GET args in cassa: %s", request.args)
    client_id = request.args.get('client_id')
    operator_id = request.args.get('operator_id')
    client_name = request.args.get('client_name')
    operator_name = request.args.get('operator_name')
    servizi_json = request.args.get('servizi')
    appointments_json = request.args.get('appointments')
    rata_id = request.args.get('rata_id')
    pacchetto_id_param = request.args.get('pacchetto_id')
    prepagata_id = request.args.get('prepagata_id')  # Pagamento carta prepagata
    ricarica_prepagata_id = request.args.get('ricarica_prepagata_id')  # Ricarica carta prepagata
    ricarica_importo = request.args.get('importo')  # Importo da pagare
    ricarica_credito = request.args.get('credito')  # Credito effettivo da caricare (può essere > importo con bonus)
    ricarica_descrizione = request.args.get('descrizione', 'Ricarica')
    servizi = []

    # Se prepagata_id presente, carica la carta prepagata da pagare
    if prepagata_id:
        try:
            pacchetto = Pacchetto.query.get(int(prepagata_id))
            if pacchetto and pacchetto.tipo.value == 'prepagata' and pacchetto.status == PacchettoStatus.Preventivo:
                # Cliente
                if pacchetto.client:
                    client_id = pacchetto.client_id
                    client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                
                # Usa costo_totale_lordo (importo da pagare), non credito_iniziale (credito caricato)
                importo_da_pagare = float(pacchetto.costo_totale_lordo) if pacchetto.costo_totale_lordo else float(pacchetto.credito_iniziale)
                
                servizi = [{
                    'id': None,
                    'nome': clean_str(f"Carta Prepagata - {nome_proprio(pacchetto.client.cliente_nome)} {nome_proprio(pacchetto.client.cliente_cognome)}"),
                    'prezzo': importo_da_pagare,
                    'categoria': 'Estetica',
                    'is_fiscale': False,
                    'is_non_fiscale': True,
                    'metodo_pagamento': 'contanti',
                    'prepagata_id': pacchetto.id,
                    'credito_da_caricare': float(pacchetto.credito_iniziale)
                }]
        except Exception as e:
            current_app.logger.error(f"Errore caricamento prepagata {prepagata_id}: {e}")

    # Se ricarica_prepagata_id presente, carica la ricarica da pagare
    if ricarica_prepagata_id and ricarica_importo:
        try:
            pacchetto = Pacchetto.query.get(int(ricarica_prepagata_id))
            if pacchetto and pacchetto.tipo.value == 'prepagata':
                importo = float(ricarica_importo)
                
                # Cliente
                if pacchetto.client:
                    client_id = pacchetto.client_id
                    client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                
                # Credito da caricare: se specificato usa quello, altrimenti usa l'importo pagato
                credito_da_caricare = float(ricarica_credito) if ricarica_credito else importo
                
                servizi = [{
                    'id': None,
                    'nome': clean_str(f"Ricarica Prepagata - {ricarica_descrizione}"),
                    'prezzo': importo,  # Importo da pagare in cassa
                    'categoria': 'Estetica',
                    'is_fiscale': True,
                    'metodo_pagamento': 'contanti',
                    'ricarica_prepagata_id': pacchetto.id,
                    'ricarica_importo': importo,
                    'ricarica_credito': credito_da_caricare,  # Credito effettivo da caricare
                    'ricarica_descrizione': ricarica_descrizione
                }]
        except Exception as e:
            current_app.logger.error(f"Errore caricamento ricarica prepagata {ricarica_prepagata_id}: {e}")

    # Se pacchetto_id presente (pagamento pacchetto intero), carica tutte le rate non pagate
    if pacchetto_id_param:
        try:
            pacchetto = Pacchetto.query.get(int(pacchetto_id_param))
            if pacchetto and pacchetto.status == PacchettoStatus.Preventivo:
                # Cliente
                if pacchetto.client:
                    client_id = pacchetto.client_id
                    client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                
                # Operatore preferito (primo se presente)
                if pacchetto.preferred_operators:
                    first_op = pacchetto.preferred_operators[0]
                    operator_id = first_op.id
                    operator_name = first_op.user_nome
                
                # Determina categoria dal primo servizio del pacchetto
                categoria = "Estetica"  # default
                if pacchetto.sedute:
                    first_seduta = pacchetto.sedute[0] if pacchetto.sedute else None
                    if first_seduta and first_seduta.service:
                        categoria = first_seduta.service.servizio_categoria.value
                
                # Carica tutte le rate non pagate come righe separate
                rate_non_pagate = PacchettoRata.query.filter_by(
                    pacchetto_id=pacchetto.id, 
                    is_pagata=False
                ).order_by(PacchettoRata.id).all()
                
                rate_ordinate = PacchettoRata.query.filter_by(pacchetto_id=pacchetto.id).order_by(PacchettoRata.id).all()
                
                for rata in rate_non_pagate:
                    numero_rata = next((i+1 for i, r in enumerate(rate_ordinate) if r.id == rata.id), 1)
                    servizi.append({
                        'id': None,
                        'nome': clean_str(f"Rata {numero_rata} - {pacchetto.nome}"),
                        'prezzo': float(rata.importo),
                        'categoria': clean_str(categoria),
                        'is_fiscale': True,
                        'metodo_pagamento': 'contanti',
                        'rata_id': rata.id,
                        'pacchetto_id': pacchetto.id
                    })
        except Exception as e:
            current_app.logger.error(f"Errore caricamento pacchetto {pacchetto_id_param}: {e}")
    
    # Se rata_id presente, carica dati dalla rata del pacchetto
    elif rata_id:
        try:
            rata = PacchettoRata.query.get(int(rata_id))
            if rata and not rata.is_pagata:
                pacchetto = Pacchetto.query.get(rata.pacchetto_id)
                if pacchetto:
                    # Determina numero rata
                    rate_ordinate = PacchettoRata.query.filter_by(pacchetto_id=pacchetto.id).order_by(PacchettoRata.id).all()
                    numero_rata = next((i+1 for i, r in enumerate(rate_ordinate) if r.id == rata.id), 1)
                    
                    # Cliente
                    if pacchetto.client:
                        client_id = pacchetto.client_id
                        client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                    
                    # Operatore preferito (primo se presente)
                    if pacchetto.preferred_operators:
                        first_op = pacchetto.preferred_operators[0]
                        operator_id = first_op.id
                        operator_name = first_op.user_nome
                    
                    # Determina categoria dal primo servizio del pacchetto
                    categoria = "Estetica"  # default
                    if pacchetto.sedute:
                        first_seduta = pacchetto.sedute[0] if pacchetto.sedute else None
                        if first_seduta and first_seduta.service:
                            categoria = first_seduta.service.servizio_categoria.value
                    
                    servizi = [{
                        'id': None,  # Nessun service_id reale
                        'nome': clean_str(f"Rata {numero_rata} - {pacchetto.nome}"),
                        'prezzo': float(rata.importo),
                        'categoria': clean_str(categoria),
                        'is_fiscale': True,
                        'metodo_pagamento': 'contanti',
                        'rata_id': rata.id,  # IMPORTANTE: per marcare come pagata dopo
                        'pacchetto_id': pacchetto.id
                    }]
        except Exception as e:
            current_app.logger.error(f"Errore caricamento rata {rata_id}: {e}")

    if servizi_json:
        try:
            servizi_raw = json.loads(servizi_json)
            # Precarica categoria/sottocategoria_id dai Service reali (una sola query):
            # il payload che arriva da Agenda non porta questi campi, e senza di essi
            # una prepagata con vincolo "solo categoria/sottocategoria" non risulta mai
            # utilizzabile per i servizi portati in cassa da un appuntamento.
            _srv_ids = [s.get("id") for s in servizi_raw if s.get("id")]
            _servizi_db = {}
            if _srv_ids:
                for _sv in Service.query.filter(Service.id.in_(_srv_ids)).all():
                    _servizi_db[_sv.id] = _sv
            # Appuntamenti delle righe (una query): servono a giudicare la PROMO,
            # che dipende da giorno e orario (vedi _prezzo_riga_appuntamento).
            _appt_ids = set()
            for s in servizi_raw:
                try:
                    _appt_ids.add(int(s.get("appointment_id")))
                except (TypeError, ValueError):
                    pass
            _appts_db = {}
            if _appt_ids and any(getattr(sv, 'is_promo', False) for sv in _servizi_db.values()):
                for _a in Appointment.query.filter(Appointment.id.in_(_appt_ids)).all():
                    _appts_db[_a.id] = _a
            # Assicurati che ogni servizio abbia operator_id e operator_nome
            servizi = []
            for s in servizi_raw:
                # Recupera operator_id e operator_nome
                op_id = s.get("operator_id")
                op_nome = s.get("operator_nome", "")
                
                # Se operator_id è null/vuoto/stringa "null", recuperalo dall'appointment
                appt_id = s.get("appointment_id")
                if (not op_id or op_id == '' or op_id == 'null' or str(op_id).lower() == 'none') and appt_id:
                    try:
                        appt = db.session.get(Appointment, int(appt_id))
                        if appt and appt.operator_id:
                            op_id = appt.operator_id
                            op = db.session.get(Operator, appt.operator_id)
                            if op:
                                op_nome = op.user_nome or ''
                    except Exception:
                        pass
                
                _sv_db = _servizi_db.get(s.get("id"))
                srv = {
                    "id": s.get("id"),
                    "nome": clean_str(s.get("nome", "")),
                    "prezzo": s.get("prezzo", 0),
                    "tag": clean_str(s.get("tag", "")),
                    "sottocategoria": clean_str(s.get("sottocategoria", "")),
                    "categoria": _sv_db.servizio_categoria.value if _sv_db and _sv_db.servizio_categoria else None,
                    "sottocategoria_id": _sv_db.servizio_sottocategoria_id if _sv_db else None,
                    "appointment_id": appt_id,
                    "operator_id": op_id,
                    "operator_nome": op_nome
                }
                # PROMO: solo se l'appuntamento rientra, la riga arriva col prezzo
                # promo e con i dati del servizio gia' pronti (cosi' la pagina
                # non li richiede al listino, che riporterebbe il prezzo pieno).
                try:
                    _sv_promo = _servizi_db.get(int(s.get("id")))
                    _appt_promo = _appts_db.get(int(appt_id)) if appt_id else None
                except (TypeError, ValueError):
                    _sv_promo = _appt_promo = None
                if _sv_promo is not None and _appt_promo is not None:
                    _prezzo, _in_promo = _prezzo_riga_appuntamento(_sv_promo, _appt_promo)
                    if _in_promo:
                        srv["prezzo"] = _prezzo
                        srv["promo"] = True
                        srv["nome"] = srv["nome"] or clean_str(_sv_promo.servizio_nome or "")
                        srv["tag"] = srv["tag"] or clean_str(_sv_promo.servizio_tag or "")
                        if not srv["sottocategoria"] and _sv_promo.servizio_sottocategoria:
                            srv["sottocategoria"] = clean_str(_sv_promo.servizio_sottocategoria.nome)
                        if srv["categoria"] is None and _sv_promo.servizio_categoria:
                            srv["categoria"] = _sv_promo.servizio_categoria.value
                        if srv["sottocategoria_id"] is None:
                            srv["sottocategoria_id"] = _sv_promo.servizio_sottocategoria_id
                servizi.append(srv)
        except Exception as e:
            current_app.logger.error(f"Errore parsing servizi_json: {e}")
            servizi = []

    if appointments_json:
        try:
            appointments_ids = json.loads(appointments_json)
            appointments = Appointment.query.filter(
                Appointment.id.in_(appointments_ids),
                Appointment.is_cancelled_by_client == False
            ).all()
            for appt in appointments:
                appt_op = appt.operator
                servizi.append({
                    "id": appt.service.id,
                    "nome": clean_str(appt.service.servizio_nome),
                    # Listino, o prezzo promo se l'appuntamento rientra nella promo
                    "prezzo": _prezzo_riga_appuntamento(appt.service, appt)[0],
                    "tag": clean_str(appt.service.servizio_tag),
                    "sottocategoria": clean_str(appt.service.servizio_sottocategoria.nome) if appt.service.servizio_sottocategoria else "",
                    "appointment_id": appt.id,
                    "operator_id": appt_op.id if appt_op else None,
                    "operator_nome": appt_op.user_nome if appt_op else ""
                })
        except Exception as e:
            servizi = []
    
    try:
        if client_id:
            cid = int(client_id)
            cli = db.session.get(Client, cid)
            if cli:
                client_name = f"{nome_proprio(cli.cliente_nome)} {nome_proprio(cli.cliente_cognome)}".strip()
        elif client_name:
            client_name = html.unescape(client_name)
    except Exception:
        if client_name:
            client_name = html.unescape(client_name)

    # Se operator_name non è passato ma operator_id sì, recupera nome e cognome dal DB
    if not operator_name and operator_id:
        op = db.session.get(Operator, operator_id)
        if op:
            operator_name = f"{op.user_nome} {op.user_cognome}"

    giorno = date.today()
    businessinfo = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()

    # Aggiungi ruolo utente per mostrare/nascondere console RCH
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    user_role = user.ruolo.value if user else None

    return render_template(
        'cassa.html',
        client_id=client_id,
        operator_id=operator_id,
        client_name=client_name,
        operator_name=operator_name,
        servizi=servizi,
        giorno=giorno,
        businessinfo=businessinfo,
        user_role=user_role
    )

@cassa_bp.route('/cassa/api/operators')
def api_operators():
    # Restituisce la lista operatori attivi ordinati per il campo 'order'
    operators = Operator.query.filter_by(is_visible=True, is_deleted=False).order_by(Operator.order.asc()).all()
    return jsonify([
        {"id": op.id, "nome": op.user_nome, "cognome": op.user_cognome}
        for op in operators
    ])

def _extract_service_id(v):
    """Estrae l'id servizio da una voce di scontrino, supportando vari nomi/format."""
    if not isinstance(v, dict):
        return None
    for key in ('servizio_id', 'service_id', 'id', 'servizioId', 'servizioID'):
        if key in v and v[key] not in (None, ''):
            try:
                return int(v[key])
            except Exception:
                try:
                    return int(str(v[key]).strip())
                except Exception:
                    return None
    return None


def _servizi_in_voci(voci):
    """Gli id servizio presenti nelle voci di uno scontrino (lista o JSON testuale)."""
    if not isinstance(voci, list):
        voci = json.loads(voci or '[]') if voci else []
    return [sid for sid in (_extract_service_id(v) for v in voci) if sid]


# ---- "Frequenti": la classifica dei servizi piu' usati in cassa --------------
# Prima si rileggevano TUTTI gli scontrini di sempre a ogni apertura della Cassa
# (Receipt.query.all(): al 29/09/2026 sunexp3 ne aveva ~20.000, 1,4-1,9 s a ogni
# apertura, e cresce con ogni scontrino emesso). Ora la classifica si ricorda in
# memoria per negozio e si aggiorna leggendo SOLO gli scontrini nuovi.
# Si valida con (numero scontrini, id piu' alto): se coincidono non si legge
# niente; se e' solo salito l'id e il numero e' cresciuto di altrettanti si
# aggiungono i nuovi; in ogni altro caso (scontrino cancellato, modificato) si
# ricalcola tutto. Il ricalcolo completo avviene comunque ogni 30 minuti.
_FREQUENTI_RICALCOLO_S = 30 * 60
_frequenti_cache = {}   # chiave negozio -> {'n', 'max_id', 'ts', 'cnt'}


def _frequenti_top_ids(limite=28):
    from collections import Counter
    from appl.services import usage_monitor

    chiave = usage_monitor.chiave_tenant()
    n_ora, max_ora = db.session.query(func.count(Receipt.id), func.max(Receipt.id)).one()
    st = _frequenti_cache.get(chiave)

    cnt = None
    if st and pytime.time() - st['ts'] < _FREQUENTI_RICALCOLO_S:
        if (n_ora, max_ora) == (st['n'], st['max_id']):
            cnt = st['cnt']
        elif max_ora is not None and st['max_id'] is not None and max_ora > st['max_id']:
            nuovi = db.session.query(Receipt.voci).filter(Receipt.id > st['max_id']).all()
            if n_ora == st['n'] + len(nuovi):
                cnt = Counter(st['cnt'])
                for (voci,) in nuovi:
                    cnt.update(_servizi_in_voci(voci))
                _frequenti_cache[chiave] = {'n': n_ora, 'max_id': max_ora, 'ts': st['ts'], 'cnt': cnt}

    if cnt is None:
        cnt = Counter()
        for (voci,) in db.session.query(Receipt.voci).all():
            cnt.update(_servizi_in_voci(voci))
        _frequenti_cache[chiave] = {'n': n_ora, 'max_id': max_ora, 'ts': pytime.time(), 'cnt': cnt}

    # a parita' di utilizzi, l'id piu' basso: l'ordine non cambia da una chiamata all'altra
    return [sid for sid, _ in sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:limite]]


@cassa_bp.route('/cassa/api/services')
def api_services():
    try:
        id = request.args.get('id')
        q = request.args.get('q', '').strip()
        ultimi = request.args.get('ultimi')
        frequenti = request.args.get('frequenti')
        categoria = request.args.get('categoria')
        sottocategoria = request.args.get('sottocategoria')

        # helper: estrae id servizio supportando vari nomi/format
        extract_sid = _extract_service_id

        # base query (sempre applicata se non viene sovrascritta)
        base_query = Service.query.filter(Service.is_deleted == False)

        services = []
        # caso: ricerca per id o testo
        if id:
            query = base_query.filter(Service.id == id)
            services = query.limit(28).all()
        elif q and len(q) >= 3:
            query = base_query.filter(Service.servizio_nome.ilike(f"%{q}%"))
            services = query.limit(28).all()
        elif ultimi:
            # ULTIMI: prendi receipt recenti, estrai servizi unici nell'ordine di apparizione
            recent_receipts = Receipt.query.order_by(Receipt.created_at.desc()).limit(200).all()
            seen = set()
            ordered_ids = []
            for r in recent_receipts:
                voci = r.voci if isinstance(r.voci, list) else (json.loads(r.voci or '[]') if r.voci else [])
                for v in voci:
                    sid = extract_sid(v)
                    if sid and sid not in seen:
                        seen.add(sid)
                        ordered_ids.append(sid)
                        if len(ordered_ids) >= 28:
                            break
                if len(ordered_ids) >= 28:
                    break
            if ordered_ids:
                db_services = Service.query.filter(Service.id.in_(ordered_ids), Service.is_deleted == False).all()
                svc_map = {s.id: s for s in db_services}
                services = [svc_map[sid] for sid in ordered_ids if sid in svc_map]
            else:
                services = []
        elif frequenti:
            # FREQUENTI: servizi piu' presenti negli scontrini, in ordine di frequenza
            # (la classifica e' in memoria, vedi _frequenti_top_ids)
            top = _frequenti_top_ids()
            if top:
                db_services = Service.query.filter(Service.id.in_(top), Service.is_deleted == False).all()
                svc_map = {s.id: s for s in db_services}
                # preserva l'ordine dei top
                services = [svc_map[sid] for sid in top if sid in svc_map]
            else:
                services = []
        elif sottocategoria:
            query = base_query.join(Service.servizio_sottocategoria).filter(Subcategory.nome == sottocategoria)
            services = query.limit(28).all()
        elif categoria:
            query = base_query.filter(Service.servizio_categoria == categoria)
            services = query.limit(28).all()
        else:
            services = base_query.order_by(Service.servizio_nome).limit(28).all()

        # server-side dedup (preserva primo-occurrence) e limit finale
        seen = set()
        unique_services = []
        for s in services:
            sid = getattr(s, 'id', None)
            if sid is None or sid in seen:
                continue
            seen.add(sid)
            unique_services.append(s)
            if len(unique_services) >= 28:
                break
        services = unique_services

        return jsonify([
            {
                "id": s.id,
                "nome": clean_str(s.servizio_nome),
                "tag": clean_str(s.servizio_tag),
                "prezzo": s.servizio_prezzo,
                "categoria": clean_str(s.servizio_categoria.value) if s.servizio_categoria else "",
                "sottocategoria": clean_str(s.servizio_sottocategoria.nome) if s.servizio_sottocategoria else "",
                "sottocategoria_id": s.servizio_sottocategoria_id,
                "is_prodotti": (
                    s.servizio_sottocategoria and clean_str(s.servizio_sottocategoria.nome.lower()) == "prodotti"
                )
            }
            for s in services
        ])
    except Exception as e:
        current_app.logger.error("Errore in /cassa/api/services: %s", str(e))
        return jsonify({"error": "Errore nel recupero dei servizi."}), 500
        
@cassa_bp.route('/cassa/api/clients')
def api_clients():
    q_raw = request.args.get('q', '').strip().lower()

    # Se meno di 2 caratteri → ritorna lista vuota
    if len(q_raw) < 2:
        return jsonify([])

    # Suddividi in parti (nome, cognome o pezzi multipli)
    parts = [p for p in q_raw.split() if p]

    # Costruzione filtri avanzati come nella route calendar
    if len(parts) == 1:
        term = f"%{parts[0]}%"
        filters = or_(
            func.lower(Client.cliente_nome).like(term),
            func.lower(Client.cliente_cognome).like(term),
            Client.cliente_cellulare.like(term)
        )
    else:
        # Cerca tutte le parti nel nome o cognome (AND combinato)
        conditions = []
        for part in parts:
            term = f"%{part}%"
            conditions.append(
                or_(
                    func.lower(Client.cliente_nome).like(term),
                    func.lower(Client.cliente_cognome).like(term)
                )
            )
        filters = and_(*conditions)

    # Applichiamo filtri di esclusione
    query = Client.query.filter(
        filters,
        Client.is_deleted == False,
        ~((Client.cliente_nome == "cliente") & (Client.cliente_cognome == "booking")),
        ~((func.lower(Client.cliente_nome) == "booking") & (func.lower(Client.cliente_cognome) == "online")),
        func.lower(Client.cliente_nome) != "dummy",
        func.lower(Client.cliente_cognome) != "dummy",
    )

    clients = query.order_by(Client.cliente_nome).limit(20).all()

    return jsonify([
        {
            "id": c.id,
            "nome": c.cliente_nome,
            "cognome": c.cliente_cognome
        }
        for c in clients
    ])

IDEMPOTENCY_STORE = {}
RCH_PENDING = {}


def _read_printer_lastz(ip, printer_model):
    """Legge dalla stampante il numero dell'ultima chiusura fiscale (Z) via =C453.
    Ritorna int (numero Z gia' eseguite) oppure None se non leggibile."""
    try:
        url = _rch_url(ip, printer_model)
        headers = _rch_headers(printer_model)
        rch_kwargs = _rch_request_kwargs(printer_model)
        payload = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C453/$0</cmd></Service>'
        resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers, timeout=8,
                             **rch_kwargs)
        m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp.text or "")
        if m_z:
            return int(m_z.group(1))
    except Exception as exc:
        try:
            current_app.logger.warning("lettura lastZ (=C453) fallita: %s", str(exc))
        except Exception:
            pass
    return None


def _wait_for_z_advance(ip, printer_model, z_before, budget_s=180, sleep_s=10):
    """Chiede ALLA STAMPANTE se la chiusura Z e' stata davvero eseguita.

    Serve perche' la RCH Print F, mentre stampa la Z, chiude il socket senza
    rispondere (ConnectionResetError 10054 nei log): il CRM vede un errore di rete
    su una chiusura in realta' perfettamente riuscita, l'operatore riprova e il
    negozio si ritrova due Z. L'unico esito attendibile e' l'avanzamento del
    contatore lastZ (=C453), leggibile solo quando la stampante ha finito di
    stampare Z + esito trasmissione AdE e torna a rispondere (~2 minuti).

    Ritorna il nuovo lastZ se e' avanzato rispetto a `z_before`, altrimenti None.
    Se `z_before` e' None (lettura pre-chiusura non riuscita) manca il termine di
    paragone: ritorna None senza attendere e la chiusura resta data per fallita,
    come si comportava il codice prima di questa verifica.
    """
    if z_before is None:
        try:
            current_app.logger.warning(
                "verifica Z: lastZ pre-chiusura non letto, impossibile stabilire "
                "se la chiusura e' avvenuta."
            )
        except Exception:
            pass
        return None

    deadline = pytime.monotonic() + budget_s
    tentativo = 0
    while pytime.monotonic() < deadline:
        tentativo += 1
        pytime.sleep(sleep_s)
        z_now = _read_printer_lastz(ip, printer_model)
        try:
            current_app.logger.info(
                "verifica Z, tentativo %d: lastZ prima=%s adesso=%s",
                tentativo, z_before, z_now
            )
        except Exception:
            pass
        # Finche' la stampante non risponde sta ancora stampando: si insiste. Alla
        # prima risposta valida la questione e' decisa, in un senso o nell'altro,
        # senza aspettare la fine del budget.
        if z_now is not None:
            return z_now if z_now > z_before else None
    return None


def _is_weekly_closing_day(day):
    """True se `day` cade in un giorno di chiusura SETTIMANALE configurato
    (BusinessInfo.closing_days, nomi in inglese es. 'Sunday'). Solo lettura DB.
    Usa weekday() (locale-independent) per il nome del giorno."""
    bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
    if not bi:
        return False
    closing = bi.closing_days_list or []
    if not closing:
        return False
    EN_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return EN_DAYS[day.weekday()] in closing


def _day_had_no_activity(day):
    """GOLDEN RULE: quel giorno il negozio era chiuso se in calendario NON c'e' stata
    NESSUNA attivita', cioe' contemporaneamente:
      - nessun APPUNTAMENTO reale (i blocchi OFF/dummy non contano: sono blocchi di
        servizio, non lavoro svolto), e
      - nessuna CELLA ATTIVA (tutte le colonne grigie).

    Basta UNA delle due per dire che il negozio era aperto -> nessun avviso. Copre le
    festivita' infrasettimanali (25 aprile, 2 giugno...) che non sono fra i closing_days,
    senza dipendere da come sono stati impostati i turni.

    Celle attive: replica la regola del calendario (updateCalendarDisplay in calendar.js).
    La colonna di un operatore e' tutta grigia solo se ha turni quel giorno e sono TUTTI
    'OFF' (shift_start_time == shift_end_time, es. 00:00-00:00); se NON ha turni ricade
    sugli orari di default dell'attivita' -> colonna aperta.
    """
    from appl.models import OperatorShift

    # 1) C'e' stato lavoro vero quel giorno? -> aperto (qualunque cosa dicano i turni)
    day_start = datetime.combine(day, datetime.min.time())
    day_end = datetime.combine(day, datetime.max.time())
    appt = (Appointment.query
            .join(Client, Appointment.client_id == Client.id)
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.start_time >= day_start,
                    Appointment.start_time <= day_end,
                    Appointment.is_cancelled_by_client == False,
                    Client.cliente_nome.ilike('%dummy%') == False,
                    Client.cliente_cognome.ilike('%dummy%') == False,
                    Service.servizio_nome.ilike('%dummy%') == False)
            .first())
    if appt is not None:
        return False

    # 2) C'era almeno una cella attiva? -> aperto
    operators = Operator.query.filter_by(is_deleted=False, is_visible=True).all()
    if not operators:
        return False  # nessun operatore configurato: non deduciamo nulla

    shifts = OperatorShift.query.filter_by(shift_date=day).all()
    if not shifts:
        return False  # nessun turno -> orari default -> celle attive

    by_operator = defaultdict(list)
    for s in shifts:
        by_operator[s.operator_id].append(s)

    for op in operators:
        op_shifts = by_operator.get(op.id)
        if not op_shifts:
            return False  # operatore senza turni -> orari default -> colonna aperta
        if any(s.shift_end_time > s.shift_start_time for s in op_shifts):
            return False  # almeno un turno reale -> colonna aperta

    # Nessun appuntamento reale E nessuna cella attiva -> giornata chiusa
    return True


def _previous_day_was_closure(today):
    """True se il giorno PRECEDENTE a `today` era di chiusura, per uno qualsiasi dei due
    motivi: chiusura settimanale (business info) OPPURE nessuna attivita' in calendario
    (ne' celle attive ne' appuntamenti reali: festivita' infrasettimanale non segnata
    fra i closing_days). Ritorna (bool, reason). Solo lettura DB, nessuna stampante."""
    yesterday = today - timedelta(days=1)
    try:
        if _is_weekly_closing_day(yesterday):
            return True, "weekly_closing_day"
    except Exception as exc:
        current_app.logger.warning("closing_days non leggibili: %s", str(exc))

    try:
        if _day_had_no_activity(yesterday):
            return True, "no_activity"
    except Exception as exc:
        current_app.logger.warning("attivita' del giorno precedente non leggibile: %s", str(exc))

    return False, "open_day"


def _record_fiscal_closure(ip, printer_model, dgfe_total=None):
    """Registra in DB (fiscal_closures) la chiusura fiscale (Z) appena eseguita.
    Legge il nuovo lastZ dalla stampante (numero della Z appena fatta). Best-effort:
    non solleva mai e non interrompe il flusso di chiusura."""
    try:
        from appl.models import FiscalClosure
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        bid = bi.id if bi else 0
        z_num = _read_printer_lastz(ip, printer_model)  # lastZ DOPO la Z = numero di questa Z

        # Evita righe duplicate per lo stesso numero di Z (es. doppio click).
        if z_num is not None:
            existing = FiscalClosure.query.filter_by(business_info_id=bid, z_number=z_num).first()
            if existing:
                return

        row = FiscalClosure(
            business_info_id=bid,
            z_number=z_num,
            closed_at=datetime.now(),
            giorno=date.today(),
            dgfe_total=(float(dgfe_total) if dgfe_total is not None else None),
        )
        db.session.add(row)
        db.session.commit()
        try:
            current_app.logger.info("Chiusura Z registrata in DB: z_number=%s bid=%s", z_num, bid)
        except Exception:
            pass
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.warning("registrazione chiusura Z fallita: %s", str(exc))
        except Exception:
            pass


# Varianti della sequenza DOCUMENTO GESTIONALE (=o, manuale PRINT! sez. 17):
# (comando_apertura, comando_chiusura). Il manuale elenca =o, =o/*1, =o/&1 e
# =o/&2 senza dire quale apra e quale chiuda, e nel progetto questo comando non
# era mai stato usato. Invece di scommettere su una forma sola le proviamo in
# ordine e ci fermiamo alla prima che la stampante accetta: e' l'unico modo di
# essere robusti senza avere il registratore sotto mano.
GESTIONALE_SEQUENZE = [
    ('=o/&1', '=o/&2'),
    ('=o', '=o'),
    ('=o/*1', '=o'),
]

# Variante risultata valida, memorizzata per la vita del processo: dal secondo
# scontrino a zero in poi si va dritti a quella giusta, senza ritentare le altre.
_gestionale_sequenza_ok = None


def _righe_promemoria(voci_zero, max_caratteri):
    """Descrizioni ripulite delle voci a importo zero, pronte per il comando ="."""
    righe = []
    for v in voci_zero:
        srv = db.session.get(Service, v.get("servizio_id")) if v.get("servizio_id") else None
        desc = (v.get("nome") or (srv.servizio_nome if srv else "Servizio"))
        desc = clean_str(html.unescape(desc)).replace(")", "").replace("(", "").replace("/", "-")
        desc = desc.strip()
        if desc:
            righe.append(desc[:max_caratteri])
    return righe


def _rch_clear(ip, printer_model):
    """=K (clear): riporta la stampante a documento chiuso. Va mandato dopo un
    tentativo rifiutato, perche' un documento rimasto aperto blocca ogni stampa
    successiva - fiscale compresa. Non solleva mai."""
    try:
        _rch_post(
            _rch_url(ip, printer_model),
            data='<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=K</cmd></Service>'.encode("UTF-8"),
            headers=_rch_headers(printer_model), timeout=10,
            **_rch_request_kwargs(printer_model)
        )
    except Exception as exc:
        current_app.logger.warning("=K dopo tentativo gestionale fallito: %s", exc)


def _stampa_promemoria_gestionale(voci_zero, cliente_id=None, operatore_id=None):
    """Stampa le voci a importo zero su un DOCUMENTO GESTIONALE: un foglio
    NON fiscale, separato dallo scontrino.

    Serve quando la bozza non ha nessun importo da incassare. In quel caso non
    esiste un documento commerciale su cui appoggiare le righe descrittive:
    senza importo non c'e' un =T con cui chiuderlo, e un documento lasciato
    aperto bloccherebbe ogni stampa successiva. L'unico modo di dare comunque
    la carta al cliente e' quindi un documento a parte.

    Non fiscale: nessun corrispettivo, nessun progressivo, nessun effetto sulla
    DGFE. Non solleva mai eccezioni: se la stampa fallisce lo scontrino resta
    registrato a database e l'errore finisce nei log.
    Ritorna (ok: bool, info: str).
    """
    global _gestionale_sequenza_ok

    # Sul gestionale il testo arriva a 32 caratteri (sez. 11, "32 gestionale"),
    # contro i 25 della riga descrittiva dentro lo scontrino fiscale.
    righe = _righe_promemoria(voci_zero, 32)
    if not righe:
        return False, "nessuna riga da stampare"

    ip, printer_model = _get_printer_config()
    if not ip:
        return False, "IP stampante RCH non configurato"

    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)

    # Prima la variante gia' rivelatasi buona, poi le altre.
    sequenze = list(GESTIONALE_SEQUENZE)
    if _gestionale_sequenza_ok in sequenze:
        sequenze.remove(_gestionale_sequenza_ok)
        sequenze.insert(0, _gestionale_sequenza_ok)

    tentativi = []
    for apri, chiudi in sequenze:
        cmds = [f'<cmd>{apri}</cmd>']
        cmds += [f'<cmd>="/({r})</cmd>' for r in righe]
        cmds.append(f'<cmd>{chiudi}</cmd>')
        payload = ('<?xml version="1.0" encoding="UTF-8"?>\n<Service>\n'
                   + "\n".join(cmds) + '\n</Service>')
        current_app.logger.debug("PAYLOAD GESTIONALE (%s ... %s):\n%s", apri, chiudi, payload)

        try:
            resp = _rch_post(url, data=payload.encode("UTF-8"), headers=headers,
                                 timeout=15, **rch_kwargs)
        except Exception as exc:
            # Stampante irraggiungibile o in timeout: le altre varianti
            # fallirebbero allo stesso modo. Si esce subito, senza far
            # aspettare l'operatore per tre tentativi di rete.
            log_crm_error(
                "Documento gestionale non inviato (stampante irraggiungibile)",
                context={"operatore_id": operatore_id, "printer_ip": ip,
                         "printer_model": printer_model, "righe": righe,
                         "sequenza": f"{apri} ... {chiudi}", "exception": str(exc)},
                client_id=cliente_id,
            )
            return False, f"stampante non raggiungibile ({exc})"

        body = (resp.text or "")[:400]
        tentativi.append({"apri": apri, "chiudi": chiudi, "risposta": body})
        if _rch_is_success(resp):
            _gestionale_sequenza_ok = (apri, chiudi)
            current_app.logger.info(
                "Documento gestionale stampato con la sequenza %s ... %s (%d righe)",
                apri, chiudi, len(righe)
            )
            return True, f"{len(righe)} righe (sequenza {apri} ... {chiudi})"

        # Variante rifiutata: pulisci prima di provare la prossima, altrimenti
        # un'eventuale apertura a meta' resterebbe pendente sul registratore.
        current_app.logger.warning(
            "Documento gestionale rifiutato con %s ... %s: %s", apri, chiudi, body or "(vuoto)"
        )
        _rch_clear(ip, printer_model)

    log_crm_error(
        "Documento gestionale: nessuna variante di =o accettata dalla stampante",
        context={"operatore_id": operatore_id, "printer_ip": ip,
                 "printer_model": printer_model, "righe": righe,
                 "tentativi": tentativi},
        client_id=cliente_id,
    )
    return False, "nessuna variante del comando =o accettata (vedi log per le risposte)"


def _applica_movimenti_incasso(voci):
    """Movimenti che seguono un incasso registrato: ricarica e attivazione
    delle carte prepagate, rate dei pacchetti. Va chiamata UNA volta, solo
    dopo che lo scontrino e' stato registrato (in send_to_rch, oppure piu'
    tardi in rch_retry quando la stampante conferma uno scontrino rimasto da
    verificare). Ritorna (redirect_pacchetto_id, pacchetto_ids_modificati)."""
    redirect_pacchetto_id = None
    pacchetto_ids_modificati = set()
    
    # Processa TUTTE le voci per prepagata/rate (sia fiscali che non fiscali)
    for v in voci:
        # Gestione ricarica carta prepagata
        ricarica_prepagata_id = v.get('ricarica_prepagata_id')
        if ricarica_prepagata_id:
            try:
                pacchetto = Pacchetto.query.get(int(ricarica_prepagata_id))
                if pacchetto and pacchetto.tipo.value == 'prepagata':
                    importo = Decimal(str(v.get('ricarica_importo', 0)))
                    credito_da_caricare = Decimal(str(v.get('ricarica_credito', importo)))
                    descrizione = v.get('ricarica_descrizione', 'Ricarica')
                    
                    vecchio_saldo = pacchetto.credito_residuo or Decimal('0')
                    nuovo_saldo = vecchio_saldo + credito_da_caricare
                    pacchetto.credito_residuo = nuovo_saldo

                    # Torna Attiva se aveva credito a zero (era Completato,
                    # cioe' grigia in elenco) o se era ancora un Preventivo.
                    from appl.routes.pacchetti import riattiva_prepagata_se_ricaricata
                    riattiva_prepagata_se_ricaricata(pacchetto)
                    
                    from appl.models import MovimentoPrepagata
                    movimento = MovimentoPrepagata(
                        pacchetto_id=pacchetto.id,
                        tipo_movimento='ricarica',
                        importo=importo,
                        saldo_dopo=nuovo_saldo,
                        descrizione=descrizione
                    )
                    db.session.add(movimento)
                    db.session.commit()
                    current_app.logger.info(f"Ricarica prepagata {ricarica_prepagata_id}: +€{importo:.2f}, nuovo saldo €{nuovo_saldo:.2f}")
                    # IMPORTANTE: Salva ID per redirect
                    redirect_pacchetto_id = int(ricarica_prepagata_id)
            except Exception as e:
                current_app.logger.error(f"Errore ricarica prepagata {ricarica_prepagata_id}: {e}")

        # Gestione pagamento carta prepagata (ATTIVAZIONE)
        prepagata_id = v.get('prepagata_id')
        if prepagata_id:
            try:
                pacchetto = Pacchetto.query.get(int(prepagata_id))
                if pacchetto and pacchetto.tipo.value == 'prepagata':
                    credito = Decimal(str(v.get('credito_da_caricare', pacchetto.credito_iniziale)))
                    
                    pacchetto.credito_residuo = credito
                    pacchetto.status = PacchettoStatus.Attivo
                    
                    from appl.models import MovimentoPrepagata
                    movimento = MovimentoPrepagata(
                        pacchetto_id=pacchetto.id,
                        tipo_movimento='ricarica',
                        importo=credito,
                        saldo_dopo=credito,
                        descrizione='Caricamento iniziale (pagamento)'
                    )
                    db.session.add(movimento)
                    db.session.commit()
                    current_app.logger.info(f"Prepagata {prepagata_id} attivata con credito €{credito:.2f}")
                    # IMPORTANTE: Salva l'ID per redirect
                    redirect_pacchetto_id = int(prepagata_id)
            except Exception as e:
                current_app.logger.error(f"Errore attivazione prepagata {prepagata_id}: {e}")

        # Gestione rate pacchetto
        rata_id = v.get('rata_id')
        if rata_id:
            try:
                rata = PacchettoRata.query.get(int(rata_id))
                if rata and not rata.is_pagata:
                    importo_pagato = float(v.get('prezzo', 0))
                    importo_originale = float(rata.importo)
                    importo_modificato = abs(importo_pagato - importo_originale) > 0.01
                    
                    if importo_modificato:
                        rata.importo = importo_pagato
                        pacchetto_ids_modificati.add(rata.pacchetto_id)
                    
                    rata.is_pagata = True
                    rata.data_pagamento = datetime.now()
                    
                    pacchetto = rata.pacchetto
                    if pacchetto:
                        rata_num = next((i+1 for i, r in enumerate(pacchetto.rate) if r.id == rata.id), 0)
                        try:
                            history = json.loads(pacchetto.history) if pacchetto.history else []
                        except:
                            history = []
                        
                        if importo_modificato:
                            history.append({"ts": datetime.now().isoformat(), "azione": f"Pagata rata {rata_num} (importo modificato: €{importo_pagato:.2f})"})
                        else:
                            history.append({"ts": datetime.now().isoformat(), "azione": f"Pagata rata {rata_num}"})
                        pacchetto.history = json.dumps(history)
                        
                        if pacchetto.status.value not in ("completato", "eliminato"):
                            pacchetto.status = PacchettoStatus.Attivo
                    
                    db.session.commit()
                    current_app.logger.info(f"Rata {rata_id} marcata come pagata (importo: €{importo_pagato:.2f})")
            except Exception as e:
                current_app.logger.error(f"Errore marcatura rata {rata_id}: {e}")

    return redirect_pacchetto_id, pacchetto_ids_modificati

@cassa_bp.route('/cassa/send-to-rch', methods=['POST'])
def send_to_rch():
    data = request.get_json(force=True)
    voci = data.get("voci", [])

    def _is_fiscale(v):
        if not isinstance(v, dict):
            return True
        if "is_fiscale" in v:
            return bool(v.get("is_fiscale"))
        if "is_non_fiscale" in v:
            return not bool(v.get("is_non_fiscale"))
        return True

    voci_fiscali = [v for v in voci if _is_fiscale(v)]
    voci_non_fiscali = [v for v in voci if not _is_fiscale(v)]

    if voci_fiscali:
        idempotency_key = data.get("idempotency_key")
        if not idempotency_key:
            return jsonify({"error": "Missing idempotency_key for fiscal payments"}), 400
        if idempotency_key in IDEMPOTENCY_STORE:
            return jsonify(IDEMPOTENCY_STORE[idempotency_key])
    else:
        idempotency_key = None

    cliente_id = data.get("cliente_id")
    operatore_id = data.get("operatore_id")

    if not voci:
        return jsonify({"error": "Nessuna voce da registrare"}), 400
    
    # Variabile per tracciare redirect a pacchetto prepagata
    redirect_pacchetto_id = None
    
    # --- VALIDAZIONE E NORMALIZZAZIONE PREZZI: solo numeri >= 0 ---
    for idx, v in enumerate(voci, start=1):
        # ensure prezzo key exists and is numeric
        prezzo_raw = v.get("prezzo", 0)
        try:
            # accetta stringhe numeriche, numeri; vuoto -> 0
            prezzo_val = float(prezzo_raw) if prezzo_raw not in (None, "") else 0.0
        except Exception:
            return jsonify({"error": f"Prezzo non valido nella voce #{idx} ({v.get('nome') or 'sconosciuto'})."}), 400

        if prezzo_val < 0:
            return jsonify({"error": f"Prezzi negativi non consentiti nella voce #{idx} ({v.get('nome') or 'sconosciuto'})."}), 400

        # normalizza il prezzo nella voce (2 decimali)
        v["prezzo"] = round(prezzo_val, 2)

    # --- VOCI A ZERO SULLO SCONTRINO FISCALE ---
    # Una RIGA DI VENDITA a zero (=R1/$0) viene rifiutata dal registratore e
    # lascia il documento APERTO: da li' in poi ogni stampa fallisce finche' non
    # si chiude il documento a mano. Ma la voce a zero NON va persa: viene
    # stampata sullo scontrino come RIGA DESCRITTIVA (="/(testo), manuale PRINT!
    # sez. 11), che e' esattamente il promemoria per il cliente - compare sul
    # documento commerciale, senza importo e senza toccare i corrispettivi.
    # Serve pero' almeno una riga con importo positivo: un documento commerciale
    # di soli promemoria non esiste (nessun importo da pagare, nessun pagamento
    # da chiudere). In quel caso le voci a zero diventano non fiscali.
    # "Zero" va deciso negli stessi centesimi che vede la stampante, non in euro:
    # un prezzo di 0,004 risulterebbe positivo qui e diventerebbe poi =R1/$0 nel
    # payload, cioe' proprio la riga che il registratore rifiuta.
    def _centesimi(v):
        try:
            return int(round(float(v.get("prezzo", 0) or 0) * 100))
        except Exception:
            return 0

    zero_fiscali = [v for v in voci if _is_fiscale(v) and _centesimi(v) <= 0]
    ha_importi_positivi = any(_is_fiscale(v) and _centesimi(v) > 0 for v in voci)
    # Voci declassate a non fiscali perche' la bozza e' TUTTA a zero: vanno
    # comunque stampate, ma su un documento gestionale a parte (vedi sotto).
    voci_promemoria_zero = []
    for v in zero_fiscali:
        # Uno split di pagamento su un importo zero non ha significato.
        v.pop("pagamenti", None)
        if not ha_importi_positivi:
            v["is_fiscale"] = False
            v["is_non_fiscale"] = True
            v["metodo_pagamento"] = "contanti"
            voci_promemoria_zero.append(v)
            current_app.logger.info(
                "Voce a zero resa non fiscale (nessun importo positivo sullo scontrino): %s",
                v.get("nome") or v.get("servizio_id")
            )
        # NB: sulla riga promemoria il metodo di pagamento resta quello della
        # riga, altrimenti uno scontrino tutto POS con un promemoria forzato a
        # contanti risulterebbe "MIX" nel registro.

    # Ricalcola voci fiscali/non fiscali dopo normalizzazione prezzi
    voci_fiscali = [v for v in voci if _is_fiscale(v)]
    voci_non_fiscali = [v for v in voci if not _is_fiscale(v)]

    # --- SEDUTE SCALATE DA CARTA PREPAGATA ---
    # Non vanno MAI scontrinate: ne' alla stampante ne' nel registro scontrini.
    # Il pagamento e' gia' tracciato dal movimento sulla carta (endpoint
    # /pacchetti/api/pacchetti/<id>/utilizza, chiamato dalla cassa prima della
    # stampa) e al cliente arriva il WhatsApp col saldo aggiornato. Vale anche
    # quando la seduta scalata sta in uno scontrino con altre voci pagate.
    # ATTENZIONE: le RICARICHE della carta sono un'altra cosa - sono vendite a
    # tutti gli effetti, restano fiscali e non passano di qui.
    def _e_scalo_prepagata(v):
        return (v.get("metodo_pagamento") == "prepagata"
                and not v.get("ricarica_prepagata_id"))

    # Le sedute scalate RESTANO nel registro come record non fiscale a importo
    # zero: sono comunque passate dalla cassa e serve la traccia. Non vengono
    # tolte da voci_non_fiscali, quindi finiscono nel Receipt non fiscale.
    # Sullo scontrino compaiono come RIGA DESCRITTIVA, ma solo se il documento
    # esiste gia' per altri motivi: una seduta scalata non fa nascere uno
    # scontrino da sola (vedi il blocco fiscale piu' sotto).
    voci_scalo_prepagata = [v for v in voci_non_fiscali if _e_scalo_prepagata(v)]
    if voci_scalo_prepagata:
        current_app.logger.info(
            "Sedute scalate da prepagata registrate a zero (non fiscali): %s",
            ", ".join(str(v.get("nome") or v.get("servizio_id")) for v in voci_scalo_prepagata)
        )

    results = []
    oggi = datetime.now().date()

    # completa nomi servizi mancanti
    for v in voci:
        if not v.get("nome") and v.get("servizio_id"):
            srv = db.session.get(Service, v["servizio_id"])
            if srv:
                v["nome"] = srv.servizio_nome

    # =========================
    # 1. SCONTRINO FISCALE
    # =========================
    if voci_fiscali:
        ip, printer_model = _get_printer_config()
        if not ip:
            return jsonify({"error": "IP stampante RCH non configurato"}), 400

        # NOTA: nessun gate bloccante prima della stampa. L'avviso di eseguire la
        # chiusura (Z) viene dato all'APERTURA della cassa (vedi /cassa/chiusura-dovuta):
        # la stampa non viene mai impedita.

        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Service>'
        ]
        totali = {}  # tender RCH (es. "T1", "T4") -> centesimi

        # Righe promemoria in attesa: una riga descrittiva (="/(testo)) va emessa
        # a documento commerciale gia' aperto, e il documento si apre con la prima
        # riga di vendita. Se la voce a zero e' la prima della bozza, mandarla
        # subito significherebbe parlare a documento chiuso; quindi si accumula e
        # si scarica appena passa una riga con importo (che c'e' sempre: se non ci
        # fosse, le voci a zero sarebbero gia' state declassate a non fiscali).
        promemoria_pendenti = []
        vendita_emessa = False

        for v in voci_fiscali:
            srv = db.session.get(Service, v.get("servizio_id"))
            prezzo_pieno = float(srv.servizio_prezzo) if srv else float(v.get("prezzo", 0))
            prezzo_finale = float(v.get("prezzo", prezzo_pieno))
            prezzo_cents = int(round(prezzo_finale * 100))

            desc = (v.get("nome") or (srv.servizio_nome if srv else "Servizio"))[:32]
            desc = clean_str(html.unescape(desc)).replace(")", "").replace("(", "").replace("/", "-")

            if prezzo_cents <= 0:
                # PROMEMORIA: voce a zero stampata come riga descrittiva sul
                # documento commerciale (="/(testo), manuale PRINT! sez. 11, max
                # 25 caratteri). Compare sullo scontrino del cliente ma non e'
                # una vendita: nessun importo, nessun tender, corrispettivi
                # invariati. La riga di vendita a zero (=R/$0) sarebbe invece
                # rifiutata e lascerebbe il documento aperto.
                if vendita_emessa:
                    xml_lines.append(f'<cmd>="/({desc[:25]})</cmd>')
                else:
                    promemoria_pendenti.append(desc[:25])
                continue

            reparto = "R2" if getattr(srv, "servizio_sottocategoria", None) and \
                               srv.servizio_sottocategoria.nome.upper() == "PRODOTTI" else "R1"
            xml_lines.append(f'<cmd>={reparto}/${prezzo_cents}/({desc})</cmd>')

            if not vendita_emessa:
                # Documento ora aperto: si scaricano i promemoria arrivati prima.
                vendita_emessa = True
                for testo in promemoria_pendenti:
                    xml_lines.append(f'<cmd>="/({testo})</cmd>')
                promemoria_pendenti = []

            if prezzo_pieno > 0 and prezzo_finale < prezzo_pieno:
                sconto = 100 - (prezzo_finale / prezzo_pieno * 100)
                xml_lines.append(f'<cmd>="/(Scontato del {sconto:.2f}%)</cmd>')

            # Split pagamento: una singola voce puo' essere saldata con piu' metodi
            # (es. 50€ = 30 contanti + 20 POS). In tal caso 'pagamenti' contiene la
            # ripartizione; la riga merce resta stampata una sola volta, ma il totale
            # finisce su tender distinti. Se assente, comportamento storico (un metodo).
            pagamenti_split = v.get("pagamenti")
            if isinstance(pagamenti_split, list) and pagamenti_split:
                assegnati = 0
                for p in pagamenti_split:
                    cents_p = int(round(float(p.get("importo", 0)) * 100))
                    if cents_p <= 0:
                        continue
                    tcode_p = _tender_code(p.get("metodo", "cash"), printer_model)
                    totali[tcode_p] = totali.get(tcode_p, 0) + cents_p
                    assegnati += cents_p
                # eventuale arrotondamento: assegna il resto al primo tender valido
                diff = prezzo_cents - assegnati
                if diff != 0 and pagamenti_split:
                    tcode_first = _tender_code(pagamenti_split[0].get("metodo", "cash"), printer_model)
                    totali[tcode_first] = totali.get(tcode_first, 0) + diff
            else:
                metodo = v.get("metodo_pagamento", "cash")
                tcode = _tender_code(metodo, printer_model)
                totali[tcode] = totali.get(tcode, 0) + prezzo_cents

        def _voce_ha_digitale(v):
            if v.get("metodo_pagamento", "cash") in ("pos", "bank"):
                return True
            return any(
                p.get("metodo", "cash") in ("pos", "bank")
                for p in (v.get("pagamenti") or [])
            )

        # SEDUTE SCALATE DALLA CARTA sullo scontrino: righe descrittive a importo
        # zero, con lo stesso comando dei promemoria (="/(testo), max 25 char).
        # Non sono vendite - il cliente le ha gia' pagate comprando il credito -
        # quindi nessun reparto, nessun tender, corrispettivi invariati.
        # Si aggiungono SOLO se il documento e' gia' stato aperto da una riga di
        # vendita: una seduta scalata non fa nascere uno scontrino da sola.
        if vendita_emessa and voci_scalo_prepagata:
            for testo in _righe_promemoria(voci_scalo_prepagata, 25):
                xml_lines.append(f'<cmd>="/({testo})</cmd>')

        codice_lotteria = (data.get("lotteria") or "").strip().upper()
        pagamenti_digitali = any(_voce_ha_digitale(v) for v in voci_fiscali)
        if (
            len(codice_lotteria) == 8
            and codice_lotteria.isalnum()
            and pagamenti_digitali
        ):
            xml_lines.insert(2, f'<cmd>="/?L/$1/({codice_lotteria})</cmd>')

        if not totali or sum(totali.values()) <= 0:
            # Non deve accadere: le voci a zero sono gia' state gestite sopra
            # (promemoria o non fiscali). Se accade, NON si stampa: un pagamento
            # a zero (=T5/$0) verrebbe rifiutato lasciando il documento aperto
            # sul registratore, bloccando tutte le stampe successive.
            log_crm_error(
                "Stampa fiscale annullata: totale a zero",
                context={"operatore_id": operatore_id, "printer_ip": ip,
                         "printer_model": printer_model,
                         "promemoria_non_stampati": promemoria_pendenti,
                         "voci": [{"nome": v.get("nome"), "prezzo": v.get("prezzo")}
                                  for v in voci_fiscali]},
                client_id=cliente_id,
            )
            return jsonify({"error": "Scontrino fiscale a importo zero: nessun documento emesso."}), 400

        for tcode in ("T1", "T2", "T3", "T4", "T5"):
            if totali.get(tcode, 0) > 0:
                xml_lines.append(f'<cmd>={tcode}/${totali[tcode]}</cmd>')

        xml_lines.append('</Service>')
        payload_vendita = "\n".join(xml_lines)

        # --- STAMPA IL PAYLOAD NEL TERMINALE ---
        current_app.logger.debug("PAYLOAD XML INVIATO:\n%s", payload_vendita)

        # ip/printer_model gia' letti all'inizio del blocco fiscale
        url = _rch_url(ip, printer_model)
        headers = _rch_headers(printer_model)
        rch_kwargs = _rch_request_kwargs(printer_model)

        # expected_total e line_count usati sia per RCH_PENDING sia per il lazy recover
        expected_total = round(sum(float(v.get("prezzo", 0)) for v in voci_fiscali), 2)
        # Solo le righe con importo: le voci a zero sono righe descrittive, che
        # il parser DGFE non conta (cerca "IVA% importo"). Contarle sfaserebbe il
        # confronto con la DGFE nel lazy recover.
        expected_line_count = len([v for v in voci_fiscali if float(v.get("prezzo", 0) or 0) > 0])

        # ---------- conversazione con la RCH: UNA alla volta ----------
        # Dentro il lucchetto: contatore PRIMA dell'invio, sorte degli scontrini
        # rimasti da verificare, invio, conferma dal contatore. Fuori dal
        # lucchetto solo le scritture del risultato. Se la stampante e' impegnata
        # da un'altra richiesta oltre RCH_ATTESA_LIBERA_S: RchOccupata -> 409.
        # Tempi (RCH_*_S): al peggio ~10 s, poi la cassa sa cosa e' successo.
        t_inizio = pytime.monotonic()
        blocco_pendente = None
        esecuzione = None
        with _rch_in_uso():
            # Il contatore PRIMA dell'invio e' il termine di paragone che decide
            # se lo scontrino e' uscito (vedi _rch_esito). Senza, non si manda
            # niente: meglio uno scontrino non stampato che uno registrato senza
            # sapere se esiste.
            contatori_prima = _rch_leggi_contatori(url, headers, rch_kwargs)
            if contatori_prima is not None and not _rch_bloccata_prima_dell_invio(contatori_prima):
                blocco_pendente = _rch_risolvi_pendenti(contatori_prima)
                if blocco_pendente is None:
                    esecuzione = _rch_esegui_scontrino(url, headers, rch_kwargs,
                                                       payload_vendita, contatori_prima)
        totale_ms = int((pytime.monotonic() - t_inizio) * 1000)

        if contatori_prima is None:
            log_crm_error(
                "RCH non risponde prima della stampa: scontrino non inviato",
                context={"operatore_id": operatore_id, "printer_ip": ip,
                         "printer_model": printer_model, "expected_total": expected_total,
                         "attesa_ms": totale_ms},
                client_id=cliente_id,
            )
            return jsonify({"error": "La stampante non risponde: lo scontrino NON è stato "
                                     "inviato e NON è stato registrato. Controlla che sia accesa "
                                     "e col cavo di rete collegato; se lo è, spegnila e "
                                     "riaccendila. Poi premi di nuovo Stampa.",
                            "rch_non_risponde": True}), 502
        if _rch_bloccata_prima_dell_invio(contatori_prima):
            log_crm_error(
                "RCH bloccata prima della stampa (Z 0, Doc 0): scontrino non inviato",
                context={"operatore_id": operatore_id, "printer_ip": ip,
                         "printer_model": printer_model, "expected_total": expected_total,
                         "stato": contatori_prima.get("raw")},
                client_id=cliente_id,
            )
            return jsonify({"error": MSG_RCH_BLOCCATA_NON_INVIATO, "rch_bloccata": True}), 503
        if blocco_pendente is not None:
            corpo, stato_http = blocco_pendente
            return jsonify(corpo), stato_http

        def _build_pending_entry():
            adesso = pytime.time()
            return {
                "payload_xml": payload_vendita,
                "cliente_id": cliente_id,
                "operatore_id": operatore_id,
                "voci": voci_fiscali,
                # tutte le voci della richiesta: ricariche, attivazioni carta e
                # rate vanno applicate anche se lo scontrino viene confermato
                # piu' tardi dalla verifica (rch_retry) o dalla ristampa
                "voci_richiesta": voci,
                "contatori_prima": {"z": contatori_prima["z"], "doc": contatori_prima["doc"]},
                "created_ts": adesso,          # ultimo invio (si aggiorna a ogni ristampa)
                "primo_invio_ts": adesso,
                "expected_total": expected_total,
                "giorno": datetime.now().strftime("%Y-%m-%d"),
                "line_count": expected_line_count,
                "printer_ip": ip,
                "printer_model": printer_model
            }

        contatori_dopo = esecuzione["dopo"]
        current_app.logger.info(
            "RCH scontrino: esito=%s motivo=%s prima=%s/%s dopo=%s invio_ms=%s totale_ms=%s",
            esecuzione["esito"], esecuzione["motivo"], contatori_prima["z"], contatori_prima["doc"],
            (f"{contatori_dopo['z']}/{contatori_dopo['doc']}" if contatori_dopo else None),
            esecuzione["invio_ms"], totale_ms)

        contesto_log = {
            "idempotency_key": idempotency_key, "operatore_id": operatore_id,
            "printer_ip": ip, "printer_model": printer_model,
            "expected_total": expected_total, "motivo": esecuzione["motivo"],
            "invio_ms": esecuzione["invio_ms"], "totale_ms": totale_ms,
            "contatori_prima": {"z": contatori_prima["z"], "doc": contatori_prima["doc"]},
            "contatori_dopo": ({"z": contatori_dopo["z"], "doc": contatori_dopo["doc"]}
                               if contatori_dopo else None),
            "stato_dopo": (contatori_dopo or {}).get("raw"),
            "risposta_vendita": esecuzione["risposta"], "errcode": esecuzione["errcode"],
        }

        if esecuzione["esito"] == 'non_arrivato':
            # La connessione non si e' mai aperta: niente e' arrivato alla
            # stampante, niente stampato. Ristampare e' sicuro.
            log_crm_error("RCH: scontrino non arrivato alla stampante (connessione non riuscita)",
                          context=contesto_log, client_id=cliente_id)
            return jsonify({"error": "Lo scontrino NON è arrivato alla stampante (non risponde in "
                                     "rete): niente stampato, niente registrato. Controlla che sia "
                                     "accesa e col cavo collegato, poi premi di nuovo Stampa.",
                            "rch_non_risponde": True}), 502

        if esecuzione["esito"] != 'emesso':
            # NIENTE nel registro. Lo scontrino resta da verificare: la finestra
            # in cassa rilegge il contatore (rch_retry) e lo registra se e'
            # uscito; se non e' uscito offre la Ristampa (rch_ristampa).
            log_crm_error("Scontrino non confermato dalla stampante: nulla registrato",
                          context=contesto_log, client_id=cliente_id)
            RCH_PENDING[idempotency_key] = _build_pending_entry()
            return jsonify({
                "pending": True,
                "reason": esecuzione["motivo"],
                "message": _rch_messaggio_motivo(esecuzione),
                "idempotency_key": idempotency_key,
                "expected_total": expected_total,
                "retry_after": 2
            }), 202

        progressivo_completo = _rch_progressivo(contatori_dopo)

        # ---------- persiste Receipt ----------
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = expected_total,
            is_fiscale       = True,
            voci             = voci_fiscali,
            cliente_id       = cliente_id,
            operatore_id     = operatore_id,
            numero_progressivo = progressivo_completo  # stringa tipo 1825-0046
        )
        db.session.add(nuovo_receipt)
        db.session.commit()

        ids_pagati = [v.get("appointment_id") for v in voci_fiscali if v.get("appointment_id")]
        if ids_pagati:
            Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
            )
            db.session.commit()

        results.append({
            "message": f"Scontrino fiscale registrato (progressivo {progressivo_completo})",
            "is_fiscale": True
        })

    # =========================
    # 2. SCONTRINO NON FISCALE
    # =========================
    if voci_non_fiscali:
        ultimo = Receipt.query.filter(
            Receipt.created_at >= datetime.combine(oggi, datetime.min.time()),
            Receipt.created_at <= datetime.combine(oggi, datetime.max.time())
        ).order_by(Receipt.numero_progressivo.desc()).first()
        if not ultimo or not str(ultimo.numero_progressivo).isdigit():
            numero_progressivo = "1"
        else:
            numero_progressivo = str(int(ultimo.numero_progressivo) + 1)

        total_amount = round(sum(float(v.get("prezzo", 0)) for v in voci_non_fiscali), 2)
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = total_amount,
            is_fiscale       = False,
            voci             = voci_non_fiscali,
            cliente_id       = cliente_id,
            operatore_id     = operatore_id,
            numero_progressivo = numero_progressivo
        )
        db.session.add(nuovo_receipt)
        db.session.commit()

        ids_pagati = [v.get("appointment_id") for v in voci_non_fiscali if v.get("appointment_id")]
        if ids_pagati:
            Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
            )
            db.session.commit()

        results.append({
            "message": "Scontrino non fiscale registrato",
            "is_fiscale": False
        })

    # =========================
    # 2-bis. PROMEMORIA SU DOCUMENTO GESTIONALE (bozza tutta a zero)
    # =========================
    # Nessun documento commerciale e' stato emesso (nessun importo da incassare),
    # quindi le voci sono finite tra le non fiscali: senza questa stampa il
    # cliente non riceverebbe nulla. Non blocca la risposta - il record e' gia'
    # a database, un errore di stampa qui non deve far fallire l'incasso.
    if voci_promemoria_zero:
        # Rete di sicurezza: qualsiasi imprevisto qui dentro (helper, stampante,
        # parsing) non deve mai trasformarsi in un 500 e far credere alla cassa
        # che l'incasso sia fallito. Il Receipt e' gia' salvato.
        try:
            ok_gest, info_gest = _stampa_promemoria_gestionale(
                voci_promemoria_zero, cliente_id, operatore_id
            )
        except Exception as exc:
            current_app.logger.exception("Stampa promemoria gestionale fallita")
            ok_gest, info_gest = False, str(exc)
        results.append({
            "message": ("Promemoria stampato su documento gestionale (non fiscale)"
                        if ok_gest
                        else f"Promemoria NON stampato: {info_gest}"),
            "is_fiscale": False,
            "gestionale_ok": ok_gest
        })

    # Appuntamenti delle sedute scalate da prepagata: niente scontrino, ma vanno
    # comunque marcati PAGATO, altrimenti resterebbero aperti in Calendar.
    if voci_scalo_prepagata:
        _ids_prep = [v.get("appointment_id") for v in voci_scalo_prepagata if v.get("appointment_id")]
        if _ids_prep:
            try:
                Appointment.query.filter(Appointment.id.in_(_ids_prep)).update(
                    {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
                )
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception("Marcatura PAGATO sedute prepagata fallita")
        results.append({
            "message": f"{len(voci_scalo_prepagata)} sedute scalate da prepagata (nessuno scontrino emesso)",
            "is_fiscale": False,
            "scalo_prepagata": True
        })

    # IMPORTANTE: Gestione prepagata/rate PRIMA di costruire response
    # Deve essere FUORI dai blocchi fiscale/non fiscale perché le prepagate
    # possono essere in entrambi i casi
    redirect_pacchetto_id, pacchetto_ids_modificati = _applica_movimenti_incasso(voci)

    # Prepara response con info per redirect a pacchetto se necessario
    response = {"results": results, "reset_voci": True}

    # Verifica se il modulo pacchetti è abilitato per questo tenant
    _pacchetti_abilitati = True
    try:
        from appl.models import OWNER
        _owner_cfg = OWNER.query.first()
        if _owner_cfg:
            _pacchetti_abilitati = bool(_owner_cfg.module_pacchetti_enabled)
    except Exception:
        pass

    if _pacchetti_abilitati:
        # PRIORITA' 1: Redirect a prepagata se è stata attivata/ricaricata
        if redirect_pacchetto_id:
            response["redirect_to_pacchetto"] = redirect_pacchetto_id
            response["prepagata_attivata"] = True
            current_app.logger.info(f"Redirect impostato a prepagata {redirect_pacchetto_id}")
        # PRIORITA' 2: Se c'è un pacchetto con rata modificata
        elif pacchetto_ids_modificati:
            pacchetto_id = list(pacchetto_ids_modificati)[0]
            response["redirect_to_pacchetto"] = pacchetto_id
            response["rata_importo_modificato"] = True
        # PRIORITA' 3: Se c'era una rata, redirect al pacchetto
        elif any(v.get('rata_id') for v in voci):
            for v in voci:
                if v.get('rata_id'):
                    rata = PacchettoRata.query.get(int(v['rata_id']))
                    if rata:
                        response["redirect_to_pacchetto"] = rata.pacchetto_id
                        break
        # PRIORITA' 4: Cerca prepagata_id o ricarica nelle voci (fallback)
        if not response.get("redirect_to_pacchetto"):
            for v in voci:
                pid = v.get('prepagata_id') or v.get('ricarica_prepagata_id')
                if pid:
                    response["redirect_to_pacchetto"] = int(pid)
                    current_app.logger.info(f"Redirect fallback a prepagata {pid}")
                    break
    
    # Salva idempotency solo se non ci sono errori nei risultati
    if idempotency_key and not any("error" in str(r).lower() for r in results):
        IDEMPOTENCY_STORE[idempotency_key] = response
    return jsonify(response)

@cassa_bp.route('/cassa/registro-scontrini')
def registro_scontrini():
    # 1. Determina il giorno da visualizzare
    data_str = request.args.get('data')
    if data_str:
        try:
            giorno = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            giorno = date.today()
    else:
        giorno = date.today()

    # 2. Ottieni utente e ruolo
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    user_role = user.ruolo.value if user else None

    # 3. Carica scontrini del giorno (filtro per ruolo)
    giorno_start = datetime.combine(giorno, datetime.min.time())
    giorno_end = datetime.combine(giorno, datetime.max.time())
    
    # Include ANCHE le voci di allineamento DGFE (dummy ADJ-YYYYMMDD): sono fiscali,
    # concorrono ai totali e ora vengono mostrate come riga dedicata
    # ("ALLINEAMENTO DGFE") cosi' il totale del registro combacia col totale DGFE.
    if user_role == "user":
        scontrini = Receipt.query.filter(
            Receipt.is_fiscale == True,
            Receipt.created_at >= giorno_start,
            Receipt.created_at <= giorno_end,
        ).order_by(Receipt.created_at.asc()).all()
    else:
        scontrini = Receipt.query.filter(
            Receipt.created_at >= giorno_start,
            Receipt.created_at <= giorno_end,
        ).order_by(Receipt.created_at.asc()).all()

    # 4. Normalizza i dati di ogni scontrino
    for s in scontrini:
        s.is_fiscale = bool(s.is_fiscale)
        if isinstance(s.voci, str):
            try:
                s.voci = json.loads(s.voci)
            except Exception:
                s.voci = []
        if s.voci is None:
            s.voci = []
        # Voce di allineamento DGFE (dummy ADJ-YYYYMMDD): riga dedicata, NON e' uno
        # scontrino reale ne' uno storno.
        s.is_adjustment = bool(s.numero_progressivo and str(s.numero_progressivo).startswith('ADJ-'))
        if s.is_adjustment:
            s.display_numero_progressivo = 'ALLINEAMENTO DGFE'
        else:
            s.display_numero_progressivo = s.numero_progressivo
        s.annullato = False

    # 5. Separa scontrini positivi (originali) e negativi (storni).
    #    Le voci di allineamento DGFE (ADJ) sono escluse: non sono storni.
    storni = [s for s in scontrini if not s.is_adjustment and s.is_fiscale and s.total_amount is not None and float(s.total_amount) < 0]
    positivi = [s for s in scontrini if not s.is_adjustment and s.is_fiscale and s.total_amount is not None and float(s.total_amount) > 0]

    # 6. Per ogni storno, trova lo scontrino originale corrispondente
    progressivi_stornati = set()
    
    for storno in storni:
        # Riferimento esplicito, scritto dalla rettifica stessa (_voci_negative):
        # annullo o reso sanno quale documento stanno rettificando, non serve
        # indovinarlo. L'euristica sotto resta solo per le righe negative create
        # prima di questo riferimento.
        rif = None
        rif_tipo = None
        for v in (storno.voci or []):
            if isinstance(v, dict) and v.get('_rettifica_di'):
                rif = str(v.get('_rettifica_di'))
                rif_tipo = v.get('_rettifica_tipo')
                break
        if rif:
            storno.display_numero_progressivo = f"{'RESO' if rif_tipo == 'reso' else 'STORNO'} {rif}"
            progressivi_stornati.add(rif)
            continue

        candidati = [
            p for p in positivi
            if (
                p.operatore_id == storno.operatore_id
                and p.cliente_id == storno.cliente_id
                and abs(float(p.total_amount) - abs(float(storno.total_amount))) < 0.01
                and p.created_at < storno.created_at
            )
        ]

        if candidati:
            originale = max(candidati, key=lambda x: x.created_at)
            storno.display_numero_progressivo = f"STORNO {originale.numero_progressivo}"
            if originale.numero_progressivo:
                progressivi_stornati.add(str(originale.numero_progressivo))
        else:
            storno.display_numero_progressivo = f"STORNO {storno.numero_progressivo}"

    # 7. Marca come "annullato" SOLO gli scontrini il cui progressivo è stato stornato
    for s in scontrini:
        if not s.is_adjustment and s.is_fiscale and s.total_amount is not None and float(s.total_amount) > 0:
            if s.numero_progressivo and str(s.numero_progressivo) in progressivi_stornati:
                s.annullato = True

    # 7b. Ultimo scontrino fiscale del giorno: su quello la rettifica e' un
    #     ANNULLAMENTO, su tutti i precedenti e' un RESO (vedi
    #     _storna_scontrino_rch). Serve solo a etichettare il pulsante: la
    #     scelta dell'operazione resta del server.
    ultimo_fiscale_id = None
    if giorno == date.today():
        ultimo_stornabile = _ultimo_scontrino_stornabile()
        if ultimo_stornabile:
            ultimo_fiscale_id = ultimo_stornabile.id

    # 8. Riepilogo conciliazione DGFE per il giorno (solo informativo, no I/O stampante).
    #    Legge il log di riconciliazione gia' persistito (reconcile_day / Allinea a DGFE)
    #    cosi' l'utente vede SEMPRE se il registro fiscale quadra col DGFE, anche quando
    #    NON c'e' la riga "ALLINEAMENTO DGFE" perche' i totali gia' combaciano (delta 0).
    dgfe_recon = None
    if user_role in ('admin', 'owner'):
        try:
            registro_fiscale_total = round(
                sum(float(s.total_amount or 0) for s in scontrini if s.is_fiscale), 2
            )
            has_adj = any(getattr(s, 'is_adjustment', False) for s in scontrini)
            bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
            recon = _load_reconciliation_log(bi.id).get(giorno.strftime('%Y-%m-%d')) if bi else None

            dgfe_total = recon.get('dgfe_total') if recon else None
            dgfe_count = int(recon.get('dgfe_count') or 0) if recon else 0
            dgfe_total_f = float(dgfe_total) if dgfe_total is not None else None
            available = bool(recon) and dgfe_count > 0 and dgfe_total_f is not None
            aligned = available and abs(dgfe_total_f - registro_fiscale_total) < 0.01
            run_at = recon.get('run_at') if recon else None
            run_at_fmt = None
            if run_at:
                try:
                    run_at_fmt = datetime.fromisoformat(run_at).strftime('%d/%m/%Y %H:%M')
                except Exception:
                    run_at_fmt = run_at
            # SEMPRE valorizzato per admin/owner: se per il giorno non c'e' una lettura
            # DGFE nel log, mostriamo lo stato grigio "non ancora letto" (available=False).
            # Cosi' il badge e' SEMPRE visibile, non sparisce mai.
            dgfe_recon = {
                'available': available,
                'aligned': aligned,
                'has_adj': has_adj,
                'registro_total': registro_fiscale_total,
                'dgfe_total': dgfe_total_f,
                'dgfe_count': dgfe_count,
                'delta': round((dgfe_total_f - registro_fiscale_total), 2) if dgfe_total_f is not None else None,
                'run_at': run_at_fmt,
            }
        except Exception:
            current_app.logger.exception("registro_scontrini: riepilogo DGFE non calcolabile")
            dgfe_recon = None

    # 9. Render template
    return render_template(
        'registro_scontrini.html',
        scontrini=scontrini,
        giorno=giorno,
        user_role=user_role,
        date_today=date.today(),
        dgfe_recon=dgfe_recon,
        ultimo_fiscale_id=ultimo_fiscale_id,
    )

@cassa_bp.route('/cassa/api/receipt/<int:receipt_id>')
def api_receipt_detail(receipt_id):
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    s = db.session.get(Receipt, receipt_id)
    if not s:
        abort(404)
    # Filtro: se user e lo scontrino NON è fiscale, blocca l'accesso
    if user and user.ruolo.value == "user" and not s.is_fiscale:
        return jsonify({"error": "Non autorizzato"}), 403

    voci = s.voci
    if isinstance(voci, str):
        try:
            voci = json.loads(voci)
        except Exception:
            voci = []
    if voci is None:
        voci = []

    for v in voci:
        if not v.get("nome") and v.get("servizio_id"):
            servizio = db.session.get(Service, v["servizio_id"])
            if servizio:
                v["nome"] = servizio.servizio_nome

    return jsonify({
        "id": s.id,
        "created_at": s.created_at.strftime('%d/%m/%Y %H:%M:%S'),
        "is_fiscale": s.is_fiscale,
        "operatore": f"{s.operatore.user_nome} {s.operatore.user_cognome}" if s.operatore else "-",
        "cliente": f"{nome_proprio(s.cliente.cliente_nome)} {nome_proprio(s.cliente.cliente_cognome)}".strip() if s.cliente else "Generico",
        "voci": [
            {
                "nome": v.get('servizio_nome') or v.get('nome', ''),
                "prezzo": v.get('prezzo', 0),
                "metodo_pagamento": v.get('metodo_pagamento', ''),
                "is_non_fiscale": v.get('is_non_fiscale', False)
            } for v in (voci or [])
        ],
        "totale": s.total_amount,
        "totale_scontrinato": s.total_amount if s.is_fiscale else 0
    })

def ripristina_rate_da_scontrino(scontrino):
    """Ripristina le rate pacchetto associate a uno scontrino stornato/eliminato"""
    if not scontrino or not scontrino.voci:
        return
    
    voci = scontrino.voci
    if isinstance(voci, str):
        try:
            voci = json.loads(voci)
        except:
            voci = []
    
    for v in voci:
        rata_id = v.get('rata_id')
        if rata_id:
            try:
                rata = db.session.get(PacchettoRata, int(rata_id))
                if rata and rata.is_pagata:
                    rata.is_pagata = False
                    rata.data_pagamento = None
                    # Ricalcola status pacchetto
                    pacchetto = rata.pacchetto
                    if pacchetto and pacchetto.status == PacchettoStatus.Attivo:
                        # Verifica se ci sono ancora rate pagate o sedute effettuate
                        ha_rata_pagata = any(r.is_pagata for r in pacchetto.rate if r.id != rata.id)
                        ha_seduta_effettuata = any(s.stato == 4 for s in pacchetto.sedute)
                        if not ha_rata_pagata and not ha_seduta_effettuata:
                            pacchetto.status = PacchettoStatus.Preventivo
                    current_app.logger.info(f"Rata {rata_id} ripristinata (non pagata)")
            except Exception as e:
                current_app.logger.error(f"Errore ripristino rata {rata_id}: {e}")
    
    db.session.commit()

@cassa_bp.route('/cassa/api/receipt/<int:id>', methods=['DELETE'])
def api_receipt_delete(id):
    try:
        scontrino = db.session.get(Receipt, id)
        if not scontrino:
            abort(404)
        
        # Controllo ruolo: solo ADMIN/OWNER
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or user.ruolo.value not in ["admin", "owner"]:
            return jsonify({"error": "Non autorizzato: solo amministratori possono eliminare scontrini"}), 403
        
        oggi = datetime.now().date()
        data_scontrino = scontrino.created_at.date() if scontrino.created_at else None
        
        if scontrino.is_fiscale:
            if data_scontrino != oggi:
                return jsonify({"error": "Eliminazione possibile solo per scontrini fiscali del giorno corrente"}), 400

            # Storno fiscale: percorso unico, identico a "annulla ultimo scontrino"
            # e identico per RCH Print 3.0 RT e RCH Print F. Ripristina anche le
            # rate pacchetto, ma solo a storno confermato dal registratore.
            storno_result = _storna_scontrino_rch(scontrino)
            if "error" in storno_result:
                return jsonify({"error": f"Storno fallito: {storno_result['error']}"}), storno_result.get("status", 400)

            # NON eliminare lo scontrino originale: la voce negativa e' gia' stata
            # registrata da _storna_scontrino_rch.
            return '', 204

        # Per non fiscali, ripristina rate prima di eliminare
        ripristina_rate_da_scontrino(scontrino)
        
        # Per non fiscali, puoi continuare a eliminare
        db.session.delete(scontrino)
        db.session.commit()
        return '', 204
    except Exception as e:
        current_app.logger.error("Errore eliminazione scontrino %s: %s", id, str(e))
        return jsonify({"error": "Errore durante l'eliminazione"}), 400
    
@cassa_bp.route('/cassa/api/receipt/<int:receipt_id>/update-metodo', methods=['POST'])
def update_metodo_pagamento(receipt_id):
    scontrino = db.session.get(Receipt, receipt_id)
    if not scontrino:
        abort(404)
    data = request.get_json()
    metodi = data.get('metodi')
    voci = scontrino.voci
    if isinstance(voci, str):
        voci = json.loads(voci)
    if not isinstance(voci, list) or not isinstance(metodi, list) or len(metodi) != len(voci):
        return jsonify({'error': 'Dati non validi'}), 400
    for idx, metodo in enumerate(metodi):
        voci[idx]['metodo_pagamento'] = metodo
    scontrino.voci = voci
    flag_modified(scontrino, "voci")
    db.session.commit()
    return jsonify({'success': True})

def _run_post_z_reconciliation(max_attempts=6, settle_s=1.5, retry_sleep_s=2.5):
    """Esegue reconcile_day(today) usando la BusinessInfo corrente, DOPO la chiusura
    fiscale (Z). Subito dopo la Z la stampante puo' essere ancora occupata (invio
    corrispettivi all'AdE, finalizzazione DGFE): una singola lettura DGFE puo'
    fallire o tornare vuota, e in quel caso l'allineamento (dummy ADJ-YYYYMMDD che
    fa combaciare il totale del registro col totale DGFE) NON verrebbe applicato.

    Per questo riproviamo con una breve attesa finche' l'allineamento risulta
    effettivamente applicato (action created/updated/noop/deleted). Cosi' i
    Corrispettivi combaciano col DGFE in automatico, senza correzioni manuali.

    Best-effort: non solleva mai eccezioni al chiamante. Ritorna il summary o None.
    """
    try:
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        if not bi:
            return None

        # Piccola attesa iniziale: lascia che la Z si finalizzi prima di leggere il DGFE.
        if settle_s and settle_s > 0:
            pytime.sleep(settle_s)

        summary = None
        # action "buone" = allineamento applicato (o gia' allineato / niente da fare).
        good_actions = ("created", "updated", "noop", "deleted")
        # Statuti di lettura DGFE considerati affidabili.
        reliable_statuses = ("ok", "ej_empty", "ej_no_blocks")
        for attempt in range(1, max_attempts + 1):
            summary = reconcile_day(date.today(), bi)
            action = (summary or {}).get("alignment_action")
            diag = (summary or {}).get("dgfe_diagnostic") or {}
            dgfe_status = diag.get("status")
            dgfe_count = (summary or {}).get("dgfe_count") or 0
            current_app.logger.info(
                "post-Z reconciliation tentativo %d/%d: alignment=%s dgfe_status=%s dgfe_count=%s delta=%s",
                attempt, max_attempts, action, dgfe_status,
                dgfe_count, (summary or {}).get("alignment_delta")
            )
            if action in good_actions:
                break
            # Lettura affidabile ma giorno legittimamente vuoto (0 scontrini):
            # non c'e' nulla da allineare, inutile ritentare.
            if dgfe_status in reliable_statuses and dgfe_count == 0:
                break
            # Lettura DGFE non affidabile o vuota (stampante ancora occupata):
            # aspetta e riprova, tranne all'ultimo tentativo.
            if attempt < max_attempts:
                pytime.sleep(retry_sleep_s)

        if summary and summary.get("alignment_action") not in good_actions:
            current_app.logger.warning(
                "post-Z reconciliation: allineamento DGFE NON applicato dopo %d tentativi "
                "(alignment=%s). Il totale del registro potrebbe non combaciare col DGFE; "
                "usare 'Carica DGFE'/'Correggi' nei Corrispettivi.",
                max_attempts, summary.get("alignment_action")
            )
        return summary
    except Exception as exc:
        try:
            current_app.logger.error("Reconciliation post-Z fallita: %s", str(exc))
        except Exception:
            pass
        return None

@cassa_bp.route('/cassa/dgfe-total', methods=['GET'])
def dgfe_total_for_day():
    """Ritorna il totale fiscale letto dal DGFE della stampante per un singolo giorno.
    Solo owner. Usa lo stesso meccanismo di /cassa/api/dgfe (comando =C452).
    Query: ?day=YYYY-MM-DD
    Response: {date, dgfe_total, dgfe_count, status, http_status, body_len, error}
    """
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        day_str = (request.args.get('day') or '').strip()
        if not day_str:
            return jsonify({"error": "Parametro day mancante"}), 400
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400

        ip, _ = _get_printer_config()
        if not ip:
            return jsonify({"error": "IP stampante non configurato"}), 400

        entries, diag = _dgfe_entries_with_diag(ip, day)
        total = round(sum(float(e.get("totale_float", 0) or 0) for e in entries), 2)

        # Persisti la lettura in DB (anche se e' solo un "Carica DGFE"/check), cosi'
        # il badge del Registro Scontrini la riflette. Solo se la lettura e' affidabile.
        if diag.get("status") in ("ok", "ej_empty", "ej_no_blocks"):
            _persist_dgfe_reading(
                day, total, len(entries),
                status="checked",
                notes="Lettura DGFE da 'Carica DGFE' (Corrispettivi).",
            )

        return jsonify({
            "date": day_str,
            "dgfe_total": total,
            "dgfe_count": len(entries),
            "status": diag.get("status"),
            "http_status": diag.get("http_status"),
            "body_len": diag.get("body_len"),
            "error": diag.get("error"),
        })
    except Exception as exc:
        try:
            current_app.logger.exception("dgfe-total: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


CORREGGI_DAY_THRESHOLD = 0.15  # 15% sul totale DGFE: sopra → verifica rinforzata richiesta


def _adj_progressivo_for_day(day_date):
    """Progressivo univoco per la dummy ADJ del giorno: 'ADJ-YYYYMMDD'."""
    return f"ADJ-{day_date.strftime('%Y%m%d')}"


def _db_receipts_for_day_no_adj(day_date):
    """Tutti i Receipt fiscali del giorno escludendo le dummy ADJ-*."""
    day_start = datetime.combine(day_date, datetime.min.time())
    day_end = datetime.combine(day_date, datetime.max.time())
    return Receipt.query.filter(
        Receipt.created_at >= day_start,
        Receipt.created_at <= day_end,
        Receipt.is_fiscale == True,
        or_(Receipt.numero_progressivo.is_(None),
            ~Receipt.numero_progressivo.like('ADJ-%'))
    ).order_by(Receipt.created_at.asc()).all()


def _correggi_day_compute(day_date):
    """Calcola tutto cio' che serve per Correggi su un giorno:
    DGFE total/entries, DB total/entries (no ADJ), delta, soglia, eventuale ADJ esistente.
    Ritorna dict (errore -> 'error', altrimenti dati)."""
    ip, _ = _get_printer_config()
    if not ip:
        return {"error": "IP stampante non configurato"}

    entries, diag = _dgfe_entries_with_diag(ip, day_date)
    if not diag or diag.get("status") not in ("ok", "ej_empty", "ej_no_blocks"):
        return {
            "error": f"Lettura DGFE non affidabile ({diag.get('status') if diag else 'unknown'})."
                     " Riprova fra qualche secondo o controlla la stampante."
        }

    dgfe_total = round(sum(float(e.get("totale_float", 0) or 0) for e in entries), 2)
    dgfe_count = len(entries)

    db_receipts = _db_receipts_for_day_no_adj(day_date)
    db_total = round(sum(float(r.total_amount or 0) for r in db_receipts), 2)
    db_count = len(db_receipts)

    delta = round(dgfe_total - db_total, 2)
    # Soglia in valore assoluto rispetto al DGFE; se DGFE = 0 trattiamo come "fuori soglia"
    if dgfe_total > 0:
        rel = abs(delta) / dgfe_total
    else:
        rel = 1.0 if abs(delta) > 0.01 else 0.0
    needs_strong = (rel > CORREGGI_DAY_THRESHOLD)

    adj_prog = _adj_progressivo_for_day(day_date)
    existing_adj = Receipt.query.filter_by(numero_progressivo=adj_prog).first()

    # Persisti la lettura DGFE del giorno in DB (questa funzione e' usata da 'Allinea a
    # DGFE' anteprima/reale e da 'Correggi'): cosi' anche un semplice check dai
    # Corrispettivi popola la riconciliazione vista nel Registro Scontrini.
    _persist_dgfe_reading(
        day_date, dgfe_total, dgfe_count, db_total=db_total,
        status="checked", notes="Lettura DGFE da Corrispettivi.",
    )

    return {
        "ok": True,
        "date": day_date.strftime("%Y-%m-%d"),
        "dgfe_total": dgfe_total,
        "dgfe_count": dgfe_count,
        "db_total": db_total,
        "db_count": db_count,
        "delta": delta,
        "relative": round(rel * 100, 2),
        "threshold_pct": round(CORREGGI_DAY_THRESHOLD * 100, 2),
        "needs_strong_verification": needs_strong,
        "dgfe_safe": (dgfe_count > 0),  # se 0, blocchiamo
        "existing_adj_total": float(existing_adj.total_amount) if existing_adj else None,
        "dgfe_entries": [
            {
                "progressivo": e.get("progressivo_raw"),
                "dataora": e["dataora_dt"].strftime("%H:%M") if e.get("dataora_dt") else "",
                "totale": float(e.get("totale_float", 0) or 0),
                "line_count": e.get("line_count", 0),
            }
            for e in entries
        ],
        "db_entries": [
            {
                "id": r.id,
                "numero_progressivo": str(r.numero_progressivo) if r.numero_progressivo else "",
                "dataora": r.created_at.strftime("%H:%M") if r.created_at else "",
                "totale": float(r.total_amount or 0),
                "voci_count": len(r.voci) if isinstance(r.voci, list) else 0,
            }
            for r in db_receipts
        ],
    }


def _set_day_alignment_adj(day_date, dgfe_total):
    """Allinea il totale fiscale del giorno in DB al totale DGFE in modo ADDITIVO
    e reversibile: crea/aggiorna/elimina la dummy ADJ-YYYYMMDD col delta, senza
    toccare gli scontrini reali (cliente/operatore/voci restano intatti).

    Risultato garantito: somma scontrini reali del giorno + ADJ == dgfe_total.
    Ritorna (action, delta) con action in {created, updated, deleted, noop}.
    Esegue il commit. In caso di errore solleva (gestire dal chiamante).
    """
    db_receipts = _db_receipts_for_day_no_adj(day_date)
    db_total = round(sum(float(r.total_amount or 0) for r in db_receipts), 2)
    delta = round(float(dgfe_total or 0.0) - db_total, 2)

    adj_prog = _adj_progressivo_for_day(day_date)
    existing = Receipt.query.filter_by(numero_progressivo=adj_prog).first()
    adj_dt = datetime.combine(day_date, datetime.min.time().replace(hour=23, minute=59))

    if abs(delta) < 0.01:
        # Gia' allineato: rimuovo eventuale ADJ residua di una correzione precedente.
        if existing:
            db.session.delete(existing)
            db.session.commit()
            return ("deleted", delta)
        return ("noop", delta)

    voci = [{
        "_dummy_adjustment": True,
        "reason": "Allineamento DGFE",
        "applied_at": datetime.now().isoformat(timespec='seconds'),
        "delta": delta
    }]
    if existing:
        existing.total_amount = delta
        existing.created_at = adj_dt
        existing.voci = voci
        flag_modified(existing, "voci")
        db.session.commit()
        return ("updated", delta)

    new_adj = Receipt(
        created_at=adj_dt,
        total_amount=delta,
        is_fiscale=True,
        voci=voci,
        cliente_id=None,
        operatore_id=None,
        numero_progressivo=adj_prog
    )
    db.session.add(new_adj)
    db.session.commit()
    return ("created", delta)


@cassa_bp.route('/cassa/correggi-day/preview', methods=['GET'])
def correggi_day_preview():
    """Anteprima per il bottone Correggi: confronto DGFE vs DB per un giorno.
    Owner-only. Query: ?day=YYYY-MM-DD"""
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        day_str = (request.args.get('day') or '').strip()
        if not day_str:
            return jsonify({"error": "Parametro day mancante"}), 400
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400

        result = _correggi_day_compute(day)
        if result.get("error"):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as exc:
        try:
            current_app.logger.exception("correggi-day/preview: errore")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


@cassa_bp.route('/cassa/correggi-day/apply', methods=['POST'])
def correggi_day_apply():
    """Applica la correzione: crea/aggiorna/elimina la dummy ADJ-YYYYMMDD.
    Body: {date: 'YYYY-MM-DD', confirmed_delta?: float}
    Se la discrepanza supera la soglia, confirmed_delta DEVE corrispondere al delta calcolato.
    Owner-only."""
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        data = request.get_json(force=True, silent=True) or {}
        day_str = (data.get("date") or "").strip()
        if not day_str:
            return jsonify({"error": "Parametro date mancante"}), 400
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400

        result = _correggi_day_compute(day)
        if result.get("error"):
            return jsonify(result), 400

        if not result["dgfe_safe"]:
            return jsonify({
                "error": "DGFE vuoto o non leggibile per quel giorno: correzione bloccata. "
                         "Verifica manualmente prima di procedere."
            }), 400

        delta = result["delta"]
        if result["needs_strong_verification"]:
            confirmed = data.get("confirmed_delta")
            if confirmed is None:
                return jsonify({
                    "error": "Discrepanza oltre soglia: serve conferma esplicita.",
                    "preview": result
                }), 409
            try:
                confirmed_f = round(float(confirmed), 2)
            except (TypeError, ValueError):
                return jsonify({"error": "confirmed_delta non numerico"}), 400
            if abs(confirmed_f - delta) > 0.01:
                return jsonify({
                    "error": f"confirmed_delta {confirmed_f} non corrisponde al delta calcolato {delta}",
                    "preview": result
                }), 409

        try:
            # Allineamento additivo: l'helper porta (scontrini reali + ADJ) == DGFE.
            action, _applied = _set_day_alignment_adj(day, result["dgfe_total"])
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error("correggi-day/apply: scrittura DB fallita: %s", str(exc))
            return jsonify({"error": f"Errore scrittura DB: {exc}"}), 500

        # PERSISTENZA (come 'Allinea a DGFE'): scrivi l'esito nel log di
        # riconciliazione cosi' la colonna DGFE del report resta valorizzata col
        # totale fiscale corretto anche dopo ricarica/logout. Senza questo, la
        # correzione modificava solo gli scontrini (dummy ADJ) ma la colonna
        # continuava a mostrare il vecchio valore (es. 0 dopo una doppia Z
        # mattutina), facendo sembrare che "Correggi" non avesse funzionato.
        try:
            bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
            if bi is not None:
                _set_reconciliation_entry(bi.id, day_str, {
                    "status": "fixed" if action in ("created", "updated", "deleted") else "ok",
                    "date": day_str,
                    "run_at": datetime.now().isoformat(timespec='seconds'),
                    "dgfe_count": result["dgfe_count"],
                    "db_count": result["db_count"],
                    "dgfe_total": result["dgfe_total"],
                    # Dopo l'allineamento il totale fiscale del giorno == DGFE.
                    "db_total": result["dgfe_total"],
                    "created_orphans": 0,
                    "suspicious_extras": [],
                    "notes": f"Corretto a DGFE da 'Correggi' (delta {delta:+.2f}).",
                })
        except Exception:
            current_app.logger.warning("correggi-day/apply: log recon non scritto per %s", day_str)

        # Ricalcola lo stato post-correzione
        post = _correggi_day_compute(day)
        return jsonify({
            "ok": True,
            "action": action,
            "applied_delta": delta,
            "post": post,
        })
    except Exception as exc:
        try:
            current_app.logger.exception("correggi-day/apply: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


@cassa_bp.route('/cassa/dgfe-align-range', methods=['POST'])
def dgfe_align_range():
    """Allinea (e SALVA) il totale fiscale del DB al DGFE per ogni giorno del range.

    E' l'azione dietro al pulsante "Carica DGFE": per ogni giorno legge il totale
    dalla DGFE della stampante RCH e, se diverso dal totale registrato in DB, crea/
    aggiorna la voce fiscale di allineamento ADJ-YYYYMMDD (additiva e reversibile)
    cosi' che (scontrini reali + ADJ) == DGFE. La voce e' is_fiscale=True quindi
    rientra nei corrispettivi del CRM: il dato corretto persiste fra le sessioni.

    Sicurezza fiscale: NON azzera giorni con DGFE vuoto/illeggibile (dgfe_safe=False)
    e salta i giorni futuri. Solo owner/admin, solo on-premise (stampante in LAN).
    Body JSON: {dateFrom, dateTo}
    """
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        ip, _ = _get_printer_config()
        if not ip:
            return jsonify({"error": "IP stampante non configurato"}), 400

        data = request.get_json(force=True, silent=True) or {}
        date_from = (data.get("dateFrom") or "").strip()
        date_to = (data.get("dateTo") or "").strip()
        # dry_run=True: legge la DGFE e calcola i delta SENZA scrivere nulla.
        # Serve ad alimentare il modal di conferma prima del salvataggio.
        dry_run = bool(data.get("dry_run", False))
        if not date_from or not date_to:
            return jsonify({"error": "Date non valide"}), 400
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400
        if d_to < d_from:
            return jsonify({"error": "dateTo precede dateFrom"}), 400
        if (d_to - d_from).days > 366:
            return jsonify({"error": "Range troppo ampio (max 366 giorni)"}), 400

        # Business per il log di riconciliazione (serve solo al salvataggio reale).
        bi = None
        if not dry_run:
            bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()

        today = date.today()
        results = []
        corrected = 0
        skipped_future = 0
        skipped_unsafe = 0
        cur = d_from
        while cur <= d_to:
            day_str = cur.strftime("%Y-%m-%d")
            # Non leggere/correggere il futuro
            if cur > today:
                skipped_future += 1
                results.append({"date": day_str, "status": "skipped_future"})
                cur += timedelta(days=1)
                continue

            comp = _correggi_day_compute(cur)
            if comp.get("error"):
                # Lettura DGFE inaffidabile: NON tocchiamo il DB, segnaliamo.
                results.append({
                    "date": day_str,
                    "status": "unreadable",
                    "error": comp.get("error"),
                })
                cur += timedelta(days=1)
                continue

            if not comp.get("dgfe_safe"):
                # DGFE vuoto (0 scontrini): non azzeriamo dati validi del DB.
                skipped_unsafe += 1
                results.append({
                    "date": day_str,
                    "status": "skipped_empty_dgfe",
                    "dgfe_total": comp.get("dgfe_total", 0.0),
                    "dgfe_count": comp.get("dgfe_count", 0),
                    "db_total": comp.get("db_total", 0.0),
                })
                cur += timedelta(days=1)
                continue

            if dry_run:
                # Anteprima: nessuna scrittura. Comunichiamo cosa cambierebbe.
                will_change = abs(comp["delta"]) >= 0.01
                if will_change:
                    corrected += 1
                results.append({
                    "date": day_str,
                    "status": "preview",
                    "will_change": will_change,
                    "delta": comp["delta"],
                    "dgfe_total": comp["dgfe_total"],
                    "dgfe_count": comp["dgfe_count"],
                    "db_total_before": comp["db_total"],
                })
                cur += timedelta(days=1)
                continue

            try:
                action, applied = _set_day_alignment_adj(cur, comp["dgfe_total"])
            except Exception as exc:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                current_app.logger.error("dgfe-align-range: scrittura DB fallita su %s: %s", day_str, str(exc))
                results.append({"date": day_str, "status": "error", "error": str(exc)})
                cur += timedelta(days=1)
                continue

            if action in ("created", "updated", "deleted"):
                corrected += 1
            current_app.logger.info(
                "dgfe-align-range: %s action=%s delta=%.2f dgfe=%.2f",
                day_str, action, comp["delta"], comp["dgfe_total"]
            )
            # Persisti l'esito nel log di riconciliazione cosi' la colonna DGFE
            # resta valorizzata (verde) anche dopo ricarica/logout.
            if bi is not None:
                try:
                    _set_reconciliation_entry(bi.id, day_str, {
                        "status": "fixed" if action in ("created", "updated", "deleted") else "ok",
                        "date": day_str,
                        "run_at": datetime.now().isoformat(timespec='seconds'),
                        "dgfe_count": comp["dgfe_count"],
                        "db_count": comp["db_count"],
                        "dgfe_total": comp["dgfe_total"],
                        # Dopo l'allineamento il totale fiscale del giorno == DGFE.
                        "db_total": comp["dgfe_total"],
                        "created_orphans": 0,
                        "suspicious_extras": [],
                        "notes": f"Allineato a DGFE da 'Allinea a DGFE' (delta {comp['delta']:.2f})",
                    })
                except Exception:
                    current_app.logger.warning("dgfe-align-range: log recon non scritto per %s", day_str)
            results.append({
                "date": day_str,
                "status": "aligned",
                "action": action,
                "delta": comp["delta"],
                "dgfe_total": comp["dgfe_total"],
                "dgfe_count": comp["dgfe_count"],
                # Totale fiscale del giorno DOPO l'allineamento == DGFE.
                "db_total": comp["dgfe_total"],
            })
            cur += timedelta(days=1)

        return jsonify({
            "ok": True,
            "dry_run": dry_run,
            "processed": len(results),
            "corrected": corrected,
            "skipped_future": skipped_future,
            "skipped_empty_dgfe": skipped_unsafe,
            "results": results,
        })
    except Exception as exc:
        try:
            current_app.logger.exception("dgfe-align-range: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


@cassa_bp.route('/cassa/reconcile-range', methods=['POST'])
def reconcile_range():
    """Riconciliazione retroattiva su un range di date (solo owner).
    Body JSON: {dateFrom: 'YYYY-MM-DD', dateTo: 'YYYY-MM-DD', only_pending: bool}
    Esegue reconcile_day per ogni giorno del range.
    Se only_pending=True (default), salta i giorni che hanno gia' una entry diversa da 'pending'/'error'.
    """
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        data = request.get_json(force=True, silent=True) or {}
        date_from = (data.get("dateFrom") or "").strip()
        date_to = (data.get("dateTo") or "").strip()
        only_pending = bool(data.get("only_pending", True))
        if not date_from or not date_to:
            return jsonify({"error": "Date non valide"}), 400
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400
        if d_to < d_from:
            return jsonify({"error": "dateTo precede dateFrom"}), 400
        # Limite di sicurezza: max 366 giorni in un singolo range
        if (d_to - d_from).days > 366:
            return jsonify({"error": "Range troppo ampio (max 366 giorni)"}), 400

        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        if not bi:
            return jsonify({"error": "BusinessInfo non configurata"}), 400

        # Le letture DGFE sono ora persistite in DB (tabella dgfe_readings), nessuna
        # cartella file da verificare.
        log_pre = _load_reconciliation_log(bi.id)

        today = date.today()
        results = []
        skipped_future = 0
        skipped_already_done = 0
        cur = d_from
        while cur <= d_to:
            # Non riconciliare il futuro
            if cur > today:
                skipped_future += 1
                cur += timedelta(days=1)
                continue
            if only_pending:
                existing = log_pre.get(cur.strftime("%Y-%m-%d"))
                if existing and existing.get('status') in ('ok', 'fixed', 'discrepant'):
                    skipped_already_done += 1
                    cur += timedelta(days=1)
                    continue
            try:
                summary = reconcile_day(cur, bi)
                results.append({
                    "date": cur.strftime("%Y-%m-%d"),
                    "status": summary.get("status"),
                    "created_orphans": summary.get("created_orphans", 0),
                    "suspicious_extras": len(summary.get("suspicious_extras", []) or []),
                })
            except Exception as exc:
                current_app.logger.error("reconcile-range: errore su %s: %s", cur, str(exc))
                results.append({"date": cur.strftime("%Y-%m-%d"), "status": "error", "error": str(exc)})
            cur += timedelta(days=1)

        return jsonify({
            "ok": True,
            "processed": len(results),
            "skipped_future": skipped_future,
            "skipped_already_done": skipped_already_done,
            "results": results
        })
    except Exception as exc:
        try:
            current_app.logger.exception("reconcile-range: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500

@cassa_bp.route('/cassa/chiusura-dovuta', methods=['GET'])
def chiusura_dovuta():
    """Check SOLO su DB (niente stampante, niente DGFE) da chiamare all'APERTURA della cassa.

    Regola: se IERI il negozio era chiuso, avvisa di eseguire la chiusura fiscale (Z)
    prima di battere scontrini. "Chiuso" significa, indifferentemente:
      - giorno di chiusura SETTIMANALE (BusinessInfo.closing_days), oppure
      - NESSUNA ATTIVITA' in calendario: ne' appuntamenti reali ne' celle attive (i
        blocchi OFF/dummy non contano). Copre le festivita' infrasettimanali (25 aprile,
        2 giugno...) che NON sono segnate fra i closing_days.

    Il registro `fiscal_closures` viene consultato solo per NON avvisare quando la Z
    risulta gia' fatta, ma e' un di piu': se la tabella manca o la lettura fallisce,
    l'avviso viene mostrato lo stesso (meglio un avviso in piu' che un silenzio: e' un
    avviso, non un blocco). La visualizzazione "una sola volta al giorno" e' gestita lato
    client (primo accesso alla cassa).
    """
    today = date.today()
    try:
        was_closed, closure_reason = _previous_day_was_closure(today)
    except Exception as exc:
        current_app.logger.warning("chiusura-dovuta: check giorno precedente fallito: %s", str(exc))
        return jsonify({"warning": False, "reason": "error", "today": today.isoformat()})

    if not was_closed:
        return jsonify({"warning": False, "reason": closure_reason, "today": today.isoformat()})

    # Z gia' registrata da ieri in poi? Best-effort: qualunque problema qui NON silenzia
    # l'avviso (a differenza di prima, dove un'eccezione lo faceva sparire per sempre).
    yesterday = today - timedelta(days=1)
    try:
        from appl.models import FiscalClosure
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        bid = bi.id if bi else 0
        z = db.session.query(FiscalClosure.id).filter(
            FiscalClosure.business_info_id == bid,
            FiscalClosure.giorno >= yesterday,
        ).first()
        if z is not None:
            return jsonify({"warning": False, "reason": "z_done", "today": today.isoformat()})
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        current_app.logger.warning(
            "chiusura-dovuta: registro chiusure non leggibile (%s): mostro l'avviso comunque.",
            str(exc)
        )

    return jsonify({
        "warning": True,
        "reason": closure_reason,  # weekly_closing_day | no_activity
        "today": today.isoformat(),
        "message": ("Ieri il negozio era chiuso. Stampa la chiusura fiscale (Z) prima di "
                    "emettere il primo scontrino di oggi."),
    })


@cassa_bp.route('/cassa/chiusura-giornaliera', methods=['POST'])
@_rch_esclusivo
def chiusura_giornaliera():
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400

    url = _rch_url(ip, printer_model)
    headers = _rch_chiusura_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)

    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<Service>
<cmd>&gt;C117/$0/*1/&amp;0/[0/]0/_0/@0</cmd>
<cmd>=C3</cmd>
<cmd>=C10</cmd>
<cmd>=C1</cmd>
</Service>"""

    # Contatore Z PRIMA di inviare il comando: e' l'unico riferimento che permette,
    # dopo, di sapere se la chiusura e' stata davvero eseguita anche quando la
    # stampante non risponde (vedi _wait_for_z_advance).
    z_before = _read_printer_lastz(ip, printer_model)
    current_app.logger.info("Chiusura giornaliera: lastZ prima dell'invio = %s", z_before)

    def _chiusura_ok(motivo):
        """Ramo di successo: riconciliazione DGFE + registrazione della Z in DB."""
        current_app.logger.info("Chiusura giornaliera riuscita (%s)", motivo)
        recon = _run_post_z_reconciliation()
        _record_fiscal_closure(ip, printer_model, (recon or {}).get("dgfe_total"))
        return jsonify({"status": "ok", "code": 200, "message": "Chiusura giornaliera completata",
                        "reconciliation": recon}), 200

    def _chiusura_ko(motivo):
        """Ramo di errore: la Z NON risulta eseguita. Lo sblocco (=C1) ha senso solo
        qui: mandarlo mentre la Z e' in corso la interromperebbe a meta'."""
        try:
            unlock = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            _rch_post(url, data=unlock.encode("UTF-8"), headers=headers, timeout=8,
                          **rch_kwargs)
        except Exception:
            pass
        current_app.logger.error("Chiusura giornaliera NON eseguita (%s)", motivo)
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502

    try:
        resp = _rch_post(url, data=xml_payload.encode("UTF-8"), headers=headers, timeout=60,
                             **rch_kwargs)
        body = resp.text or ""
        masked = re.sub(r'([A-Za-z0-9_\-]{8,})', '[REDACTED]', body)
        current_app.logger.debug("Chiusura giornaliera raw (masked): %s", masked[:4000])

        # Codici di esito: SOLO errCode/errorCode (piu' l'eventuale "Risultato: n" in
        # chiaro). <result> NON e' un codice di errore ma il numero documento, ed e'
        # letto proprio come tale altrove (_read_progressivo): trattarlo come esito
        # significava bocciare una chiusura riuscita usando il numero del suo documento.
        codes = set()
        codes.update(int(m) for m in re.findall(r'<(?:errCode|errorCode)>(\d+)</(?:errCode|errorCode)>', body))
        codes.update(int(m) for m in re.findall(r'Risultat[oi]\s*:\s*(\d+)', body, flags=re.IGNORECASE))

        # Considera 0 e 410 come non fatali (410 = nessuna richiesta codici pendente)
        non_fatali = {0, 200, 410}
        fatali = {c for c in codes if c not in non_fatali}

        # Nessun codice fatale: esito ok anche se l'HTTP code non e' 200.
        if not fatali:
            return _chiusura_ok("risposta senza codici fatali")

        # Codici fatali: prima di dichiarare fallita la chiusura chiediamo alla
        # stampante se la Z e' comunque avanzata.
        z_after = _wait_for_z_advance(ip, printer_model, z_before)
        if z_after is not None:
            return _chiusura_ok("codici %s ma lastZ %s -> %s" % (sorted(fatali), z_before, z_after))
        return _chiusura_ko("codici fatali %s, lastZ fermo a %s" % (sorted(fatali), z_before))

    except Exception as e:
        # La RCH Print F, mentre stampa la Z, chiude il socket senza rispondere
        # (ConnectionResetError 10054): un errore di rete qui NON significa che la
        # chiusura non sia stata fatta. Lo si verifica sul contatore Z.
        current_app.logger.warning(
            "Chiusura giornaliera: nessuna risposta dalla stampante (%s). "
            "Verifico sul contatore Z se e' stata comunque eseguita.", str(e))
        z_after = _wait_for_z_advance(ip, printer_model, z_before)
        if z_after is not None:
            return _chiusura_ok("nessuna risposta ma lastZ %s -> %s" % (z_before, z_after))
        return _chiusura_ko("nessuna risposta e lastZ fermo a %s (%s)" % (z_before, e))


@cassa_bp.route('/cassa/api/dgfe', methods=['POST'])
@_rch_esclusivo
def api_dgfe():
    data = request.get_json(force=True) or {}
    current_app.logger.debug("DEBUG /cassa/api/dgfe: %s", {"date": data.get("date"), "ip": ("[REDACTED]" if data.get("ip") else None)})

    ip = data.get("ip") if isinstance(data.get("ip"), str) else None
    date_str = data.get("date") if isinstance(data.get("date"), str) else None

    if not ip or not date_str:
        return jsonify({"error": "IP e data obbligatori"}), 400

    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return jsonify({"error": "Formato data non valido"}), 400

    if not re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', ip) or any(int(p) > 255 for p in ip.split('.')):
        return jsonify({"error": "IP non valido"}), 400

    _, printer_model = _get_printer_config()
    url = _rch_url(ip, printer_model)
    headers = _rch_dgfe_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    timeout_short = 5
    timeout_mid = 10

    try:
        with requests.Session() as s:
            s.headers.update({'Connection': 'close'})
            if 'verify' in rch_kwargs:
                s.verify = rch_kwargs['verify']
            xml_c3 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C3</cmd></Service>'
            s.post(url, data=xml_c3.encode('iso-8859-1'), headers=headers, timeout=timeout_short, allow_redirects=False)

            d = datetime.strptime(date_str, '%Y-%m-%d')
            d_str = d.strftime('%d%m%y')
            xml_c452 = '<?xml version="1.0" encoding="UTF-8"?><Service>' \
                       f'<cmd>=C452/$0/&{d_str}/[1/]9999</cmd>' \
                       '</Service>'
            resp2 = s.post(url, data=xml_c452.encode('iso-8859-1'), headers=headers, timeout=timeout_mid, allow_redirects=False)

            xml_c1 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            s.post(url, data=xml_c1.encode('iso-8859-1'), headers=headers, timeout=timeout_short, allow_redirects=False)
    except requests.exceptions.RequestException as e:
        current_app.logger.error("Errore durante la richiesta DGFE (network): %s", str(e))
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502

    ej_match = re.search(r"<EJ[^>]*>(.*?)</EJ>", resp2.text, re.DOTALL)
    dgfe_text = ej_match.group(1).strip() if ej_match else ""

    scontrini = []
    for blocco in dgfe_text.split('\n\n'):
        lines = blocco.strip().splitlines()
        if not lines:
            continue
        progressivo = re.search(r'PROGR:\s*(\d+)', blocco)
        dataora = re.search(r'DATA:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2})', blocco)
        servizi = re.findall(r'SERVIZIO:\s*(.*?)\s*PREZZO:\s*([\d,.]+)', blocco)
        metodo = re.search(r'PAGAMENTO:\s*(\w+)', blocco)
        totale = re.search(r'TOTALE:\s*([\d,.]+)', blocco)
        if progressivo and dataora and servizi and metodo and totale:
            scontrini.append({
                "progressivo": progressivo.group(1),
                "dataora": dataora.group(1),
                "servizi": [{"nome": s[0], "prezzo": s[1]} for s in servizi],
                "metodo": metodo.group(1),
                "totale": totale.group(1)
            })

    return jsonify({
        "dgfe_text": dgfe_text or "Nessun dato DGFE trovato.",
        "scontrini": scontrini,
        "raw_xml": resp2.text
    })
    
@cassa_bp.route('/cassa/api/myspia')
def api_myspia():
    try:
        # Limite: solo appuntamenti IN_ISTITUTO della data corrente
        today = datetime.now().date()
        day_start = datetime.combine(today, datetime.min.time())
        day_end = datetime.combine(today, datetime.max.time())

        apps = Appointment.query.filter(
            Appointment.stato == AppointmentStatus.IN_ISTITUTO,
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end,
            Appointment.is_cancelled_by_client == False
        ).options(selectinload(Appointment.client), selectinload(Appointment.service), selectinload(Appointment.operator)).all()

        # Raggruppa per cliente
        gruppi = {}
        for app in apps:
            if not app.client:
                continue
            key = (app.client.id, app.client.cliente_nome, app.client.cliente_cognome)
            gruppi.setdefault(key, []).append(app)

        result = []
        for (client_id, nome, cognome), apps in gruppi.items():
            result.append({
                "cliente_id": client_id,
                "cliente_nome": nome_proprio(nome),
                "cliente_cognome": nome_proprio(cognome),
                "ids": [a.id for a in apps],
                "appuntamenti": [
                    {
                        "servizio_nome": a.service.servizio_nome if a.service else "",
                        "durata": a._duration,
                        "prezzo": _prezzo_riga_appuntamento(a.service, a)[0] if a.service else 0,
                        "bg_color": a.colore or "#fff",
                        "font_color": a.colore_font or "#000",
                        "data": a.start_time.strftime("%Y-%m-%d") if a.start_time else "",
                        "start_time": a.start_time.strftime("%H:%M") if a.start_time else "",
                        "operator_nome": f"{a.operator.user_nome} {a.operator.user_cognome}" if a.operator else ""
                    } for a in apps
                ]
            })
        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("api_myspia error")
        return jsonify([]), 500

def _ultimo_scontrino_stornabile():
    """Ultimo scontrino fiscale odierno effettivamente stornabile: importo
    positivo (uno storno non si storna) e progressivo reale (le voci di
    allineamento DGFE 'ADJ-...' sono escluse)."""
    oggi = datetime.now().date()
    candidati = Receipt.query.filter(
        Receipt.is_fiscale == True,
        Receipt.created_at >= datetime.combine(oggi, datetime.min.time()),
        Receipt.created_at <= datetime.combine(oggi, datetime.max.time()),
        Receipt.total_amount > 0,
    ).order_by(Receipt.created_at.desc()).all()
    for r in candidati:
        prog = str(r.numero_progressivo or '')
        if prog and not prog.startswith('ADJ-'):
            return r
    return None

@cassa_bp.route('/cassa/annulla-ultimo-scontrino', methods=['POST'])
def annulla_ultimo_scontrino():
    # Stessa identica logica del tasto "Elimina" del registro scontrini:
    # unico percorso, uguale per RCH Print 3.0 RT e RCH Print F.
    ultimo = _ultimo_scontrino_stornabile()
    if not ultimo:
        return jsonify({"error": "Nessuno scontrino fiscale da annullare"}), 404

    res = _storna_scontrino_rch(ultimo)
    if "error" in res:
        return jsonify({"error": res["error"]}), res.get("status", 400)

    return jsonify({
        "status": "ok",
        "code": 200,
        "progressivo": res["progressivo_storno"],
        "documento_stornato": res["documento_stornato"],
    }), 200

@cassa_bp.route('/cassa/api/myspia/dettagli', methods=['POST'])
def myspia_dettagli():
    try:
        data = request.get_json(force=True) or {}
        ids = data.get('ids') or []
        if isinstance(ids, str):
            ids = [x for x in re.split(r'[,\s]+', ids) if x]
        ids = [int(x) for x in ids if str(x).isdigit()]
        if not ids:
            return jsonify({"success": False, "error": "Nessun id appuntamento"}), 400

        apps = (Appointment.query
                .filter(Appointment.id.in_(ids),
                        Appointment.is_cancelled_by_client == False)
                .options(selectinload(Appointment.client),
                        selectinload(Appointment.service),
                        selectinload(Appointment.operator))
                .all())
        if not apps:
            return jsonify({"success": False, "error": "Appuntamenti non trovati"}), 404

        apps.sort(key=lambda a: a.start_time or datetime.min)

        cli = next((a.client for a in apps if a.client), None)
        op = next((a.operator for a in apps if a.operator), None)

        result = {
            "success": True,
            "cliente_id": cli.id if cli else None,
            "cliente_nome": nome_proprio(cli.cliente_nome if cli else ""),
            "cliente_cognome": nome_proprio(cli.cliente_cognome if cli else ""),
            "operatore_id": op.id if op else None,
            "operatore_nome": (op.user_nome if op else "") or "",
            "appuntamenti": []
        }

        for a in apps:
            s = a.service
            # Operatore specifico di questo appuntamento
            appt_op = a.operator
            result["appuntamenti"].append({
                "id": s.id if s else None,
                "nome": s.servizio_nome if s else "",
                # Listino, o prezzo promo se l'appuntamento rientra nella promo
                "prezzo": _prezzo_riga_appuntamento(s, a)[0] if s else 0,
                "tag": s.servizio_tag if s else "",
                "sottocategoria": s.servizio_sottocategoria.nome if (s and s.servizio_sottocategoria) else "",
                # Servono per verificare se una prepagata con vincolo "categoria"/"sottocategoria"
                # è utilizzabile su questo servizio (vedi verificaVincoliPrepagata in cassa.js)
                "categoria": s.servizio_categoria.value if (s and s.servizio_categoria) else None,
                "sottocategoria_id": s.servizio_sottocategoria_id if s else None,
                "appointment_id": a.id,
                "operator_id": appt_op.id if appt_op else None,
                "operator_nome": appt_op.user_nome if appt_op else ""
            })

        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("Errore /cassa/api/myspia/dettagli")
        return jsonify({"success": False, "error": "Errore interno"}), 500
    
# =========================================================================
# STORNO FISCALE: UNICA IMPLEMENTAZIONE, UN SOLO COMANDO, DUE MODELLI
# =========================================================================
# Comando e controlli sono gli stessi per RCH Print 3.0 RT e RCH Print F:
# entrambi parlano il protocollo PRINT!, e l'unica differenza fra i due e' il
# trasporto (URL, header, verify SSL), gia' incapsulato in _rch_url /
# _rch_headers / _rch_request_kwargs. Qui NON si ramifica mai sul modello e
# NON si tentano varianti di comando: si invia sempre e solo la forma
# documentata nel manuale PRINT! (sez. 15):
#     =k/&ggmmaa/[chiusura/]numero
#
# FATTO ACCERTATO (incidente Biella, RCH Print 3.0 RT, 01/08/2026):
# quel comando, inviato per il documento 42, ha annullato il 44, cioe'
# l'ULTIMO documento emesso: il registratore non ha risolto il riferimento.
# Il difetto era rimasto invisibile perche' l'unico uso storico era "annulla
# ultimo scontrino", dove il bersaglio corretto e l'ultimo documento
# coincidono.
#
# DUE OPERAZIONI DIVERSE, SCELTE DAL SERVER (_storna_scontrino_rch):
#
#  - ULTIMO documento emesso  -> ANNULLAMENTO (=k). Qui le due possibili
#    semantiche del firmware (riferimento onorato / ultimo documento)
#    colpiscono lo stesso identico documento, quindi l'esito e' corretto su RT
#    3.0 e su Print F senza dipendere dal firmware.
#
#  - documento PRECEDENTE     -> RESO (=r, manuale PRINT! sez. 14). Il reso non
#    tocca il documento originale: emette un NUOVO documento negativo che lo
#    riferisce. Per questo e' l'unica operazione sicura sui documenti non
#    ultimi: anche nel caso peggiore in cui il registratore non risolvesse il
#    riferimento, il documento negativo verrebbe emesso comunque per l'importo
#    giusto, e nessun altro documento puo' essere annullato per errore.
#    L'originale resta nel registro e nel DGFE, come dev'essere: la rettifica
#    e' la riga negativa successiva.
#
# In entrambi i casi l'esito viene verificato (errCode + avanzamento del
# progressivo) PRIMA di scrivere qualsiasi cosa in DB, e la riga negativa
# porta con se' il riferimento esplicito al documento rettificato
# (chiave '_rettifica_di' nelle voci: nessuna modifica allo schema), cosi' il
# registro non deve piu' indovinare l'abbinamento in base all'importo.
def _voci_list(scontrino):
    """Voci dello scontrino sempre come lista di dict (alcune righe storiche le
    hanno salvate come stringa JSON)."""
    voci = scontrino.voci if scontrino else None
    if isinstance(voci, str):
        try:
            voci = json.loads(voci)
        except Exception:
            voci = []
    if not isinstance(voci, list):
        return []
    return [v for v in voci if isinstance(v, dict)]


def _voci_negative(scontrino, tipo, progressivo_originale):
    """Voci della riga negativa: stesse voci dell'originale a segno invertito,
    con il riferimento esplicito al documento rettificato."""
    voci_out = []
    for v in _voci_list(scontrino):
        voce = v.copy()
        try:
            voce['prezzo'] = -abs(float(voce.get('prezzo', 0)))
        except Exception:
            voce['prezzo'] = -0.0
        voce['nome'] = voce.get('nome') or voce.get('servizio_nome') or tipo.upper()
        voce['_rettifica_di'] = progressivo_originale
        voce['_rettifica_tipo'] = tipo          # 'annullo' | 'reso'
        voci_out.append(voce)
    return voci_out


def _righe_reso_rch(scontrino, printer_model):
    """Righe merce e pagamenti del documento di RESO, ricostruiti dalle voci
    dell'originale. Ritorna (cmds, totale_cents) oppure (None, errore).

    Le voci a importo zero non vengono rese: sull'originale erano righe
    descrittive (promemoria), non vendite, quindi non c'e' nulla da rimborsare
    - e una riga di vendita a zero verrebbe comunque rifiutata dal
    registratore, lasciando il documento aperto.
    """
    cmds = []
    totali = {}
    totale_cents = 0

    for v in _voci_list(scontrino):
        try:
            prezzo = float(v.get('prezzo', 0) or 0)
        except Exception:
            prezzo = 0.0
        cents = int(round(abs(prezzo) * 100))
        if cents <= 0:
            continue

        srv = db.session.get(Service, v.get('servizio_id')) if v.get('servizio_id') else None
        desc = (v.get('nome') or v.get('servizio_nome') or (srv.servizio_nome if srv else 'Servizio'))[:32]
        desc = clean_str(html.unescape(desc)).replace(")", "").replace("(", "").replace("/", "-")
        reparto = "R2" if getattr(srv, "servizio_sottocategoria", None) and \
                           srv.servizio_sottocategoria.nome.upper() == "PRODOTTI" else "R1"
        cmds.append(f'<cmd>={reparto}/${cents}/({desc})</cmd>')
        totale_cents += cents

        # Il rimborso segue le stesse forme di pagamento dell'originale
        # (split compreso), come in send_to_rch.
        pagamenti_split = v.get('pagamenti')
        if isinstance(pagamenti_split, list) and pagamenti_split:
            assegnati = 0
            for p in pagamenti_split:
                cents_p = int(round(abs(float(p.get('importo', 0) or 0)) * 100))
                if cents_p <= 0:
                    continue
                tcode_p = _tender_code(p.get('metodo', 'cash'), printer_model)
                totali[tcode_p] = totali.get(tcode_p, 0) + cents_p
                assegnati += cents_p
            diff = cents - assegnati
            if diff != 0:
                tcode_first = _tender_code(pagamenti_split[0].get('metodo', 'cash'), printer_model)
                totali[tcode_first] = totali.get(tcode_first, 0) + diff
        else:
            tcode = _tender_code(v.get('metodo_pagamento', 'cash'), printer_model)
            totali[tcode] = totali.get(tcode, 0) + cents

    if totale_cents <= 0:
        return None, "Lo scontrino non ha voci con importo positivo da rendere"

    for tcode in ("T1", "T2", "T3", "T4", "T5"):
        if totali.get(tcode, 0) > 0:
            cmds.append(f'<cmd>={tcode}/${totali[tcode]}</cmd>')

    return cmds, totale_cents


def _storna_scontrino_rch(scontrino):
    """Storno sotto il lucchetto della stampante: lettura del progressivo,
    annullo/reso e verifica sono una sola conversazione (vedi _RCH_BUS)."""
    try:
        with _rch_in_uso():
            return _storna_scontrino_rch_impl(scontrino)
    except RchOccupata:
        return {"error": MSG_RCH_OCCUPATA, "status": 409}


def _storna_scontrino_rch_impl(scontrino):
    """Rettifica fiscalmente uno scontrino e registra la riga negativa in DB.

    Annullamento se e' l'ultimo documento emesso, altrimenti reso.
    Ritorna {"success": True, "progressivo_storno": ..., "tipo": ...} oppure
    {"error": "...", "status": <http status suggerito>}.
    """
    # ---------- validazione del documento ----------
    if not scontrino or not scontrino.is_fiscale or not scontrino.numero_progressivo:
        return {"error": "Scontrino non fiscale o senza progressivo", "status": 400}

    progressivo_str = str(scontrino.numero_progressivo).strip()
    if progressivo_str.startswith('ADJ-'):
        return {"error": "Le voci di allineamento DGFE non sono stornabili", "status": 400}

    try:
        progressivo_sx, progressivo_dx = progressivo_str.split('-')
        chiusura = progressivo_sx.zfill(4)
        documento = int(progressivo_dx)
    except Exception:
        return {"error": "Progressivo non valido", "status": 400}

    if documento == 0:
        # Il documento 0 non esiste: il registratore numera da 1 dopo ogni Z.
        # Sono gli scontrini registrati senza che la stampante li avesse emessi
        # (contatore fermo o RCH bloccata, vedi _rch_esito): non c'e' niente da
        # stornare e il reso verrebbe solo rifiutato (errorCode 1).
        return {"error": (f"Lo scontrino {progressivo_str} non risulta emesso dalla stampante "
                          f"(il documento 0 non esiste): non c'è nulla da stornare."),
                "status": 409}

    try:
        importo = float(scontrino.total_amount or 0)
    except Exception:
        importo = 0.0
    if importo <= 0:
        return {"error": "Una rettifica non puo' essere rettificata a sua volta", "status": 400}

    data_scontrino = scontrino.created_at.date() if scontrino.created_at else None
    if data_scontrino != datetime.now().date():
        return {"error": "Operazione possibile solo per scontrini del giorno corrente", "status": 400}

    ip, printer_model = _get_printer_config()
    if not ip:
        return {"error": "IP stampante RCH non configurato", "status": 400}

    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)

    # ---------- 1. annullo o reso? lo decide il progressivo della stampante ----------
    doc_prima, _z_prima = _read_progressivo(url, headers, rch_kwargs,
                                            max_attempts=6, sleep_s=0.5)
    if doc_prima is None:
        return {"error": "Stampante non raggiungibile: progressivo non leggibile, operazione annullata",
                "status": 502}

    data_str = data_scontrino.strftime("%d%m%y")
    riferimento = f"&{data_str}/[{chiusura}/]{documento}"
    e_ultimo = (documento == doc_prima)

    if e_ultimo:
        # ANNULLAMENTO dell'ultimo documento (manuale PRINT! sez. 15).
        tipo = "annullo"
        cmds = [f'<cmd>=k/{riferimento}</cmd>']
    else:
        # RESO del documento precedente (manuale PRINT! sez. 14): apre il
        # documento di reso col riferimento all'originale, ne ripete le righe
        # merce e lo chiude con le stesse forme di pagamento. L'originale non
        # viene toccato: la rettifica e' questo nuovo documento negativo.
        tipo = "reso"
        righe, esito = _righe_reso_rch(scontrino, printer_model)
        if righe is None:
            return {"error": esito, "status": 400}   # esito = messaggio d'errore
        totale_cents = esito
        if abs(totale_cents - int(round(importo * 100))) > 1:
            # Le righe ricostruite non fanno il totale dello scontrino: meglio
            # non emettere nulla che emettere un reso di importo sbagliato.
            log_crm_error(
                "Reso non emesso: totale righe diverso dal totale scontrino",
                context={"receipt_id": scontrino.id, "progressivo": progressivo_str,
                         "totale_righe_cents": totale_cents,
                         "totale_scontrino_cents": int(round(importo * 100))},
                client_id=scontrino.cliente_id,
            )
            return {"error": (f"Reso non emesso: le righe ricostruite valgono "
                              f"{totale_cents/100:.2f} € contro i {importo:.2f} € dello "
                              f"scontrino."), "status": 409}
        cmds = [f'<cmd>=r/{riferimento}</cmd>'] + righe

    # ---------- 2. invio ----------
    # Sequenza in un unico payload, come per la vendita: se una riga venisse
    # rifiutata a meta' sequenza il documento resterebbe aperto sul
    # registratore, bloccando le stampe successive.
    xml = ('<?xml version="1.0" encoding="UTF-8" ?>\n<Service>\n'
           + "\n".join(cmds) + '\n</Service>')

    try:
        resp = _rch_post(url, data=xml.encode("UTF-8"), headers=headers, timeout=30,
                             **rch_kwargs)
    except Exception as exc:
        current_app.logger.error("%s: errore di rete verso la stampante: %s", tipo, str(exc))
        log_crm_error(
            f"{tipo.capitalize()}: stampante non raggiungibile",
            context={"receipt_id": scontrino.id, "progressivo": progressivo_str,
                     "payload": xml, "printer_ip": ip, "printer_model": printer_model,
                     "exception": str(exc)},
            client_id=scontrino.cliente_id,
        )
        return {"error": f"Stampante non raggiungibile durante il {tipo}: verificare sulla "
                         f"stampante se il documento e' stato stampato prima di riprovare",
                "status": 502}

    current_app.logger.info("%s doc %s su %s: %s", tipo, progressivo_str, printer_model,
                            (resp.text or "")[:400])

    # ---------- 3. verifica esito PRIMA di scrivere in DB ----------
    # Senza questo controllo il DB registrava la rettifica anche quando il
    # registratore l'aveva rifiutata, sfasando corrispettivi e DGFE.
    if not _rch_is_success(resp):
        log_crm_error(
            f"{tipo.capitalize()} rifiutato dal registratore (errCode)",
            context={"receipt_id": scontrino.id, "progressivo": progressivo_str,
                     "payload": xml, "printer_ip": ip, "printer_model": printer_model,
                     "errCode": _rch_parse_errcode(resp.text or ""),
                     "response_body": (resp.text or "")[:400]},
            client_id=scontrino.cliente_id,
        )
        return {"error": f"Il registratore ha rifiutato il {tipo}: nessuna voce registrata",
                "status": 502}

    doc_dopo, z_dopo = _read_progressivo(url, headers, rch_kwargs, max_attempts=10, sleep_s=0.5)
    if doc_dopo is None or z_dopo is None:
        log_crm_error(
            f"{tipo.capitalize()}: progressivo successivo non leggibile",
            context={"receipt_id": scontrino.id, "progressivo": progressivo_str,
                     "printer_ip": ip, "printer_model": printer_model},
            client_id=scontrino.cliente_id,
        )
        return {"error": "Impossibile leggere il progressivo dopo l'operazione: verificare sulla "
                         "stampante e sul DGFE prima di riprovare", "status": 502}
    if doc_dopo <= doc_prima:
        # Annullo e reso emettono a loro volta un documento: se il contatore non
        # e' avanzato, non e' stato stampato nulla.
        log_crm_error(
            f"{tipo.capitalize()} non confermato: progressivo invariato",
            context={"receipt_id": scontrino.id, "progressivo": progressivo_str,
                     "doc_prima": doc_prima, "doc_dopo": doc_dopo,
                     "printer_ip": ip, "printer_model": printer_model},
            client_id=scontrino.cliente_id,
        )
        return {"error": f"{tipo.capitalize()} non confermato dal registratore: nessuna voce registrata",
                "status": 502}

    progressivo_completo = f"{z_dopo:04d}-{doc_dopo:04d}"

    # ---------- 4. registrazione della riga negativa ----------
    # L'originale NON viene toccato: la rettifica e' questa riga negativa
    # successiva, che porta con se' il riferimento al documento rettificato.
    nuovo_receipt = Receipt(
        created_at       = datetime.now(),
        total_amount     = -abs(scontrino.total_amount),
        is_fiscale       = True,
        voci             = _voci_negative(scontrino, tipo, progressivo_str),
        cliente_id       = scontrino.cliente_id,
        operatore_id     = scontrino.operatore_id,
        numero_progressivo = progressivo_completo  # Sequenziale come DGFE
    )
    db.session.add(nuovo_receipt)
    db.session.commit()

    # Rate pacchetto: ripristinate solo a operazione riuscita, per entrambi i
    # punti di ingresso (registro scontrini e "annulla ultimo scontrino").
    ripristina_rate_da_scontrino(scontrino)

    return {"success": True, "progressivo_storno": progressivo_completo,
            "documento_stornato": progressivo_str, "tipo": tipo}


@cassa_bp.route('/api/user-role')
def api_user_role():
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    return jsonify({"role": user.ruolo.value if user else None})

@cassa_bp.route('/cassa/rch-status', methods=['GET'])
def rch_status():
    key = request.args.get('idempotency_key', '').strip()
    if not key:
        return jsonify({"error": "Missing idempotency_key"}), 400
    if key in IDEMPOTENCY_STORE:
        return jsonify({"done": True, **IDEMPOTENCY_STORE[key]}), 200
    if key in RCH_PENDING:
        return jsonify({"done": False, "pending": True, "retry_after": 3}), 200
    return jsonify({"error": "Not found"}), 404

def _dgfe_entries_with_diag(ip: str, day: date):
    """Lettura DGFE sotto il lucchetto della stampante: =C3, =C452 e =C1
    sono una sola sequenza (uno scontrino in mezzo la troverebbe in modo Z).
    Se la stampante e' impegnata da altri, la lettura risulta fallita come
    per un errore di rete: nessuno la scambia per un giorno vuoto."""
    try:
        with _rch_in_uso():
            return _dgfe_entries_with_diag_impl(ip, day)
    except RchOccupata:
        return [], {"status": "network_error", "http_status": None, "body_len": 0,
                    "ej_found": False, "blocks": 0, "parsed_entries": 0,
                    "parse_failures": 0, "error": "stampante impegnata da un'altra operazione",
                    "body_excerpt": "", "printer_model": None, "url": None}


def _dgfe_entries_with_diag_impl(ip: str, day: date):
    """Come _dgfe_entries_for_date ma ritorna (entries, diag) con info diagnostica.
    diag e' un dict con: status, http_status, body_len, ej_found, blocks, parsed_entries,
    parse_failures, error, body_excerpt, printer_model, url.
    """
    diag = {
        "status": "unknown",
        "http_status": None,
        "body_len": 0,
        "ej_found": False,
        "blocks": 0,
        "parsed_entries": 0,
        "parse_failures": 0,
        "error": None,
        "body_excerpt": "",
        "printer_model": None,
        "url": None,
    }
    resp = None
    try:
        _, printer_model = _get_printer_config()
        diag["printer_model"] = printer_model
        url = _rch_url(ip, printer_model)
        diag["url"] = url
        headers = _rch_dgfe_headers(printer_model)
        rch_kwargs = _rch_request_kwargs(printer_model)
        try:
            current_app.logger.info("DGFE read: ip=%s model=%s day=%s", ip, printer_model, day)
        except Exception:
            pass
        with requests.Session() as s:
            s.headers.update({'Connection': 'close'})
            if 'verify' in rch_kwargs:
                s.verify = rch_kwargs['verify']
            xml_c3 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C3</cmd></Service>'
            s.post(url, data=xml_c3.encode('iso-8859-1'), headers=headers, timeout=5, allow_redirects=False)
            d_str = day.strftime('%d%m%y')
            xml_c452 = '<?xml version="1.0" encoding="UTF-8"?><Service>' \
                       f'<cmd>=C452/$0/&{d_str}/[1/]9999</cmd>' \
                       '</Service>'
            resp = s.post(url, data=xml_c452.encode('iso-8859-1'), headers=headers, timeout=15, allow_redirects=False)
            # Unlock (best-effort)
            try:
                xml_c1 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
                s.post(url, data=xml_c1.encode('iso-8859-1'), headers=headers, timeout=4, allow_redirects=False)
            except Exception:
                pass
    except requests.exceptions.RequestException as exc:
        diag["status"] = "network_error"
        diag["error"] = str(exc)
        try:
            current_app.logger.warning("DGFE read network error per %s: %s", day, str(exc))
        except Exception:
            pass
        return [], diag
    except Exception as exc:
        diag["status"] = "unexpected_error"
        diag["error"] = str(exc)
        try:
            current_app.logger.exception("DGFE read errore inatteso per %s", day)
        except Exception:
            pass
        return [], diag

    diag["http_status"] = getattr(resp, 'status_code', None)
    body = resp.text or ""
    diag["body_len"] = len(body)
    diag["body_excerpt"] = body[:4000]

    try:
        current_app.logger.info(
            "DGFE %s body (first 2000 chars): %s",
            day, body[:2000].replace('\n', '\\n')
        )
    except Exception:
        pass

    ej_match = re.search(r"<EJ[^>]*>(.*?)</EJ>", body, re.DOTALL)
    if not ej_match:
        diag["status"] = "no_ej_block"
        try:
            current_app.logger.warning(
                "DGFE %s: nessun <EJ> nel body (http=%s len=%s)",
                day, diag["http_status"], diag["body_len"]
            )
        except Exception:
            pass
        return [], diag

    diag["ej_found"] = True
    dgfe_text = ej_match.group(1).strip()
    if not dgfe_text:
        diag["status"] = "ej_empty"
        try:
            current_app.logger.info("DGFE %s: <EJ> presente ma vuoto", day)
        except Exception:
            pass
        return [], diag

    # Parser specifico per il formato DGFE della RCH Print 3.0 RT.
    # Ogni scontrino fiscale e' delimitato da:
    #   "DOCUMENTO COMMERCIALE" ... "DOCUMENTO N. ZZZZ-NNNN"
    # All'interno trova:
    #   "TOTALE COMPLESSIVO    13,00"
    #   "DD-MM-YYYY HH:MM"
    receipt_pattern = re.compile(
        r'DOCUMENTO\s+COMMERCIALE'         # marker inizio scontrino
        r'(?P<body>.*?)'                    # corpo (lazy)
        r'DOCUMENTO\s+N\.\s+(?P<z>\d+)-(?P<n>\d+)',  # marker fine + progressivo Z-DOC
        re.DOTALL
    )

    matches = list(receipt_pattern.finditer(dgfe_text))
    diag["blocks"] = len(matches)

    entries = []
    parse_failures = 0
    for match in matches:
        body = match.group('body') or ""
        z_num = match.group('z')
        n_num = match.group('n')
        progressivo = f"{z_num}-{n_num}"

        # TOTALE COMPLESSIVO (solo dei DOCUMENTI COMMERCIALI; i DOCUMENTI GESTIONALI
        # di chiusura giornaliera usano "VENDITE" / "GRAN TOTALE" e sono esclusi dal
        # pattern perche' iniziano con "DOCUMENTO GESTIONALE", non "DOCUMENTO COMMERCIALE")
        # Supporta anche segno negativo eventuale (es. "-24,00") che alcune RCH
        # stampano per i documenti di annullamento/reso.
        m_tot = re.search(r'TOTALE\s+COMPLESSIVO\s+(-?[\d.,]+)', body)
        if not m_tot:
            parse_failures += 1
            continue
        raw_tot = m_tot.group(1).strip()
        sign = -1 if raw_tot.startswith('-') else 1
        raw_tot_abs = raw_tot.lstrip('-').strip()
        try:
            # Formato italiano: "1.006,00" -> 1006.00
            tot_float = sign * float(raw_tot_abs.replace('.', '').replace(',', '.'))
        except Exception:
            try:
                tot_float = sign * float(raw_tot_abs)
            except Exception:
                parse_failures += 1
                continue

        # I documenti di ANNULLAMENTO/RESO (emessi dalla RCH con il comando =k oppure =r)
        # appaiono nel DGFE come "DOCUMENTO COMMERCIALE / EMESSO PER ANNULLAMENTO" (o RESO).
        # Il "TOTALE COMPLESSIVO" e' tipicamente stampato come valore positivo perche' rappresenta
        # l'importo del documento; fiscalmente pero' e' un rimborso e nel DB SunBooking viene
        # salvato come total_amount negativo. Forziamo il segno negativo per allineare la somma
        # DGFE alla somma DB ed evitare falsi delta nella riconciliazione e nel modal Corrispettivi.
        is_storno = bool(re.search(r'EMESSO\s+PER\s+(?:ANNULLAMENTO|RESO)', body, re.IGNORECASE))
        if is_storno and tot_float > 0:
            tot_float = -tot_float
        tot_float = round(tot_float, 2)

        # Data/ora nel formato "04-05-2026 09:04"
        m_dt = re.search(r'(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})', body)
        dt = None
        if m_dt:
            try:
                dt = datetime(
                    int(m_dt.group(3)), int(m_dt.group(2)), int(m_dt.group(1)),
                    int(m_dt.group(4)), int(m_dt.group(5))
                )
            except ValueError:
                dt = None
        if dt is None:
            dt = datetime.combine(day, datetime.min.time())

        # Numero voci: conto le righe "<IVA>%   <prezzo>" prima del primo "TOTALE COMPLESSIVO".
        # In questo formato ogni servizio ha una riga "Nome servizio    22%   13,00"
        body_before_total = body[:m_tot.start()] if m_tot else body
        line_count = len(re.findall(r'\b\d+%\s+[\d.,]+', body_before_total))

        entries.append({
            "dataora_dt": dt,
            "totale_float": tot_float,
            "progressivo_raw": progressivo,  # formato "ZZZZ-NNNN"
            "line_count": line_count,
            "raw": body[:300],
        })

    entries.sort(key=lambda e: e["dataora_dt"])
    diag["parsed_entries"] = len(entries)
    diag["parse_failures"] = parse_failures
    if entries:
        diag["status"] = "ok"
    elif matches:
        diag["status"] = "parse_failed_all"
    else:
        diag["status"] = "ej_no_blocks"

    try:
        current_app.logger.info(
            "DGFE %s: status=%s receipts=%d parse_failures=%d body_len=%d total_sum=%.2f",
            day, diag["status"], diag["parsed_entries"],
            diag["parse_failures"], diag["body_len"],
            sum(e["totale_float"] for e in entries)
        )
    except Exception:
        pass

    return entries, diag


def _dgfe_entries_for_date(ip: str, day: date):
    """Wrapper retro-compatibile: ritorna solo le entries (vuote in caso di qualunque errore)."""
    entries, _ = _dgfe_entries_with_diag(ip, day)
    return entries

def _max_progressivo_doc_in_db_today():
    """Massimo numero documento (parte dopo il '-') tra i Receipt fiscali odierni.
    Ritorna 0 se nessun Receipt presente."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    receipts_today = Receipt.query.filter(
        Receipt.created_at >= today_start,
        Receipt.created_at <= today_end,
        Receipt.is_fiscale == True
    ).all()
    max_doc = 0
    for r in receipts_today:
        try:
            parts = str(r.numero_progressivo).split('-')
            if len(parts) == 2:
                n = int(parts[1])
                if n > max_doc:
                    max_doc = n
        except Exception:
            pass
    return max_doc

def _registra_fiscale_confermato(voci, cliente_id, operatore_id, totale, progressivo):
    """Scrive nel registro uno scontrino fiscale GIA' confermato dal contatore
    della stampante e marca PAGATO gli appuntamenti delle sue voci.
    Ritorna True se l'ha scritto, False se quel progressivo c'era gia' (due
    verifiche arrivate insieme: la seconda non duplica)."""
    with _RCH_LOCK:
        if Receipt.query.filter_by(numero_progressivo=progressivo).first():
            return False
        db.session.add(Receipt(
            created_at=datetime.now(),
            total_amount=round(float(totale), 2),
            is_fiscale=True,
            voci=voci or [],
            cliente_id=cliente_id,
            operatore_id=operatore_id,
            numero_progressivo=progressivo
        ))
        db.session.commit()

    ids_pagati = [v.get("appointment_id") for v in (voci or []) if v.get("appointment_id")]
    if ids_pagati:
        Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
            {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
        )
        db.session.commit()
    return True


# ============================================================
# RECONCILIATION DGFE <-> DB (persistita IN DATABASE, tabella dgfe_readings)
# ============================================================
# La lettura DGFE riconciliata per ogni giorno e' salvata in DB (modello
# DgfeReading), NON piu' su file JSON. Una riga per (negozio, giorno). Il campo
# `payload` conserva il dict completo dell'esito per retro-compatibilita' con i
# consumatori (badge registro scontrini + colonna DGFE nei Corrispettivi), che
# continuano a ricevere la stessa forma {date_str: entry_dict}.

def _recon_bid(business_info_id):
    """Normalizza il business_info_id (None -> 0) come chiave del negozio."""
    try:
        return int(business_info_id) if business_info_id is not None else 0
    except Exception:
        return 0

def _load_reconciliation_log(business_info_id):
    """Legge da DB tutte le letture DGFE del negozio. Ritorna dict
    {date_str: entry_dict} per compatibilita' col vecchio formato.
    Non solleva mai eccezioni (es. se la tabella non esiste ancora -> {})."""
    try:
        from appl.models import DgfeReading
        bid = _recon_bid(business_info_id)
        rows = DgfeReading.query.filter_by(business_info_id=bid).all()
        out = {}
        for r in rows:
            key = r.giorno.strftime('%Y-%m-%d') if r.giorno else None
            entry = None
            if r.payload:
                try:
                    entry = json.loads(r.payload)
                except Exception:
                    entry = None
            if not isinstance(entry, dict):
                # Fallback dalle colonne dedicate se il payload manca/corrotto.
                entry = {
                    "date": key,
                    "dgfe_total": r.dgfe_total,
                    "dgfe_count": r.dgfe_count,
                    "status": r.status,
                    "run_at": r.run_at.isoformat(timespec='seconds') if r.run_at else None,
                }
            if key:
                out[key] = entry
        return out
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.warning("DgfeReading: load fallita: %s", str(exc))
        except Exception:
            pass
        return {}

def _set_reconciliation_entry(business_info_id, day_str, entry):
    """UPSERT in DB della lettura DGFE riconciliata del giorno (tabella dgfe_readings).

    ROBUSTEZZA FISCALE (anti-azzeramento): non degrada MAI un giorno gia'
    verificato col DGFE (dgfe_count>0 e totale>0) verso una lettura vuota
    (dgfe_count==0). Capita con la doppia chiusura Z mattutina a 0 (la 2a Z ha
    gran totale 0) o quando la stampante e' occupata: la lettura torna vuota ma
    il dato fiscale gia' acquisito NON deve essere sovrascritto/azzerato. Le
    correzioni reali ('Correggi'/'Allinea a DGFE') leggono sempre scontrini
    (dgfe_count>0) quindi non sono mai bloccate da questo guard.

    Best-effort: non solleva mai eccezioni al chiamante (se la tabella non esiste
    ancora, semplicemente non persiste; il flusso Z non si interrompe).
    """
    try:
        from appl.models import DgfeReading
        bid = _recon_bid(business_info_id)
        try:
            giorno = datetime.strptime(day_str, '%Y-%m-%d').date()
        except Exception:
            return

        existing = DgfeReading.query.filter_by(business_info_id=bid, giorno=giorno).first()

        # Guard anti-azzeramento.
        if existing is not None:
            try:
                prev_cnt = int(existing.dgfe_count or 0)
                prev_tot = abs(float(existing.dgfe_total or 0.0))
                new_cnt = int(entry.get("dgfe_count") or 0)
            except (TypeError, ValueError):
                prev_cnt = prev_tot = new_cnt = 0
            if prev_cnt > 0 and prev_tot > 0.01 and new_cnt == 0:
                try:
                    current_app.logger.warning(
                        "DgfeReading %s: ignoro lettura DGFE vuota (new dgfe_count=0, "
                        "status=%s) per non azzerare il dato gia' verificato "
                        "(prev dgfe_count=%s tot=%.2f).",
                        day_str, entry.get("status"), prev_cnt, prev_tot
                    )
                except Exception:
                    pass
                return

        run_at_dt = None
        ra = entry.get('run_at')
        if ra:
            try:
                run_at_dt = datetime.fromisoformat(ra)
            except Exception:
                run_at_dt = None

        try:
            dgfe_total_v = float(entry.get('dgfe_total')) if entry.get('dgfe_total') is not None else None
        except (TypeError, ValueError):
            dgfe_total_v = None
        try:
            dgfe_count_v = int(entry.get('dgfe_count') or 0)
        except (TypeError, ValueError):
            dgfe_count_v = 0

        payload = json.dumps(entry, ensure_ascii=False, default=str)
        status_v = (entry.get('status') or '')[:32] or None

        if existing is None:
            existing = DgfeReading(business_info_id=bid, giorno=giorno)
            db.session.add(existing)
        existing.dgfe_total = dgfe_total_v
        existing.dgfe_count = dgfe_count_v
        existing.status = status_v
        existing.run_at = run_at_dt
        existing.payload = payload
        existing.updated_at = datetime.now()
        db.session.commit()
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.error("DgfeReading: UPSERT FALLITO per %s: %s", day_str, str(exc))
        except Exception:
            pass

def _persist_dgfe_reading(day_date, dgfe_total, dgfe_count, db_total=None,
                          status="checked", notes=None):
    """Persiste in DB la lettura DGFE di un giorno, da QUALSIASI sorgente: semplice
    'Carica DGFE'/check, anteprima, allineamento, chiusura Z. Cosi' il badge del
    Registro Scontrini riflette sempre l'ultima lettura. Best-effort, mai solleva.

    Rispetta il guard anti-azzeramento di `_set_reconciliation_entry` (non sovrascrive
    un giorno gia' verificato con una lettura vuota)."""
    try:
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        if bi is None:
            return
        day_str = day_date.strftime("%Y-%m-%d")
        entry = {
            "status": status,
            "date": day_str,
            "run_at": datetime.now().isoformat(timespec='seconds'),
            "dgfe_count": dgfe_count,
            "dgfe_total": dgfe_total,
        }
        if db_total is not None:
            entry["db_total"] = db_total
        if notes:
            entry["notes"] = notes
        _set_reconciliation_entry(bi.id, day_str, entry)
    except Exception:
        try:
            current_app.logger.warning("persistenza lettura DGFE fallita per %s", day_date)
        except Exception:
            pass

def reconcile_day(day_date, business_info):
    """Riconcilia il giorno con il DGFE della stampante e crea Receipt orfani per le
    entry mancanti. Persiste un'entry nel log JSON per-tenant.
    business_info: oggetto BusinessInfo (id, business_name, city, printer_ip, printer_model).
    Ritorna dict riassuntivo: {status, dgfe_count, db_count, created_orphans, suspicious_extras, run_at}.
    """
    started_at = datetime.now()
    bid = getattr(business_info, 'id', None)
    ip = getattr(business_info, 'printer_ip', None)
    raw_model = getattr(business_info, 'printer_model', None)
    printer_model = _normalize_model(raw_model)

    summary = {
        "status": "error",
        "business_info_id": bid,
        "business_name": getattr(business_info, 'business_name', None),
        "city": getattr(business_info, 'city', None),
        "printer_ip": ip,
        "printer_model": printer_model,
        "date": day_date.strftime("%Y-%m-%d"),
        "run_at": started_at.isoformat(timespec='seconds'),
        "dgfe_count": 0,
        "db_count": 0,
        "dgfe_total": 0.0,
        "db_total": 0.0,
        "created_orphans": 0,
        "suspicious_extras": [],
        "dgfe_diagnostic": None,
        "notes": ""
    }

    if not ip:
        summary["notes"] = "IP stampante non configurato"
        try:
            _set_reconciliation_entry(bid, summary["date"], summary)
        except Exception:
            pass
        return summary

    try:
        dgfe_entries, dgfe_diag = _dgfe_entries_with_diag(ip, day_date)
        dgfe_entries = dgfe_entries or []
    except Exception as exc:
        summary["notes"] = f"Errore lettura DGFE: {exc}"
        try:
            _set_reconciliation_entry(bid, summary["date"], summary)
        except Exception:
            pass
        return summary

    summary["dgfe_diagnostic"] = dgfe_diag
    # Se la lettura DGFE non e' "ok", non possiamo pretendere riconciliazione affidabile.
    # In particolare per network_error / no_ej_block la status diventa "error" con nota.
    dgfe_status = dgfe_diag.get("status") if dgfe_diag else None
    if dgfe_status in ("network_error", "unexpected_error", "no_ej_block", "parse_failed_all"):
        summary["notes"] = (
            f"Lettura DGFE fallita ({dgfe_status}): "
            f"http={dgfe_diag.get('http_status')} body_len={dgfe_diag.get('body_len')}"
            + (f" err={dgfe_diag.get('error')}" if dgfe_diag.get('error') else "")
        )
        summary["status"] = "error"
        try:
            _set_reconciliation_entry(bid, summary["date"], summary)
        except Exception:
            pass
        return summary

    summary["dgfe_count"] = len(dgfe_entries)
    summary["dgfe_total"] = round(sum(float(e.get("totale_float", 0.0)) for e in dgfe_entries), 2)

    day_start = datetime.combine(day_date, datetime.min.time())
    day_end = datetime.combine(day_date, datetime.max.time())
    receipts = Receipt.query.filter(
        Receipt.created_at >= day_start,
        Receipt.created_at <= day_end,
        Receipt.is_fiscale == True
    ).all()
    summary["db_count"] = len(receipts)
    summary["db_total"] = round(sum(float(r.total_amount or 0) for r in receipts), 2)

    # Match DGFE -> DB per totale (+ line_count se disponibile)
    db_used = set()
    orphans_created = 0
    for e in dgfe_entries:
        try:
            tot_e = round(float(e.get("totale_float", 0)), 2)
        except Exception:
            continue
        line_e = e.get("line_count")
        matched_idx = None
        for idx, r in enumerate(receipts):
            if idx in db_used:
                continue
            try:
                tot_r = round(float(r.total_amount or 0), 2)
            except Exception:
                continue
            if abs(tot_r - tot_e) >= 0.01:
                continue
            if line_e and r.voci is not None:
                voci_list = r.voci if isinstance(r.voci, list) else []
                if voci_list and len(voci_list) != line_e:
                    continue
            matched_idx = idx
            break
        if matched_idx is not None:
            db_used.add(matched_idx)
            continue

        # Nessun match: crea Receipt orfano con created_at = data DGFE (non oggi)
        try:
            dt = e.get("dataora_dt") or datetime.combine(day_date, datetime.min.time())
            prog_raw = e.get("progressivo_raw") or ""
            # Per la RCH Print 3.0 RT progressivo_raw e' gia' "ZZZZ-NNNN", uguale
            # al formato che usa il flusso normale (cassa.py:849). Usalo direttamente.
            if re.match(r'^\d+-\d+$', prog_raw):
                prog_str = prog_raw
            else:
                try:
                    prog_n = int(prog_raw)
                    prog_str = f"DGFE-{prog_n:04d}"
                except Exception:
                    prog_str = f"DGFE-{prog_raw}" if prog_raw else "DGFE-?"

            # Se un Receipt con quel progressivo esiste gia' (es. flusso normale),
            # NON duplicare: e' lo stesso scontrino, gia' tracciato, ma con totale
            # diverso (raro). Salta — sara' segnalato come "extra DB" nella tabella.
            existing_same_prog = Receipt.query.filter_by(numero_progressivo=prog_str).first()
            if existing_same_prog:
                continue

            orphan = Receipt(
                created_at=dt,
                total_amount=tot_e,
                is_fiscale=True,
                voci=[],
                cliente_id=None,
                operatore_id=None,
                numero_progressivo=prog_str
            )
            db.session.add(orphan)
            db.session.commit()
            orphans_created += 1
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error("reconcile_day: errore creazione orfano: %s", str(exc))

    summary["created_orphans"] = orphans_created

    # Receipt extra (in DB ma non in DGFE) -> log soltanto, niente azione
    extras = []
    for idx, r in enumerate(receipts):
        if idx in db_used:
            continue
        extras.append({
            "id": r.id,
            "numero_progressivo": str(r.numero_progressivo),
            "total_amount": float(r.total_amount or 0),
            "created_at": r.created_at.isoformat(timespec='seconds') if r.created_at else None
        })
    summary["suspicious_extras"] = extras

    if orphans_created == 0 and not extras:
        summary["status"] = "ok"
    elif orphans_created > 0 and not extras:
        summary["status"] = "fixed"
    else:
        summary["status"] = "discrepant"

    # ALLINEAMENTO AUTOMATICO AL DGFE (chiusura fiscale serale).
    # Dopo aver creato gli orfani mancanti, porta in modo ADDITIVO e reversibile
    # il totale fiscale del giorno in DB a coincidere col totale DGFE, scrivendo
    # la dummy ADJ-YYYYMMDD col residuo. Cosi' il dato del registro scontrini in
    # DB resta permanentemente allineato al dato fiscale della DGFE.
    # SICUREZZA: solo se la DGFE ha almeno 1 scontrino (dgfe_count > 0), per non
    # azzerare un giorno su una lettura vuota/ambigua.
    summary["alignment_action"] = "skipped"
    summary["alignment_delta"] = 0.0
    if summary["dgfe_count"] > 0:
        try:
            action, applied = _set_day_alignment_adj(day_date, summary["dgfe_total"])
            summary["alignment_action"] = action
            summary["alignment_delta"] = applied
            # Totale fiscale effettivo del giorno (scontrini reali + ADJ) == DGFE.
            summary["db_total"] = summary["dgfe_total"]
            if action in ("created", "updated"):
                summary["notes"] = (
                    (summary.get("notes") or "")
                    + f" Allineamento DGFE applicato (delta {applied:+.2f})."
                ).strip()
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error("reconcile_day: allineamento DGFE fallito: %s", str(exc))
            summary["alignment_action"] = "error"
            summary["notes"] = (
                (summary.get("notes") or "") + f" Allineamento DGFE fallito: {exc}."
            ).strip()

    try:
        _set_reconciliation_entry(bid, summary["date"], summary)
    except Exception as exc:
        current_app.logger.error("reconcile_day: scrittura log fallita: %s", str(exc))
        summary["notes"] = f"Log non scritto: {exc}"

    return summary

@cassa_bp.route('/cassa/rch-retry', methods=['POST'])
def rch_retry():
    """Verifica di uno scontrino rimasto "da verificare". NON ristampa.

    Rilegge il contatore della stampante e lo confronta con quello letto prima
    dell'ultimo invio (salvato nel pending):
    - stessa Z, documento +1         -> e' uscito: si registra (esito 'registrato')
    - stampante pronta e contatore
      fermo per due letture, e almeno
      RCH_MIN_PRIMA_DI_RISTAMPA_S
      dall'invio                     -> non e' uscito: NIENTE nel registro, il
                                        pending resta e la cassa offre la
                                        Ristampa (esito 'non_emesso')
    - contatore che non si spiega
      con un solo documento          -> non si registra niente (esito 'incerto')
    - stampante bloccata/occupata/
      senza carta/non raggiungibile  -> si aspetta (202, esito 'attesa')

    Una lettura costa al massimo ~3 s; la cassa la ripete ogni 2 s.
    """
    data = request.get_json(force=True) or {}
    key = (data.get("idempotency_key") or "").strip()
    if not key:
        return jsonify({"error": "Missing idempotency_key"}), 400
    if key in IDEMPOTENCY_STORE:
        return jsonify({"esito": "registrato", **IDEMPOTENCY_STORE[key]}), 200

    pending = RCH_PENDING.get(key)
    if not pending or not pending.get("contatori_prima"):
        RCH_PENDING.pop(key, None)
        return jsonify({
            "esito": "incerto",
            "messaggio": ("Questo scontrino non è più in verifica (il gestionale è stato "
                          "riavviato?). Non è stato registrato: controlla se è uscito "
                          "dalla stampante prima di ristamparlo.")
        }), 409

    prima = pending["contatori_prima"]
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)

    try:
        with _rch_in_uso(attesa_s=1.5):
            dopo = _rch_contatori(url, headers, rch_kwargs)
            esito = _rch_esito(prima, dopo)
            if esito == 'non_emesso':
                # Una lettura sola potrebbe cadere mentre la stampante finisce o
                # riparte: si conferma con una seconda prima di dire "non uscito".
                pytime.sleep(1.5)
                dopo = _rch_contatori(url, headers, rch_kwargs)
                esito = _rch_esito(prima, dopo)
            if esito == 'emesso':
                result = _rch_registra_pendente(key, pending, _rch_progressivo(dopo),
                                                "verifica in cassa")
                return jsonify({"esito": "registrato", **result}), 200
    except RchOccupata:
        return jsonify({"pending": True, "esito": "attesa",
                        "messaggio": MSG_RCH_OCCUPATA, "retry_after": 2}), 202

    if esito == 'attesa':
        return jsonify({"pending": True, "esito": "attesa",
                        "messaggio": _rch_messaggio_stato(dopo), "retry_after": 2}), 202

    if esito == 'non_emesso':
        if pytime.time() - pending.get("created_ts", 0) < RCH_MIN_PRIMA_DI_RISTAMPA_S:
            # Troppo presto per escludere che stia ancora finendo di stampare.
            return jsonify({"pending": True, "esito": "attesa",
                            "messaggio": "Controllo se lo scontrino è uscito...",
                            "retry_after": 2}), 202
        if not pending.get("non_emesso_registrato"):
            pending["non_emesso_registrato"] = True
            log_crm_error(
                "Scontrino non uscito (verificato dal contatore): pronto per la ristampa",
                context={"idempotency_key": key, "contatori_prima": prima,
                         "contatori_dopo": {"z": dopo["z"], "doc": dopo["doc"]},
                         "expected_total": pending.get("expected_total"),
                         "ristampe": pending.get("ristampe", 0),
                         "secondi_dall_invio": round(pytime.time() - pending.get("created_ts", 0), 1)},
                client_id=pending.get("cliente_id"),
            )
        return jsonify({
            "esito": "non_emesso",
            "puo_ristampare": True,
            "messaggio": ("Lo scontrino NON è uscito e NON è registrato. "
                          "La stampante è pronta: premi Ristampa.")
        }), 409

    # incerto
    RCH_PENDING.pop(key, None)
    log_crm_error(
        "Verifica scontrino: contatore non spiegabile, nulla registrato",
        context={"idempotency_key": key, "contatori_prima": prima,
                 "contatori_dopo": {"z": dopo["z"], "doc": dopo["doc"]},
                 "expected_total": pending.get("expected_total"),
                 "stato": dopo.get("raw")},
        client_id=pending.get("cliente_id"),
    )
    return jsonify({
        "esito": "incerto",
        "messaggio": ("La stampante ha cambiato numerazione in modo inatteso (documento "
                      f"{_rch_progressivo(dopo)}): lo scontrino NON è stato registrato. "
                      "Controlla se è uscito prima di ristamparlo.")
    }), 409


@cassa_bp.route('/cassa/rch-ristampa', methods=['POST'])
def rch_ristampa():
    """Ristampa dello scontrino rimasto da verificare, dalla finestra in cassa.

    Non ristampa mai alla cieca: sotto il lucchetto rilegge il contatore e
    - se il primo invio risulta uscito (documento +1) lo REGISTRA e non manda
      niente;
    - se e' fermo e la stampante e' pronta, rimanda LO STESSO scontrino (stesso
      payload, stesse voci) con la stessa regola del contatore +1;
    - altrimenti non manda niente e dice perche'.
    """
    data = request.get_json(force=True) or {}
    key = (data.get("idempotency_key") or "").strip()
    if not key:
        return jsonify({"error": "Missing idempotency_key"}), 400
    if key in IDEMPOTENCY_STORE:
        return jsonify({"esito": "registrato", **IDEMPOTENCY_STORE[key]}), 200

    pending = RCH_PENDING.get(key)
    if not pending or not pending.get("contatori_prima") or not pending.get("payload_xml"):
        RCH_PENDING.pop(key, None)
        return jsonify({
            "esito": "incerto",
            "messaggio": ("Questo scontrino non è più in verifica (il gestionale è stato "
                          "riavviato?). Controlla se è uscito dalla stampante; se no, chiudi "
                          "e premi di nuovo Stampa.")
        }), 409
    if pytime.time() - pending.get("created_ts", 0) < RCH_MIN_PRIMA_DI_RISTAMPA_S:
        return jsonify({"pending": True, "esito": "attesa",
                        "messaggio": "Controllo se lo scontrino è uscito...",
                        "retry_after": 2}), 202

    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)

    esecuzione = None
    try:
        with _rch_in_uso():
            pre = _rch_leggi_contatori(url, headers, rch_kwargs)
            esito_primo = _rch_esito(pending["contatori_prima"], pre)
            if esito_primo == 'emesso':
                result = _rch_registra_pendente(key, pending, _rch_progressivo(pre),
                                                "ristampa: il primo invio era uscito")
                return jsonify({"esito": "registrato", **result}), 200
            if esito_primo == 'non_emesso':
                pending["contatori_prima"] = {"z": pre["z"], "doc": pre["doc"]}
                pending["created_ts"] = pytime.time()
                pending["ristampe"] = pending.get("ristampe", 0) + 1
                pending.pop("non_emesso_registrato", None)
                esecuzione = _rch_esegui_scontrino(url, headers, rch_kwargs,
                                                   pending["payload_xml"], pre)
                if esecuzione["esito"] == 'emesso':
                    result = _rch_registra_pendente(key, pending,
                                                    _rch_progressivo(esecuzione["dopo"]), "ristampa")
                    return jsonify({"esito": "registrato", **result}), 200
    except RchOccupata:
        return jsonify({"pending": True, "esito": "attesa",
                        "messaggio": MSG_RCH_OCCUPATA, "retry_after": 2}), 202

    if esecuzione is None:
        # Niente mandato: stampante non pronta o numerazione inattesa.
        if esito_primo == 'incerto':
            RCH_PENDING.pop(key, None)
            return jsonify({"esito": "incerto",
                            "messaggio": ("La stampante ha cambiato numerazione in modo inatteso: "
                                          "niente ristampato, niente registrato. Controlla se lo "
                                          "scontrino è uscito prima di ristamparlo.")}), 409
        return jsonify({"pending": True, "esito": "attesa",
                        "messaggio": "Non ristampo: " + _rch_messaggio_stato(pre),
                        "retry_after": 2}), 202

    log_crm_error(
        "Ristampa non confermata dalla stampante: nulla registrato",
        context={"idempotency_key": key, "esito": esecuzione["esito"],
                 "motivo": esecuzione["motivo"], "invio_ms": esecuzione["invio_ms"],
                 "ristampe": pending.get("ristampe"),
                 "contatori_prima": pending.get("contatori_prima"),
                 "stato_dopo": (esecuzione["dopo"] or {}).get("raw"),
                 "risposta_vendita": esecuzione["risposta"]},
        client_id=pending.get("cliente_id"),
    )
    if esecuzione["esito"] == 'non_arrivato':
        messaggio = ("La ristampa NON è arrivata alla stampante (non risponde in rete). "
                     "Controlla che sia accesa e col cavo collegato.")
    else:
        messaggio = _rch_messaggio_motivo(esecuzione)
    return jsonify({"pending": True, "esito": "attesa", "messaggio": messaggio,
                    "retry_after": 2}), 202

# ========================================
# CONSOLE RCH - Route per sblocco manuale
# ========================================

@cassa_bp.route('/cassa/rch-console/status', methods=['GET'])
@_rch_esclusivo
def rch_console_status():
    """Query stato stampante RCH"""
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    # Codici RCH che indicano stato OK (non errore)
    # 0 = OK, 20 = Idle/pronta, 99 = operazione completata
    RCH_OK_CODES = {0, 20, 99}
    # Codici che indicano documento aperto
    RCH_DOC_OPEN_CODES = {2, 3, 4}
    
    try:
        # Query stato con C453
        payload = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C453/$0</cmd></Service>'
        resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers, timeout=8,
                             **rch_kwargs)
        
        result = {
            "printer_ip": ip,
            "printer_model": printer_model,
            "printer_url": url,
            "status": "ok",
            "error_code": None,
            "error_message": None,
            "document_open": False,
            "last_z": None,
            "last_doc": None,
            "raw_response": resp.text[:500]
        }
        
        # Parse errorCode / errCode (supporta entrambi i formati)
        m_err = re.search(r'<(?:errCode|errorCode)>(\d+)</(?:errCode|errorCode)>', resp.text)
        if m_err:
            code = int(m_err.group(1))
            result["error_code"] = code
            
            if code in RCH_OK_CODES:
                result["status"] = "ok"
                result["error_message"] = None
            elif code in RCH_DOC_OPEN_CODES:
                result["status"] = "warning"
                result["document_open"] = True
                result["error_message"] = "Documento fiscale aperto"
            else:
                result["status"] = "warning"
                result["error_message"] = f"Codice stato: {code}"
        
        # Parse lastZ e lastDocF
        m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp.text)
        m_doc = re.search(r'<lastDocF>(\d+)</lastDocF>', resp.text)
        if m_z:
            result["last_z"] = int(m_z.group(1))
        if m_doc:
            result["last_doc"] = int(m_doc.group(1))

        # errorCode dice solo se il COMANDO e' stato accettato: lo stato della
        # meccanica sta in campi separati. Con la RCH bloccata (Biella,
        # 10/10/2026) errorCode era 0 e la Console scriveva "PRONTA".
        c = _rch_parse_contatori(resp.text)
        if c is not None and result["status"] == "ok" and not _rch_pronta(c):
            result["status"] = "warning"
            result["error_message"] = _rch_messaggio_stato(c)

        return jsonify(result)
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout - stampante non risponde", "printer_ip": ip}), 504
    except Exception as e:
        return jsonify({"error": str(e), "printer_ip": ip}), 500

@cassa_bp.route('/cassa/rch-console/send-cl', methods=['POST'])
@_rch_esclusivo
def rch_console_send_cl():
    """Invia comando CL (C3 + C1) - equivale a premere tasto CL"""
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    results = []
    commands = ["=C3", "=C1"]
    
    for cmd in commands:
        try:
            payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
            resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers, timeout=10,
                                 **rch_kwargs)
            success = _rch_is_success(resp)
            results.append({"cmd": cmd, "success": success, "response": resp.text[:200]})
            pytime.sleep(0.3)
        except Exception as e:
            results.append({"cmd": cmd, "success": False, "error": str(e)})
    
    return jsonify({"results": results})


@cassa_bp.route('/cassa/rch-console/full-reset', methods=['POST'])
@_rch_esclusivo
def rch_console_full_reset():
    """Reset completo: C99 → C10 → C3 → T5/$0 → C3 → C1"""
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    results = []
    commands = ["=C99", "=C10", "=C3", "=T5/$0", "=C3", "=C1"]
    
    for cmd in commands:
        try:
            payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
            resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers, timeout=15,
                                 **rch_kwargs)
            success = _rch_is_success(resp)
            results.append({"cmd": cmd, "success": success, "response": resp.text[:200]})
            pytime.sleep(0.5)
        except Exception as e:
            results.append({"cmd": cmd, "success": False, "error": str(e)})
    
    return jsonify({"results": results})


@cassa_bp.route('/cassa/rch-console/close-document', methods=['POST'])
@_rch_esclusivo
def rch_console_close_document():
    """Chiude documento aperto con importo e metodo specificati"""
    data = request.get_json(force=True) or {}
    importo = float(data.get("importo", 0))
    metodo = data.get("metodo", "contanti")
    
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    results = []

    # Contatore PRIMA della chiusura: e' cio' che decide se lo scontrino esce
    # davvero (vedi _rch_esito). Il 10/10/2026 a Biella questa chiusura, con la
    # RCH bloccata, ha avuto errorCode 0 su tutti i comandi e ha registrato lo
    # scontrino 0001-0000, mai emesso.
    contatori_prima = None
    if importo > 0:
        contatori_prima = _rch_leggi_contatori(url, headers, rch_kwargs)
        if contatori_prima is None:
            return jsonify({
                "success": False, "esito": "attesa", "results": [],
                "error": ("La stampante non risponde: nessun comando inviato, "
                          "niente registrato."),
                "messaggio": _rch_messaggio_stato(None),
            }), 502
        if _rch_bloccata_prima_dell_invio(contatori_prima):
            return jsonify({
                "success": False, "esito": "attesa", "results": [],
                "error": "Stampante bloccata: nessun comando inviato, niente registrato.",
                "messaggio": ("La stampante risponde con i contatori a zero: è bloccata. "
                              "Se la carta c'è, spegnila e riaccendila."),
            }), 503

    # Determina comando pagamento (tender dipendente dal modello, vedi _tender_code)
    if importo <= 0:
        pay_cmd = "=T5/$0"
    else:
        cents = int(round(importo * 100))
        pay_cmd = f"={_tender_code(metodo, printer_model)}/${cents}"
    
    commands = [pay_cmd, "=C3", "=C1"]
    
    for cmd in commands:
        try:
            payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
            resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers, timeout=15,
                                 **rch_kwargs)
            success = _rch_is_success(resp)
            results.append({"cmd": cmd, "success": success, "response": resp.text[:200]})
            pytime.sleep(0.3)
        except Exception as e:
            results.append({"cmd": cmd, "success": False, "error": str(e)})
    
    all_success = all(r.get("success") for r in results)

    # Scrittura su Registro Scontrini per allineare DB ↔ AE/DGFE.
    # Eseguita solo se chiusura andata a buon fine e con importo > 0
    # (T5/$0 = abbandono documento, nessuno scontrino fiscale emesso da contabilizzare).
    receipt_progressivo = None
    db_already_present = False
    used_pending_key = None
    esito_doc = None
    contatori_dopo = None
    if all_success and importo > 0:
        try:
            esito_doc, contatori_dopo = _rch_attendi_emissione(
                url, headers, rch_kwargs, contatori_prima
            )
            if esito_doc != 'emesso':
                log_crm_error(
                    "Chiudi documento: comandi accettati ma scontrino non emesso, nulla registrato",
                    context={"importo": importo, "metodo": metodo, "esito": esito_doc,
                             "contatori_prima": {"z": contatori_prima["z"], "doc": contatori_prima["doc"]},
                             "contatori_dopo": ({"z": contatori_dopo["z"], "doc": contatori_dopo["doc"]}
                                                if contatori_dopo else None),
                             "stato_dopo": (contatori_dopo or {}).get("raw"),
                             "printer_ip": ip, "printer_model": printer_model},
                )
            else:
                progressivo_completo = _rch_progressivo(contatori_dopo)
                # Cerca un RCH_PENDING odierno con totale corrispondente, per
                # recuperare voci/cliente/operatore. Prendo il piu' recente.
                today_str = datetime.now().strftime("%Y-%m-%d")
                matched_key = None
                matched_pending = None
                for k, p in list(RCH_PENDING.items()):
                    if p.get("giorno") != today_str:
                        continue
                    try:
                        ptot = float(p.get("expected_total") or 0)
                    except Exception:
                        ptot = 0.0
                    if abs(ptot - importo) < 0.01:
                        if (matched_pending is None
                                or p.get("created_ts", 0) > matched_pending.get("created_ts", 0)):
                            matched_key = k
                            matched_pending = p

                # Il pending si toglie PRIMA di scrivere: la verifica automatica
                # della cassa (rch_retry) potrebbe vedere lo stesso documento
                # nello stesso istante e registrarlo una seconda volta.
                if matched_pending is not None and RCH_PENDING.pop(matched_key, None) is None:
                    matched_pending = None

                if matched_pending:
                    voci = matched_pending.get("voci", []) or []
                    cliente_id = matched_pending.get("cliente_id")
                    operatore_id = matched_pending.get("operatore_id")
                    used_pending_key = matched_key
                else:
                    # Receipt orfano: nessun pending in memoria (es. server riavviato,
                    # o stampante sbloccata in un momento successivo).
                    voci = []
                    cliente_id = None
                    operatore_id = None

                scritto = _registra_fiscale_confermato(voci, cliente_id, operatore_id,
                                                       importo, progressivo_completo)
                if not scritto:
                    # Gia' registrato (da send-to-rch o dalla verifica in cassa).
                    db_already_present = True
                elif matched_pending:
                    try:
                        _applica_movimenti_incasso(matched_pending.get("voci_richiesta") or voci)
                    except Exception:
                        current_app.logger.exception("close-document: movimenti carte/rate non applicati")

                if used_pending_key:
                    # Popola IDEMPOTENCY_STORE cosi' la verifica della finestra
                    # di attesa in cassa chiude da sola.
                    IDEMPOTENCY_STORE[used_pending_key] = {
                        "results": [{
                            "message": f"Scontrino fiscale registrato (progressivo {progressivo_completo})",
                            "is_fiscale": True
                        }],
                        "reset_voci": True,
                        "closed_via_console": True
                    }

                receipt_progressivo = progressivo_completo
        except Exception as exc:
            current_app.logger.error(
                "rch_console_close_document: errore scrittura Receipt: %s", str(exc)
            )
            # Non far fallire l'operazione: la stampante e' gia' sbloccata.

    if importo > 0 and all_success:
        esito_finale = 'emesso' if receipt_progressivo else (esito_doc or 'attesa')
    else:
        esito_finale = None
    return jsonify({
        "success": all_success,
        "esito": esito_finale,
        "messaggio": (None if esito_finale in (None, 'emesso') else
                      "La stampante ha accettato i comandi ma lo scontrino NON è uscito: "
                      "niente registrato. " + _rch_messaggio_stato(contatori_dopo)),
        "results": results,
        "receipt_progressivo": receipt_progressivo,
        "db_already_present": db_already_present,
        "used_pending_key": used_pending_key
    })


@cassa_bp.route('/cassa/rch-console/send-raw', methods=['POST'])
@_rch_esclusivo
def rch_console_send_raw():
    """Invia comandi raw alla stampante, in UNA sola richiesta HTTP.
    Corpo: {"command": "..."} oppure {"commands": ["...", ...]} (massimo 5).
    La forma a lista serve alla tastiera virtuale, che scrive le due righe del
    display RCH (=D1 e =D2) insieme: due richieste separate potrebbero
    accavallarsi, e la stampante non accetta comandi in parallelo."""
    data = request.get_json(force=True) or {}
    lista = data.get("commands")
    if not isinstance(lista, list):
        lista = [data.get("command")]
    commands = [str(c).strip() for c in lista if c is not None and str(c).strip()]

    if not commands:
        return jsonify({"error": "Comando vuoto"}), 400
    if len(commands) > 5:
        return jsonify({"error": "Massimo 5 comandi per richiesta"}), 400

    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400

    # Aggiungi = se non presente. Il prefisso > è supportato solo su RCH Print 3.0 RT
    def _con_prefisso(command):
        if printer_model == PrinterModel.RCH_PRINT_RT.value:
            if not command.startswith("=") and not command.startswith(">"):
                return "=" + command
        elif not command.startswith("="):
            return "=" + command
        return command

    commands = [_con_prefisso(c) for c in commands]

    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)

    try:
        # escape: "&", "<", ">" dentro <cmd> (parametri &data, testi liberi della
        # tastiera virtuale, prefisso ">") rendevano l'XML non valido. La
        # stampante decodifica le entita': la chiusura giornaliera manda gia'
        # &gt;C117 e &amp;0.
        cmd_xml = ''.join(f'<cmd>{_xml_escape(c)}</cmd>' for c in commands)
        payload = f'<?xml version="1.0" encoding="UTF-8"?><Service>{cmd_xml}</Service>'
        resp = _rch_post(url, data=payload.encode('utf-8'), headers=headers, timeout=15,
                             **rch_kwargs)

        error_code = _rch_parse_errcode(resp.text)

        return jsonify({
            "success": error_code == 0 or error_code is None,
            "error_code": error_code,
            "response": resp.text[:500],
            "command_sent": " | ".join(commands)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500