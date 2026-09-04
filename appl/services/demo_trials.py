"""Prova gratuita di 7 giorni: assegnazione degli slot, coda, scadenze.

COME FUNZIONA, IN BREVE
-----------------------
Ci sono tre database demo sempre esistenti (demo1/2/3, montati su /s/91-93).
Una richiesta di prova prende uno slot libero, lo risemina con dati freschi e
crea l'utente; se non ce n'e' nessuno libero la richiesta si mette in coda con
una data di partenza CALCOLATA - non stimata - perche' ogni prova dura sette
giorni esatti e quindi si sa quando il primo slot torna disponibile.

Alla scadenza lo slot non si cancella: si risemina e torna libero.

DOVE STANNO I DATI
------------------
Nel registro centrale (tosca_registry), tabelle demo_slot / demo_trial /
demo_deroga. Non nella tabella `tenant`: una prova gratuita non e' un negozio
e non deve entrare nel conteggio dei clienti ne' nella fatturazione.

IL LIMITE E' IL CELLULARE, NON L'IP
-----------------------------------
Una prova per numero. L'indirizzo IP serve solo come freno agli invii a
raffica: su rete mobile migliaia di persone condividono lo stesso indirizzo, e
usarlo come blocco murerebbe interi quartieri. Il numero invece viene
verificato di fatto, perche' il link di accesso arriva su WhatsApp.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

from appl.registry_models import (
    DemoDeroga, DemoSlot, DemoTrial, registry_enabled, registry_session,
)

# ── Regole ─────────────────────────────────────────────────────────────
PROVA_GIORNI = 7      # durata della prova, dal primo accesso
CLAIM_GIORNI = 3      # tempo per entrare dopo che lo slot si e' liberato
CODA_MAX = 6          # oltre questa lunghezza si offre solo la chiamata
VERSIONE_TERMINI = '1.0'
VERSIONE_PRIVACY = '1.0'

# La pagina di prenotazione online di un centro di esempio, quella che vedrebbe
# una cliente dal telefono. Sta su un tenant SEPARATO dagli slot della prova:
# chi prenota li' non tocca l'agenda della propria prova, ed e' il motivo per
# cui va detto a chiare lettere dove si sta prenotando.
# Sta qui, e non in due template, perche' la usano due applicazioni diverse:
# la pagina /prova (root_app) e la finestra "versione completa" dentro l'Agenda.
URL_BOOKING_DEMO = ('https://websunbooking-ckaxbhf6cjewabb8.italynorth-01'
                    '.azurewebsites.net/t3/booking')

# Alfabeto senza caratteri che si confondono a voce o su carta (0/O, 1/l/I):
# la password la si detta al telefono piu' spesso di quanto si creda.
ALFABETO = 'abcdefghijkmnpqrstuvwxyz23456789'


def _adesso():
    return datetime.now(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════
#  TELEFONO
# ═══════════════════════════════════════════════════════════════════════

def normalizza_telefono(numero: str | None) -> str | None:
    """Da "+39 333 123 4567" o "333 1234567" a "393331234567".

    Ritorna None se non somiglia a un cellulare italiano. Non e' una verifica
    che il numero esista: quella la fa il messaggio WhatsApp, che o arriva o no.
    """
    if not numero:
        return None
    cifre = re.sub(r'\D', '', str(numero))
    if cifre.startswith('00'):
        cifre = cifre[2:]
    if cifre.startswith('39') and len(cifre) >= 11:
        pass
    elif cifre.startswith('3') and 9 <= len(cifre) <= 11:
        cifre = '39' + cifre
    else:
        return None
    if not (11 <= len(cifre) <= 14):
        return None
    return cifre


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def genera_password(lunghezza: int = 10) -> str:
    return ''.join(secrets.choice(ALFABETO) for _ in range(lunghezza))


# ═══════════════════════════════════════════════════════════════════════
#  STATO DELLA CODA
# ═══════════════════════════════════════════════════════════════════════

def _liberi(s):
    return (s.query(DemoSlot)
             .filter(DemoSlot.stato == 'libero')
             .order_by(DemoSlot.idx).all())


def _in_coda(s):
    return (s.query(DemoTrial)
             .filter(DemoTrial.stato == 'in_coda')
             .order_by(DemoTrial.creata_at).all())


def _prossime_liberazioni(s):
    """Le date in cui gli slot occupati tornano liberi, dalla piu' vicina.

    Una prova non ancora iniziata (link mandato, nessun accesso) scade al
    massimo alla fine del tempo per entrare piu' la durata della prova: e' il
    caso peggiore, ed e' l'unico onesto da promettere a chi sta in coda.
    """
    date = []
    attive = (s.query(DemoTrial)
               .filter(DemoTrial.stato.in_(('attiva', 'invitata')))
               .all())
    for t in attive:
        if t.scadenza_at:
            date.append(t.scadenza_at)
        elif t.claim_entro:
            date.append(t.claim_entro + timedelta(days=PROVA_GIORNI))
        else:
            date.append(_adesso() + timedelta(days=PROVA_GIORNI))
    return sorted(date)


def stato_coda() -> dict:
    """Quello che serve alla pagina pubblica per dire la verita' a chi chiede.

    `prima_data_libera` e' calcolata, non stimata: le prove durano sette giorni
    esatti, quindi la data in cui il prossimo slot si libera si sa gia'.
    """
    if not registry_enabled():
        return {'disponibile': False, 'motivo': 'registro non configurato'}

    with registry_session() as s:
        liberi = len(_liberi(s))
        coda = _in_coda(s)
        liberazioni = _prossime_liberazioni(s)

        if liberi > 0:
            return {'disponibile': True, 'slot_liberi': liberi,
                    'in_coda': len(coda), 'coda_aperta': True}

        # Chi si accoda adesso e' il (len(coda)+1)-esimo: prende lo slot che si
        # libera per (len(coda)+1)-esimo. Se le liberazioni note non bastano,
        # si somma un altro giro di sette giorni per ogni posto mancante.
        posizione = len(coda) + 1
        if liberazioni:
            if posizione <= len(liberazioni):
                data = liberazioni[posizione - 1]
            else:
                giri = posizione - len(liberazioni)
                data = liberazioni[-1] + timedelta(days=PROVA_GIORNI * giri)
        else:
            data = _adesso() + timedelta(days=PROVA_GIORNI)

        return {
            'disponibile': False,
            'slot_liberi': 0,
            'in_coda': len(coda),
            'posizione_se_accodato': posizione,
            'prima_data_libera': data,
            # Sopra il tetto non si promettono date: a cinque settimane di
            # distanza nessuno aspetta, e una data mancata vale meno di un no.
            'coda_aperta': len(coda) < CODA_MAX,
        }


# ═══════════════════════════════════════════════════════════════════════
#  CHI PUO' CHIEDERE UNA PROVA
# ═══════════════════════════════════════════════════════════════════════

def puo_richiedere(telefono_norm: str) -> tuple[bool, str]:
    """Una prova per numero, salvo deroga dell'owner."""
    with registry_session() as s:
        precedenti = (s.query(DemoTrial)
                       .filter(DemoTrial.telefono_norm == telefono_norm)
                       .filter(DemoTrial.stato != 'annullata')
                       .count())
        if precedenti == 0:
            return True, ''
        deroga = s.get(DemoDeroga, telefono_norm)
        concesse = 1 + (deroga.prove_extra if deroga else 0)
        if precedenti < concesse:
            return True, ''
        return False, ('Da questo numero risulta gia' + "'" +
                       ' una prova. Scrivici e la riapriamo noi.')


