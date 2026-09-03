"""Semina di uno slot demo: un centro estetico finto, credibile e sempre attuale.

PERCHE' UNO SCRIPT E NON UN DUMP
--------------------------------
La prima idea era tenere un database "modello" e ricaricarlo con pg_dump ad ogni
scadenza. Ha un difetto che si vede solo fra due mesi: le date dentro il dump
restano quelle del giorno in cui e' stato fatto, e il potenziale cliente aprirebbe
l'Agenda su una settimana vuota e un Report di gennaio. Qui invece i giorni sono
calcolati a partire da OGGI ad ogni semina, quindi la demo non invecchia mai. In
piu' e' un database in meno da tenere allineato alle migrazioni.

COSA SEMINA
-----------
Tre settimane di passato e due di futuro: operatori con i turni, listino,
clienti, appuntamenti e - questo e' il punto che si dimentica - gli SCONTRINI.
Il Report legge la tabella `scontrini`, quindi senza scontrini finti la pagina
Report della demo sarebbe bianca proprio mentre si cerca di far vedere quanto e'
utile.

I NOMI SONO NEUTRI DI PROPOSITO
-------------------------------
Rossi, Bianchi, Verdi. Le schermate della demo finiscono negli screenshot e nelle
guide: nessun nome-scherzo, nessun dato di persone vere. Le e-mail usano
example.com, che RFC 2606 riserva apposta e che nessuno puo' registrare.

SICUREZZA
---------
`azzera_schema()` si rifiuta di lavorare su un database il cui nome non sia
demo<numero>. E' l'unico argine fra questo script e un database di produzione,
e non va tolto ne' allentato.

Uso:
    python -m appl.services.demo_seed --slot 1
    python -m appl.services.demo_seed --uri postgresql://... --no-reset
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from datetime import date, datetime, time, timedelta
from urllib.parse import urlparse

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# ═══════════════════════════════════════════════════════════════════════
#  ANAGRAFICA FINTA
# ═══════════════════════════════════════════════════════════════════════

NOMI_F = ["Laura", "Maria", "Anna", "Giulia", "Chiara", "Sara", "Elena", "Paola",
          "Silvia", "Francesca", "Martina", "Alessia", "Valentina", "Roberta",
          "Cristina", "Federica", "Ilaria", "Monica", "Daniela", "Barbara"]
NOMI_M = ["Marco", "Luca", "Mario", "Andrea", "Davide", "Simone", "Roberto",
          "Stefano", "Paolo", "Alessandro"]
COGNOMI = ["Rossi", "Bianchi", "Verdi", "Neri", "Gallo", "Conti", "Ricci",
           "Marino", "Greco", "Bruno", "Costa", "Fontana", "Rizzo", "Moretti",
           "Ferrari", "Russo", "Romano", "Colombo", "Barbieri", "Villa",
           "Sartori", "Longo", "Martini", "Leone", "Pellegrini"]

# Colori dei blocchi in Agenda. Tinte tenui: in una giornata piena devono
# restare leggibili, non sembrare un cartellone.
COLORI = ["#f8d7da", "#d1e7dd", "#cfe2ff", "#fff3cd", "#e2d9f3", "#d7f5f0",
          "#ffe5d0", "#e6e6fa", "#d9f2d9", "#fde2e4"]

# (nome, tag, durata, prezzo, categoria, sottocategoria)
LISTINO = [
    ("Manicure",               "MANI",  45, 25.0, "Estetica", "Mani e piedi"),
    ("Semipermanente mani",    "SEMIP", 60, 35.0, "Estetica", "Mani e piedi"),
    ("Ricostruzione unghie",   "RICOS", 90, 60.0, "Estetica", "Mani e piedi"),
    ("Pedicure estetico",      "PEDIC", 60, 35.0, "Estetica", "Mani e piedi"),
    ("Pulizia viso",           "VISO",  60, 45.0, "Estetica", "Viso"),
    ("Trattamento antieta",    "ANTIE", 75, 65.0, "Estetica", "Viso"),
    ("Laminazione ciglia",     "CIGLI", 60, 50.0, "Estetica", "Viso"),
    ("Ceretta gambe",          "CERGA", 40, 25.0, "Estetica", "Epilazione"),
    ("Ceretta completa",       "CERCO", 60, 40.0, "Estetica", "Epilazione"),
    ("Massaggio relax",        "MASRE", 50, 50.0, "Estetica", "Massaggi"),
    ("Massaggio decontratt.",  "MASDE", 50, 55.0, "Estetica", "Massaggi"),
    ("Pressoterapia",          "PRESS", 40, 30.0, "Estetica", "Corpo"),
    ("Trattamento corpo",      "CORPO", 60, 55.0, "Estetica", "Corpo"),
]

# Niente solarium nella demo, ne' fra i servizi ne' fra gli operatori: il
# modulo Solarium ha bisogno di macchinari, lampade e collegamenti veri, e in
# una prova mostrerebbe solo pulsanti che non fanno niente. Il centro finto e'
# un'estetica pura, con quattro postazioni.
OPERATORI = [
    ("Laura",   "Bianchi", "estetista"),
    ("Sara",    "Verdi",   "estetista"),
    ("Giulia",  "Rossi",   "estetista"),
    ("Martina", "Conti",   "estetista"),
]

# Apertura del centro finto: 9-19 tutti i giorni tranne la domenica. La
# griglia dell'agenda mostra pero' 8-20 (vedi BusinessInfo piu' sotto), cosi'
# il primo appuntamento non sta incollato al bordo.
ORA_APERTURA = time(9, 0)
ORA_CHIUSURA = time(19, 0)

GIORNI_PASSATO = 21
GIORNI_FUTURO = 14
CHIUSO = {6}  # domenica (weekday(): lunedi = 0)


# ═══════════════════════════════════════════════════════════════════════
#  UTILITA'
# ═══════════════════════════════════════════════════════════════════════

def uri_dallo_slot(slot: int) -> str:
    """URI del database demo<slot>, ricavata dalle credenziali gia' nel .env.

    Si appoggia a SQLALCHEMY_DATABASE_URI3 perche' e' l'unica delle tre a nome
    di un ruolo che possiede i database demo: con l'utente `suncity` non si
    entrerebbe nemmeno.
    """
    radice = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(radice, '.env')
    base = None
    with open(env_path, encoding='utf-8') as f:
        for riga in f:
            m = re.match(r'^SQLALCHEMY_DATABASE_URI3=(.+)$', riga.strip())
            if m:
                base = m.group(1).strip().strip('"').strip("'")
                break
    if not base:
        raise SystemExit("SQLALCHEMY_DATABASE_URI3 non trovata nel .env")
    return re.sub(r'/[^/?]+(\?|$)', '/demo%d\\1' % slot, base)


def _nome_db(uri: str) -> str:
    ripulita = uri.replace('postgresql+psycopg2://', 'postgresql://')
    return (urlparse(ripulita).path or '/').strip('/').split('/')[-1]


def azzera_schema(engine, uri: str) -> None:
    """Svuota il database dello slot. Solo demo<numero>, mai nient'altro."""
    nome = _nome_db(uri)
    if not re.fullmatch(r'demo\d+', nome or ''):
        raise SystemExit(
            "RIFIUTO: '%s' non e' uno slot demo. Questo script azzera lo schema, "
            "e lo fa solo su database chiamati demo<numero>." % nome)
    with engine.begin() as conn:
        conn.execute(text('DROP SCHEMA public CASCADE'))
        conn.execute(text('CREATE SCHEMA public'))
    print("  schema di %s azzerato" % nome)


