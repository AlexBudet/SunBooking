# appl/services/usage_projection.py
"""Proiezioni di scalabilita': dai consumi misurati oggi, a quanti negozi si
rompe cosa.

Il senso di questo modulo e' togliere dai fogli di calcolo e dagli appunti i
numeri di capienza, e ricalcolarli sui consumi VERI invece che su stime fatte
una volta sola. Le stime invecchiano; una media misurata sugli ultimi 30 giorni
no.

Ogni proiezione dichiara le proprie ipotesi (`ipotesi`) e il proprio limite
(`limite`), perche' un numero come "reggi 11 negozi" senza sapere da cosa
deriva non e' utilizzabile per decidere.

I prezzi NON sono scritti nel codice come verita': stanno in variabili
d'ambiente con un valore di partenza. Un listino cambia senza avvisare, e un
prezzo sbagliato dentro il codice e' peggio di un prezzo assente perche' nessuno
va a ricontrollarlo.
"""

import os


def _euro(chiave, predefinito):
    try:
        return float(os.environ.get(chiave, predefinito))
    except (TypeError, ValueError):
        return float(predefinito)


# Valori di partenza, tutti sovrascrivibili da .env.
PREZZO_WHATSAPP_TENANT_MESE = ('PREZZO_WHATSAPP_TENANT_MESE', 5.0)   # Unipile, per account collegato
PREZZO_EMAIL_UNITARIO       = ('PREZZO_EMAIL_UNITARIO', 0.00025)     # Azure Communication Services, per e-mail
TENANT_WHATSAPP_INCLUSI     = ('TENANT_WHATSAPP_INCLUSI', 10)        # account gia' compresi nel canone

# Tetti mensili di messaggi, se ce ne sono. Zero (o variabile assente) = nessun
# tetto: si mostrano i totali e basta. NON si mette qui un numero inventato -
# una soglia sbagliata e' peggio di una soglia assente, perche' fa stare
# tranquilli fino al giorno in cui non arrivano piu' i messaggi.
SOGLIA_WHATSAPP_MESE        = ('SOGLIA_WHATSAPP_MESE', 0)
SOGLIA_EMAIL_MESE           = ('SOGLIA_EMAIL_MESE', 0)


def proiezione_connessioni(n_tenant, tetto_pool_per_tenant, max_connections,
                           connessioni_riservate=0, connessioni_altre_app=0):
    """Quanti negozi entrano nel server prima che finiscano gli slot.

    Il conto e' pool x tenant, non "utenti collegati": una connessione non e'
    un utente, viene presa in prestito per la durata della query. Il tetto per
    tenant e' pool_size + max_overflow, cioe' il massimo che quel tenant puo'
    arrivare a occupare contemporaneamente.

    connessioni_altre_app: gli altri processi che pescano dallo stesso server e
    che sono facilissimi da dimenticare nel conto (l'app di prenotazione ha i
    propri engine, con i propri pool).
    """
    disponibili = max(0, max_connections - connessioni_riservate - connessioni_altre_app)
    per_tenant = max(1, tetto_pool_per_tenant)
    capienza = disponibili // per_tenant
    usate_ora = n_tenant * per_tenant
    return {
        'tipo': 'connessioni',
        'metrica': 'Connessioni al database',
        'valore_attuale': usate_ora,
        'limite': max_connections,
        'disponibili_per_app': disponibili,
        'per_tenant': per_tenant,
        'tenant_ora': n_tenant,
        'tenant_massimi': capienza,
        'margine_tenant': capienza - n_tenant,
        'percentuale_usata': round(100.0 * usate_ora / disponibili, 1) if disponibili else None,
        'ipotesi': ("nel momento peggiore ogni negozio occupa tutte le "
                    "connessioni che ha a disposizione contemporaneamente"),
        'nota': ("e' il primo limite che si incontra aggiungendo negozi. Si "
                 "sposta in due modi: passare a un piano Azure con piu' "
                 "connessioni, oppure mettere davanti al database un "
                 "ripartitore di connessioni (PgBouncer). NON si risolve "
                 "dandone di piu' a ogni negozio: i posti sul server "
                 "restano quelli."),
    }


