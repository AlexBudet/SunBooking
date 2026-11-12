"""
RISORSE: postazioni, cabine, macchinari condivisi fra piu' servizi.

Una risorsa ha una QUANTITA' (quante ce ne sono in negozio: "Postazione Mani" 4)
e si associa ai servizi, ognuno col SUO tetto ("Manicure" 2, "Semipermanente
mani" 3). Ogni appuntamento di un servizio associato occupa UNA unita' della
risorsa per tutta la sua durata. Valgono sempre DUE regole insieme:
  - totale:   gli appuntamenti contemporanei di TUTTI i servizi che usano la
              risorsa non superano la quantita' della risorsa;
  - servizio: quelli dello STESSO servizio non superano il tetto del servizio.
Esempio (4 postazioni, manicure 2, semipermanente 3): 3 semi + 1 manicure =
pieno, blocca entrambi; 2 + 2 = pieno, blocca entrambi; una terza manicure con
una sola semi in corso e' fermata dal tetto del servizio anche se le
postazioni non sono finite.

Un servizio puo' usare piu' risorse (es. Pressoterapia = Cabina + Macchinario):
deve esserci posto in TUTTE.

Servizi senza risorse associate: nessun vincolo, tutto come prima. Se le
tabelle non esistono ancora (deploy fatto prima dello script SQL) la funzione
e' spenta, non rompe niente.

Chi applica le regole:
  - Agenda: avviso con "Procedi comunque" (calendar.py /api/check-risorse);
  - "Trova un buco": non propone orari pieni;
  - prenotazione online (repo booking, routes/risorse.py): lo slot non si vede
    e /prenota rifiuta chi arriva secondo.
La logica di conflitti() e' COPIATA nel repo booking: se cambi la regola qui,
cambiala anche li'.

Appuntamenti che occupano una risorsa: quelli del giorno non annullati dal
cliente, con un servizio, esclusi i "non arrivato" (la postazione era libera).
Tabelle: risorse, servizio_risorse (migrations/manual_risorse.sql).
"""
from datetime import datetime, timedelta, time as dtime

from sqlalchemy import inspect as sa_inspect, text


def carica_config(session):
    """Configurazione delle risorse, letta sulla connessione della sessione:
    {'risorse': {id: (nome, quantita)}, 'per_servizio': {service_id: [(risorsa_id, tetto)]}}
    oppure None se non c'e' nessuna associazione (o le tabelle non esistono
    ancora): in quel caso nessun vincolo, tutto come prima.
    Va chiamata PRIMA di qualsiasi scrittura della richiesta: su un errore
    inatteso fa rollback della sessione."""
    try:
        conn = session.connection()
        ispettore = sa_inspect(conn)
        if not (ispettore.has_table('servizio_risorse') and ispettore.has_table('risorse')):
            return None
        righe = conn.execute(text(
            "SELECT sr.service_id, sr.risorsa_id, sr.quantita, r.nome, r.quantita "
            "FROM servizio_risorse sr JOIN risorse r ON r.id = sr.risorsa_id "
            "WHERE r.is_deleted = false"
        )).fetchall()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass
        return None
    if not righe:
        return None
    risorse = {}
    per_servizio = {}
    for service_id, risorsa_id, tetto, nome, quantita in righe:
        risorse[int(risorsa_id)] = (nome or '', max(1, int(quantita or 1)))
        per_servizio.setdefault(int(service_id), []).append((int(risorsa_id), max(1, int(tetto or 1))))
    return {'risorse': risorse, 'per_servizio': per_servizio}


def _picco(intervalli, inizio, fine):
    """Massimo numero di intervalli sovrapposti in uno stesso istante dentro
    [inizio, fine). Un appuntamento che finisce alle 11:00 e uno che comincia
    alle 11:00 NON si sovrappongono."""
    eventi = []
    for a, b in intervalli:
        a2, b2 = max(a, inizio), min(b, fine)
        if a2 < b2:
            eventi.append((a2, 1))
            eventi.append((b2, -1))
    eventi.sort(key=lambda e: (e[0], e[1]))   # a parita' di istante prima chi finisce
    corrente = picco = 0
    for _, delta in eventi:
        corrente += delta
        if corrente > picco:
            picco = corrente
    return picco


