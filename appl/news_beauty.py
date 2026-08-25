# appl/news_beauty.py
"""
Scan automatico delle notizie dal mondo beauty / estetica / normativa estetica /
solarium in Italia, tramite l'API di Claude con la ricerca web attiva.

COME FUNZIONA
-------------
- create_app() (appl/__init__.py) registra qui ogni tenant con register_app().
- Il PRIMO tenant registrato avvia un thread daemon che si sveglia ogni 30
  minuti e controlla se e' ora di fare uno scan.
- Lo scan viene eseguito UNA SOLA VOLTA (una sola chiamata all'API) e il
  risultato viene scritto nel database di TUTTI i tenant registrati: le notizie
  sono le stesse per tutti, cosi' si paga una chiamata invece di tre e la
  pagina Report legge sempre e solo dal proprio DB.
- Cadenza: due volte a settimana, lunedi' e giovedi', dall'ora indicata da
  NEWS_SCAN_HOUR in poi. Se l'app e' rimasta spenta e sono passati piu' di
  NEWS_MAX_GIORNI giorni, lo scan parte al primo avvio utile anche in un altro
  giorno della settimana (altrimenti restando spenta di lunedi' e giovedi' non
  si aggiornerebbe mai).

VARIABILI D'AMBIENTE (App Settings su Azure)
--------------------------------------------
  ANTHROPIC_API_KEY        obbligatoria. Senza chiave il modulo resta inerte:
                           nessun thread, nessuna chiamata, il tile resta vuoto.
  NEWS_SCAN_ENABLED        '1' (default) / '0' per spegnere lo scheduler.
  NEWS_SCAN_HOUR           ora locale di inizio finestra, default '7'.
  NEWS_SCAN_MODEL          default 'claude-sonnet-5'.
  NEWS_SCAN_EFFORT         default 'low'.
  NEWS_SCAN_MAX_RICERCHE   default 4.
  NEWS_SCAN_MAX_TOKEN      default 4000.

NOTA AZURE: perche' il thread giri anche senza traffico serve "Always On"
attivo sulla Web App. Se e' spento, lo scan parte comunque alla prima visita
utile (il controllo di scadenza avviene anche all'avvio del thread), e in ogni
caso resta il pulsante "Aggiorna adesso" in Report per admin/owner.
"""

import json
import os
import random
import re
import threading
import time
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Configurazione
#
# Le quattro voci che determinano il costo di uno scan sono tutte variabili
# d'ambiente, cosi' si possono tarare da Azure senza toccare il codice:
#
#   NEWS_SCAN_MODEL          il modello (voce di spesa principale)
#   NEWS_SCAN_MAX_RICERCHE   quante ricerche web al massimo; ogni risultato
#                            finisce nel contesto, quindi e' la leva che pesa
#                            di piu' dopo il modello
#   NEWS_SCAN_EFFORT         profondita' di ragionamento: 'low' basta per
#                            cercare tre notizie e riassumerle
#   NEWS_SCAN_MAX_TOKEN      tetto ai token generati
#
# Il default e' la configurazione economica: Sonnet 5 a sforzo basso. Il
# compito - trovare 3 notizie e riassumerle in due frasi - non richiede il
# modello piu' capace, e la differenza di prezzo per token e' notevole.
# ---------------------------------------------------------------------------
MODELLO = os.getenv('NEWS_SCAN_MODEL', 'claude-sonnet-5')
# 'low' faceva mollare troppo presto: il modello si limitava a quello che
# chiedeva la prima ricerca e concludeva che non c'era nulla. 'medium' gli fa
# cambiare angolazione quando una query non rende.
EFFORT = os.getenv('NEWS_SCAN_EFFORT', 'medium')

def _intero_env(nome, predefinito, minimo, massimo):
    try:
        return max(minimo, min(int(os.getenv(nome, str(predefinito))), massimo))
    except (TypeError, ValueError):
        return predefinito

MAX_RICERCHE = _intero_env('NEWS_SCAN_MAX_RICERCHE', 6, 1, 15)
MAX_TOKEN = _intero_env('NEWS_SCAN_MAX_TOKEN', 4000, 1000, 16000)

