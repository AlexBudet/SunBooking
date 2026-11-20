# appl/services/performance.py
"""Performance del negozio, dei servizi e degli operatori.

Serve al pannello "Performance" dell'INFO BOX in Agenda (static/js/performance.js),
riservato ad admin e owner: il controllo del ruolo sta nella rotta
(/calendar/api/info/performance in routes/calendar.py), qui solo i conti.

Definizioni (le stesse del Report, dove esiste gia' un numero uguale):

- INCASSO = soldi entrati: somma degli scontrini del periodo, fiscali e non
  fiscali, come il Report per admin e owner. Le rettifiche (storni, resi) sono
  scontrini negativi e si sottraggono da sole; l'allineamento DGFE (scontrini
  ADJ-...) entra nel totale, come nel registro, ma in nessun servizio.
- Per SERVIZIO e per OPERATORE l'incasso e' la somma delle VOCI: ogni voce porta
  il suo servizio e l'operatore della riga (operator_id, scritto dalla cassa);
  se la voce non ce l'ha vale l'operatore dello scontrino.
- Le sedute scalate da carta prepagata sono voci a zero: contano come passaggio
  in cassa del servizio ma non come incasso, perche' i soldi sono entrati alla
  vendita (o ricarica) della carta.
- APPUNTAMENTO = una persona in un giorno (stessa regola di _chiave_visita in
  routes/report.py, decisa il 14/11/2026). Blocchi OFF e annullati dal cliente
  non contano mai.
- AGENDA OCCUPATA = minuti prenotati / minuti di turno. Qui, a differenza del
  riquadro Saturazione del Report, i blocchi OFF NON sono minuti prenotati: un
  OFF e' tempo tolto, non lavoro.
"""
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from sqlalchemy.orm import joinedload

from appl import db
from appl.formati import nome_operatore
from appl.models import (Appointment, AppointmentSource, AppointmentStatus, Client,
                         Operator, OperatorShift, Receipt, Service, ServiceCategory)
from appl.services import no_show as no_show_mod

# Oltre tre anni la richiesta diventa pesante (si leggono tutte le voci degli
# scontrini) e il grafico illeggibile: si rifiuta prima di toccare il database.
MAX_GIORNI = 1100

CATEGORIE = (
    ('estetica',  'Estetica'),
    ('solarium',  'Solarium'),
    ('prodotti',  'Prodotti'),
    ('carte',     'Carte prepagate'),
    ('pacchetti', 'Pacchetti (rate)'),
    ('dgfe',      'Allineamento DGFE'),
    ('altro',     'Altre voci'),
)
_NOME_CATEGORIA = dict(CATEGORIE)


# ---------------------------------------------------------------------------
# Voci degli scontrini
# ---------------------------------------------------------------------------
def _voci(raw):
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def _intero(v):
    if v in (None, ''):
        return None
    try:
        return int(str(v).strip())
    except Exception:
        return None


def _importo(voce):
    try:
        if 'prezzo' in voce:
            return float(voce.get('prezzo') or 0)
        return float(voce.get('importo') or 0)
    except Exception:
        return 0.0


def _e_carta(voce):
    nome = (voce.get('nome') or '').strip().lower()
    return bool(voce.get('prepagata_id') or voce.get('ricarica_prepagata_id')
                or nome.startswith('carta prepagata') or nome.startswith('ricarica prepagata'))


def _e_adj(numero_progressivo):
    return bool(numero_progressivo and str(numero_progressivo).startswith('ADJ-'))


def _servizi_per_id(ids):
    if not ids:
        return {}
    righe = (Service.query.options(joinedload(Service.servizio_sottocategoria))
             .filter(Service.id.in_(list(ids))).all())
    out = {}
    for s in righe:
        sub = (s.servizio_sottocategoria.nome or '') if s.servizio_sottocategoria else ''
        # Prodotto = sottocategoria che contiene "prod", la stessa regola del
        # Report (_build_product_maps): niente ipotesi sul nome del servizio.
        if 'prod' in sub.strip().lower():
            cat = 'prodotti'
        elif s.servizio_categoria == ServiceCategory.Solarium:
            cat = 'solarium'
        else:
            cat = 'estetica'
        out[s.id] = {'nome': s.servizio_nome or f'Servizio {s.id}', 'categoria': cat,
                     'sottocategoria': sub, 'eliminato': bool(s.is_deleted)}
    return out


