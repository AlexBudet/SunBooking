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

# I limiti dei fornitori sono AL MINUTO e ALL'ORA, non al mese: un totale
# mensile tranquillo non esclude affatto una raffica che li sfonda, e infatti
# un tetto mensile non esiste ne' per ACS ne' per Unipile (le due SOGLIA_*_MESE
# restano a 0 apposta).
#
# Questi tre numeri stanno NEL CODICE e non solo nell'ambiente, al contrario
# dei prezzi qui sopra. Non e' un'incoerenza: un prezzo cambia in silenzio con
# un contratto e nessuno se ne accorge, un limite di piattaforma e' pubblicato
# da Microsoft e cambia con la documentazione. Averlo qui vuol dire che il
# pannello avvisa da subito, senza dipendere da una variabile che qualcuno deve
# ricordarsi di impostare. La variabile d'ambiente resta e ha la precedenza:
# serve il giorno che si ottiene un aumento di quota dal supporto.
#
# Fonte: learn.microsoft.com/azure/communication-services/concepts/service-limits
# "Rate Limits for Email" - Custom Domains, letta il 28/08/2026.
# Attenzione: quei limiti sono PER SOTTOSCRIZIONE, non per risorsa e non per
# negozio - tutti i tenant pescano dallo stesso tetto.
SOGLIA_EMAIL_MINUTO         = ('SOGLIA_EMAIL_MINUTO', 30)    # ACS, dominio verificato
SOGLIA_EMAIL_ORA            = ('SOGLIA_EMAIL_ORA', 100)      # ACS, dominio verificato

# WhatsApp via Unipile: **nessun limite orario esiste**, ne' di Unipile ne' di
# WhatsApp. Unipile non impone tetti (il piano e' ad account collegati, non a
# messaggi) e WhatsApp non pubblica soglie: restringe in base al COMPORTAMENTO
# - troppe chat nuove senza risposta, segnalazioni di spam. Quindi qui 0: una
# percentuale su un tetto inventato e' peggio di nessuna percentuale.
SOGLIA_WHATSAPP_ORA         = ('SOGLIA_WHATSAPP_ORA', 0)

# L'unico numero che Unipile pubblica davvero e' un INTERVALLO: mai sotto i
# 10-20 secondi fra un messaggio e l'altro. Tradotto in tetto misurabile sono 6
# messaggi al minuto al massimo (3 volendo stare sui 20 secondi).
# E il rischio non e' un errore che si ritenta: e' la sospensione del numero
# WhatsApp DEL NEGOZIO, che nessuna riprova rimette a posto.
# Fonte: developer.unipile.com/docs/provider-limits-and-restrictions, 28/08/2026.
SOGLIA_WHATSAPP_MINUTO      = ('SOGLIA_WHATSAPP_MINUTO', 6)

# Sopra questa percentuale si avvisa PRIMA di sbattere. Un allarme che scatta
# al 100% e' un allarme che scatta a danno avvenuto.
ATTENZIONE_PCT = 80.0


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
                        tenant_non_misurati=0, picchi_orari=None):
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
    # La conseguenza NON e' la stessa sui due canali, e scriverne una sola
    # sarebbe falso su uno dei due: superare ACS fa respingere i messaggi e si
    # ritenta, superare il ritmo su WhatsApp puo' far sospendere il numero DEL
    # NEGOZIO - e da li' non si torna indietro con una riprova.
    RISCHIO = {
        'E-mail': 'gli invii oltre il tetto vengono respinti dal fornitore (errore 429)',
        'WhatsApp': 'WhatsApp puo’ sospendere il numero del negozio',
    }

    def _soglia(canale, periodo, usati, tetto, previsti=None):
        """Un tetto solo, con il suo livello di allarme.

        `livello` e' cio' che il pannello colora: 'ok' / 'attenzione' / 'superata'.
        Si avvisa all'80% e non al 100% perche' un allarme che scatta quando il
        limite e' gia' stato raggiunto arriva a messaggi gia' respinti.
        """
        if not tetto:
            return None
        pct = 100.0 * usati / tetto
        voce = {
            'canale': canale,
            'periodo': periodo,
            'inviati': round(usati),
            'soglia': int(tetto),
            'percentuale': round(pct, 1),
            'margine': int(round(tetto - usati)),
            'livello': ('superata' if pct >= 100 else
                        'attenzione' if pct >= ATTENZIONE_PCT else 'ok'),
            'rischio': RISCHIO.get(canale, ''),
        }
        if previsti is not None:
            voce.update({
                'previsti_obiettivo': round(previsti),
                'percentuale_obiettivo': round(100.0 * previsti / tetto, 1),
                'sfora_a_obiettivo': previsti > tetto,
                'tenant_obiettivo': tenant_obiettivo,
            })
        return voce

    picchi = picchi_orari or {}
    soglie = [
        _soglia('WhatsApp', 'al mese', wa_mese, int(_euro(*SOGLIA_WHATSAPP_MESE)),
                previsti=wa_per_tenant * tenant_obiettivo),
        _soglia('E-mail', 'al mese', em_mese, int(_euro(*SOGLIA_EMAIL_MESE)),
                previsti=em_per_tenant * tenant_obiettivo),
        # I picchi NON si proiettano a 100 negozi: il picco di un negozio non
        # si somma a quello di un altro se non mandano nello stesso istante, e
        # moltiplicarlo per 100 produrrebbe un allarme finto.
        _soglia('WhatsApp', "nell'ora di punta", picchi.get('whatsapp_ora', 0),
                int(_euro(*SOGLIA_WHATSAPP_ORA))),
        _soglia('WhatsApp', 'nel minuto di punta', picchi.get('whatsapp_minuto', 0),
                int(_euro(*SOGLIA_WHATSAPP_MINUTO))),
        _soglia('E-mail', "nell'ora di punta", picchi.get('email_ora', 0),
                int(_euro(*SOGLIA_EMAIL_ORA))),
        _soglia('E-mail', 'nel minuto di punta', picchi.get('email_minuto', 0),
                int(_euro(*SOGLIA_EMAIL_MINUTO))),
    ]
    res['soglie'] = [s for s in soglie if s]
    res['picchi'] = {
        'whatsapp_ora': picchi.get('whatsapp_ora', 0),
        'whatsapp_minuto': picchi.get('whatsapp_minuto', 0),
        'email_ora': picchi.get('email_ora', 0),
        'email_minuto': picchi.get('email_minuto', 0),
    }
    if not res['soglie']:
        res['soglie_assenti'] = (
            'nessun tetto dichiarato. I limiti dei fornitori sono al minuto e '
            "all'ora, non al mese: le variabili sono SOGLIA_EMAIL_MINUTO, "
            'SOGLIA_EMAIL_ORA, SOGLIA_EMAIL_MESE (e le corrispondenti '
            'SOGLIA_WHATSAPP_*)')

    if tenant_non_misurati:
        def _negozi(n):
            return '1 negozio' if n == 1 else '%d negozi' % n
        res['avviso'] = (
            "Di %s su %d non si riesce a leggere il conteggio (manca la tabella "
            "usage_events o il database non risponde): i messaggi qui sotto sono "
            "solo quelli di %s, non un totale."
            % (_negozi(tenant_non_misurati), n_tenant, _negozi(misurati)))
    return res