GIORNI_SCAN = (0, 3)          # 0 = lunedi', 3 = giovedi'
NEWS_MAX_GIORNI = 5           # oltre questi giorni lo scan parte in qualsiasi giorno
INTERVALLO_CHECK = 30 * 60    # ogni mezz'ora
COOLDOWN_ORE = 6              # attesa minima fra due tentativi automatici
# Attesa minima fra due scan MANUALI andati a buon fine. Serve contro il doppio
# click e contro chi preme il pulsante per abitudine: le notizie appena scaricate
# sono le stesse, rifare la ricerca sarebbe solo una spesa in piu'. Un tentativo
# FALLITO non fa scattare l'attesa, cosi' dopo aver sistemato il problema
# (credito ricaricato, tabella creata) si puo' riprovare subito.
COOLDOWN_MANUALE_MIN = 60
MAX_NOTIZIE = 3

_apps = []                    # [(etichetta, flask_app)]
_lock = threading.Lock()      # protegge _apps e l'avvio del thread
_thread = None
_scan_in_corso = threading.Lock()   # impedisce due scan sovrapposti
_ultimo_errore = None
_ultimo_tentativo = None      # quando e' partita l'ultima chiamata all'API


def _abilitato():
    if os.getenv('NEWS_SCAN_ENABLED', '1').strip() not in ('1', 'true', 'yes', 'on'):
        return False
    return bool((os.getenv('ANTHROPIC_API_KEY') or '').strip())


def _ora_scan():
    try:
        return max(0, min(int(os.getenv('NEWS_SCAN_HOUR', '7')), 23))
    except (TypeError, ValueError):
        return 7


# ---------------------------------------------------------------------------
# Registrazione tenant + avvio thread
# ---------------------------------------------------------------------------
def register_app(app, etichetta=None):
    """Registra un'app tenant e, la prima volta, avvia il thread di scan."""
    global _thread
    if not _abilitato():
        return
    with _lock:
        if any(a is app for _e, a in _apps):
            return
        _apps.append((etichetta or app.config.get('SQLALCHEMY_DATABASE_URI', '')[-20:], app))
        if _thread is None:
            _thread = threading.Thread(
                target=_loop, name='beauty-news-scan', daemon=True
            )
            _thread.start()
            app.logger.info("[news_beauty] scheduler avviato (modello=%s, ora=%s)",
                            MODELLO, _ora_scan())


def _loop():
    # Ritardo iniziale casuale: lascia finire l'avvio dell'app prima di toccare
    # il DB e, se il server gira con piu' processi (gunicorn con piu' worker),
    # sfasa i controlli cosi' due processi non partono nello stesso istante.
    time.sleep(60 + random.randint(0, 240))
    while True:
        try:
            _tick()
        except Exception as exc:   # il thread non deve MAI morire
            try:
                _apps[0][1].logger.exception("[news_beauty] errore nel tick: %s", exc)
            except Exception:
                pass
        time.sleep(INTERVALLO_CHECK + random.randint(0, 300))


def app_registrate():
    """Le app tenant registrate. Serve anche ad appl/oroscopo.py, che si
    appoggia a questo thread invece di aprirne uno suo."""
    return list(_apps)


def _tick():
    # Tutte le verifiche (libreria presente, tabella raggiungibile, scadenza,
    # attesa dopo un errore) sono dentro esegui_scan: qui basta chiamarla.
    if not _apps:
        return
    esegui_scan(force=False)

    # Secondo lavoro settimanale sullo stesso thread: un solo timer nell'app.
    # Se l'oroscopo esplode non deve fermare le notizie, da qui in avanti.
    try:
        from appl.oroscopo import esegui_se_dovuto
        esegui_se_dovuto()
    except Exception as exc:
        try:
            _apps[0][1].logger.exception("[oroscopo] errore nel tick: %s", exc)
        except Exception:
            pass


def _ultimo_scan():
    """
    (leggibile, datetime_ultimo_batch) letti dal primo tenant.
    leggibile=False se la tabella non esiste o il DB non risponde.
    """
    from appl.models import BeautyNews
    from appl import db
    _etichetta, app = _apps[0]
    with app.app_context():
        try:
            from sqlalchemy import func as sa_func
            return True, db.session.query(sa_func.max(BeautyNews.created_at)).scalar()
        except Exception:
            db.session.rollback()
            return False, None