def _cassa(start, end):
    """Incasso del periodo [start, end): totali, per giorno, per categoria,
    per servizio, per operatore e per operatore x servizio."""
    righe = (db.session.query(Receipt.created_at, Receipt.total_amount, Receipt.is_fiscale,
                              Receipt.voci, Receipt.operatore_id, Receipt.numero_progressivo)
             .filter(Receipt.created_at >= start, Receipt.created_at < end)
             .all())

    tot = {'incasso': 0.0, 'fiscale': 0.0, 'non_fiscale': 0.0,
           'scontrini': 0, 'incasso_scontrini': 0.0, 'pagato_con_carta': 0.0}
    per_giorno = defaultdict(float)
    categorie = defaultdict(float)
    # chiave servizio: ('s', id) per i servizi a listino, ('v', categoria) per
    # le voci senza servizio (carte, rate, allineamento, altro)
    servizi = defaultdict(lambda: {'incasso': 0.0, 'quantita': 0, 'carta': 0.0, '_appt': set()})
    operatori = defaultdict(lambda: {'incasso': 0.0, 'carta': 0.0})
    op_servizi = defaultdict(lambda: defaultdict(lambda: {'incasso': 0.0, 'quantita': 0, '_appt': set()}))

    voci_lette = []
    ids_servizi = set()
    for r in righe:
        importo_scontrino = float(r.total_amount or 0)
        tot['incasso'] += importo_scontrino
        if r.is_fiscale:
            tot['fiscale'] += importo_scontrino
        else:
            tot['non_fiscale'] += importo_scontrino
        adj = _e_adj(r.numero_progressivo)
        # Passaggi in cassa e scontrino medio come il Report (report_scontrino_medio):
        # solo scontrini sopra zero, quindi niente sedute scalate dalla carta ne'
        # rettifiche. In piu' qui si tolgono gli allineamenti DGFE, che non sono
        # un cliente passato in cassa.
        if importo_scontrino > 0 and not adj:
            tot['scontrini'] += 1
            tot['incasso_scontrini'] += importo_scontrino
        if r.created_at:
            per_giorno[r.created_at.date().isoformat()] += importo_scontrino
        for v in _voci(r.voci):
            if not isinstance(v, dict):
                continue
            sid = _intero(v.get('servizio_id') or v.get('service_id'))
            if sid:
                ids_servizi.add(sid)
            voci_lette.append((r, adj, v, sid))

    meta = _servizi_per_id(ids_servizi)

    for r, adj, v, sid in voci_lette:
        importo = _importo(v)
        info = meta.get(sid) if sid else None
        if adj:
            cat, chiave = 'dgfe', ('v', 'dgfe')
        elif info:
            cat, chiave = info['categoria'], ('s', sid)
        elif _e_carta(v):
            cat, chiave = 'carte', ('v', 'carte')
        elif v.get('rata_id') or v.get('pacchetto_id'):
            cat, chiave = 'pacchetti', ('v', 'pacchetti')
        else:
            cat, chiave = 'altro', ('v', 'altro')
        categorie[cat] += importo

        # Seduta scalata dalla carta: voce a zero, il valore sta in prezzo_originale.
        carta = 0.0
        if (v.get('metodo_pagamento') == 'prepagata' and not v.get('ricarica_prepagata_id')):
            try:
                carta = float(v.get('prezzo_originale') or 0)
            except Exception:
                carta = 0.0
            tot['pagato_con_carta'] += carta

        # Quantita': una riga di cassa = un servizio. Quando la riga e' spezzata
        # in piu' voci (quota carta + resto, o fiscale + non fiscale) le voci
        # portano lo stesso appointment_id e si contano una volta sola. Le
        # rettifiche (importo negativo) tolgono sempre uno.
        appt = _intero(v.get('appointment_id'))
        op_id = _intero(v.get('operator_id')) or r.operatore_id or 0

        rec = servizi[chiave]
        rec['incasso'] += importo
        rec['carta'] += carta
        rec_op = op_servizi[op_id][chiave]
        rec_op['incasso'] += importo
        if importo < 0:
            rec['quantita'] -= 1
            rec_op['quantita'] -= 1
        elif chiave[0] == 's':
            if appt:
                if appt not in rec['_appt']:
                    rec['_appt'].add(appt)
                    rec['quantita'] += 1
                if appt not in rec_op['_appt']:
                    rec_op['_appt'].add(appt)
                    rec_op['quantita'] += 1
            else:
                rec['quantita'] += 1
                rec_op['quantita'] += 1
        else:
            rec['quantita'] += 1
            rec_op['quantita'] += 1

        if not adj:
            operatori[op_id]['incasso'] += importo
            operatori[op_id]['carta'] += carta

    return {
        'tot': tot,
        'per_giorno': per_giorno,
        'categorie': categorie,
        'servizi': servizi,
        'operatori': operatori,
        'op_servizi': op_servizi,
        'meta_servizi': meta,
    }


