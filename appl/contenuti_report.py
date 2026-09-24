# appl/contenuti_report.py
"""
Contenuti editoriali del Report: notizie dal mondo beauty e oroscopo della
settimana.

COME CI FINISCONO DENTRO
------------------------
Li scrive una persona e li pubblica a mano dalla pagina Contenuti Report
(/contenuti-report, solo owner): si incolla un blocco JSON, l'app lo controlla
e lo scrive UNA VOLTA SOLA nel registro centrale (tosca_registry, tabelle
contenuto_news e contenuto_oroscopo). Tutti i negozi, di qualunque copia
dell'app, leggono da li': i contenuti sono uguali per tutti.

Prima c'era un thread che due volte a settimana interrogava un'API esterna a
pagamento e scriveva da solo in tutti i tenant. Quella strada e' stata smontata:
l'app non chiama piu' nessun servizio esterno per questi due pannelli, non ha
piu' chiavi da custodire e non ha piu' un costo che cresce con i negozi.

Le tabelle beauty_news e oroscopo_settimanale dei negozi restano come RIPIEGO:
il Report le legge solo se il registro non e' configurato, non risponde o non
ha ancora niente di pubblicato. Non si scrivono piu'.

REGOLE CHE RESTANO, ed e' qui che vanno tenute
----------------------------------------------
1. FRESCHEZZA DELLE NOTIZIE. Una notizia piu' vecchia di GIORNI_FRESCHEZZA non
   entra: la data e' obbligatoria e viene verificata qui, non chiesta per
   cortesia a chi incolla. Una notizia di cinque mesi presentata come attuale e'
   l'errore peggiore che questo pannello possa fare.
2. TESTO NEUTRO NELL'OROSCOPO. Lo stesso testo viene letto in centri diversi:
   niente nome dell'istituto, niente trattamenti specifici, niente nomi di
   clienti. Il controllo sul nome del centro e' automatico (_righe_senza_nome).
3. NIENTE DATI DELLE CLIENTI, mai, in nessuno dei due blocchi.
"""

import json
import logging
import re
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Notizie
# ---------------------------------------------------------------------------
MAX_NOTIZIE = 3
GIORNI_FRESCHEZZA = 90        # tetto di eta' di una notizia, in giorni
MAX_BATCH_NEWS = 10           # batch conservati come archivio
CATEGORIE = ('normativa', 'estetica', 'solarium', 'mercato', 'beauty')

# ---------------------------------------------------------------------------
# Oroscopo
# ---------------------------------------------------------------------------
# Simbolo e periodo sono dati fissi: non ha senso salvarli a ogni pubblicazione.
# L'ordine e' quello classico dello zodiaco e decide l'ordine in pagina.
SEGNI = [
    ('Ariete',      '♈', '21 mar – 19 apr'),
    ('Toro',        '♉', '20 apr – 20 mag'),
    ('Gemelli',     '♊', '21 mag – 20 giu'),
    ('Cancro',      '♋', '21 giu – 22 lug'),
    ('Leone',       '♌', '23 lug – 22 ago'),
    ('Vergine',     '♍', '23 ago – 22 set'),
    ('Bilancia',    '♎', '23 set – 22 ott'),
    ('Scorpione',   '♏', '23 ott – 21 nov'),
    ('Sagittario',  '♐', '22 nov – 21 dic'),
    ('Capricorno',  '♑', '22 dic – 19 gen'),
    ('Acquario',    '♒', '20 gen – 18 feb'),
    ('Pesci',       '♓', '19 feb – 20 mar'),
]
NOMI_SEGNI = [s[0] for s in SEGNI]
DETTAGLI_SEGNO = {s[0]: {'simbolo': s[1], 'periodo': s[2]} for s in SEGNI}

MIN_SEGNI = 6                 # sotto questa soglia il blocco non si pubblica
MAX_BATCH_OROSCOPO = 8


class ContenutoNonValido(ValueError):
    """Il blocco incollato non e' pubblicabile. Il messaggio va mostrato a chi
    l'ha incollato: e' l'owner, cioe' chi puo' correggerlo."""


class RegistroNonDisponibile(RuntimeError):
    """Il registro centrale non e' configurato: non c'e' dove pubblicare."""