def _eta_minuti(quando, adesso=None):
    """Minuti trascorsi da un istante, tollerando i datetime con fuso orario."""
    adesso = adesso or datetime.now()
    if quando.tzinfo is not None:
        quando = quando.replace(tzinfo=None)
    return (adesso - quando).total_seconds() / 60


def _scan_dovuto(ultimo, adesso=None):
    adesso = adesso or datetime.now()
    if adesso.hour < _ora_scan():
        return False
    if ultimo is None:
        return True
    if ultimo.tzinfo is not None:
        ultimo = ultimo.replace(tzinfo=None)
    trascorsi = adesso - ultimo
    # Recupero: l'app e' rimasta spenta troppo a lungo, si aggiorna comunque.
    if trascorsi >= timedelta(days=NEWS_MAX_GIORNI):
        return True
    if adesso.weekday() not in GIORNI_SCAN:
        return False
    # Almeno un giorno pieno dall'ultimo batch: evita di ripetere lo scan
    # ogni mezz'ora nello stesso lunedi'.
    return trascorsi >= timedelta(hours=20)


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
MESI_FINESTRA = 3   # ampiezza della finestra temporale della ricerca

# Tetto di eta' oltre il quale una notizia NON entra in pagina, per quanto il
# modello la giudichi interessante. Il prompt chiedeva gia' notizie recenti, ma
# era solo un suggerimento e nessuno lo verificava: il 25/08/2026 e' finita in
# pagina una notizia di marzo, cinque mesi prima, su limiti a sostanze negli
# smalti. Il controllo va fatto sui dati che tornano, non chiesto per favore.
# La ricerca web di Claude non offre filtri di data (i parametri del tool sono
# max_uses, allowed_domains/blocked_domains e user_location), quindi lo screening
# per forza di cose avviene qui.
GIORNI_FRESCHEZZA = _intero_env('NEWS_GIORNI_MAX', MESI_FINESTRA * 30, 15, 365)

PROMPT_SISTEMA = (
    "Selezioni notizie per la titolare di un centro estetico in Italia. "
    "Le leggera' in due minuti fra un cliente e l'altro, quindi ti servono "
    "notizie che cambino qualcosa nel suo lavoro: obblighi e scadenze di legge, "
    "regole su solarium e apparecchiature, tendenze e trattamenti che i clienti "
    "inizieranno a chiedere, andamento del mercato dei centri estetici. "
    "Il settore italiano dell'estetica produce poche notizie al giorno ma non "
    "sta mai fermo per mesi: se la prima ricerca non rende, cambia angolazione "
    "e riprova prima di arrenderti. Insistere pero' non significa ripiegare sul "
    "vecchio: una notizia di mesi fa non diventa attuale perche' non ne hai "
    "trovate altre, e presentarla come nuova e' l'errore peggiore che puoi fare "
    "qui. Meglio tornare con una notizia sola, o con nessuna. "
    "Scarta pubblicita' mascherate da notizia, schede prodotto e gossip."
)


