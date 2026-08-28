# appl/services/azure_monitor.py
"""Lettura delle metriche Azure (CPU, RAM, storage, e-mail) via Azure Monitor.

Perche' serve un servizio esterno per CPU e RAM: dentro l'App Service il
processo NON vede la propria quota. Un psutil.virtual_memory() qui riporta la
memoria della macchina che ospita il container, non quella del piano: si
misurerebbe una cosa diversa da quella che fa scattare il throttling. L'unica
fonte che conosce il tetto reale e' Azure Monitor.

Autenticazione: managed identity dell'App Service. Nessuna chiave e nessun
segreto nel .env - Azure inietta IDENTITY_ENDPOINT/IDENTITY_HEADER nel processo
e da li' si ottiene un token per management.azure.com.

Niente dipendenze nuove: si parla direttamente HTTP con `requests`, che e' gia'
in requirements.txt. azure-identity + azure-monitor-query farebbero la stessa
cosa portandosi dietro una decina di pacchetti.

Se la managed identity non e' configurata il modulo NON esplode: ogni funzione
risponde con stato 'non_configurato' e il pannello lo mostra come tale. Il
monitoraggio e' una comodita', non deve poter far cadere il pannello owner.
"""

import os
import time
import threading
from datetime import datetime, timedelta, timezone

import requests

# ---- Configurazione (tutta da variabili d'ambiente) -------------------------
# Gli ID risorsa completi si copiano dal portale Azure: Proprieta' > ID risorsa.
# Formato: /subscriptions/<sub>/resourceGroups/<rg>/providers/<tipo>/<nome>
RES_APP_SERVICE = 'AZURE_RES_APP_SERVICE'   # Microsoft.Web/serverfarms (il PIANO, non il sito)
RES_POSTGRES    = 'AZURE_RES_POSTGRES'      # Microsoft.DBforPostgreSQL/flexibleServers
RES_ACS         = 'AZURE_RES_ACS'           # Microsoft.Communication/communicationServices
RES_STORAGE     = 'AZURE_RES_STORAGE'       # Microsoft.Storage/storageAccounts

API_VERSION_METRICS = '2023-10-01'
MANAGEMENT_SCOPE = 'https://management.azure.com'

# Le metriche costano (chiamate API a consumo) e sono soggette a throttling.
# Il pannello si puo' aggiornare quanto vuole: sotto c'e' questa cache.
CACHE_TTL = 300          # 5 minuti
TIMEOUT_HTTP = 10        # secondi: meglio un riquadro vuoto che un pannello appeso

_lock = threading.Lock()
_cache = {}              # chiave -> (scadenza_monotonic, valore)
_token_cache = {}        # scope -> (scadenza_epoch, token)


# ---- Token dalla managed identity ------------------------------------------
def _get_token(scope=MANAGEMENT_SCOPE):
    """Token della managed identity assegnata all'App Service.

    Due generazioni di endpoint, entrambe ancora in giro:
      - IDENTITY_ENDPOINT + IDENTITY_HEADER  (attuale, api-version 2019-08-01)
      - MSI_ENDPOINT + MSI_SECRET            (vecchia, api-version 2017-09-01)
    In locale non esiste nessuna delle due e la funzione torna None: e' il caso
    normale in sviluppo, non un errore.
    """
    with _lock:
        scaduto_il, token = _token_cache.get(scope, (0, None))
        # Margine di 5 minuti: un token che scade mentre e' in volo produce un
        # 401 difficile da leggere nei log.
        if token and time.time() < scaduto_il - 300:
            return token

    endpoint = os.environ.get('IDENTITY_ENDPOINT') or os.environ.get('MSI_ENDPOINT')
    if not endpoint:
        return None

    if os.environ.get('IDENTITY_HEADER'):
        headers = {'X-IDENTITY-HEADER': os.environ['IDENTITY_HEADER']}
        params = {'resource': scope, 'api-version': '2019-08-01'}
    else:
        headers = {'Secret': os.environ.get('MSI_SECRET', '')}
        params = {'resource': scope, 'api-version': '2017-09-01'}

    try:
        r = requests.get(endpoint, headers=headers, params=params, timeout=TIMEOUT_HTTP)
        r.raise_for_status()
        dati = r.json()
    except Exception:
        return None

    token = dati.get('access_token')
    if not token:
        return None

    # expires_on a volte e' un epoch, a volte una data leggibile: se non si
    # riesce a interpretarlo si tiene il token per 10 minuti e si rifa'.
    try:
        scade = int(dati.get('expires_on'))
    except (TypeError, ValueError):
        scade = int(time.time()) + 600

    with _lock:
        _token_cache[scope] = (scade, token)
    return token


def identita_configurata():
    """True se il processo gira con una managed identity utilizzabile."""
    return bool(os.environ.get('IDENTITY_ENDPOINT') or os.environ.get('MSI_ENDPOINT'))


