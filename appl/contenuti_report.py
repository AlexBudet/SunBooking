# appl/contenuti_report.py
"""
Contenuti editoriali del Report: notizie dal mondo beauty e oroscopo della
settimana.

COME CI FINISCONO DENTRO
------------------------
Li scrive una persona e li pubblica a mano dalla pagina Contenuti Report
(/contenuti-report, solo admin/owner): si incolla un blocco JSON, l'app lo
controlla e lo scrive nel database DI QUESTO tenant.

Prima c'era un thread che due volte a settimana interrogava un'API esterna a
pagamento e scriveva da solo in tutti i tenant. Quella strada e' stata smontata:
l'app non chiama piu' nessun servizio esterno per questi due pannelli, non ha
piu' chiavi da custodire e non ha piu' un costo che cresce con i negozi. La
conseguenza operativa e' che la pubblicazione va fatta UNA VOLTA PER NEGOZIO,
perche' ogni tenant ha il suo database.

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
import re
from datetime import date, datetime, timedelta

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
    l'ha incollato: e' admin o owner, cioe' chi puo' correggerlo."""


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
def _righe_senza_nome(righe, nome_centro):
    """Rete di sicurezza al nome dell'istituto.

    Vale anche adesso che i testi li scrive una persona: lo stesso blocco viene
    incollato in piu' negozi, e una battuta che nomina un centro verrebbe letta
    dagli altri come un errore. I nomi corti (< 5 caratteri) non si filtrano:
    sono spesso parole comuni e butterebbero righe innocenti.
    """
    nome = (nome_centro or '').strip().lower()
    if len(nome) < 5:
        return righe, []
    tenute, avvisi = [], []
    for segno, testo in righe:
        if nome in testo.lower():
            avvisi.append('Riga "%s" scartata: nomina il centro.' % segno)
            continue
        tenute.append((segno, testo))
    return tenute, avvisi


def valida_oroscopo(dati, nome_centro=None):
    """Tiene i segni riconosciuti, li rimette in ordine zodiacale e restituisce
    (righe, avvisi). Sotto MIN_SEGNI non si pubblica: meglio lasciare in pagina
    l'oroscopo della settimana scorsa che uno a meta'."""
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
    righe, avvisi_nome = _righe_senza_nome(righe, nome_centro)
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
# Scrittura
# ---------------------------------------------------------------------------
def _nuovo_batch():
    return datetime.now().strftime('%Y%m%dT%H%M')


def _pota(modello, tenere):
    """Elimina i batch piu' vecchi, tenendone `tenere`."""
    from appl import db
    vecchi = [b[0] for b in db.session.query(modello.scan_batch)
              .distinct().order_by(modello.scan_batch.desc())
              .offset(tenere).all()]
    if vecchi:
        (modello.query.filter(modello.scan_batch.in_(vecchi))
         .delete(synchronize_session=False))


def pubblica_notizie(notizie):
    """Scrive un batch nuovo di notizie nel database del tenant corrente."""
    from appl import db
    from appl.models import BeautyNews

    batch = _nuovo_batch()
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
    _pota(BeautyNews, MAX_BATCH_NEWS)
    db.session.commit()
    return batch


def pubblica_oroscopo(righe):
    """Scrive un batch nuovo di oroscopo nel database del tenant corrente."""
    from appl import db
    from appl.models import Oroscopo

    batch = _nuovo_batch()
    for i, (segno, testo) in enumerate(righe):
        db.session.add(Oroscopo(scan_batch=batch, segno=segno,
                                testo=testo, ordine=i))
    _pota(Oroscopo, MAX_BATCH_OROSCOPO)
    db.session.commit()
    return batch