def _prompt_utente():
    oggi = date.today()
    limite = oggi - timedelta(days=GIORNI_FRESCHEZZA)
    return (
        f"Oggi e' il {oggi.strftime('%d/%m/%Y')}. Cerca sul web notizie italiane "
        f"utili a chi gestisce un centro estetico.\n\n"

        f"VINCOLO DI DATA, non negoziabile: ogni notizia deve essere stata "
        f"pubblicata dal {limite.strftime('%d/%m/%Y')} in poi. Una notizia "
        f"anteriore a quella data viene scartata a prescindere da quanto sia "
        f"interessante, e cosi' una notizia di cui non riesci a stabilire la data "
        f"di pubblicazione: nel dubbio cercane un'altra. Preferisci sempre la "
        f"notizia piu' recente fra due che dicono la stessa cosa, e se una "
        f"ricerca restituisce solo materiale vecchio cambia angolazione invece "
        f"di ripiegare su quello.\n\n"

        f"Angolazioni da coprire (usa ricerche diverse, non ripetere la stessa "
        f"query con parole simili):\n"
        f"- normativa dell'attivita' di estetista: legge 1/1990, regolamenti "
        f"regionali e comunali, requisiti dei locali, apparecchiature "
        f"elettromeccaniche, obblighi e scadenze per le imprese artigiane\n"
        f"- solarium e abbronzatura: limiti UV, controlli, obblighi informativi, "
        f"studi e prese di posizione sanitarie\n"
        f"- mercato e gestione: andamento dei consumi beauty in Italia, aperture "
        f"e chiusure, prezzi, credito e incentivi per le imprese del settore\n"
        f"- trattamenti e tendenze professionali che i clienti inizieranno a "
        f"chiedere in cabina\n\n"

        f"Fonti da preferire: testate di settore (Kosmetica, Beauty Business, "
        f"Estetica Magazine, Cosmetica Italia), associazioni di categoria "
        f"(Confartigianato Benessere, CNA Benessere e Sanita'), fonti "
        f"istituzionali (Gazzetta Ufficiale, Ministero della Salute, bollettini "
        f"regionali), stampa economica e quotidiani quando trattano il settore. "
        f"Evita e-commerce e pagine di vendita.\n\n"

        f"Scegli da 2 a {MAX_NOTIZIE} notizie fra quelle che rispettano il "
        f"vincolo di data, dalla piu' recente alla piu' vecchia. Non serve che "
        f"siano eccezionali: devono essere utili e attuali. Una sola notizia "
        f"recente vale piu' di tre vecchie. Restituisci un array vuoto se le "
        f"ricerche non hanno prodotto nulla di abbastanza recente: e' un esito "
        f"previsto e preferibile a riempire con notizie superate.\n\n"

        f"Rispondi con un array JSON e nient'altro, senza testo prima o dopo. "
        f"Ogni elemento:\n"
        f'  "titolo": massimo 90 caratteri, in italiano\n'
        f'  "sintesi": 2 frasi, massimo 280 caratteri, cosa cambia concretamente\n'
        f'  "categoria": una fra "normativa", "estetica", "solarium", "mercato"\n'
        f'  "fonte": nome della testata o dell\'ente\n'
        f'  "url": link diretto alla notizia\n'
        f'  "data": data di pubblicazione in formato AAAA-MM-GG, OBBLIGATORIA: '
        f'un elemento senza data valida viene scartato'
    )


def _parametri_modello():
    """
    Parametri che cambiano a seconda della generazione del modello scelto.

    I modelli recenti (Opus 5/4.x, Sonnet 5/4.6, Fable 5) accettano il
    ragionamento adattivo, il parametro 'effort' e la ricerca web con filtro
    dinamico - quest'ultima costa meno perche' screma i risultati prima che
    entrino nel contesto. Haiku 4.5 e i modelli piu' vecchi rifiutano sia
    'thinking: adaptive' sia 'effort', e hanno solo la ricerca web di base.
    """
    recenti = ('fable-5', 'opus-5', 'opus-4-8', 'opus-4-7', 'opus-4-6',
               'sonnet-5', 'sonnet-4-6')
    e_recente = any(m in MODELLO for m in recenti)

    extra = {}
    if e_recente:
        extra['thinking'] = {'type': 'adaptive'}
        extra['output_config'] = {'effort': EFFORT}

    ricerca = {
        "type": "web_search_20260209" if e_recente else "web_search_20250305",
        "name": "web_search",
        "max_uses": MAX_RICERCHE,
        "user_location": {"type": "approximate", "country": "IT",
                          "timezone": "Europe/Rome"},
    }
    return extra, ricerca


