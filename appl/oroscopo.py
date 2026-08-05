# appl/oroscopo.py
"""
Oroscopo settimanale in chiave estetista: dodici segni, tono leggero, battute
sul mestiere (cerette, lampade, ricostruzioni, la cliente che arriva in
ritardo). Operazione simpatia, non astrologia.

COME FUNZIONA
-------------
Non ha un thread suo: si appoggia a quello di appl/news_beauty.py, che ogni
mezz'ora chiama esegui_se_dovuto(). Un solo thread per due lavori, cosi' non si
moltiplicano i timer dentro l'app.

Cadenza: una volta a settimana, il LUNEDI'. Se l'app e' rimasta spenta e sono
passati piu' di OROSCOPO_MAX_GIORNI giorni, riparte al primo avvio utile anche
in un altro giorno - meglio un oroscopo di martedi' che un tile vuoto.

PRIVACY: all'API non viene mandato NESSUN dato dei clienti. Solo il nome
dell'istituto e la stagione. Le battute girano su situazioni tipiche del
mestiere, mai su persone reali: i nomi veri non escono dall'app, e un oroscopo
che nomina una cliente vera sarebbe divertente per una persona sola e
imbarazzante per tutte le altre.

COSTO: nessuna ricerca web, solo scrittura. Poche migliaia di token in uscita
una volta a settimana, cioe' pochi centesimi al mese.

VARIABILI D'AMBIENTE
--------------------
  OROSCOPO_ENABLED    '1' (default) / '0' per spegnerlo.
  OROSCOPO_MODEL      default: lo stesso modello delle notizie.
  OROSCOPO_MAX_TOKEN  default 3000.
"""

import os
from datetime import datetime, timedelta

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------
GIORNO_OROSCOPO = 0        # lunedi'
ORE_MINIME = 20            # non rifarlo due volte nello stesso lunedi'
# Recupero: oltre gli 8 giorni un lunedi' e' stato saltato di sicuro, quindi si
# rigenera in qualunque giorno. Con una soglia piu' alta si sarebbe aspettato il
# lunedi' successivo tenendo il tile fermo su un oroscopo di due settimane fa.
OROSCOPO_MAX_GIORNI = 8

# Simbolo e periodo sono dati fissi: non ha senso rigenerarli e salvarli ogni
# settimana. L'ordine e' quello classico dello zodiaco.
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

_ultimo_errore = None


def _abilitato():
    if os.getenv('OROSCOPO_ENABLED', '1').strip() not in ('1', 'true', 'yes', 'on'):
        return False
    return bool((os.getenv('ANTHROPIC_API_KEY') or '').strip())


def _modello():
    from appl.news_beauty import MODELLO
    return os.getenv('OROSCOPO_MODEL', MODELLO)


def _max_token():
    try:
        return max(1500, min(int(os.getenv('OROSCOPO_MAX_TOKEN', '3000')), 8000))
    except (TypeError, ValueError):
        return 3000


# ---------------------------------------------------------------------------
# Quando farlo
# ---------------------------------------------------------------------------
def _ultimo_batch(app):
    """(leggibile, datetime_ultimo) dal database di un tenant."""
    from appl import db
    from appl.models import Oroscopo
    from sqlalchemy import func as sa_func
    with app.app_context():
        try:
            return True, db.session.query(sa_func.max(Oroscopo.created_at)).scalar()
        except Exception:
            db.session.rollback()
            return False, None


def _dovuto(ultimo, adesso=None):
    from appl.news_beauty import _eta_minuti
    adesso = adesso or datetime.now()
    if ultimo is None:
        return True
    ore = _eta_minuti(ultimo, adesso) / 60
    # Recupero: l'app e' rimasta spenta a lungo, si rigenera comunque.
    if ore >= OROSCOPO_MAX_GIORNI * 24:
        return True
    if adesso.weekday() != GIORNO_OROSCOPO:
        return False
    return ore >= ORE_MINIME


