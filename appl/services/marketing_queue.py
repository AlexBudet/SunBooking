# appl/services/marketing_queue.py
"""Coda degli invii WhatsApp di marketing.

PERCHE' ESISTE. Il marketing mandava i messaggi dentro la richiesta HTTP, in un
ciclo `for`, uno dietro l'altro senza nessuna pausa: trenta messaggi partivano
nello stesso minuto. Sotto i 10-20 secondi fra un messaggio e l'altro WhatsApp
puo' sospendere IL NUMERO DEL NEGOZIO, e da li' non si torna indietro - non e'
un errore che si ritenta.

PERCHE' UNA CODA E NON UN'ATTESA NEL CICLO. L'attesa non si poteva mettere dove
stavano gli invii: quella e' una route sincrona, trenta messaggi per 12-20
secondi fanno fino a dieci minuti di richiesta appesa, e il browser molla molto
prima. Quindi la richiesta ACCODA e torna subito; a mandare ci pensa un thread,
con lo stesso ritmo dell'invio manuale dall'Agenda e con lo stesso orologio
condiviso (`usage_events`), cosi' marketing, Agenda e app booking si contano a
vicenda invece di sovrapporsi.

PERCHE' IN MEMORIA E NON SU TABELLA. Se l'applicazione viene riavviata a meta'
lavoro, i messaggi ancora in coda NON partono e vanno rimandati a mano. E' il
guasto giusto da avere: una coda persistente che riparte da sola all'avvio
vorrebbe dire messaggi veri a clienti veri a ogni riavvio del processo, e i
tenant montati da wsgi.py sono quelli di produzione.

Una coda per tenant: `chiave_tenant()` distingue i negozi che girano nello
stesso processo.
"""

import threading
import time as _time
from datetime import datetime, timezone

# Media della finestra 12-20 s, usata solo per dire all'operatore quanto ci
# vorra'. Non e' il ritmo vero: quello lo decide usage_monitor, messaggio per
# messaggio e con un po' di caso dentro.
SECONDI_MEDI_PER_MESSAGGIO = 16

_lock = threading.Lock()
_code = {}          # chiave tenant -> _Coda


class _Coda(object):
    def __init__(self, config):
        self.config = config
        self.messaggi = []
        self.totale = 0
        self.inviati = 0
        self.errori = 0
        self.dettagli_errori = []
        self.iniziata = datetime.now(timezone.utc)
        self.finita = None
        self.thread = None


def in_coda(chiave):
    """Quanti messaggi aspettano ancora di partire. Serve a chi calcola il
    limite giornaliero: un messaggio accodato e' un messaggio gia' impegnato,
    anche se la riga in `marketing_invii` non c'e' ancora."""
    with _lock:
        coda = _code.get(chiave)
        return len(coda.messaggi) if coda else 0


def stato(chiave):
    """Come sta andando il lavoro, per la pagina Marketing."""
    with _lock:
        coda = _code.get(chiave)
        if coda is None:
            return {'attiva': False, 'mai_partita': True}
        restanti = len(coda.messaggi)
        return {
            'attiva': bool(restanti) or coda.thread is not None,
            'totale': coda.totale,
            'inviati': coda.inviati,
            'errori': coda.errori,
            'in_coda': restanti,
            'dettagli_errori': list(coda.dettagli_errori[:5]),
            'iniziata': coda.iniziata.isoformat(),
            'finita': coda.finita.isoformat() if coda.finita else None,
            'secondi_stimati': restanti * SECONDI_MEDI_PER_MESSAGGIO,
        }


def accoda(app, chiave, messaggi, config):
    """Mette in coda i messaggi gia' pronti e, se non sta girando, avvia il
    thread che li manda. `messaggi` e' una lista di dizionari con client_id,
    nome, numero e testo: la sostituzione delle variabili e la validazione del
    numero sono gia' state fatte dentro la richiesta, dove gli errori si
    possono ancora mostrare all'operatore.

    Ritorna quanti ne ha accodati.
    """
    if not messaggi:
        return 0
    with _lock:
        coda = _code.get(chiave)
        # Una coda finita si ricomincia da zero, cosi' i contatori mostrati
        # nella pagina sono quelli dell'invio che si sta guardando e non la
        # somma di tutti quelli di oggi.
        if coda is None or (not coda.messaggi and coda.thread is None):
            coda = _Coda(config)
            _code[chiave] = coda
        coda.config = config
        coda.messaggi.extend(messaggi)
        coda.totale += len(messaggi)
        coda.finita = None
        if coda.thread is None:
            coda.thread = threading.Thread(
                target=_lavora, args=(app, chiave), daemon=True,
                name='marketing-whatsapp-%s' % chiave)
            coda.thread.start()
    return len(messaggi)