def proiezione_traffico(picco_simultaneo, richieste_totali, ore_osservate,
                        n_tenant, tenant_obiettivo=100,
                        tetto_richieste_secondo=None):
    """Richieste al secondo, oggi e all'obiettivo.

    Attenzione a cosa sono gli ingredienti, perche' la versione precedente di
    questa funzione sbagliava proprio qui:

    - `picco_simultaneo` e' l'ora peggiore sommando i negozi NELLA STESSA ORA.
      Prima si sommavano i picchi di ciascun negozio, che pero' capitano in ore
      diverse: il risultato era un'ora che non e' mai esistita, presentata come
      "richieste al secondo" attuali.
    - `richieste_totali` / `ore_osservate` danno la media VERA. Prima la
      "media oraria per negozio" era la media dei picchi, cioe' un numero
      sistematicamente troppo alto con l'etichetta di una media.

    Il numero su cui si decide resta il picco: un'applicazione cade nell'ora di
    punta, non nella media della settimana.
    """
    if not richieste_totali or not ore_osservate:
        return {'tipo': 'traffico', 'metrica': 'Traffico HTTP',
                'in_attesa': ('il conteggio parte dal primo rilascio di questa '
                              'versione: i primi numeri compaiono dopo qualche '
                              'ora di lavoro normale')}
    tenant = max(1, n_tenant)
    media_oraria_totale = richieste_totali / float(ore_osservate)
    media_per_tenant = media_oraria_totale / tenant
    picco_per_tenant = picco_simultaneo / float(tenant)

    res = {
        'tipo': 'traffico',
        'metrica': 'Traffico HTTP',
        'picco_simultaneo': round(picco_simultaneo),
        'picco_per_tenant': round(picco_per_tenant),
        'media_oraria_per_tenant': round(media_per_tenant, 1),
        'ore_osservate': round(ore_osservate),
        'req_sec_medio': round(media_oraria_totale / 3600.0, 2),
        'req_sec_picco': round(picco_simultaneo / 3600.0, 2),
        'req_sec_obiettivo': round(media_per_tenant * tenant_obiettivo / 3600.0, 2),
        'req_sec_obiettivo_picco': round(picco_per_tenant * tenant_obiettivo / 3600.0, 2),
        'tenant_obiettivo': tenant_obiettivo,
        'ipotesi': ("per la riga di punta si assume che i negozi abbiano l'ora "
                    "piena nello stesso momento: e' l'ipotesi prudente, stessi "
                    "orari di apertura e stessa zona"),
    }
    if tetto_richieste_secondo:
        res['tetto_richieste_secondo'] = tetto_richieste_secondo
        # La capienza si calcola sul PICCO per negozio, non sulla media: un
        # server dimensionato sulla media va giu' tutti i giorni alle nove.
        if picco_per_tenant:
            res['tenant_massimi'] = int(tetto_richieste_secondo * 3600 / picco_per_tenant)
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
