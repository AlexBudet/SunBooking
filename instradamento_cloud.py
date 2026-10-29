"""
Instradamento del cloud (wsgi.py): ogni negozio e' montato su /s/<idx>.

Lo importa SOLO wsgi.py. Il .exe (start.py, un solo negozio sulla radice) non
lo carica: per il .exe non cambia niente.
"""
import re
from urllib.parse import urlsplit

from flask import redirect, request

# Le 5 rotte della scheda cliente stanno in appl/routes/calendar.py con
# @app.route sull'app globale: il modulo si importa una volta sola, quindi le
# riceve solo la prima app creata nel processo. Ogni altro negozio le riceve
# qui, con le STESSE funzioni del .exe (stessi controlli, stessa maiuscola
# dei nomi via nome_proprio).
_ROTTE_CLIENTE = (
    ('/settings/api/client_info/<int:client_id>', 'client_info', ('GET',)),
    ('/settings/api/update_client_info', 'update_client_info', ('POST',)),
    ('/settings/api/update_client_phone', 'update_client_phone', ('POST',)),
    ('/settings/api/update_client_email', 'update_client_email', ('POST',)),
    ('/settings/api/update_client_note', 'update_client_note', ('POST',)),
)


def collega_rotte_cliente(child):
    """Da chiamare subito dopo create_app per ogni negozio del cloud,
    anche per quelli aggiunti a caldo da provision_tenant."""
    from appl.routes import calendar as rotte_calendar
    for regola, endpoint, metodi in _ROTTE_CLIENTE:
        if endpoint in child.view_functions:
            continue  # la prima app le ha gia' da calendar.py
        child.add_url_rule(regola, endpoint=endpoint,
                           view_func=getattr(rotte_calendar, endpoint),
                           methods=list(metodi))


_NEGOZIO_NEL_PERCORSO = re.compile(r'^(/s/\d+)(?:/|$)')


def installa_rimando_al_negozio(root_app, mounts):
    """Le pagine dei negozi chiamano molti indirizzi assoluti ('/calendar/...',
    '/cassa/...', '/pacchetti/...', '/settings/api/...'): sul .exe sono giusti,
    nel cloud arrivano alla root_app senza /s/<idx> e finivano in 404.

    Se la root_app non ha quella rotta e la richiesta parte da una pagina di un
    negozio montato (Referer della stessa origine che inizia con /s/<idx>), la
    si rimanda li' con 307: stesso metodo e stesso corpo, quindi vale per fetch,
    jQuery, POST/DELETE, link e cambi di pagina. Il cookie di sessione del
    negozio ha Path=/s/<idx>: lo riceve solo la richiesta rimandata, e li'
    valgono gli stessi controlli di login di sempre.

    `mounts` e' lo stesso dizionario passato a DispatcherMiddleware: i negozi
    aggiunti a caldo da provision_tenant valgono subito.
    """
    @root_app.errorhandler(404)
    def _rimanda_al_negozio(errore):
        # 404 di una rotta che la root ha davvero (es. token inesistente): resta
        if request.url_rule is not None:
            return errore
        # /s/<idx> di un negozio che non esiste: resta 404, niente giri a vuoto
        if _NEGOZIO_NEL_PERCORSO.match(request.path):
            return errore
        referer = request.headers.get('Referer') or ''
        if not referer:
            return errore
        try:
            parti = urlsplit(referer)
        except ValueError:
            return errore
        if parti.netloc.lower() != (request.host or '').lower():
            return errore
        trovato = _NEGOZIO_NEL_PERCORSO.match(parti.path or '')
        if not trovato or trovato.group(1) not in mounts:
            return errore
        destinazione = trovato.group(1) + request.path
        if request.query_string:
            destinazione += '?' + request.query_string.decode('latin-1')
        return redirect(destinazione, code=307)