# ---- Chiamata generica alle metriche ---------------------------------------
def _leggi_metriche(resource_id, metriche, minuti=60, intervallo='PT5M',
                    aggregazione='Average'):
    """Ritorna {nome_metrica: {'ultimo': float|None, 'serie': [(iso, valore)]}}.

    Solleva RuntimeError con un messaggio leggibile: chi chiama decide se
    mostrarlo o ignorarlo.
    """
    token = _get_token()
    if not token:
        raise RuntimeError('managed identity non disponibile')

    fine = datetime.now(timezone.utc)
    inizio = fine - timedelta(minutes=minuti)
    url = MANAGEMENT_SCOPE + resource_id + '/providers/Microsoft.Insights/metrics'
    timespan = '{}/{}'.format(
        inizio.isoformat().replace('+00:00', 'Z'),
        fine.isoformat().replace('+00:00', 'Z'),
    )
    params = {
        'api-version': API_VERSION_METRICS,
        'metricnames': ','.join(metriche),
        'timespan': timespan,
        'interval': intervallo,
        'aggregation': aggregazione,
    }
    r = requests.get(url, headers={'Authorization': 'Bearer ' + token},
                     params=params, timeout=TIMEOUT_HTTP)
    if r.status_code == 403:
        raise RuntimeError("permesso negato: manca il ruolo Monitoring Reader sulla risorsa")
    if r.status_code == 404:
        raise RuntimeError('risorsa non trovata: ID risorsa errato')
    r.raise_for_status()

    campo = aggregazione.lower()
    risultato = {}
    for m in r.json().get('value', []):
        nome = (m.get('name') or {}).get('value') or ''
        serie = []
        for ts in m.get('timeseries', []):
            for punto in ts.get('data', []):
                valore = punto.get(campo)
                if valore is not None:
                    serie.append((punto.get('timeStamp'), float(valore)))
        risultato[nome] = {
            'ultimo': serie[-1][1] if serie else None,
            'serie': serie,
        }
    return risultato


def _con_cache(chiave, produttore):
    """Esegue `produttore` al massimo una volta ogni CACHE_TTL secondi."""
    adesso = time.monotonic()
    with _lock:
        scadenza, valore = _cache.get(chiave, (0, None))
        if valore is not None and adesso < scadenza:
            return valore
    valore = produttore()
    with _lock:
        _cache[chiave] = (adesso + CACHE_TTL, valore)
    return valore


def _blocco(resource_env, metriche, minuti, etichette):
    """Costruisce un riquadro del pannello, gestendo i tre stati possibili:
    non configurato / errore / dati."""
    resource_id = os.environ.get(resource_env)
    if not resource_id:
        return {'stato': 'non_configurato',
                'dettaglio': 'variabile ' + resource_env + ' non impostata'}
    if not identita_configurata():
        return {'stato': 'non_configurato',
                'dettaglio': 'managed identity non attiva su questa app'}
    try:
        dati = _leggi_metriche(resource_id, metriche, minuti=minuti)
    except Exception as e:
        return {'stato': 'errore', 'dettaglio': str(e)[:200]}

    valori = {}
    for nome, etichetta in etichette.items():
        m = dati.get(nome) or {}
        valori[nome] = {
            'etichetta': etichetta,
            'valore': m.get('ultimo'),
            'serie': m.get('serie', []),
        }
    return {'stato': 'ok', 'metriche': valori}


# ---- I quattro riquadri ----------------------------------------------------
def metriche_app_service(minuti=180):
    """CPU e memoria del PIANO App Service (non del singolo sito: le quote sono
    del piano, ed e' il piano che va in throttling)."""
    return _con_cache(('appservice', minuti), lambda: _blocco(
        RES_APP_SERVICE,
        ['CpuPercentage', 'MemoryPercentage'],
        minuti,
        {'CpuPercentage': 'CPU %', 'MemoryPercentage': 'RAM %'},
    ))


def metriche_postgres(minuti=180):
    """Server PostgreSQL: e' qui che si legge quanto manca al tetto delle
    connessioni, la metrica che ha prodotto l'avviso del 27/08/2026."""
    return _con_cache(('postgres', minuti), lambda: _blocco(
        RES_POSTGRES,
        ['cpu_percent', 'memory_percent', 'storage_percent', 'active_connections'],
        minuti,
        {'cpu_percent': 'CPU %', 'memory_percent': 'RAM %',
         'storage_percent': 'Storage %', 'active_connections': 'Connessioni attive'},
    ))


def metriche_email(minuti=1440):
    """Volume e-mail di Azure Communication Services. Conta gli invii DAL LATO
    DI AZURE: e' il numero che finisce in fattura, e comprende anche quelli che
    l'applicazione non e' riuscita a registrare (processo morto a meta' invio)."""
    return _con_cache(('acs', minuti), lambda: _blocco(
        RES_ACS,
        ['EmailSendMailRequestCount', 'EmailDeliveredCount', 'EmailBouncedCount'],
        minuti,
        {'EmailSendMailRequestCount': 'Richieste di invio',
         'EmailDeliveredCount': 'Consegnate',
         'EmailBouncedCount': 'Respinte'},
    ))


def metriche_storage(minuti=1440):
    """Spazio occupato dall'account di storage (allegati, backup applicativi)."""
    return _con_cache(('storage', minuti), lambda: _blocco(
        RES_STORAGE,
        ['UsedCapacity'],
        minuti,
        {'UsedCapacity': 'Spazio usato (byte)'},
    ))


def stato_configurazione():
    """Riassunto per il pannello: cosa manca prima che i riquadri Azure possano
    funzionare. Serve a non far indovinare all'utente quale delle quattro
    variabili non ha impostato."""
    return {
        'managed_identity': identita_configurata(),
        'risorse': {
            'app_service': bool(os.environ.get(RES_APP_SERVICE)),
            'postgres': bool(os.environ.get(RES_POSTGRES)),
            'acs': bool(os.environ.get(RES_ACS)),
            'storage': bool(os.environ.get(RES_STORAGE)),
        },
    }