def _chiama_claude():
    """Interroga Claude con la ricerca web attiva. Restituisce il testo della risposta."""
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
    extra, ricerca = _parametri_modello()

    messaggi = [{"role": "user", "content": _prompt_utente()}]
    testo_finale = ""

    # La ricerca web e' un tool server-side: puo' fermarsi con pause_turn se
    # supera il limite interno di iterazioni. In quel caso si rimanda la stessa
    # conversazione e il server riprende da dove si era interrotto.
    for _tentativo in range(4):
        with client.messages.stream(
            model=MODELLO,
            max_tokens=MAX_TOKEN,
            system=PROMPT_SISTEMA,
            tools=[ricerca],
            messages=messaggi,
            **extra,
        ) as stream:
            risposta = stream.get_final_message()

        if risposta.stop_reason == "refusal":
            raise RuntimeError("La richiesta e' stata rifiutata dai filtri di sicurezza.")

        testo_finale = "".join(
            b.text for b in risposta.content if getattr(b, 'type', '') == 'text'
        )

        if risposta.stop_reason == "max_tokens":
            # Il JSON e' stato tagliato a meta': senza questo controllo il
            # parser restituirebbe una lista vuota e l'errore sarebbe il
            # generico "nessuna notizia trovata", che manda fuori strada.
            raise RuntimeError(
                "Risposta troncata: alza NEWS_SCAN_MAX_TOKEN "
                f"(ora {MAX_TOKEN}) o abbassa NEWS_SCAN_EFFORT."
            )

        if risposta.stop_reason != "pause_turn":
            break

        # Rimanda la conversazione cosi' com'e': il server riprende il turno.
        messaggi = [
            {"role": "user", "content": _prompt_utente()},
            {"role": "assistant", "content": risposta.content},
        ]

    return testo_finale


def _registra_errore(motivo, dettaglio):
    """
    Manda il guasto nel canale degli errori del gestionale (crm_error_logs), da
    cui l'app di prenotazione costruisce il riepilogo che arriva via email.

    Serve perche' l'utente finale di Tosca NON deve mai vedere il motivo tecnico
    di un fallimento dello scan: che sia il credito Anthropic finito, una chiave
    revocata o un timeout, per lui il tile deve solo restare com'era. Chi deve
    intervenire lo scopre dal riepilogo errori, non dalla schermata di lavoro.
    """
    if not _apps:
        return
    _etichetta, app = _apps[0]
    try:
        with app.app_context():
            from appl.services.error_log import log_crm_error
            log_crm_error(
                reason=str(motivo)[:255],
                context={'modulo': 'news_beauty', 'dettaglio': str(dettaglio)[:900]},
            )
    except Exception:
        try:
            app.logger.warning("[news_beauty] impossibile registrare l'errore nel report")
        except Exception:
            pass


def _errore_leggibile(exc):
    """
    Traduce gli errori dell'API in un messaggio che ha senso leggere nel tile.
    Il traceback completo resta nei log dell'app per la diagnosi tecnica.
    """
    testo = str(exc)
    minuscolo = testo.lower()
    if 'credit balance is too low' in minuscolo:
        return ("Credito Anthropic esaurito: ricaricalo da console.anthropic.com "
                "(Plans & Billing), poi riprova.")
    if 'authentication' in minuscolo or 'invalid x-api-key' in minuscolo or 'error code: 401' in minuscolo:
        return "Chiave ANTHROPIC_API_KEY non valida o revocata."
    if 'error code: 429' in minuscolo or 'rate limit' in minuscolo:
        return "Troppe richieste in poco tempo: riprova fra qualche minuto."
    if 'error code: 5' in minuscolo or 'overloaded' in minuscolo:
        return "Il servizio Anthropic non risponde in questo momento: riprova piu' tardi."
    if 'connection' in minuscolo or 'timeout' in minuscolo:
        return "Nessuna connessione verso Anthropic: controlla la rete del server."
    # Caso non previsto: si mostra l'inizio del messaggio, non l'intero JSON.
    return 'Chiamata API fallita: ' + testo[:200]


def _estrai_json(testo):
    """Estrae l'array JSON dalla risposta, tollerando testo o code fence attorno."""
    if not testo:
        return []
    fence = re.search(r"```(?:json)?\s*(.+?)```", testo, re.S)
    if fence:
        testo = fence.group(1)
    inizio = testo.find('[')
    fine = testo.rfind(']')
    if inizio == -1 or fine <= inizio:
        return []
    try:
        dati = json.loads(testo[inizio:fine + 1])
    except (ValueError, TypeError):
        return []
    return dati if isinstance(dati, list) else []