# ---------------------------------------------------------------------------
# Generazione
# ---------------------------------------------------------------------------
PROMPT_SISTEMA = (
    "Scrivi l'oroscopo settimanale per le ragazze di un centro estetico "
    "italiano. Lo leggono il lunedi' mattina mentre aprono, e deve strappare "
    "un sorriso: tono da rivista in sala d'attesa, un filo kitsch, mai serio "
    "sul serio. "
    "Le battute nascono dal mestiere - cerette, lampade, ricostruzione unghie, "
    "la cliente che arriva in ritardo e vuole tutto, il telefono che squilla "
    "mentre hai le mani nella cera, il magazzino da riordinare. "
    "Sii affettuosa, mai cattiva: le clienti si prendono in giro con simpatia, "
    "non si sfottono. Niente previsioni che possano preoccupare davvero "
    "(salute, soldi, amore in crisi): e' un gioco, non un responso."
)


def _prompt_utente(nome_centro):
    oggi = datetime.now()
    stagione = ('inverno', 'inverno', 'primavera', 'primavera', 'primavera',
                'estate', 'estate', 'estate', 'autunno', 'autunno', 'autunno',
                'inverno')[oggi.month - 1]
    riferimento = f' Il centro si chiama "{nome_centro}".' if nome_centro else ''

    return (
        f"Settimana che inizia il {oggi.strftime('%d/%m/%Y')}, siamo in "
        f"{stagione}.{riferimento}\n\n"
        f"Scrivi l'oroscopo per tutti e dodici i segni, in questo ordine: "
        f"{', '.join(NOMI_SEGNI)}.\n\n"
        f"Per ogni segno: 2 frasi, massimo 230 caratteri in tutto. Una battuta "
        f"o un'immagine legata al lavoro in istituto, e una piccola spinta "
        f"positiva per la settimana. Varia gli argomenti fra un segno e "
        f"l'altro: se hai gia' fatto la battuta sulla ceretta non rifarla.\n\n"
        f"Ogni tanto (non a tutti i segni) puoi tirare in ballo il centro o la "
        f"stagione. Non inventare nomi di clienti: parla di \"la cliente delle "
        f"tre\", \"quella del pacchetto da dieci\", cose cosi'.\n\n"
        f"Rispondi con un array JSON e nient'altro, senza testo prima o dopo. "
        f"Ogni elemento:\n"
        f'  "segno": il nome esatto del segno come te l\'ho scritto\n'
        f'  "testo": l\'oroscopo, massimo 230 caratteri'
    )


def _nome_centro(app):
    from appl import db
    from appl.models import BusinessInfo
    with app.app_context():
        try:
            info = BusinessInfo.query.first()
            return (info.business_name or '').strip() if info else ''
        except Exception:
            db.session.rollback()
            return ''


def _chiama_claude(nome_centro):
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

    # Niente ricerca web: e' scrittura creativa, non c'e' niente da cercare.
    # E' questo che rende l'oroscopo molto piu' economico delle notizie.
    with client.messages.stream(
        model=_modello(),
        max_tokens=_max_token(),
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": _prompt_utente(nome_centro)}],
    ) as stream:
        risposta = stream.get_final_message()

    if risposta.stop_reason == "refusal":
        raise RuntimeError("Richiesta rifiutata dai filtri di sicurezza.")
    if risposta.stop_reason == "max_tokens":
        raise RuntimeError(
            f"Risposta troncata: alza OROSCOPO_MAX_TOKEN (ora {_max_token()})."
        )

    return "".join(b.text for b in risposta.content
                   if getattr(b, 'type', '') == 'text')


def _normalizza(dati):
    """
    Tiene solo i segni riconosciuti e li rimette in ordine zodiacale.
    Se il modello ne salta qualcuno si accetta lo stesso: undici segni su
    dodici sono comunque un tile che funziona.
    """
    per_segno = {}
    for elem in dati if isinstance(dati, list) else []:
        if not isinstance(elem, dict):
            continue
        segno = (elem.get('segno') or '').strip().capitalize()
        testo = (elem.get('testo') or '').strip()
        if segno in DETTAGLI_SEGNO and testo and segno not in per_segno:
            per_segno[segno] = testo[:600]
    return [(s, per_segno[s]) for s in NOMI_SEGNI if s in per_segno]