# ---------------------------------------------------------------------------
# Lettura del blocco incollato
# ---------------------------------------------------------------------------
def carica_json(testo):
    """Legge il JSON incollato, tollerando i code fence e il testo attorno.

    Chi incolla arriva quasi sempre da una chat, dove il JSON e' dentro un
    blocco di codice: pretendere che lo ripulisca a mano sarebbe solo un modo
    per far fallire la pubblicazione su un dettaglio che si puo' sistemare qui.
    Accetta sia l'array nudo sia l'oggetto con la chiave 'news'/'oroscopo'.
    """
    testo = (testo or '').strip()
    if not testo:
        raise ContenutoNonValido('Non hai incollato niente.')

    fence = re.search(r"```(?:json)?\s*(.+?)```", testo, re.S)
    if fence:
        testo = fence.group(1).strip()

    try:
        dati = json.loads(testo)
    except ValueError as exc:
        raise ContenutoNonValido(
            'Il testo incollato non e\' un JSON valido: %s' % exc)

    if isinstance(dati, dict):
        for chiave in ('news', 'notizie', 'oroscopo', 'righe', 'dati'):
            if isinstance(dati.get(chiave), list):
                return dati[chiave]
        raise ContenutoNonValido(
            "Il JSON e' un oggetto ma non contiene una lista 'news' o 'oroscopo'.")

    if not isinstance(dati, list):
        raise ContenutoNonValido('Serve una lista di elementi.')
    return dati