def _normalizza(dati, oggi=None):
    """Ripulisce, valida e SCREMA gli elementi restituiti dal modello.

    Restituisce (notizie, scartate): due regole che il solo prompt non garantiva.

    1. La data e' obbligatoria e deve rientrare nella finestra di freschezza.
       Senza data non si puo' dimostrare che la notizia sia recente; con una data
       vecchia non lo e'. Il modello, lasciato libero, ha gia' proposto come
       attuale una notizia di cinque mesi prima.
    2. Le notizie escono ordinate dalla piu' recente alla piu' vecchia, cosi' il
       campo `ordine` con cui la pagina le dispone segue la freschezza.

    Se non sopravvive nulla si torna una lista vuota: chi chiama NON salva, e in
    pagina restano le notizie dell'ultima ricerca andata a buon fine.
    """
    oggi = oggi or date.today()
    limite = oggi - timedelta(days=GIORNI_FRESCHEZZA)
    categorie = {'normativa', 'estetica', 'solarium', 'mercato', 'beauty'}
    puliti = []
    scartate = 0
    # Si esamina TUTTO quello che e' arrivato e si taglia a MAX_NOTIZIE solo alla
    # fine: tagliando prima, tre notizie vecchie in testa all'array avrebbero
    # coperto quelle recenti che seguivano.
    for elem in dati:
        if not isinstance(elem, dict):
            continue
        titolo = (elem.get('titolo') or '').strip()
        if not titolo:
            continue
        url = (elem.get('url') or '').strip()
        if url and not url.startswith(('http://', 'https://')):
            url = ''
        categoria = (elem.get('categoria') or '').strip().lower()
        if categoria not in categorie:
            categoria = 'beauty'
        data_notizia = None
        raw_data = (elem.get('data') or '').strip()
        if raw_data:
            try:
                data_notizia = datetime.strptime(raw_data[:10], '%Y-%m-%d').date()
            except ValueError:
                data_notizia = None
        # Il filtro di freschezza: qui si decide, non nel prompt.
        # Una data nel futuro e' un errore del modello, non una primizia.
        if data_notizia is None or data_notizia < limite or data_notizia > oggi:
            scartate += 1
            continue
        puliti.append({
            'titolo': titolo[:300],
            'sintesi': (elem.get('sintesi') or '').strip()[:1000],
            'categoria': categoria,
            'fonte': (elem.get('fonte') or '').strip()[:200],
            'url': url[:1000],
            'data_notizia': data_notizia,
        })
    puliti.sort(key=lambda n: n['data_notizia'], reverse=True)
    return puliti[:MAX_NOTIZIE], scartate


def _salva(app, notizie, batch):
    """Scrive il batch nel database di un tenant."""
    from appl import db
    from appl.models import BeautyNews
    with app.app_context():
        try:
            for i, n in enumerate(notizie):
                db.session.add(BeautyNews(
                    scan_batch=batch,
                    titolo=n['titolo'],
                    sintesi=n['sintesi'],
                    categoria=n['categoria'],
                    fonte=n['fonte'],
                    url=n['url'],
                    data_notizia=n['data_notizia'],
                    ordine=i,
                ))
            # Archivio: si tengono gli ultimi 10 batch, il resto si elimina.
            vecchi = [
                b[0] for b in db.session.query(BeautyNews.scan_batch)
                .distinct()
                .order_by(BeautyNews.scan_batch.desc())
                .offset(10)
                .all()
            ]
            if vecchi:
                (BeautyNews.query
                 .filter(BeautyNews.scan_batch.in_(vecchi))
                 .delete(synchronize_session=False))
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("[news_beauty] salvataggio fallito: %s", exc)
            return False