# ═══════════════════════════════════════════════════════════════════════
#  CODICE DI VERIFICA (OTP)
#
#  Serve a sapere che l'indirizzo e-mail esiste ed e' di chi lo scrive, PRIMA
#  di bruciare uno slot: gli slot sono tre, e uno assegnato a un indirizzo
#  inventato resterebbe fermo per tre giorni prima di tornare libero.
#
#  Sta in memoria e non nel registro di proposito: e' un dato che vive dieci
#  minuti e non serve a nessuno il giorno dopo. Il prezzo e' che un riavvio
#  dell'applicazione perde i codici in volo - chi stava scrivendo il codice si
#  vede dire che e' scaduto e ne chiede un altro. Con un'istanza sola (e
#  l'istanza deve restare una: vedi wsgi.py) non c'e' altro da sapere.
# ═══════════════════════════════════════════════════════════════════════

OTP_VALIDO_MINUTI = 15
OTP_TENTATIVI_MAX = 5

_codici: dict[str, dict] = {}      # richiesta_id -> dati + codice
_LUNGHEZZA_CODICE = 6


def _pulisci_codici():
    adesso = _adesso()
    for chiave in [k for k, v in _codici.items() if v['scade'] < adesso]:
        _codici.pop(chiave, None)


def genera_codice() -> str:
    """Sei cifre. Va letto ad alta voce e ribattuto a mano: niente lettere."""
    return ''.join(secrets.choice('0123456789') for _ in range(_LUNGHEZZA_CODICE))


