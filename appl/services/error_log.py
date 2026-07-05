"""
Scrittura degli errori del gestionale CRM su tabella DB (crm_error_logs),
in aggiunta al normale logging su stdout (app.logger) gia' presente nelle
route. Solo scrittura: nessun ticker, nessuna lettura/aggregazione, nessun
invio email - quello resta nell'altra web app di prenotazione, che condivide
lo stesso database e in futuro potra' leggere anche questa tabella.

Fail-open: un problema nello scrivere il log (es. DB temporaneamente giu')
non deve mai rompere la risposta gia' pronta per l'utente.
"""
from flask import current_app
from appl.models import db, CrmErrorLog


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