def conflitti(config, blocchi, occupati):
    """Blocchi che non ci stanno.

    blocchi:  [{'service_id', 'inizio', 'fine'}] da piazzare (datetime naive);
              piu' blocchi della stessa richiesta contano anche fra loro.
    occupati: [{'id', 'service_id', 'inizio', 'fine'}] gia' in agenda, SENZA
              quelli che si stanno spostando.
    Ritorna [{'indice', 'service_id', 'risorsa_id', 'risorsa', 'tipo',
              'limite', 'occupanti'}]:
      tipo 'totale'   -> la risorsa e' tutta occupata (limite = sua quantita')
      tipo 'servizio' -> il servizio ha raggiunto il suo tetto (limite = tetto)
      occupanti = gli 'occupati' che si sovrappongono e usano la risorsa (per
      'totale') o sono dello stesso servizio (per 'servizio').
    Una sola voce per blocco e risorsa: se la risorsa e' piena non serve dire
    anche che lo e' il servizio."""
    if not config:
        return []
    per_servizio = config['per_servizio']
    risorse = config['risorse']
    servizi_di = {}
    for sid, lista in per_servizio.items():
        for rid, _ in lista:
            servizi_di.setdefault(rid, set()).add(sid)

    trovati = []
    for i, b in enumerate(blocchi):
        sid = b.get('service_id')
        inizio, fine = b['inizio'], b['fine']
        if not sid or not (inizio < fine):
            continue
        for rid, tetto in per_servizio.get(sid, []):
            nome, quantita = risorse[rid]
            usa = servizi_di.get(rid, set())

            occ_r = [o for o in occupati if o['service_id'] in usa
                     and o['inizio'] < fine and o['fine'] > inizio]
            altri_r = [(x['inizio'], x['fine']) for j, x in enumerate(blocchi)
                       if j != i and x.get('service_id') in usa]
            intervalli = [(o['inizio'], o['fine']) for o in occ_r] + altri_r + [(inizio, fine)]
            if _picco(intervalli, inizio, fine) > quantita:
                trovati.append({'indice': i, 'service_id': sid, 'risorsa_id': rid,
                                'risorsa': nome, 'tipo': 'totale', 'limite': quantita,
                                'occupanti': occ_r})
                continue

            limite_servizio = min(tetto, quantita)
            occ_s = [o for o in occ_r if o['service_id'] == sid]
            altri_s = [(x['inizio'], x['fine']) for j, x in enumerate(blocchi)
                       if j != i and x.get('service_id') == sid]
            intervalli = [(o['inizio'], o['fine']) for o in occ_s] + altri_s + [(inizio, fine)]
            if _picco(intervalli, inizio, fine) > limite_servizio:
                trovati.append({'indice': i, 'service_id': sid, 'risorsa_id': rid,
                                'risorsa': nome, 'tipo': 'servizio', 'limite': limite_servizio,
                                'occupanti': occ_s})
    return trovati


def _naive(dt):
    if dt is not None and getattr(dt, 'tzinfo', None) is not None:
        return dt.replace(tzinfo=None)
    return dt


def occupati_del_giorno(appuntamenti, ignora_ids=()):
    """Dagli appuntamenti di un giorno, quelli che occupano risorse, nel formato
    di conflitti(). Esclusi annullati, senza servizio, "non arrivato" e quelli
    che si stanno spostando (ignora_ids). Ogni voce porta anche 'appt'."""
    ignora = {str(x) for x in (ignora_ids or ()) if x}
    out = []
    for a in appuntamenti:
        if getattr(a, 'is_cancelled_by_client', False) or not a.service_id:
            continue
        if str(a.id) in ignora:
            continue
        stato = getattr(a, 'stato', None)
        if getattr(stato, 'name', stato) == 'NON_ARRIVATO':
            continue
        inizio = _naive(a.start_time)
        durata = int(getattr(a, '_duration', None) or getattr(a, 'duration', 0) or 0)
        if durata <= 0:
            continue
        out.append({'id': a.id, 'service_id': a.service_id, 'inizio': inizio,
                    'fine': inizio + timedelta(minutes=durata), 'appt': a})
    return out


def blocchi_consecutivi(giorno, ora_inizio, servizi_durate):
    """[(service_id, durata)] uno dopo l'altro da `ora_inizio` (time o 'HH:MM')
    nel formato di conflitti()."""
    if isinstance(ora_inizio, str):
        ora_inizio = datetime.strptime(ora_inizio.strip(), '%H:%M').time()
    cur = datetime.combine(giorno, ora_inizio)
    out = []
    for sid, durata in servizi_durate:
        fine = cur + timedelta(minutes=int(durata or 0))
        out.append({'service_id': sid, 'inizio': cur, 'fine': fine})
        cur = fine
    return out


def inizio_giorno(giorno):
    return datetime.combine(giorno, dtime.min)