def prepara_codice(dati: dict) -> dict:
    """Controlla i dati, mette da parte la richiesta e restituisce il codice.

    Non manda niente: l'invio lo fa chi chiama, che sa gia' come si spedisce.
    Ritorna anche `coda` per far scrivere alla pagina la cosa giusta prima di
    chiedere il codice, invece di scoprire solo dopo che non ci sono slot.
    """
    _pulisci_codici()

    telefono_norm = normalizza_telefono(dati.get('telefono'))
    if not telefono_norm:
        return {'ok': False, 'errore': 'Il numero di cellulare non sembra valido.'}
    email = (dati.get('email') or '').strip()
    if '@' not in email or '.' not in email.split('@')[-1]:
        return {'ok': False, 'errore': "L'indirizzo e-mail non sembra valido."}

    ok, motivo = puo_richiedere(telefono_norm)
    if not ok:
        return {'ok': False, 'errore': motivo, 'gia_usata': True}

    stato = stato_coda()
    if not stato.get('disponibile') and not stato.get('coda_aperta'):
        return {'ok': False, 'coda_piena': True,
                'errore': ('Le prove sono tutte impegnate e la lista d' + "'" +
                           'attesa e' + "'" + ' al completo. '
                           'Prenota una presentazione: te la mostriamo noi.')}

    richiesta_id = secrets.token_urlsafe(18)
    codice = genera_codice()
    _codici[richiesta_id] = {
        'codice': codice,
        'dati': dict(dati, telefono_norm=telefono_norm, email=email),
        'scade': _adesso() + timedelta(minutes=OTP_VALIDO_MINUTI),
        'tentativi': 0,
    }
    return {'ok': True, 'richiesta_id': richiesta_id, 'codice': codice,
            'email': email, 'in_coda': not stato.get('disponibile'),
            'minuti': OTP_VALIDO_MINUTI}


def verifica_codice(richiesta_id: str, codice: str) -> dict:
    """Confronta il codice e restituisce i dati della richiesta se torna.

    Il codice si consuma solo quando e' giusto: sbagliare a digitare non deve
    costare un giro di e-mail. Dopo cinque tentativi pero' la richiesta si
    butta, altrimenti sei cifre si indovinano provando.
    """
    _pulisci_codici()
    voce = _codici.get(richiesta_id or '')
    if not voce:
        return {'ok': False, 'scaduto': True,
                'errore': 'Il codice non e' + "'" + ' piu' + "'" +
                          ' valido. Richiedine uno nuovo.'}

    voce['tentativi'] += 1
    if voce['tentativi'] > OTP_TENTATIVI_MAX:
        _codici.pop(richiesta_id, None)
        return {'ok': False, 'scaduto': True,
                'errore': 'Troppi tentativi. Richiedi un codice nuovo.'}

    if (codice or '').strip() != voce['codice']:
        rimasti = OTP_TENTATIVI_MAX - voce['tentativi']
        return {'ok': False,
                'errore': 'Codice non corretto.%s' % (
                    ' Hai ancora %d tentativi.' % rimasti if rimasti > 0 else '')}

    dati = _codici.pop(richiesta_id)['dati']
    return {'ok': True, 'dati': dati}


# ═══════════════════════════════════════════════════════════════════════
#  RICHIESTA
# ═══════════════════════════════════════════════════════════════════════

def crea_richiesta(business_name: str, referente: str, email: str,
                   telefono: str, ip: str = '', user_agent: str = '',
                   fonte: str = '') -> dict:
    """Registra la richiesta e prenota uno slot se ce n'e' uno libero.

    NON semina e non crea l'utente: quello lo fa `attiva()`, che ha bisogno
    della URI dello slot e ci mette qualche secondo. Qui si decide solo se la
    prova parte subito o si mette in coda.
    """
    telefono_norm = normalizza_telefono(telefono)
    if not telefono_norm:
        return {'ok': False, 'errore': 'Il numero di cellulare non sembra valido.'}

    ok, motivo = puo_richiedere(telefono_norm)
    if not ok:
        return {'ok': False, 'errore': motivo, 'gia_usata': True}

    with registry_session() as s:
        liberi = _liberi(s)
        coda = _in_coda(s)

        trial = DemoTrial(
            business_name=(business_name or '').strip()[:150],
            referente=(referente or '').strip()[:120] or None,
            email=(email or '').strip()[:120],
            telefono=(telefono or '').strip()[:30],
            telefono_norm=telefono_norm,
            ip_richiesta=(ip or '')[:45] or None,
            user_agent=(user_agent or '')[:2000] or None,
            fonte=(fonte or '')[:200] or None,
            privacy_versione=VERSIONE_PRIVACY,
            privacy_accettata_at=_adesso(),
            termini_versione=VERSIONE_TERMINI,
            termini_accettati_at=_adesso(),
        )

        if liberi:
            slot = liberi[0]
            trial.slot_idx = slot.idx
            trial.stato = 'invitata'
            trial.invitata_at = _adesso()
            trial.claim_entro = _adesso() + timedelta(days=CLAIM_GIORNI)
            s.add(trial)
            s.flush()
            slot.stato = 'occupato'
            slot.trial_id = trial.id
            slot.updated_at = _adesso()
            return {'ok': True, 'trial_id': trial.id, 'slot_idx': slot.idx,
                    'in_coda': False}

        if len(coda) >= CODA_MAX:
            return {'ok': False, 'coda_piena': True,
                    'errore': ('Le prove sono tutte impegnate e la lista d' + "'" +
                               'attesa e' + "'" + ' al completo. '
                               'Prenota una presentazione: te la mostriamo noi.')}

        trial.stato = 'in_coda'
        s.add(trial)
        s.flush()
        return {'ok': True, 'trial_id': trial.id, 'in_coda': True,
                'posizione': len(coda) + 1}


