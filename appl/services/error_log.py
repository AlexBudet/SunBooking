"""
Scrittura degli errori del gestionale CRM su tabella DB (crm_error_logs),
in aggiunta al normale logging su stdout (app.logger) gia' presente nelle
route. Solo scrittura: nessun ticker, nessuna lettura/aggregazione, nessun
invio email - quello resta nell'altra web app di prenotazione, che condivide
lo stesso database e in futuro potra' leggere anche questa tabella.

Fail-open: un problema nello scrivere il log (es. DB temporaneamente giu')
non deve mai rompere la risposta gia' pronta per l'utente.
"""
import time

from flask import current_app
from appl.models import db, CrmErrorLog

# Ultimo istante in cui e' stato registrato un esaurimento connessioni, per
# tenant. Serve a NON scrivere una riga per ogni richiesta fallita: una
# saturazione dura secondi e genererebbe centinaia di righe identiche,
# annegando il riepilogo giornaliero proprio nel giorno in cui serve leggerlo.
_ultimo_avviso_connessioni = {}
INTERVALLO_AVVISO_CONNESSIONI = 600   # 10 minuti


def _stringify_context(context):
    if context is None:
        return None
    if isinstance(context, dict):
        return {str(k): str(v) for k, v in context.items()}
    return {"detail": str(context)}


def log_crm_error(reason, client_id=None, context=None):
    """Inserisce una riga in crm_error_logs. Il chiamante deve aver gia' fatto
    db.session.rollback() se la sessione era sporca per un'eccezione precedente,
    altrimenti l'insert stesso fallirebbe (transazione gia' abortita).
    client_id e' opzionale: un errore puo' capitare anche senza un cliente
    collegato (es. blocco OFF, utenza generica)."""
    try:
        entry = CrmErrorLog(
            reason=str(reason)[:255],
            client_id=client_id,
            context=_stringify_context(context),
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.warning("Impossibile scrivere su crm_error_logs: %s", e)


def log_connessioni_esaurite(origine, dettaglio=''):
    """Registra l'esaurimento delle connessioni al database.

    Due sorgenti possibili, entrambe sintomi dello stesso problema:
      - pool dell'app pieno    -> sqlalchemy.exc.TimeoutError
      - slot del server pieni  -> "remaining connection slots are reserved..."

    Il messaggio finisce SEMPRE nel log applicativo (che non richiede il
    database, ed e' importante: quando le connessioni finiscono, scrivere su
    DB e' proprio la cosa che potrebbe non riuscire) e, a colpi non piu'
    frequenti di INTERVALLO_AVVISO_CONNESSIONI, anche in crm_error_logs, da
    cui lo raccoglie il riepilogo giornaliero.
    """
    testo = (
        "CONNESSIONI AL DATABASE ESAURITE (%s). "
        "Il negozio puo' vedere errori o lentezza. "
        "Rimedio: passare il server a un tier con piu' connessioni (B2s) "
        "oppure attivare il pooler PgBouncer. NON alzare pool_size: il "
        "vincolo sono gli slot del server, non il pool dell'app. %s"
    ) % (origine, dettaglio)

    # 1) Log applicativo: sempre, non dipende dal database.
    try:
        current_app.logger.error("[connessioni] %s", testo)
    except Exception:
        pass

    # 2) Riepilogo giornaliero: al massimo una riga ogni 10 minuti.
    chiave = origine
    adesso = time.monotonic()
    ultimo = _ultimo_avviso_connessioni.get(chiave, 0)
    if adesso - ultimo < INTERVALLO_AVVISO_CONNESSIONI:
        return
    _ultimo_avviso_connessioni[chiave] = adesso

    log_crm_error(
        reason="Connessioni al database esaurite",
        context={'origine': origine, 'dettaglio': str(dettaglio)[:500],
                 'rimedio': 'tier superiore (B2s) o PgBouncer'},
    )