def _salva(app, righe, batch):
    from appl import db
    from appl.models import Oroscopo
    with app.app_context():
        try:
            for i, (segno, testo) in enumerate(righe):
                db.session.add(Oroscopo(scan_batch=batch, segno=segno,
                                        testo=testo, ordine=i))
            # Si tengono gli ultimi 8 batch: l'oroscopo della settimana scorsa
            # non serve a nessuno, ma un minimo di storico aiuta a capire se il
            # lavoro settimanale sta girando.
            vecchi = [b[0] for b in db.session.query(Oroscopo.scan_batch)
                      .distinct().order_by(Oroscopo.scan_batch.desc())
                      .offset(8).all()]
            if vecchi:
                (Oroscopo.query.filter(Oroscopo.scan_batch.in_(vecchi))
                 .delete(synchronize_session=False))
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            app.logger.exception("[oroscopo] salvataggio fallito: %s", exc)
            return False


def esegui(force=False):
    """
    Genera l'oroscopo e lo scrive in tutti i tenant registrati.
    Restituisce l'esito, come lo scan delle notizie.
    """
    global _ultimo_errore

    from appl.news_beauty import (app_registrate, _estrai_json,
                                  _errore_leggibile, _registra_errore,
                                  _eta_minuti, COOLDOWN_MANUALE_MIN)

    if not _abilitato():
        return {'ok': False, 'errore': 'Oroscopo non attivo (manca ANTHROPIC_API_KEY)'}

    apps = app_registrate()
    if not apps:
        return {'ok': False, 'errore': 'Nessun tenant registrato'}

    try:
        import anthropic  # noqa: F401
    except ImportError:
        _ultimo_errore = ("Libreria 'anthropic' non installata: "
                          "pip install -r requirements.txt")
        return {'ok': False, 'errore': _ultimo_errore}

    app_principale = apps[0][1]
    leggibile, ultimo = _ultimo_batch(app_principale)
    if not leggibile:
        _ultimo_errore = ("Tabella oroscopo_settimanale assente: "
                          "esegui migrations/manual_oroscopo.sql")
        return {'ok': False, 'errore': _ultimo_errore}

    if force:
        # Stessa protezione delle notizie: un doppio click non deve ripagare
        # la generazione per riottenere dodici righe equivalenti.
        if ultimo and _eta_minuti(ultimo) < COOLDOWN_MANUALE_MIN:
            minuti = int(COOLDOWN_MANUALE_MIN - _eta_minuti(ultimo))
            return {'ok': False, 'nessun_costo': True,
                    'errore': f'Oroscopo appena scritto. Se ne puo\' fare un altro '
                              f'fra {minuti} min (di norma si rifa il lunedi\').'}
    elif not _dovuto(ultimo):
        return {'ok': False, 'errore': 'Oroscopo non ancora dovuto'}

    try:
        testo = _chiama_claude(_nome_centro(app_principale))
    except Exception as exc:
        _ultimo_errore = _errore_leggibile(exc)
        app_principale.logger.exception("[oroscopo] generazione fallita: %s", exc)
        if not force:
            _registra_errore('Oroscopo settimanale fallito', exc)
        return {'ok': False, 'errore': _ultimo_errore}

    righe = _normalizza(_estrai_json(testo))
    if len(righe) < 6:
        _ultimo_errore = 'Oroscopo incompleto, riprovo alla prossima occasione'
        if not force:
            _registra_errore('Oroscopo settimanale incompleto',
                             f'segni validi: {len(righe)}')
        return {'ok': False, 'errore': _ultimo_errore}

    batch = datetime.now().strftime('%Y%m%dT%H%M')
    salvati = sum(1 for _e, app in apps if _salva(app, righe, batch))
    _ultimo_errore = None
    return {'ok': salvati > 0, 'segni': len(righe), 'tenant': salvati, 'batch': batch}


def esegui_se_dovuto():
    """Chiamata dal thread di news_beauty a ogni giro."""
    if not _abilitato():
        return
    esegui(force=False)


def stato():
    return {
        'abilitato': _abilitato(),
        'modello': _modello(),
        'giorno': 'Lunedi',
        'ultimo_errore': _ultimo_errore,
    }