# ═══════════════════════════════════════════════════════════════════════
#  ATTIVAZIONE DELLO SLOT
# ═══════════════════════════════════════════════════════════════════════

def attiva(trial_id: int, uri_slot: str, owner_user=None,
           nome_centro: str | None = None) -> dict:
    """Risemina lo slot, crea l'utente della prova e restituisce le credenziali.

    Ci mette qualche secondo (la semina genera ottocento appuntamenti e
    trecento scontrini): chi chiama deve dirlo a chi aspetta, non far finta che
    sia istantaneo.

    `owner_user` e' la coppia (username, hash) presa da un negozio VERO, cosi'
    l'owner puo' entrare nella prova per dare una mano. Non si ricava da qui
    per non legare questo modulo a wsgi.
    """
    from appl.services.demo_seed import semina

    with registry_session() as s:
        trial = s.get(DemoTrial, trial_id)
        if trial is None:
            return {'ok': False, 'errore': 'prova inesistente'}
        if trial.slot_idx is None:
            return {'ok': False, 'errore': 'prova senza slot assegnato'}
        nome = nome_centro or trial.business_name or 'Centro Estetico Aurora'
        email = trial.email

    password = genera_password()
    token = secrets.token_urlsafe(32)

    conteggi = semina(uri_slot, reset=True, password_demo=password,
                      nome_centro=nome)

    # L'utente owner viene copiato DOPO la semina, che azzera lo schema.
    if owner_user:
        _aggiungi_owner(uri_slot, owner_user[0], owner_user[1])

    with registry_session() as s:
        trial = s.get(DemoTrial, trial_id)
        trial.username = 'demo'
        trial.token_hash = _hash(token)
        trial.stato = 'invitata'
        if not trial.invitata_at:
            trial.invitata_at = _adesso()
        trial.claim_entro = _adesso() + timedelta(days=CLAIM_GIORNI)

    return {'ok': True, 'username': 'demo', 'password': password,
            'token': token, 'email': email, 'seminato': conteggi}