# ---------------------------------------------------------------------------
# Agenda
# ---------------------------------------------------------------------------
def _e_off(nome, cognome, servizio):
    return ((nome or '').strip().lower() == 'dummy'
            or (cognome or '').strip().lower() == 'dummy'
            or (servizio or '').strip().lower() == 'dummy'
            or servizio is None)


def _chiave_visita(r):
    """Copia su righe di colonne di _chiave_visita (routes/report.py): una
    persona in un giorno. La persona e' la scheda cliente; sulle schede
    segnaposto delle prenotazioni online e' la sessione di prenotazione."""
    giorno = r.start_time.date()
    if no_show_mod.scheda_segnaposto(r.cliente_nome, r.cliente_cognome):
        return (('sessione', r.booking_session_id) if r.booking_session_id
                else ('appuntamento', r.id), giorno)
    return (('cliente', r.client_id), giorno)


def _agenda(start, end):
    righe = (db.session.query(Appointment.id, Appointment.start_time,
                              Appointment._duration.label('durata'),
                              Appointment.client_id, Appointment.operator_id,
                              Appointment.stato, Appointment.source,
                              Appointment.booking_session_id,
                              Client.cliente_nome, Client.cliente_cognome,
                              Service.servizio_nome)
             .join(Client, Appointment.client_id == Client.id)
             .outerjoin(Service, Appointment.service_id == Service.id)
             .filter(Appointment.start_time >= start,
                     Appointment.start_time < end,
                     Appointment.is_cancelled_by_client.isnot(True))
             .all())

    visite = {}           # chiave -> {'noshow': bool, 'web': bool}
    servizi_agenda = 0
    op = defaultdict(lambda: {'servizi': 0, 'minuti': 0, 'visite': set(), 'noshow': set()})
    for r in righe:
        if not r.start_time or _e_off(r.cliente_nome, r.cliente_cognome, r.servizio_nome):
            continue
        k = _chiave_visita(r)
        v = visite.setdefault(k, {'noshow': False, 'web': False})
        noshow = (r.stato == AppointmentStatus.NON_ARRIVATO)
        if noshow:
            v['noshow'] = True
            op[r.operator_id]['noshow'].add(k)
            continue
        if r.source == AppointmentSource.web:
            v['web'] = True
        servizi_agenda += 1
        op[r.operator_id]['servizi'] += 1
        op[r.operator_id]['minuti'] += int(r.durata or 0)
        op[r.operator_id]['visite'].add(k)

    # Turni: minuti disponibili per operatore (come il riquadro Saturazione).
    turni = defaultdict(int)
    for op_id, t_start, t_end in (
        db.session.query(OperatorShift.operator_id, OperatorShift.shift_start_time,
                         OperatorShift.shift_end_time)
        .filter(OperatorShift.shift_date >= start.date(),
                OperatorShift.shift_date < end.date())
        .all()
    ):
        if not t_start or not t_end:
            continue
        minuti = (datetime.combine(date.today(), t_end)
                  - datetime.combine(date.today(), t_start)).total_seconds() / 60
        if minuti > 0:
            turni[op_id] += int(minuti)

    nuovi = 0
    for nome, cognome in (db.session.query(Client.cliente_nome, Client.cliente_cognome)
                          .filter(Client.created_at >= start, Client.created_at < end,
                                  Client.is_deleted.isnot(True))
                          .all()):
        if not no_show_mod.scheda_segnaposto(nome, cognome):
            nuovi += 1

    persone = {k[0] for k in visite}
    return {
        'visite': len(visite),
        'noshow': sum(1 for v in visite.values() if v['noshow']),
        'online': sum(1 for v in visite.values() if v['web']),
        'clienti': len(persone),
        'nuovi_clienti': nuovi,
        'servizi_agenda': servizi_agenda,
        'op': op,
        'turni': turni,
    }


# ---------------------------------------------------------------------------
# Periodo completo
# ---------------------------------------------------------------------------
def _periodo(dal, al):
    start = datetime.combine(dal, datetime.min.time())
    end = datetime.combine(al + timedelta(days=1), datetime.min.time())
    return {'dal': dal, 'al': al, 'giorni': (al - dal).days + 1,
            'cassa': _cassa(start, end), 'agenda': _agenda(start, end)}


