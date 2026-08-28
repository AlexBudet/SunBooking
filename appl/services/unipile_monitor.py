# appl/services/unipile_monitor.py
"""Stato degli account WhatsApp collegati a Unipile.

Perche' esiste: il canone WhatsApp si paga **per account collegato**, non per
negozio e non per messaggio. Il pannello consumi finora lo deduceva dal numero
di tenant, che e' un'altra cosa: il 28/08/2026 i negozi erano 3 e gli account
collegati 2. Dedurre un costo da un numero simile ma diverso e' esattamente il
modo in cui una previsione di spesa sbaglia.

Il secondo motivo e' operativo e vale piu' del primo: un account in stato
CREDENTIALS e' un WhatsApp scollegato. Quel negozio smette di mandare
promemoria e conferme **senza nessun segnale**, finche' qualcuno non se ne
accorge dai clienti che non si presentano.

Non c'e' niente da leggere sul piano o sulle quote: l'API di Unipile non espone
subscription, billing, plan, quota, usage, limits ne' credits (provati il
28/08/2026, tutti 404). L'unico endpoint utile e' /api/v1/accounts.

Il token e' uno solo per tutta l'installazione (sta nel .env, non per tenant):
questa funzione NON va chiamata dentro il ciclo sui negozi, si chiama una volta.
"""

import os
import time
import threading

import requests

TIMEOUT_HTTP = 10
CACHE_TTL = 300          # come le metriche Azure: il pannello si ricarica, l'API no

_lock = threading.Lock()
_cache = {}


def _leggi():
    dsn = os.environ.get('UNIPILE_DSN')
    token = os.environ.get('UNIPILE_ACCESS_TOKEN')
    if not (dsn and token):
        return {'stato': 'non_configurato',
                'dettaglio': 'UNIPILE_DSN o UNIPILE_ACCESS_TOKEN non impostate'}
    try:
        r = requests.get('https://%s/api/v1/accounts' % dsn,
                         headers={'X-API-KEY': token, 'accept': 'application/json'},
                         timeout=TIMEOUT_HTTP)
    except Exception as e:
        return {'stato': 'errore', 'dettaglio': str(e)[:300]}
    if r.status_code != 200:
        return {'stato': 'errore',
                'dettaglio': 'HTTP %s - %s' % (r.status_code, (r.text or '')[:200])}
    try:
        dati = r.json()
    except Exception:
        return {'stato': 'errore', 'dettaglio': 'risposta non JSON'}

    voci = dati.get('items') or []
    # NON si salvano i dati degli account (nome del negozio, numero collegato):
    # per contare i costi non servono, e per lo stato basta lo stato.
    stati = dati.get('status_counts') or {}
    whatsapp = [v for v in voci if str(v.get('type', '')).upper() == 'WHATSAPP']
    da_sistemare = [s for s, n in stati.items() if s.upper() != 'OK' and n]
    return {
        'stato': 'ok',
        'account_totali': dati.get('total_count', len(voci)),
        'account_whatsapp': len(whatsapp),
        'per_stato': stati,
        'stati_da_sistemare': da_sistemare,
    }


def stato_account():
    """Con cache: l'API di Unipile non va interrogata a ogni ricarica di pagina."""
    adesso = time.monotonic()
    with _lock:
        scadenza, valore = _cache.get('accounts', (0, None))
        if valore is not None and adesso < scadenza:
            return valore
    valore = _leggi()
    with _lock:
        _cache['accounts'] = (adesso + CACHE_TTL, valore)
    return valore