def _aggiungi_owner(uri_slot: str, username: str, password_hash: str) -> None:
    """Mette l'utente owner nello slot appena seminato."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session
    from appl.models import RuoloUtente, User

    engine = create_engine(uri_slot.replace('postgresql+psycopg2://', 'postgresql://'),
                           pool_size=1, max_overflow=0)
    try:
        with Session(engine) as s:
            gia = s.query(User).filter_by(username=username).first()
            if gia is None:
                s.add(User(username=username, password=password_hash,
                           ruolo=RuoloUtente.owner))
                s.commit()
    finally:
        engine.dispose()


# ═══════════════════════════════════════════════════════════════════════
#  PRIMO ACCESSO E SCADENZA
# ═══════════════════════════════════════════════════════════════════════

def consuma_token(token: str) -> dict | None:
    """Primo accesso con il link: da qui partono i sette giorni.

    Il token resta valido per tutta la prova - e' il modo in cui si rientra dal
    link ricevuto - ma il cronometro parte solo la prima volta.
    """
    if not token:
        return None
    with registry_session() as s:
        trial = (s.query(DemoTrial)
                  .filter(DemoTrial.token_hash == _hash(token))
                  .first())
        if trial is None or trial.stato not in ('invitata', 'attiva'):
            return None
        if trial.stato == 'invitata':
            trial.stato = 'attiva'
            trial.inizio_at = _adesso()
            trial.scadenza_at = _adesso() + timedelta(days=PROVA_GIORNI)
        elif trial.scadenza_at and trial.scadenza_at < _adesso():
            return None
        return {'trial_id': trial.id, 'slot_idx': trial.slot_idx,
                'username': trial.username or 'demo',
                'scadenza': trial.scadenza_at}


def prova_dello_slot(slot_idx: int) -> dict | None:
    """La prova in corso su uno slot, con i giorni che restano."""
    with registry_session() as s:
        slot = s.get(DemoSlot, slot_idx)
        if slot is None or not slot.trial_id:
            return None
        trial = s.get(DemoTrial, slot.trial_id)
        if trial is None:
            return None
        residui = None
        if trial.scadenza_at:
            # Arrotondato per eccesso: il giorno dell'attivazione mancano sette
            # giorni, non sei. `.days` tronca, e una prova appena aperta
            # sembrerebbe gia' cominciata a consumarsi.
            resta = trial.scadenza_at - _adesso()
            residui = max(0, -(-resta.total_seconds() // 86400))
            residui = int(residui)
        return {'trial_id': trial.id, 'stato': trial.stato,
                'business_name': trial.business_name,
                'scadenza_at': trial.scadenza_at,
                'giorni_residui': residui}


def da_chiudere() -> list[dict]:
    """Prove finite: scadute, o invitate e mai usate entro il tempo per entrare.

    Una prova mai reclamata va chiusa, altrimenti un indirizzo e-mail sbagliato
    terrebbe occupato uno slot per sempre.
    """
    adesso = _adesso()
    fuori = []
    with registry_session() as s:
        for t in s.query(DemoTrial).filter(
                DemoTrial.stato.in_(('attiva', 'invitata'))).all():
            if t.stato == 'attiva' and t.scadenza_at and t.scadenza_at <= adesso:
                fuori.append({'trial_id': t.id, 'slot_idx': t.slot_idx,
                              'motivo': 'scaduta'})
            elif t.stato == 'invitata' and t.claim_entro and t.claim_entro <= adesso:
                fuori.append({'trial_id': t.id, 'slot_idx': t.slot_idx,
                              'motivo': 'mai_iniziata'})
    return fuori


def chiudi(trial_id: int, uri_slot: str | None = None,
           stato: str = 'scaduta') -> dict:
    """Chiude la prova e riporta lo slot a 'libero', riseminandolo.

    L'ordine conta: prima si segna lo slot come 'da_risemina', poi si semina,
    poi lo si libera. Se la semina fallisce, lo slot resta 'da_risemina' e non
    viene assegnato a nessuno: meglio uno slot fermo che un nuovo cliente
    dentro i dati di quello prima.
    """
    with registry_session() as s:
        trial = s.get(DemoTrial, trial_id)
        if trial is None:
            return {'ok': False, 'errore': 'prova inesistente'}
        slot_idx = trial.slot_idx
        trial.stato = stato
        trial.chiusa_at = _adesso()
        trial.token_hash = None      # il link vecchio non deve piu' aprire nulla
        if slot_idx is not None:
            slot = s.get(DemoSlot, slot_idx)
            if slot is not None:
                slot.stato = 'da_risemina'
                slot.trial_id = None
                slot.updated_at = _adesso()

    if slot_idx is None or not uri_slot:
        return {'ok': True, 'slot_idx': slot_idx, 'riseminato': False}

    from appl.services.demo_seed import semina
    semina(uri_slot, reset=True)

    with registry_session() as s:
        slot = s.get(DemoSlot, slot_idx)
        if slot is not None and slot.stato == 'da_risemina':
            slot.stato = 'libero'
            slot.updated_at = _adesso()
    return {'ok': True, 'slot_idx': slot_idx, 'riseminato': True}


def primo_in_coda() -> dict | None:
    """Chi tocca quando si libera uno slot."""
    with registry_session() as s:
        coda = _in_coda(s)
        if not coda:
            return None
        t = coda[0]
        return {'trial_id': t.id, 'business_name': t.business_name,
                'referente': t.referente, 'email': t.email,
                'telefono': t.telefono}


def assegna_slot(trial_id: int, slot_idx: int) -> bool:
    """Aggancia una richiesta in coda a uno slot tornato libero."""
    with registry_session() as s:
        trial = s.get(DemoTrial, trial_id)
        slot = s.get(DemoSlot, slot_idx)
        if trial is None or slot is None or slot.stato != 'libero':
            return False
        trial.slot_idx = slot_idx
        trial.stato = 'invitata'
        trial.invitata_at = _adesso()
        trial.claim_entro = _adesso() + timedelta(days=CLAIM_GIORNI)
        slot.stato = 'occupato'
        slot.trial_id = trial.id
        slot.updated_at = _adesso()
        return True