def proiezione_storage(byte_per_tenant, n_tenant, quota_byte=None):
    """Spazio: quanto pesa oggi un negozio medio e quanti ce ne stanno.

    Si usa la MEDIA e non il totale perche' i negozi hanno anzianita' diverse:
    sommare un negozio di tre anni e uno di tre mesi e dividere per due da' un
    numero piu' onesto di quanto pesera' il prossimo.
    """
    if not byte_per_tenant:
        return {'tipo': 'storage', 'metrica': 'Spazio database',
                'in_attesa': 'nessun database misurato'}
    totale = sum(byte_per_tenant)
    medio = totale / len(byte_per_tenant)
    res = {
        'tipo': 'storage',
        'metrica': 'Spazio database',
        'totale_byte': totale,
        'medio_byte': round(medio),
        'massimo_byte': max(byte_per_tenant),
        'tenant_ora': n_tenant,
        'ipotesi': "il prossimo negozio pesera' quanto la media di quelli attuali",
    }
    if quota_byte:
        res['quota_byte'] = quota_byte
        res['percentuale_usata'] = round(100.0 * totale / quota_byte, 1)
        res['tenant_massimi'] = int(quota_byte // medio) if medio else None
        res['margine_tenant'] = (res['tenant_massimi'] - n_tenant
                                 if res['tenant_massimi'] is not None else None)
    return res


def proiezione_messaggi(invii_per_canale_per_tenant, n_tenant, tenant_obiettivo=100,
                        tenant_non_misurati=0):
    """Volume di messaggi e costo, oggi e all'obiettivo.

    Il costo WhatsApp NON e' per messaggio ma per account collegato: e' un
    canone per negozio, quindi cresce con i negozi e non con l'uso. Le e-mail
    invece si pagano a pezzo. Sono due matematiche diverse e tenerle separate
    evita la stima sbagliata classica (moltiplicare i messaggi per un prezzo
    unitario che non esiste).

    `invii_per_canale_per_tenant` contiene SOLO i negozi che si e' riusciti a
    misurare; `tenant_non_misurati` conta quelli letti male (tabella mancante,
    database non raggiungibile). La distinzione non e' formale: un negozio che
    non si riesce a leggere non e' un negozio che manda zero messaggi, e
    metterlo nel denominatore abbassa la media e sottostima la proiezione.
    """
    wa_mese = sum(t.get('whatsapp', 0) for t in invii_per_canale_per_tenant)
    em_mese = sum(t.get('email', 0) for t in invii_per_canale_per_tenant)
    misurati = len(invii_per_canale_per_tenant)
    divisore = max(1, misurati)

    wa_per_tenant = wa_mese / divisore
    em_per_tenant = em_mese / divisore

    prezzo_wa = _euro(*PREZZO_WHATSAPP_TENANT_MESE)
    prezzo_em = _euro(*PREZZO_EMAIL_UNITARIO)
    inclusi = int(_euro(*TENANT_WHATSAPP_INCLUSI))

    def blocco(n, wa_msg, em_msg):
        """I messaggi sono un dato, il costo una funzione del numero di negozi.
        Per "oggi" i messaggi sono la somma MISURATA, non una moltiplicazione:
        estrapolare il presente da se stesso e' solo un modo per nasconderci
        dentro i negozi non misurati."""
        return {
            'tenant': n,
            'whatsapp_messaggi_mese': round(wa_msg),
            'email_messaggi_mese': round(em_msg),
            'costo_whatsapp_mese': round(max(0, n - inclusi) * prezzo_wa, 2),
            'costo_email_mese': round(em_msg * prezzo_em, 2),
        }

    oggi = blocco(n_tenant, wa_mese, em_mese)
    domani = blocco(tenant_obiettivo,
                    wa_per_tenant * tenant_obiettivo,
                    em_per_tenant * tenant_obiettivo)
    res = {
        'tipo': 'messaggi',
        'metrica': 'Messaggi e costo variabile',
        'oggi': oggi,
        'obiettivo': domani,
        'tenant_misurati': misurati,
        'tenant_non_misurati': tenant_non_misurati,
        'per_tenant_mese': {
            'whatsapp': round(wa_per_tenant, 1),
            'email': round(em_per_tenant, 1),
        },
        'prezzi_usati': {
            'whatsapp_per_tenant_mese': prezzo_wa,
            'email_unitario': prezzo_em,
            'tenant_whatsapp_inclusi': inclusi,
        },
        'ipotesi': ('un negozio nuovo manda quanto la media di quelli attuali; il '
                    'canone WhatsApp si paga per account collegato, non per messaggio'),
    }
    # Quanto si e' vicini al tetto, oggi e all'obiettivo. La seconda riga e' la
    # piu' utile delle due: dice se il tetto lo si sfonda CRESCENDO, cioe'
    # mentre si e' ancora in tempo a cambiare piano.
    def _soglia(canale, inviati, previsti, tetto):
        if not tetto:
            return None
        return {
            'canale': canale,
            'inviati': round(inviati),
            'soglia': int(tetto),
            'percentuale': round(100.0 * inviati / tetto, 1),
            'margine': int(round(tetto - inviati)),
            'previsti_obiettivo': round(previsti),
            'percentuale_obiettivo': round(100.0 * previsti / tetto, 1),
            'sfora_a_obiettivo': previsti > tetto,
            'tenant_obiettivo': tenant_obiettivo,
        }

    soglie = [
        _soglia('WhatsApp', wa_mese, wa_per_tenant * tenant_obiettivo,
                int(_euro(*SOGLIA_WHATSAPP_MESE))),
        _soglia('E-mail', em_mese, em_per_tenant * tenant_obiettivo,
                int(_euro(*SOGLIA_EMAIL_MESE))),
    ]
    res['soglie'] = [s for s in soglie if s]
    if not res['soglie']:
        res['soglie_assenti'] = (
            'nessun tetto dichiarato: imposta SOGLIA_WHATSAPP_MESE e '
            'SOGLIA_EMAIL_MESE per vedere quanto manca al limite')

    if tenant_non_misurati:
        def _negozi(n):
            return '1 negozio' if n == 1 else '%d negozi' % n
        res['avviso'] = (
            "Di %s su %d non si riesce a leggere il conteggio (manca la tabella "
            "usage_events o il database non risponde): i messaggi qui sotto sono "
            "solo quelli di %s, non un totale."
            % (_negozi(tenant_non_misurati), n_tenant, _negozi(misurati)))
    return res


def proiezione_traffico(richieste_ora_per_tenant, n_tenant, tenant_obiettivo=100,
                        tetto_richieste_secondo=None):
    """Richieste al secondo, oggi e all'obiettivo.

    Il numero da guardare e' il PICCO, non la media: un'applicazione cade
    nell'ora di punta, non nella media di sette giorni.
    """
    if not richieste_ora_per_tenant:
        return {'tipo': 'traffico', 'metrica': 'Traffico HTTP',
                'in_attesa': ('il conteggio parte dal primo rilascio di questa '
                              'versione: i primi numeri compaiono dopo qualche '
                              'ora di lavoro normale')}
    tenant = max(1, n_tenant)
    picco_ora = max(richieste_ora_per_tenant)
    medio_ora = sum(richieste_ora_per_tenant) / tenant

    res = {
        'tipo': 'traffico',
        'metrica': 'Traffico HTTP',
        'picco_orario_tenant': picco_ora,
        'medio_orario_tenant': round(medio_ora, 1),
        'req_sec_oggi': round(sum(richieste_ora_per_tenant) / 3600.0, 2),
        'req_sec_obiettivo': round(medio_ora * tenant_obiettivo / 3600.0, 2),
        'req_sec_obiettivo_picco': round(picco_ora * tenant_obiettivo / 3600.0, 2),
        'tenant_obiettivo': tenant_obiettivo,
        'ipotesi': ("i negozi hanno l'ora di punta nello stesso momento. E' "
                    "l'ipotesi prudente: stessi orari di apertura, stessa zona"),
    }
    if tetto_richieste_secondo:
        res['tetto_richieste_secondo'] = tetto_richieste_secondo
        if medio_ora:
            res['tenant_massimi'] = int(tetto_richieste_secondo * 3600 / medio_ora)
            res['margine_tenant'] = res['tenant_massimi'] - n_tenant
    return res


def riepilogo(proiezioni):
    """Il vincolo che si incontra per primo.

    E' l'unica riga che conta davvero: crescendo si rompe una cosa sola, la
    prima, e le altre non si vedono nemmeno. Ordinare per margine evita di
    lavorare sul secondo collo di bottiglia mentre il primo e' gia' addosso.
    """
    candidati = []
    for p in proiezioni:
        margine = p.get('margine_tenant')
        if isinstance(margine, int):
            candidati.append((margine, p.get('metrica'), p.get('tenant_massimi')))
    if not candidati:
        return {'primo_vincolo': None}
    candidati.sort()
    margine, metrica, massimi = candidati[0]
    return {
        'primo_vincolo': metrica,
        'tenant_massimi': massimi,
        'margine_tenant': margine,
        'classifica': [
            {'metrica': m, 'tenant_massimi': mx, 'margine_tenant': mg}
            for mg, m, mx in candidati
        ],
    }