def _r2(x):
    return round(float(x or 0), 2)


def _kpi(p):
    t = p['cassa']['tot']
    a = p['agenda']
    minuti_pren = sum(v['minuti'] for oid, v in a['op'].items() if a['turni'].get(oid))
    minuti_turno = sum(a['turni'].values())
    return {
        'incasso': _r2(t['incasso']),
        'incasso_fiscale': _r2(t['fiscale']),
        'incasso_non_fiscale': _r2(t['non_fiscale']),
        'pagato_con_carta': _r2(t['pagato_con_carta']),
        'scontrini': t['scontrini'],
        'scontrino_medio': _r2(t['incasso_scontrini'] / t['scontrini']) if t['scontrini'] else 0.0,
        'incasso_medio_giorno': _r2(t['incasso'] / p['giorni']) if p['giorni'] else 0.0,
        'visite': a['visite'],
        'noshow': a['noshow'],
        'online': a['online'],
        'clienti': a['clienti'],
        'nuovi_clienti': a['nuovi_clienti'],
        'servizi_agenda': a['servizi_agenda'],
        # Solo operatori con i turni inseriti: senza turno il denominatore non c'e'.
        'ore_prenotate': round(minuti_pren / 60, 1),
        'ore_turno': round(minuti_turno / 60, 1),
        'occupazione': round(minuti_pren / minuti_turno * 100, 1) if minuti_turno else None,
    }


def _serie(p):
    """Incasso giorno per giorno, anche i giorni a zero (chiusure comprese)."""
    out = []
    g = p['dal']
    while g <= p['al']:
        out.append({'data': g.isoformat(), 'incasso': _r2(p['cassa']['per_giorno'].get(g.isoformat(), 0))})
        g += timedelta(days=1)
    return out


def _righe_servizi(p, q=None):
    meta = p['cassa']['meta_servizi']
    out = {}
    for chiave, rec in p['cassa']['servizi'].items():
        if chiave[0] == 's':
            info = meta.get(chiave[1], {})
            out[f's{chiave[1]}'] = {
                'chiave': f's{chiave[1]}', 'id': chiave[1],
                'nome': info.get('nome') or f'Servizio {chiave[1]}',
                'categoria': info.get('categoria', 'estetica'),
                'eliminato': info.get('eliminato', False),
                'incasso': _r2(rec['incasso']), 'quantita': rec['quantita'],
                'pagato_con_carta': _r2(rec['carta']),
            }
        else:
            out[f'v{chiave[1]}'] = {
                'chiave': f'v{chiave[1]}', 'id': None,
                'nome': _NOME_CATEGORIA.get(chiave[1], 'Altre voci'),
                'categoria': chiave[1], 'eliminato': False, 'voce_cassa': True,
                'incasso': _r2(rec['incasso']), 'quantita': rec['quantita'],
                'pagato_con_carta': _r2(rec['carta']),
            }
    return out


def _righe_operatori(p):
    cassa, agenda = p['cassa'], p['agenda']
    ids = set(cassa['operatori']) | set(agenda['op']) | set(agenda['turni'])
    out = {}
    for oid in ids:
        c = cassa['operatori'].get(oid, {'incasso': 0.0, 'carta': 0.0})
        a = agenda['op'].get(oid)
        minuti = a['minuti'] if a else 0
        turno = agenda['turni'].get(oid, 0)
        top = []
        for chiave, rec in cassa['op_servizi'].get(oid, {}).items():
            if chiave[0] == 's':
                nome = cassa['meta_servizi'].get(chiave[1], {}).get('nome') or f'Servizio {chiave[1]}'
            else:
                nome = _NOME_CATEGORIA.get(chiave[1], 'Altre voci')
            top.append({'nome': nome, 'incasso': _r2(rec['incasso']), 'quantita': rec['quantita']})
        top.sort(key=lambda x: -x['incasso'])
        out[str(oid)] = {
            'id': oid or None,
            'incasso': _r2(c['incasso']),
            'pagato_con_carta': _r2(c['carta']),
            'servizi': a['servizi'] if a else 0,
            'visite': len(a['visite']) if a else 0,
            'noshow': len(a['noshow']) if a else 0,
            'ore_prenotate': round(minuti / 60, 1),
            'ore_turno': round(turno / 60, 1),
            'occupazione': round(minuti / turno * 100, 1) if turno else None,
            'incasso_ora': _r2(c['incasso'] / (minuti / 60)) if minuti else None,
            'top_servizi': top[:6],
        }
    return out