def esegui_scan(force=False):
    """
    Esegue lo scan e scrive il risultato in tutti i tenant registrati.
    Restituisce un dizionario con l'esito (usato anche dall'endpoint manuale).
    """
    global _ultimo_errore

    if not _abilitato():
        return {'ok': False, 'errore': 'ANTHROPIC_API_KEY non configurata'}
    if not _apps:
        return {'ok': False, 'errore': 'Nessun tenant registrato'}

    if not _scan_in_corso.acquire(blocking=False):
        return {'ok': False, 'errore': 'Scan gia\' in corso'}
    try:
        global _ultimo_tentativo

        # Controlli che valgono SEMPRE, anche per il pulsante "aggiorna adesso":
        # se la libreria manca o non c'e' dove scrivere, la chiamata all'API
        # sarebbe comunque buttata via. force salta la pianificazione (giorno,
        # ora, attesa fra due tentativi), non le verifiche di sanita'.
        try:
            import anthropic  # noqa: F401
        except ImportError:
            _ultimo_errore = ("Libreria 'anthropic' non installata: "
                              "pip install -r requirements.txt")
            return {'ok': False, 'errore': _ultimo_errore}

        leggibile, ultimo = _ultimo_scan()
        if not leggibile:
            _ultimo_errore = ("Tabella beauty_news assente su questo database: "
                              "esegui migrations/manual_beauty_news.sql")
            return {'ok': False, 'errore': _ultimo_errore}

        if force:
            # Le notizie appena scaricate sono ancora fresche: rifare la ricerca
            # costerebbe come la prima volta per riottenere le stesse tre righe.
            # Il confronto e' sull'ultimo batch SALVATO, quindi sopravvive ai
            # riavvii e vale anche se il server gira con piu' processi.
            if ultimo and _eta_minuti(ultimo) < COOLDOWN_MANUALE_MIN:
                minuti = int(COOLDOWN_MANUALE_MIN - _eta_minuti(ultimo))
                return {'ok': False, 'nessun_costo': True, 'errore':
                        f'Notizie gia\' aggiornate poco fa. Nuova ricerca fra {minuti} min '
                        f'(le automatiche restano lunedi\' e giovedi\').'}
        else:
            if not _scan_dovuto(ultimo):
                return {'ok': False, 'errore': 'Scan non ancora dovuto'}
            # Dopo un tentativo fallito si aspetta, altrimenti a ogni giro del
            # thread si ripaga una chiamata all'API per riottenere lo stesso errore.
            if (_ultimo_tentativo
                    and datetime.now() - _ultimo_tentativo < timedelta(hours=COOLDOWN_ORE)):
                return {'ok': False, 'errore': 'In attesa dopo un tentativo recente'}

        _ultimo_tentativo = datetime.now()

        try:
            testo = _chiama_claude()
        except Exception as exc:
            _ultimo_errore = _errore_leggibile(exc)
            try:
                _apps[0][1].logger.exception("[news_beauty] chiamata API fallita: %s", exc)
            except Exception:
                pass
            # Solo lo scan automatico finisce nel report errori: quando il
            # pulsante lo lancia a mano, chi l'ha premuto sta gia' leggendo
            # l'esito e riprovare piu' volte riempirebbe il report di doppioni.
            if not force:
                _registra_errore('Scan notizie beauty fallito', exc)
            return {'ok': False, 'errore': _ultimo_errore}

        notizie, scartate = _normalizza(_estrai_json(testo))
        if not notizie:
            # Niente di abbastanza recente: NON si salva, cosi' in pagina restano
            # le notizie dell'ultima ricerca riuscita. Meglio una notizia della
            # settimana scorsa che una di cinque mesi fa spacciata per attuale.
            if scartate:
                _ultimo_errore = (
                    f"Nessuna notizia degli ultimi {GIORNI_FRESCHEZZA} giorni "
                    f"({scartate} trovate ma troppo vecchie o senza data): "
                    f"restano in pagina quelle della ricerca precedente."
                )
            else:
                _ultimo_errore = 'Nessuna notizia utile trovata'
            return {'ok': False, 'scartate': scartate, 'errore': _ultimo_errore}

        batch = datetime.now().strftime('%Y%m%dT%H%M')
        salvati = sum(1 for _e, app in list(_apps) if _salva(app, notizie, batch))
        _ultimo_errore = None
        return {'ok': salvati > 0, 'notizie': len(notizie), 'scartate': scartate,
                'tenant': salvati, 'batch': batch}
    finally:
        _scan_in_corso.release()


def stato():
    """Riepilogo di configurazione, per il tile e per la diagnostica."""
    return {
        'abilitato': _abilitato(),
        'modello': MODELLO,
        'effort': EFFORT,
        'max_ricerche': MAX_RICERCHE,
        'max_token': MAX_TOKEN,
        'ora_scan': _ora_scan(),
        'giorni': ['Lunedi', 'Giovedi'],
        'tenant_registrati': len(_apps),
        'ultimo_errore': _ultimo_errore,
    }