# ---------------------------------------------------------------------------
# Notizie: validazione
# ---------------------------------------------------------------------------
def valida_notizie(dati, oggi=None):
    """Ripulisce e SCREMA le notizie. Restituisce (notizie, avvisi).

    Il filtro di freschezza si applica qui, sui dati che arrivano: la data e'
    obbligatoria, deve essere leggibile, non puo' essere anteriore alla finestra
    e non puo' stare nel futuro. Le notizie escono ordinate dalla piu' recente.
    """
    oggi = oggi or date.today()
    limite = oggi - timedelta(days=GIORNI_FRESCHEZZA)
    puliti, avvisi = [], []

    for i, elem in enumerate(dati, start=1):
        if not isinstance(elem, dict):
            avvisi.append('Elemento %d ignorato: non e\' un oggetto.' % i)
            continue

        titolo = (elem.get('titolo') or '').strip()
        if not titolo:
            avvisi.append('Elemento %d scartato: manca il titolo.' % i)
            continue

        grezza = (elem.get('data') or '').strip()
        try:
            data_notizia = datetime.strptime(grezza[:10], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            avvisi.append('"%s" scartata: data mancante o illeggibile '
                          '(serve AAAA-MM-GG).' % titolo[:60])
            continue

        if data_notizia < limite:
            avvisi.append('"%s" scartata: e\' del %s, oltre i %d giorni.'
                          % (titolo[:60], data_notizia.strftime('%d/%m/%Y'),
                             GIORNI_FRESCHEZZA))
            continue
        if data_notizia > oggi:
            avvisi.append('"%s" scartata: la data e\' nel futuro.' % titolo[:60])
            continue

        url = (elem.get('url') or '').strip()
        if url and not url.startswith(('http://', 'https://')):
            avvisi.append('"%s": link ignorato, non inizia per http.' % titolo[:60])
            url = ''

        categoria = (elem.get('categoria') or '').strip().lower()
        if categoria not in CATEGORIE:
            categoria = 'beauty'

        puliti.append({
            'titolo': titolo[:300],
            'sintesi': (elem.get('sintesi') or '').strip()[:1000],
            'categoria': categoria,
            'fonte': (elem.get('fonte') or '').strip()[:200],
            'url': url[:1000],
            'data_notizia': data_notizia,
        })

    if not puliti:
        raise ContenutoNonValido(
            'Nessuna notizia pubblicabile. ' + (' '.join(avvisi) if avvisi else ''))

    puliti.sort(key=lambda n: n['data_notizia'], reverse=True)
    if len(puliti) > MAX_NOTIZIE:
        avvisi.append('Pubblicate le %d piu' % MAX_NOTIZIE
                      + '\' recenti, le altre sono state lasciate fuori.')
    return puliti[:MAX_NOTIZIE], avvisi


# ---------------------------------------------------------------------------
# Oroscopo: validazione
# ---------------------------------------------------------------------------
def _righe_senza_nome(righe, nomi_centri):
    """Rete di sicurezza al nome dell'istituto.

    Vale anche adesso che i testi li scrive una persona: lo stesso testo va in
    tutti i negozi, e una battuta che nomina un centro verrebbe letta dagli
    altri come un errore. Per questo si controllano i nomi di TUTTI i negozi,
    non solo di quello da cui si pubblica. I nomi corti (< 5 caratteri) non si
    filtrano: sono spesso parole comuni e butterebbero righe innocenti.
    """
    if isinstance(nomi_centri, str):
        nomi_centri = [nomi_centri]
    nomi = {n.strip().lower() for n in (nomi_centri or []) if n and len(n.strip()) >= 5}
    if not nomi:
        return righe, []
    tenute, avvisi = [], []
    for segno, testo in righe:
        minuscolo = testo.lower()
        if any(nome in minuscolo for nome in nomi):
            avvisi.append('Riga "%s" scartata: nomina un centro.' % segno)
            continue
        tenute.append((segno, testo))
    return tenute, avvisi


def valida_oroscopo(dati, nomi_centri=None):
    """Tiene i segni riconosciuti, li rimette in ordine zodiacale e restituisce
    (righe, avvisi). Sotto MIN_SEGNI non si pubblica: meglio lasciare in pagina
    l'oroscopo della settimana scorsa che uno a meta'. `nomi_centri` e' un nome
    o un elenco di nomi di negozi che il testo non deve contenere."""
    per_segno, avvisi = {}, []

    for i, elem in enumerate(dati, start=1):
        if not isinstance(elem, dict):
            avvisi.append('Elemento %d ignorato: non e\' un oggetto.' % i)
            continue
        segno = (elem.get('segno') or '').strip().capitalize()
        testo = (elem.get('testo') or '').strip()
        if segno not in DETTAGLI_SEGNO:
            avvisi.append('Segno non riconosciuto: "%s".'
                          % (elem.get('segno') or '')[:30])
            continue
        if not testo:
            avvisi.append('%s: testo vuoto.' % segno)
            continue
        if segno in per_segno:
            avvisi.append('%s compare due volte: tenuto il primo.' % segno)
            continue
        per_segno[segno] = testo[:600]

    righe = [(s, per_segno[s]) for s in NOMI_SEGNI if s in per_segno]
    righe, avvisi_nome = _righe_senza_nome(righe, nomi_centri)
    avvisi.extend(avvisi_nome)

    if len(righe) < MIN_SEGNI:
        raise ContenutoNonValido(
            'Servono almeno %d segni validi, ne sono arrivati %d. %s'
            % (MIN_SEGNI, len(righe), ' '.join(avvisi)))

    mancanti = [s for s in NOMI_SEGNI if s not in dict(righe)]
    if mancanti:
        avvisi.append('Segni mancanti: %s.' % ', '.join(mancanti))
    return righe, avvisi


# ---------------------------------------------------------------------------
# Scrittura: nel registro centrale, una volta per tutti i negozi
# ---------------------------------------------------------------------------
def _nuovo_batch():
    # Con i secondi: una correzione ripubblicata nello stesso minuto non deve
    # finire nel batch di prima (il Report mostrerebbe vecchie e nuove insieme).
    return datetime.now().strftime('%Y%m%dT%H%M%S')


def _svuota_batch(s, modello, batch):
    """Stesso nome di batch gia' usato (due pubblicazioni nello stesso
    secondo): vince l'ultima, non si sommano."""
    (s.query(modello).filter(modello.scan_batch == batch)
     .delete(synchronize_session=False))


def _pota(s, modello, tenere):
    """Elimina i batch piu' vecchi, tenendone `tenere`."""
    vecchi = [b for (b,) in s.query(modello.scan_batch).distinct()
              .order_by(modello.scan_batch.desc()).offset(tenere).all()]
    if vecchi:
        (s.query(modello).filter(modello.scan_batch.in_(vecchi))
         .delete(synchronize_session=False))


def _registro():
    from appl.registry_models import registry_enabled
    if not registry_enabled():
        raise RegistroNonDisponibile(
            'Registro centrale non configurato (manca REGISTRY_DATABASE_URI): '
            'niente pubblicato.')


def pubblica_notizie(notizie):
    """Scrive un batch nuovo di notizie nel registro: lo vedono tutti i negozi."""
    from appl.registry_models import ContenutoNews, registry_session
    _registro()
    batch = _nuovo_batch()
    with registry_session() as s:
        _svuota_batch(s, ContenutoNews, batch)
        for i, n in enumerate(notizie):
            s.add(ContenutoNews(
                scan_batch=batch,
                titolo=n['titolo'],
                sintesi=n['sintesi'],
                categoria=n['categoria'],
                fonte=n['fonte'],
                url=n['url'],
                data_notizia=n['data_notizia'],
                ordine=i,
            ))
        s.flush()
        _pota(s, ContenutoNews, MAX_BATCH_NEWS)
    _cache.pop('news', None)
    return batch


def pubblica_oroscopo(righe):
    """Scrive un batch nuovo di oroscopo nel registro: lo vedono tutti i negozi."""
    from appl.registry_models import ContenutoOroscopo, registry_session
    _registro()
    batch = _nuovo_batch()
    with registry_session() as s:
        _svuota_batch(s, ContenutoOroscopo, batch)
        for i, (segno, testo) in enumerate(righe):
            s.add(ContenutoOroscopo(scan_batch=batch, segno=segno,
                                    testo=testo, ordine=i))
        s.flush()
        _pota(s, ContenutoOroscopo, MAX_BATCH_OROSCOPO)
    _cache.pop('oroscopo', None)
    return batch


def nomi_dei_negozi():
    """Nomi di tutti i negozi del registro, per il controllo sull'oroscopo.
    Registro assente o irraggiungibile: lista vuota (il chiamante aggiunge
    comunque il nome del negozio corrente)."""
    from appl.registry_models import Tenant, registry_enabled, registry_session
    if not registry_enabled():
        return []
    try:
        with registry_session() as s:
            return [n for (n,) in s.query(Tenant.business_name).all() if n]
    except Exception as exc:
        log.warning('[contenuti_report] nomi dei negozi non letti: %s', exc)
        return []


# ---------------------------------------------------------------------------
# Lettura: dal registro, con ripiego sulle tabelle del negozio
# ---------------------------------------------------------------------------
# Il Report si apre spesso e in tutti i negozi, il registro ha un pool di 3
# connessioni per processo e i contenuti cambiano una volta a settimana: ogni
# processo lo rilegge al massimo ogni CACHE_SECONDI. Chi pubblica svuota la
# cache del proprio processo; l'altra copia dell'app si allinea entro 5 minuti.
CACHE_SECONDI = 300
# Registro che non risponde: si riprova dopo un minuto, non a ogni apertura
# del Report (pool_timeout del registro = 10 secondi di attesa ciascuna).
CACHE_GUASTO_SECONDI = 60

_cache = {}     # 'news' | 'oroscopo' -> (scade_alle, contenuto o None)


def ora_italiana(momento):
    """created_at del registro e' con fuso (UTC sul server): a video va l'ora
    italiana. Le date senza fuso, dalle tabelle del negozio, restano come sono."""
    if momento is None or momento.tzinfo is None:
        return momento
    return momento.astimezone(ZoneInfo('Europe/Rome'))


def _leggi_dal_registro(tipo):
    from appl.registry_models import (
        ContenutoNews, ContenutoOroscopo, registry_session,
    )
    from sqlalchemy import func
    modello = ContenutoNews if tipo == 'news' else ContenutoOroscopo
    with registry_session() as s:
        ultimo = s.query(func.max(modello.scan_batch)).scalar()
        if not ultimo:
            return None
        righe = (s.query(modello).filter(modello.scan_batch == ultimo)
                 .order_by(modello.ordine.asc(), modello.id.asc()).all())
        if not righe:
            return None
        if tipo == 'news':
            elenco = [{'titolo': r.titolo, 'sintesi': r.sintesi or '',
                       'categoria': r.categoria or '', 'fonte': r.fonte or '',
                       'url': r.url or '', 'data_notizia': r.data_notizia}
                      for r in righe]
        else:
            elenco = [{'segno': r.segno, 'testo': r.testo} for r in righe]
        return {'batch': ultimo, 'aggiornato': ora_italiana(righe[0].created_at),
                'righe': elenco}


def contenuti_comuni(tipo):
    """Ultimo batch pubblicato nel registro per `tipo` ('news' o 'oroscopo'):
    {'batch', 'aggiornato', 'righe'}. None se il registro non e' configurato,
    non risponde o non ha ancora niente: in quel caso il Report ripiega sulle
    tabelle del negozio, cosi' non resta mai vuoto per colpa del registro."""
    adesso = time.monotonic()
    in_cache = _cache.get(tipo)
    if in_cache and in_cache[0] > adesso:
        return in_cache[1]

    from appl.registry_models import registry_enabled
    if not registry_enabled():
        return None
    try:
        contenuto, durata = _leggi_dal_registro(tipo), CACHE_SECONDI
    except Exception as exc:
        # Tabelle non ancora create (registry/06_contenuti_report.sql) o
        # registro irraggiungibile: si ripiega, senza far fallire il Report.
        log.warning('[contenuti_report] registro non letto (%s): %s', tipo, exc)
        contenuto, durata = None, CACHE_GUASTO_SECONDI
    _cache[tipo] = (adesso + durata, contenuto)
    return contenuto


def ultime_pubblicazioni():
    """Per la pagina Contenuti Report: quando e' stato pubblicato l'ultimo
    batch di ciascun tipo nel registro. Letto al momento, senza cache.
    Restituisce (news, oroscopo, errore): stringhe gg/mm/aaaa hh:mm o None."""
    from appl.registry_models import registry_enabled
    if not registry_enabled():
        return None, None, 'Registro centrale non configurato: non si puo\' pubblicare.'
    risultati = []
    for tipo in ('news', 'oroscopo'):
        try:
            c = _leggi_dal_registro(tipo)
        except Exception as exc:
            log.warning('[contenuti_report] registro non letto (%s): %s', tipo, exc)
            return None, None, ('Registro centrale non raggiungibile o tabelle '
                                'mancanti (registry/06_contenuti_report.sql).')
        risultati.append(c['aggiornato'].strftime('%d/%m/%Y %H:%M') if c else None)
    return risultati[0], risultati[1], None