def _invia(messaggio, config):
    """La chiamata a Unipile. Ritorna (riuscito, errore).

    La forma della richiesta e' COPIATA dall'invio manuale dell'Agenda
    (`appl/routes/calendar.py`), che e' l'unico che manda davvero: form-encoded
    e non JSON, `attendees_ids` stringa e non lista, e 202 fra gli esiti buoni.
    Il marketing aveva una forma tutta sua - e infatti non ha mai spedito
    niente (`marketing_invii` vuota su tutti e due i negozi al 02/09/2026).
    """
    import requests
    resp = requests.post(
        '%s/api/v1/chats' % config['base_url'].rstrip('/'),
        headers={'X-API-KEY': config['token'], 'accept': 'application/json'},
        data={
            'account_id': config['account_id'],
            'attendees_ids': '%s@s.whatsapp.net' % messaggio['numero'],
            'text': messaggio['testo'],
        },
        timeout=30,
    )
    if resp.status_code in (200, 201, 202):
        return True, None
    return False, 'HTTP %s: %s' % (resp.status_code, (resp.text or '')[:180])


def _lavora(app, chiave):
    """Il thread che svuota la coda, un messaggio alla volta e col ritmo giusto."""
    from appl import db
    from appl.models import MarketingInvio, UsageEvent
    from appl.services import usage_monitor

    while True:
        with _lock:
            coda = _code.get(chiave)
            if coda is None:
                return
            if not coda.messaggi:
                # Fine del lavoro. Il thread si segna come chiuso QUI dentro il
                # lucchetto: accoda() guarda proprio questo per decidere se
                # deve avviarne un altro.
                coda.finita = datetime.now(timezone.utc)
                coda.thread = None
                return
            messaggio = coda.messaggi.pop(0)
            config = coda.config

        # L'attesa sta FUORI dal lucchetto degli invii. Se un operatore manda
        # una conferma dall'Agenda mentre la coda sta aspettando, non deve
        # mettersi in fila dietro a trenta messaggi di marketing: al massimo
        # aspetta il suo turno normale.
        try:
            with app.app_context():
                attesa = usage_monitor.secondi_da_attendere('whatsapp')
        except Exception:
            # Orologio non leggibile: si aspetta comunque il minimo. Il ritmo
            # e' una precauzione contro la sospensione del numero, non un
            # dettaglio da saltare quando una query non riesce.
            attesa = usage_monitor.INTERVALLO_MINIMO_S
        if attesa > 0:
            _time.sleep(attesa)

        riuscito, errore = False, None
        try:
            with app.app_context():
                with usage_monitor.lock_invio():
                    # Normalmente zero: l'attesa vera e' gia' stata fatta qui
                    # sopra. Serve per il caso in cui un invio manuale sia
                    # partito proprio mentre dormivamo.
                    usage_monitor.attendi_il_turno('whatsapp')
                    riuscito, errore = _invia(messaggio, config)

                db.session.add(MarketingInvio(
                    client_id=messaggio['client_id'],
                    messaggio=messaggio['testo'][:500],
                    stato='inviato' if riuscito else 'errore',
                    errore=(errore[:500] if errore else None),
                ))
                db.session.add(UsageEvent(
                    canale='whatsapp', tipo='marketing', origine='crm',
                    esito='ok' if riuscito else 'errore',
                    errore=(errore[:300] if errore else None),
                ))
                # Un commit per messaggio, non uno alla fine: e' `created_at`
                # di questa riga l'orologio che fa aspettare il messaggio dopo.
                # Con un commit solo in fondo tutte le righe prendono l'ora
                # d'inizio della transazione, e il ritmo non lo vede piu'
                # nessuno.
                db.session.commit()
        except Exception as e:
            riuscito, errore = False, str(e)[:300]
            try:
                with app.app_context():
                    db.session.rollback()
            except Exception:
                pass
            try:
                app.logger.warning("[marketing] invio a %s non riuscito: %s",
                                   messaggio.get('nome') or messaggio['client_id'],
                                   errore)
            except Exception:
                pass

        with _lock:
            coda = _code.get(chiave)
            if coda is None:
                return
            if riuscito:
                coda.inviati += 1
            else:
                coda.errori += 1
                if len(coda.dettagli_errori) < 20:
                    coda.dettagli_errori.append(
                        '%s: %s' % (messaggio.get('nome') or messaggio['client_id'],
                                    (errore or 'errore sconosciuto')[:80]))