def _anagrafica_operatori(chiavi):
    ids = [int(k) for k in chiavi if k not in ('0', 'None')]
    ops = {o.id: o for o in Operator.query.filter(Operator.id.in_(ids)).all()} if ids else {}
    out = {}
    for k in chiavi:
        o = ops.get(int(k)) if k not in ('0', 'None') else None
        if o is None:
            out[k] = {'nome': 'Senza operatore', 'tipo': '', 'eliminato': False, 'ordine': 10 ** 6}
        else:
            out[k] = {'nome': nome_operatore(o) or f'Operatore {o.id}', 'tipo': o.user_tipo or '',
                      'eliminato': bool(o.is_deleted), 'ordine': o.order or 0}
    return out


def calcola(dal, al, cmp_dal=None, cmp_al=None):
    """Tutto il pannello in una risposta: KPI, serie giornaliere, categorie,
    servizi e operatori del periodo e (se chiesto) del periodo di confronto."""
    att = _periodo(dal, al)
    cmp_ = _periodo(cmp_dal, cmp_al) if (cmp_dal and cmp_al) else None

    # Categorie: sempre tutte nello stesso ordine, cosi' il grafico non si
    # rimescola tra un periodo e l'altro; quelle a zero in entrambi spariscono.
    categorie = []
    for chiave, nome in CATEGORIE:
        v = _r2(att['cassa']['categorie'].get(chiave, 0))
        vc = _r2(cmp_['cassa']['categorie'].get(chiave, 0)) if cmp_ else None
        if v == 0 and not vc:
            continue
        categorie.append({'chiave': chiave, 'nome': nome, 'incasso': v, 'incasso_cmp': vc})

    serv = _righe_servizi(att)
    serv_cmp = _righe_servizi(cmp_) if cmp_ else {}
    servizi = []
    for k in set(serv) | set(serv_cmp):
        base = serv.get(k) or dict(serv_cmp[k], incasso=0.0, quantita=0, pagato_con_carta=0.0)
        c = serv_cmp.get(k)
        riga = dict(base)
        riga['incasso_cmp'] = c['incasso'] if c else (0.0 if cmp_ else None)
        riga['quantita_cmp'] = c['quantita'] if c else (0 if cmp_ else None)
        servizi.append(riga)
    servizi.sort(key=lambda r: (-r['incasso'], r['nome'].lower()))

    ops = _righe_operatori(att)
    ops_cmp = _righe_operatori(cmp_) if cmp_ else {}
    chiavi = set(ops) | set(ops_cmp)
    anag = _anagrafica_operatori(chiavi)
    vuoto = {'incasso': 0.0, 'pagato_con_carta': 0.0, 'servizi': 0, 'visite': 0, 'noshow': 0,
             'ore_prenotate': 0.0, 'ore_turno': 0.0, 'occupazione': None, 'incasso_ora': None,
             'top_servizi': []}
    operatori = []
    for k in chiavi:
        r = dict(ops.get(k) or vuoto)
        c = ops_cmp.get(k)
        # Un operatore senza nulla nel periodo attuale e senza incasso nel
        # confronto (solo turni vuoti) non aggiunge informazione.
        if not r['incasso'] and not r['servizi'] and not (c and (c['incasso'] or c['servizi'])):
            continue
        r.update(anag[k])
        r['id'] = int(k) if k not in ('0', 'None') else None
        r['incasso_cmp'] = c['incasso'] if c else (0.0 if cmp_ else None)
        r['servizi_cmp'] = c['servizi'] if c else (0 if cmp_ else None)
        r['occupazione_cmp'] = c['occupazione'] if c else None
        r['incasso_ora_cmp'] = c['incasso_ora'] if c else None
        operatori.append(r)
    operatori.sort(key=lambda r: (-r['incasso'], r['ordine'], r['nome'].lower()))

    def _intestazione(p):
        return {'dal': p['dal'].isoformat(), 'al': p['al'].isoformat(), 'giorni': p['giorni']}

    return {
        'periodo': _intestazione(att),
        'confronto': _intestazione(cmp_) if cmp_ else None,
        'kpi': _kpi(att),
        'kpi_cmp': _kpi(cmp_) if cmp_ else None,
        'serie': _serie(att),
        'serie_cmp': _serie(cmp_) if cmp_ else None,
        'categorie': categorie,
        'servizi': servizi,
        'operatori': operatori,
        'generato_il': datetime.now().strftime('%H:%M'),
    }