def _hash_password(pwd: str) -> str:
    from argon2 import PasswordHasher
    return PasswordHasher().hash(pwd)


def _giorni_apertura(da: date, a: date):
    g = da
    while g <= a:
        if g.weekday() not in CHIUSO:
            yield g
        g += timedelta(days=1)


# ═══════════════════════════════════════════════════════════════════════
#  SEMINA
# ═══════════════════════════════════════════════════════════════════════

def semina(uri: str, reset: bool = True, password_demo: str = 'prova2026',
           nome_centro: str = 'Centro Estetico Aurora') -> dict:
    """Riempie lo slot e restituisce il conto di cio' che ha scritto."""
    rng = random.Random(20260903)  # riproducibile: due semine danno lo stesso centro

    engine = create_engine(uri.replace('postgresql+psycopg2://', 'postgresql://'),
                           pool_size=1, max_overflow=0, pool_pre_ping=True)

    if reset:
        azzera_schema(engine, uri)

    from appl import db
    from appl.models import (
        Appointment, AppointmentSource, AppointmentStatus, BusinessInfo, Client,
        Operator, OperatorShift, OWNER, Receipt, RuoloUtente, Service,
        ServiceCategory, Subcategory, User,
    )

    db.metadata.create_all(engine)
    print("  tabelle create")

    oggi = date.today()

    with Session(engine) as s:
        # ── Dati del centro ────────────────────────────────────────────────
        # ATTENZIONE ai nomi, sono controintuitivi e li avevo invertiti:
        #   opening_time / closing_time         = la fascia VISIBILE in agenda
        #       (calendar.html: range(opening_time.hour, closing_time.hour + 1))
        #   active_opening_time / active_closing = l'apertura VERA del centro
        #       (fuori da questa gli slot prendono la classe calendar-closed)
        # Con le due coincidenti, il primo appuntamento della giornata finiva
        # incollato al bordo superiore della griglia e sembrava cominciare prima
        # della prima cella. Un'ora di margine sopra e una sotto lo evitano.
        s.add(BusinessInfo(
            business_name=nome_centro,
            city='Milano',
            opening_time=time(8, 0),
            closing_time=time(20, 0),
            active_opening_time=time(9, 0),
            active_closing_time=time(19, 0),
            closing_days=json.dumps(['Domenica']),
            vat_percentage=22.0,
            # Nessun invio automatico da uno slot demo: se il potenziale cliente
            # scrive per prova un numero vero, non deve partirgli niente.
            whatsapp_morning_reminder_enabled=False,
            new_client_welcome_enabled=False,
            operator_whatsapp_notification_enabled=False,
        ))

        # Solo il modulo base: niente prenotazioni web, pacchetti o solarium, e
        # Cassa spenta. Il pulsante euro in Agenda resta pero' visibile e al
        # click racconta cosa fa la Cassa: e' un recinto, non un buco.
        s.add(OWNER(
            module_base_enabled=True,
            module_web_enabled=False,
            module_pacchetti_enabled=False,
            module_solarium_enabled=False,
            module_base_activated_on=oggi,
            cassa_enabled_on_web=False,
        ))

        s.add(User(username='demo', password=_hash_password(password_demo),
                   ruolo=RuoloUtente.admin))

        # ── Listino ────────────────────────────────────────────────────────
        sottocat = {}
        for _, _, _, _, cat, sc in LISTINO:
            if (cat, sc) not in sottocat:
                voce = Subcategory(nome=sc, categoria=ServiceCategory[cat],
                                   is_deleted=False)
                s.add(voce)
                sottocat[(cat, sc)] = voce
        s.flush()

        servizi = []
        for nome, tag, durata, prezzo, cat, sc in LISTINO:
            sv = Service(
                servizio_nome=nome, servizio_tag=tag, servizio_durata=durata,
                servizio_prezzo=prezzo, servizio_categoria=ServiceCategory[cat],
                servizio_sottocategoria_id=sottocat[(cat, sc)].id,
                is_deleted=False, is_visible_in_calendar=True, is_visible_online=True,
            )
            s.add(sv)
            servizi.append(sv)

        # ── Operatori ──────────────────────────────────────────────────────
        operatori = []
        for i, (nome, cognome, tipo) in enumerate(OPERATORI):
            op = Operator(user_nome=nome, user_cognome=cognome, user_tipo=tipo,
                          user_cellulare='0', is_deleted=False, is_visible=True,
                          order=i, notify_turni_via_whatsapp=False)
            s.add(op)
            operatori.append(op)
        s.flush()

        # Chi fa cosa: qui tutte fanno tutto. Il legame servizio-operatore
        # esiste lo stesso, cosi' chi prova la demo lo trova gia' popolato e
        # puo' toglierne qualcuno per vedere l'effetto.
        for sv in servizi:
            sv.operators = list(operatori)

        # ── Clienti ────────────────────────────────────────────────────────
        clienti = []
        usati = set()
        for i in range(45):
            maschio = rng.random() < 0.15
            nome = rng.choice(NOMI_M if maschio else NOMI_F)
            cognome = rng.choice(COGNOMI)
            while (nome, cognome) in usati:
                cognome = rng.choice(COGNOMI)
            usati.add((nome, cognome))
            cl = Client(
                cliente_nome=nome, cliente_cognome=cognome,
                # Numeri finti e progressivi: riempiono la scheda, non chiamano
                # nessuno. Dallo slot demo non parte comunque alcun messaggio.
                cliente_cellulare='340000%04d' % i,
                cliente_email='%s.%s@example.com' % (nome.lower(), cognome.lower()),
                cliente_sesso='M' if maschio else 'F',
                cliente_data_nascita=date(rng.randint(1965, 2004),
                                          rng.randint(1, 12), rng.randint(1, 28)),
                is_deleted=False,
            )
            s.add(cl)
            clienti.append(cl)
        s.flush()

        # ── Turni ──────────────────────────────────────────────────────────
        # Servono al Report: la saturazione dell'agenda e' minuti prenotati
        # diviso minuti di turno, e senza turni il denominatore non esiste.
        n_turni = 0
        for g in _giorni_apertura(oggi - timedelta(days=GIORNI_PASSATO),
                                  oggi + timedelta(days=GIORNI_FUTURO)):
            for i, op in enumerate(operatori):
                # Una estetista il lunedi non c'e': un'agenda dove sono tutti
                # sempre presenti non somiglia a nessun centro vero.
                if i == 1 and g.weekday() == 0:
                    continue
                s.add(OperatorShift(operator_id=op.id, shift_date=g,
                                    shift_start_time=ORA_APERTURA,
                                    shift_end_time=ORA_CHIUSURA))
                n_turni += 1

        # ── Appuntamenti ───────────────────────────────────────────────────
        # Si riempie la colonna di ogni operatore camminando lungo il suo turno:
        # o si prenota, o si lascia un buco di un quarto d'ora. Il primo tentativo
        # sorteggiava ora e operatore a caso e scartava le sovrapposizioni:
        # veniva fuori un'agenda piena al 14%, cioe' l'esatto contrario di quello
        # che deve far vedere una demo.
        #
        # RIEMPIMENTO: quanto e' pieno un giorno della settimana. Il venerdi e il
        # sabato sono i giorni del centro estetico, il lunedi e' il giorno morto.
        RIEMPIMENTO = {0: 0.40, 1: 0.55, 2: 0.60, 3: 0.65, 4: 0.80, 5: 0.85}

        # Le clienti non sono tutte uguali: poche fisse che tornano ogni
        # settimana, molte saltuarie. Se si sorteggiasse a caso fra 45 nomi
        # verrebbe una rubrica piatta, senza affezionate.
        pesi = [6 if i < 12 else 3 if i < 25 else 1 for i in range(len(clienti))]

        appuntamenti = []
        colore_del_giorno = {}   # (cliente, giorno) -> colore

        for g in _giorni_apertura(oggi - timedelta(days=GIORNI_PASSATO),
                                  oggi + timedelta(days=GIORNI_FUTURO)):
            fine_turno = ORA_CHIUSURA
            # Il futuro non e' ancora pieno: le prenotazioni arrivano piano piano,
            # e piu' e' lontano il giorno piu' e' vuoto.
            atteso = RIEMPIMENTO[g.weekday()]
            if g > oggi:
                lontananza = (g - oggi).days
                atteso *= max(0.20, 0.85 - 0.05 * lontananza)

            for i, op in enumerate(operatori):
                if i == 1 and g.weekday() == 0:
                    continue  # il turno che manca, come nei turni seminati sopra

                orario = datetime.combine(g, ORA_APERTURA)
                chiusura = datetime.combine(g, fine_turno)
                while orario < chiusura:
                    if rng.random() > atteso:
                        orario += timedelta(minutes=15)   # buco in agenda
                        continue
                    sv = rng.choice(servizi)
                    if orario + timedelta(minutes=sv.servizio_durata) > chiusura:
                        break   # non si sfora la chiusura

                    cl = rng.choices(clienti, weights=pesi, k=1)[0]
                    chiave = (cl.id, g)
                    if chiave not in colore_del_giorno:
                        colore_del_giorno[chiave] = rng.choice(COLORI)

                    if g < oggi:
                        r = rng.random()
                        stato = (AppointmentStatus.PAGATO if r < 0.88
                                 else AppointmentStatus.NON_ARRIVATO if r < 0.96
                                 else AppointmentStatus.DEFAULT)
                    elif g == oggi:
                        stato = (AppointmentStatus.PAGATO if orario.hour < 12
                                 else AppointmentStatus.IN_ISTITUTO if orario.hour < 14
                                 else AppointmentStatus.DEFAULT)
                    else:
                        stato = AppointmentStatus.DEFAULT

                    ap = Appointment(
                        client_id=cl.id, operator_id=op.id, service_id=sv.id,
                        start_time=orario, duration=sv.servizio_durata,
                        colore=colore_del_giorno[chiave], stato=stato,
                        source=(AppointmentSource.web if rng.random() < 0.12
                                else AppointmentSource.gestionale),
                    )
                    s.add(ap)
                    appuntamenti.append((ap, sv, cl, op, g))

                    orario += timedelta(minutes=sv.servizio_durata)
                    orario += timedelta(minutes=rng.choice([0, 0, 5, 10, 15]))
                    # Riporta l'orario a un multiplo di 5 minuti: un trattamento
                    # di durata dispari lascerebbe l'agenda piena di orari come
                    # le 10:37.
                    avanzo = orario.minute % 5
                    if avanzo:
                        orario += timedelta(minutes=5 - avanzo)
        s.flush()

        # ── Scontrini ──────────────────────────────────────────────────────
        # Uno per cliente per giornata, con dentro tutte le voci di quel giorno:
        # e' come paga davvero un cliente, e da' uno scontrino medio credibile.
        per_giorno = {}
        for ap, sv, cl, op, g in appuntamenti:
            if ap.stato != AppointmentStatus.PAGATO:
                continue
            per_giorno.setdefault((g, cl.id), []).append((ap, sv, op, cl))

        n_scontrini = 0
        incasso = 0.0
        for i, giorno in enumerate(sorted({k[0] for k in per_giorno})):
            chiusura = 2200 + i          # numero della chiusura giornaliera
            progressivo = 0
            for (g, _cid), righe in sorted(per_giorno.items()):
                if g != giorno:
                    continue
                progressivo += 1
                metodo = 'contanti' if rng.random() < 0.45 else 'pos'
                voci = []
                totale = 0.0
                for ap, sv, op, cl in righe:
                    voci.append({
                        'servizio_id': str(sv.id),
                        'nome': sv.servizio_nome,
                        'prezzo': sv.servizio_prezzo,
                        'prezzo_originale': sv.servizio_prezzo,
                        'sconto_riga': 0,
                        'tipo': 'service',
                        'metodo_pagamento': metodo,
                        'is_fiscale': True,
                        'operator_id': str(op.id),
                        'appointment_id': str(ap.id),
                        'cliente_id': str(cl.id),
                        'categoria': sv.servizio_categoria.value,
                    })
                    totale += sv.servizio_prezzo
                ultima = righe[-1]
                s.add(Receipt(
                    created_at=datetime.combine(
                        giorno, time(rng.randint(10, 19), rng.randint(0, 59))),
                    total_amount=round(totale, 2), is_fiscale=True, voci=voci,
                    numero_progressivo='%d-%04d' % (chiusura, progressivo),
                    cliente_id=ultima[3].id, operatore_id=ultima[2].id,
                ))
                n_scontrini += 1
                incasso += totale

        s.commit()

        conteggi = {
            'servizi': len(servizi),
            'operatori': len(operatori),
            'clienti': len(clienti),
            'turni': n_turni,
            'appuntamenti': len(appuntamenti),
            'scontrini': n_scontrini,
            'incasso': round(incasso, 2),
            'dal': str(oggi - timedelta(days=GIORNI_PASSATO)),
            'al': str(oggi + timedelta(days=GIORNI_FUTURO)),
        }

    with engine.connect() as conn:
        conteggi['peso_database'] = conn.execute(text(
            "SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
    engine.dispose()
    return conteggi


def main(argv=None):
    ap = argparse.ArgumentParser(description="Semina uno slot demo di Tosca.")
    gruppo = ap.add_mutually_exclusive_group(required=True)
    gruppo.add_argument('--slot', type=int, help="numero dello slot: 1, 2 o 3")
    gruppo.add_argument('--uri', help="URI completa del database demo")
    ap.add_argument('--no-reset', action='store_true',
                    help="non azzerare lo schema prima di seminare")
    ap.add_argument('--password', default='prova2026',
                    help="password dell'utente demo")
    args = ap.parse_args(argv)

    uri = args.uri or uri_dallo_slot(args.slot)
    print("Semina di %s" % _nome_db(uri))
    conteggi = semina(uri, reset=not args.no_reset, password_demo=args.password)
    print("\nSeminato:")
    for k, v in conteggi.items():
        print("  %-15s %s" % (k, v))
    return 0


if __name__ == '__main__':
    sys.exit(main())
