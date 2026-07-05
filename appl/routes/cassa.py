from decimal import Decimal
import json
import os
import tempfile
import html, re, time as pytime
from flask import Blueprint, app, render_template, jsonify, request, session, abort, current_app
from appl.models import Appointment, AppointmentStatus, BusinessInfo, Operator, PrinterModel, Service, ServiceCategory, Client, Receipt, Subcategory, User, Pacchetto, PacchettoRata, PacchettoStatus, db
from appl.services.error_log import log_crm_error
from datetime import datetime, date, timedelta
import requests
import urllib3
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import selectinload
from collections import defaultdict
from sqlalchemy.orm.attributes import flag_modified

# Disabilita warning SSL per certificati self-signed RCH Print 3.0 RT
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def _rch_url(ip: str, model: str = None) -> str:
    """Costruisce URL per la stampante RCH in base al modello.
    - RCH Print 3.0 RT: HTTPS + /service.cgi
    - RCH Print F: HTTP + /service.cgi
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return f"http://{ip}/service.cgi"
    return f"https://{ip}/service.cgi"

def _rch_headers(model: str = None) -> dict:
    """Header HTTP per la stampante RCH in base al modello.
    - RCH Print 3.0 RT: application/xml + Accept obbligatorio (da specifica)
    - RCH Print F: text/xml; charset=UTF-8
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {"Content-Type": "text/xml; charset=UTF-8"}
    return {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache"
    }

def _rch_verify_ssl(model: str = None):
    """Parametro verify per requests.
    - RCH Print 3.0 RT: False (HTTPS self-signed, disabilita verifica)
    - RCH Print F: None (HTTP, parametro non necessario)
    Ritorna False per RT, None per Print F.
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return None
    return False

def _rch_chiusura_headers(model: str = None) -> dict:
    """Header speciali per la chiusura giornaliera.
    - RCH Print F: application/x-www-form-urlencoded (storicamente funzionante)
    - RCH Print 3.0 RT: application/xml (come per gli altri comandi)
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {"Content-Type": "application/x-www-form-urlencoded"}
    return {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "Connection": "keep-alive",
        "Cache-Control": "no-cache"
    }

def _rch_dgfe_headers(model: str = None) -> dict:
    """Header per lettura DGFE.
    - RCH Print F: text/xml; charset=iso-8859-1
    - RCH Print 3.0 RT: application/xml
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {'Content-Type': 'text/xml; charset=iso-8859-1'}
    return {
        "Content-Type": "application/xml",
        "Accept": "application/xml",
        "Connection": "close",
        "Cache-Control": "no-cache"
    }

def _rch_request_kwargs(model: str = None) -> dict:
    """Keyword arguments extra per requests.post() in base al modello.
    - RCH Print 3.0 RT: verify=False (HTTPS self-signed)
    - RCH Print F: niente (HTTP puro, nessun verify necessario)
    """
    model = _normalize_model(model)
    if model == PrinterModel.RCH_PRINT_F.value:
        return {}
    return {"verify": False}

def _normalize_model(model_raw) -> str:
    """Normalizza il valore printer_model a stringa canonica."""
    if model_raw is None:
        return PrinterModel.RCH_PRINT_RT.value
    if hasattr(model_raw, 'value'):
        model_raw = model_raw.value
    s = str(model_raw).strip().lower()
    if s in ('rch_print_f', 'printermodel.rch_print_f', 'print_f', 'print f'):
        return PrinterModel.RCH_PRINT_F.value
    return PrinterModel.RCH_PRINT_RT.value

def _tender_code(metodo, model=None) -> str:
    """Mappa il metodo di pagamento del CRM al comando di pagamento RCH (=T<n>).

    La tabella delle forme di pagamento differisce per modello:
    - RCH Print 3.0 RT (tabella standard di fabbrica, vedi manuale sez. 9):
        T1 contanti, T2 non riscosso, T3 assegni, T4 elettronico, T5 ticket
      => carta/POS e bonifico sono entrambi 'elettronico' (T4).
    - RCH Print F: tabella storica programmata con T2=bonifico, T3=POS.

    NB: 'bank'->T2 sulla RT 3.0 colpisce 'non riscosso' e genera errorCode 45;
    'pos'->T3 colpisce 'assegni' (non da' errore ma e' fiscalmente errato).
    """
    model = _normalize_model(model)
    metodo = (metodo or "cash").lower()
    if model == PrinterModel.RCH_PRINT_F.value:
        return {"cash": "T1", "contanti": "T1", "bank": "T2", "pos": "T3"}.get(metodo, "T1")
    # RCH Print 3.0 RT: carta/POS e bonifico sono entrambi 'elettronico' (T4)
    return {"cash": "T1", "contanti": "T1", "bank": "T4", "pos": "T4"}.get(metodo, "T1")

def _get_printer_config():
    """Ritorna (ip, model) dalla BusinessInfo corrente.
    Usa expire_all + query fresca per garantire lettura dal DB reale,
    mai dalla identity map cached di SQLAlchemy.
    """
    db.session.expire_all()
    row = db.session.execute(
        text("SELECT id, printer_ip, printer_model FROM business_info WHERE is_deleted = false ORDER BY id ASC LIMIT 1")
    ).fetchone()
    if not row:
        return None, None
    ip = (row[1] or '').strip()
    if not ip:
        return None, None
    model = _normalize_model(row[2])
    current_app.logger.debug(
        "_get_printer_config: id=%s, ip=%s, raw_model=%r, model=%s",
        row[0], ip, row[2], model
    )
    return ip, model

def _rch_parse_errcode(body: str):
    """Estrae codice errore dalla risposta RCH.
    Supporta sia <errCode> (da specifica) che <errorCode> (variante firmware).
    """
    if not body:
        return None
    m = re.search(r'<(?:errCode|errorCode)>(\d+)</(?:errCode|errorCode)>', body)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None

def _rch_is_success(resp):
    """Verifica se la risposta RCH indica successo (errCode/errorCode == 0)."""
    if resp is None:
        return False
    body = getattr(resp, 'text', '') or ''
    code = _rch_parse_errcode(body)
    if code is not None:
        return code == 0
    # Nessun codice trovato: HTTP 200 = OK presumibile
    return getattr(resp, 'status_code', 0) == 200

def _read_progressivo(url, headers, rch_kwargs, max_attempts=8, sleep_s=0.5):
    """Polla =C453/$0 (e fallback =DGFE/REG) per leggere lastDocF/lastZ.
    Ritorna (numero_progressivo, numero_z) oppure (None, None) se non leggibile.
    numero_z e' gia' incrementato di 1 (come fa il flusso esistente)."""
    for cmd in ("=C453/$0", "=DGFE/REG"):
        payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
        for _ in range(max_attempts):
            pytime.sleep(sleep_s)
            try:
                resp = requests.post(url, data=payload.encode('utf-8'), headers=headers,
                                     timeout=6, **rch_kwargs)
            except Exception:
                continue
            body = resp.text or ""
            m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', body) or
                     re.search(r'<C453[^>]*>(\d+)</C453>', body) or
                     re.search(r'<result>(\d+)</result>', body))
            m_z = re.search(r'<lastZ>(\d+)</lastZ>', body)
            if m_doc and m_z:
                try:
                    return int(m_doc.group(1)), int(m_z.group(1)) + 1
                except Exception:
                    pass
    return None, None

def clean_str(s):
    # Rimuove apostrofi e caratteri HTML problematici
    return str(s).replace("'", "").replace('"', "").replace("&", "").replace(";", "").replace("<", "").replace(">", "")

cassa_bp = Blueprint('cassa', __name__)

@cassa_bp.route('/cassa')
def cassa():
    current_app.logger.debug("GET args in cassa: %s", request.args)
    client_id = request.args.get('client_id')
    operator_id = request.args.get('operator_id')
    client_name = request.args.get('client_name')
    operator_name = request.args.get('operator_name')
    servizi_json = request.args.get('servizi')
    appointments_json = request.args.get('appointments')
    rata_id = request.args.get('rata_id')
    pacchetto_id_param = request.args.get('pacchetto_id')
    prepagata_id = request.args.get('prepagata_id')  # Pagamento carta prepagata
    ricarica_prepagata_id = request.args.get('ricarica_prepagata_id')  # Ricarica carta prepagata
    ricarica_importo = request.args.get('importo')  # Importo da pagare
    ricarica_credito = request.args.get('credito')  # Credito effettivo da caricare (può essere > importo con bonus)
    ricarica_descrizione = request.args.get('descrizione', 'Ricarica')
    servizi = []

    # Se prepagata_id presente, carica la carta prepagata da pagare
    if prepagata_id:
        try:
            pacchetto = Pacchetto.query.get(int(prepagata_id))
            if pacchetto and pacchetto.tipo.value == 'prepagata' and pacchetto.status == PacchettoStatus.Preventivo:
                # Cliente
                if pacchetto.client:
                    client_id = pacchetto.client_id
                    client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                
                # Usa costo_totale_lordo (importo da pagare), non credito_iniziale (credito caricato)
                importo_da_pagare = float(pacchetto.costo_totale_lordo) if pacchetto.costo_totale_lordo else float(pacchetto.credito_iniziale)
                
                servizi = [{
                    'id': None,
                    'nome': clean_str(f"Carta Prepagata - {pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"),
                    'prezzo': importo_da_pagare,
                    'categoria': 'Estetica',
                    'is_fiscale': False,
                    'is_non_fiscale': True,
                    'metodo_pagamento': 'contanti',
                    'prepagata_id': pacchetto.id,
                    'credito_da_caricare': float(pacchetto.credito_iniziale)
                }]
        except Exception as e:
            current_app.logger.error(f"Errore caricamento prepagata {prepagata_id}: {e}")

    # Se ricarica_prepagata_id presente, carica la ricarica da pagare
    if ricarica_prepagata_id and ricarica_importo:
        try:
            pacchetto = Pacchetto.query.get(int(ricarica_prepagata_id))
            if pacchetto and pacchetto.tipo.value == 'prepagata':
                importo = float(ricarica_importo)
                
                # Cliente
                if pacchetto.client:
                    client_id = pacchetto.client_id
                    client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                
                # Credito da caricare: se specificato usa quello, altrimenti usa l'importo pagato
                credito_da_caricare = float(ricarica_credito) if ricarica_credito else importo
                
                servizi = [{
                    'id': None,
                    'nome': clean_str(f"Ricarica Prepagata - {ricarica_descrizione}"),
                    'prezzo': importo,  # Importo da pagare in cassa
                    'categoria': 'Estetica',
                    'is_fiscale': True,
                    'metodo_pagamento': 'contanti',
                    'ricarica_prepagata_id': pacchetto.id,
                    'ricarica_importo': importo,
                    'ricarica_credito': credito_da_caricare,  # Credito effettivo da caricare
                    'ricarica_descrizione': ricarica_descrizione
                }]
        except Exception as e:
            current_app.logger.error(f"Errore caricamento ricarica prepagata {ricarica_prepagata_id}: {e}")

    # Se pacchetto_id presente (pagamento pacchetto intero), carica tutte le rate non pagate
    if pacchetto_id_param:
        try:
            pacchetto = Pacchetto.query.get(int(pacchetto_id_param))
            if pacchetto and pacchetto.status == PacchettoStatus.Preventivo:
                # Cliente
                if pacchetto.client:
                    client_id = pacchetto.client_id
                    client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                
                # Operatore preferito (primo se presente)
                if pacchetto.preferred_operators:
                    first_op = pacchetto.preferred_operators[0]
                    operator_id = first_op.id
                    operator_name = first_op.user_nome
                
                # Determina categoria dal primo servizio del pacchetto
                categoria = "Estetica"  # default
                if pacchetto.sedute:
                    first_seduta = pacchetto.sedute[0] if pacchetto.sedute else None
                    if first_seduta and first_seduta.service:
                        categoria = first_seduta.service.servizio_categoria.value
                
                # Carica tutte le rate non pagate come righe separate
                rate_non_pagate = PacchettoRata.query.filter_by(
                    pacchetto_id=pacchetto.id, 
                    is_pagata=False
                ).order_by(PacchettoRata.id).all()
                
                rate_ordinate = PacchettoRata.query.filter_by(pacchetto_id=pacchetto.id).order_by(PacchettoRata.id).all()
                
                for rata in rate_non_pagate:
                    numero_rata = next((i+1 for i, r in enumerate(rate_ordinate) if r.id == rata.id), 1)
                    servizi.append({
                        'id': None,
                        'nome': clean_str(f"Rata {numero_rata} - {pacchetto.nome}"),
                        'prezzo': float(rata.importo),
                        'categoria': clean_str(categoria),
                        'is_fiscale': True,
                        'metodo_pagamento': 'contanti',
                        'rata_id': rata.id,
                        'pacchetto_id': pacchetto.id
                    })
        except Exception as e:
            current_app.logger.error(f"Errore caricamento pacchetto {pacchetto_id_param}: {e}")
    
    # Se rata_id presente, carica dati dalla rata del pacchetto
    elif rata_id:
        try:
            rata = PacchettoRata.query.get(int(rata_id))
            if rata and not rata.is_pagata:
                pacchetto = Pacchetto.query.get(rata.pacchetto_id)
                if pacchetto:
                    # Determina numero rata
                    rate_ordinate = PacchettoRata.query.filter_by(pacchetto_id=pacchetto.id).order_by(PacchettoRata.id).all()
                    numero_rata = next((i+1 for i, r in enumerate(rate_ordinate) if r.id == rata.id), 1)
                    
                    # Cliente
                    if pacchetto.client:
                        client_id = pacchetto.client_id
                        client_name = f"{pacchetto.client.cliente_nome} {pacchetto.client.cliente_cognome}"
                    
                    # Operatore preferito (primo se presente)
                    if pacchetto.preferred_operators:
                        first_op = pacchetto.preferred_operators[0]
                        operator_id = first_op.id
                        operator_name = first_op.user_nome
                    
                    # Determina categoria dal primo servizio del pacchetto
                    categoria = "Estetica"  # default
                    if pacchetto.sedute:
                        first_seduta = pacchetto.sedute[0] if pacchetto.sedute else None
                        if first_seduta and first_seduta.service:
                            categoria = first_seduta.service.servizio_categoria.value
                    
                    servizi = [{
                        'id': None,  # Nessun service_id reale
                        'nome': clean_str(f"Rata {numero_rata} - {pacchetto.nome}"),
                        'prezzo': float(rata.importo),
                        'categoria': clean_str(categoria),
                        'is_fiscale': True,
                        'metodo_pagamento': 'contanti',
                        'rata_id': rata.id,  # IMPORTANTE: per marcare come pagata dopo
                        'pacchetto_id': pacchetto.id
                    }]
        except Exception as e:
            current_app.logger.error(f"Errore caricamento rata {rata_id}: {e}")

    if servizi_json:
        try:
            servizi_raw = json.loads(servizi_json)
            # Assicurati che ogni servizio abbia operator_id e operator_nome
            servizi = []
            for s in servizi_raw:
                # Recupera operator_id e operator_nome
                op_id = s.get("operator_id")
                op_nome = s.get("operator_nome", "")
                
                # Se operator_id è null/vuoto/stringa "null", recuperalo dall'appointment
                appt_id = s.get("appointment_id")
                if (not op_id or op_id == '' or op_id == 'null' or str(op_id).lower() == 'none') and appt_id:
                    try:
                        appt = db.session.get(Appointment, int(appt_id))
                        if appt and appt.operator_id:
                            op_id = appt.operator_id
                            op = db.session.get(Operator, appt.operator_id)
                            if op:
                                op_nome = op.user_nome or ''
                    except Exception:
                        pass
                
                srv = {
                    "id": s.get("id"),
                    "nome": clean_str(s.get("nome", "")),
                    "prezzo": s.get("prezzo", 0),
                    "tag": clean_str(s.get("tag", "")),
                    "sottocategoria": clean_str(s.get("sottocategoria", "")),
                    "appointment_id": appt_id,
                    "operator_id": op_id,
                    "operator_nome": op_nome
                }
                servizi.append(srv)
        except Exception as e:
            current_app.logger.error(f"Errore parsing servizi_json: {e}")
            servizi = []

    if appointments_json:
        try:
            appointments_ids = json.loads(appointments_json)
            appointments = Appointment.query.filter(
                Appointment.id.in_(appointments_ids),
                Appointment.is_cancelled_by_client == False
            ).all()
            for appt in appointments:
                appt_op = appt.operator
                servizi.append({
                    "id": appt.service.id,
                    "nome": clean_str(appt.service.servizio_nome),
                    "prezzo": appt.service.servizio_prezzo,
                    "tag": clean_str(appt.service.servizio_tag),
                    "sottocategoria": clean_str(appt.service.servizio_sottocategoria.nome) if appt.service.servizio_sottocategoria else "",
                    "appointment_id": appt.id,
                    "operator_id": appt_op.id if appt_op else None,
                    "operator_nome": appt_op.user_nome if appt_op else ""
                })
        except Exception as e:
            servizi = []
    
    try:
        if client_id:
            cid = int(client_id)
            cli = db.session.get(Client, cid)
            if cli:
                client_name = f"{cli.cliente_nome or ''} {cli.cliente_cognome or ''}".strip()
        elif client_name:
            client_name = html.unescape(client_name)
    except Exception:
        if client_name:
            client_name = html.unescape(client_name)

    # Se operator_name non è passato ma operator_id sì, recupera nome e cognome dal DB
    if not operator_name and operator_id:
        op = db.session.get(Operator, operator_id)
        if op:
            operator_name = f"{op.user_nome} {op.user_cognome}"

    giorno = date.today()
    businessinfo = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()

    # Aggiungi ruolo utente per mostrare/nascondere console RCH
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    user_role = user.ruolo.value if user else None

    return render_template(
        'cassa.html',
        client_id=client_id,
        operator_id=operator_id,
        client_name=client_name,
        operator_name=operator_name,
        servizi=servizi,
        giorno=giorno,
        businessinfo=businessinfo,
        user_role=user_role
    )

@cassa_bp.route('/cassa/api/operators')
def api_operators():
    # Restituisce la lista operatori attivi ordinati per il campo 'order'
    operators = Operator.query.filter_by(is_visible=True, is_deleted=False).order_by(Operator.order.asc()).all()
    return jsonify([
        {"id": op.id, "nome": op.user_nome, "cognome": op.user_cognome}
        for op in operators
    ])

@cassa_bp.route('/cassa/api/services')
def api_services():
    try:
        id = request.args.get('id')
        q = request.args.get('q', '').strip()
        ultimi = request.args.get('ultimi')
        frequenti = request.args.get('frequenti')
        categoria = request.args.get('categoria')
        sottocategoria = request.args.get('sottocategoria')

        # helper: estrae id servizio supportando vari nomi/format
        def extract_sid(v):
            if not isinstance(v, dict):
                return None
            for key in ('servizio_id', 'service_id', 'id', 'servizioId', 'servizioID'):
                if key in v and v[key] not in (None, ''):
                    try:
                        return int(v[key])
                    except Exception:
                        try:
                            return int(str(v[key]).strip())
                        except Exception:
                            return None
            return None

        # base query (sempre applicata se non viene sovrascritta)
        base_query = Service.query.filter(Service.is_deleted == False)

        services = []
        # caso: ricerca per id o testo
        if id:
            query = base_query.filter(Service.id == id)
            services = query.limit(28).all()
        elif q and len(q) >= 3:
            query = base_query.filter(Service.servizio_nome.ilike(f"%{q}%"))
            services = query.limit(28).all()
        elif ultimi:
            # ULTIMI: prendi receipt recenti, estrai servizi unici nell'ordine di apparizione
            recent_receipts = Receipt.query.order_by(Receipt.created_at.desc()).limit(200).all()
            seen = set()
            ordered_ids = []
            for r in recent_receipts:
                voci = r.voci if isinstance(r.voci, list) else (json.loads(r.voci or '[]') if r.voci else [])
                for v in voci:
                    sid = extract_sid(v)
                    if sid and sid not in seen:
                        seen.add(sid)
                        ordered_ids.append(sid)
                        if len(ordered_ids) >= 28:
                            break
                if len(ordered_ids) >= 28:
                    break
            if ordered_ids:
                db_services = Service.query.filter(Service.id.in_(ordered_ids), Service.is_deleted == False).all()
                svc_map = {s.id: s for s in db_services}
                services = [svc_map[sid] for sid in ordered_ids if sid in svc_map]
            else:
                services = []
        elif frequenti:
            # FREQUENTI: conta occorrenze nei receipt e ordina per frequenza
            from collections import Counter
            all_receipts = Receipt.query.all()
            cnt = Counter()
            for r in all_receipts:
                voci = r.voci if isinstance(r.voci, list) else (json.loads(r.voci or '[]') if r.voci else [])
                for v in voci:
                    sid = extract_sid(v)
                    if sid:
                        cnt[sid] += 1
            top = [sid for sid, _ in cnt.most_common(28)]
            if top:
                db_services = Service.query.filter(Service.id.in_(top), Service.is_deleted == False).all()
                svc_map = {s.id: s for s in db_services}
                # preserva l'ordine dei top
                services = [svc_map[sid] for sid in top if sid in svc_map]
            else:
                services = []
        elif sottocategoria:
            query = base_query.join(Service.servizio_sottocategoria).filter(Subcategory.nome == sottocategoria)
            services = query.limit(28).all()
        elif categoria:
            query = base_query.filter(Service.servizio_categoria == categoria)
            services = query.limit(28).all()
        else:
            services = base_query.order_by(Service.servizio_nome).limit(28).all()

        # server-side dedup (preserva primo-occurrence) e limit finale
        seen = set()
        unique_services = []
        for s in services:
            sid = getattr(s, 'id', None)
            if sid is None or sid in seen:
                continue
            seen.add(sid)
            unique_services.append(s)
            if len(unique_services) >= 28:
                break
        services = unique_services

        return jsonify([
            {
                "id": s.id,
                "nome": clean_str(s.servizio_nome),
                "tag": clean_str(s.servizio_tag),
                "prezzo": s.servizio_prezzo,
                "categoria": clean_str(s.servizio_categoria.value) if s.servizio_categoria else "",
                "sottocategoria": clean_str(s.servizio_sottocategoria.nome) if s.servizio_sottocategoria else "",
                "sottocategoria_id": s.servizio_sottocategoria_id,
                "is_prodotti": (
                    s.servizio_sottocategoria and clean_str(s.servizio_sottocategoria.nome.lower()) == "prodotti"
                )
            }
            for s in services
        ])
    except Exception as e:
        current_app.logger.error("Errore in /cassa/api/services: %s", str(e))
        return jsonify({"error": "Errore nel recupero dei servizi."}), 500
        
@cassa_bp.route('/cassa/api/clients')
def api_clients():
    q_raw = request.args.get('q', '').strip().lower()

    # Se meno di 2 caratteri → ritorna lista vuota
    if len(q_raw) < 2:
        return jsonify([])

    # Suddividi in parti (nome, cognome o pezzi multipli)
    parts = [p for p in q_raw.split() if p]

    # Costruzione filtri avanzati come nella route calendar
    if len(parts) == 1:
        term = f"%{parts[0]}%"
        filters = or_(
            func.lower(Client.cliente_nome).like(term),
            func.lower(Client.cliente_cognome).like(term),
            Client.cliente_cellulare.like(term)
        )
    else:
        # Cerca tutte le parti nel nome o cognome (AND combinato)
        conditions = []
        for part in parts:
            term = f"%{part}%"
            conditions.append(
                or_(
                    func.lower(Client.cliente_nome).like(term),
                    func.lower(Client.cliente_cognome).like(term)
                )
            )
        filters = and_(*conditions)

    # Applichiamo filtri di esclusione
    query = Client.query.filter(
        filters,
        Client.is_deleted == False,
        ~((Client.cliente_nome == "cliente") & (Client.cliente_cognome == "booking")),
        ~((func.lower(Client.cliente_nome) == "booking") & (func.lower(Client.cliente_cognome) == "online")),
        func.lower(Client.cliente_nome) != "dummy",
        func.lower(Client.cliente_cognome) != "dummy",
    )

    clients = query.order_by(Client.cliente_nome).limit(20).all()

    return jsonify([
        {
            "id": c.id,
            "nome": c.cliente_nome,
            "cognome": c.cliente_cognome
        }
        for c in clients
    ])

IDEMPOTENCY_STORE = {}
RCH_PENDING = {}


def _read_printer_lastz(ip, printer_model):
    """Legge dalla stampante il numero dell'ultima chiusura fiscale (Z) via =C453.
    Ritorna int (numero Z gia' eseguite) oppure None se non leggibile."""
    try:
        url = _rch_url(ip, printer_model)
        headers = _rch_headers(printer_model)
        rch_kwargs = _rch_request_kwargs(printer_model)
        payload = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C453/$0</cmd></Service>'
        resp = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=8,
                             **rch_kwargs)
        m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp.text or "")
        if m_z:
            return int(m_z.group(1))
    except Exception as exc:
        try:
            current_app.logger.warning("lettura lastZ (=C453) fallita: %s", str(exc))
        except Exception:
            pass
    return None


def _previous_day_was_closure(today):
    """True se il giorno PRECEDENTE a `today` e' un giorno di chiusura configurato
    (BusinessInfo.closing_days, nomi giorno in inglese es. 'Sunday'). Solo lettura DB,
    nessuna stampante. Usa weekday() (locale-independent) per il nome del giorno."""
    try:
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        if not bi:
            return False
        closing = bi.closing_days_list or []
        if not closing:
            return False
        EN_DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        yesterday_name = EN_DAYS[(today - timedelta(days=1)).weekday()]
        return yesterday_name in closing
    except Exception:
        return False


def _z_recorded_since(business_id, dt):
    """True se nel registro DB (fiscal_closures) risulta una chiusura Z eseguita con
    closed_at >= dt. Best-effort: se la tabella non esiste o errore -> False."""
    if dt is None:
        return False
    try:
        from appl.models import FiscalClosure
        return db.session.query(FiscalClosure.id).filter(
            FiscalClosure.business_info_id == business_id,
            FiscalClosure.closed_at >= dt,
        ).first() is not None
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        return False


def _record_fiscal_closure(ip, printer_model, dgfe_total=None):
    """Registra in DB (fiscal_closures) la chiusura fiscale (Z) appena eseguita.
    Legge il nuovo lastZ dalla stampante (numero della Z appena fatta). Best-effort:
    non solleva mai e non interrompe il flusso di chiusura."""
    try:
        from appl.models import FiscalClosure
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        bid = bi.id if bi else 0
        z_num = _read_printer_lastz(ip, printer_model)  # lastZ DOPO la Z = numero di questa Z

        # Evita righe duplicate per lo stesso numero di Z (es. doppio click).
        if z_num is not None:
            existing = FiscalClosure.query.filter_by(business_info_id=bid, z_number=z_num).first()
            if existing:
                return

        row = FiscalClosure(
            business_info_id=bid,
            z_number=z_num,
            closed_at=datetime.now(),
            giorno=date.today(),
            dgfe_total=(float(dgfe_total) if dgfe_total is not None else None),
        )
        db.session.add(row)
        db.session.commit()
        try:
            current_app.logger.info("Chiusura Z registrata in DB: z_number=%s bid=%s", z_num, bid)
        except Exception:
            pass
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.warning("registrazione chiusura Z fallita: %s", str(exc))
        except Exception:
            pass


def _check_chiusura_precedente(ip, printer_model):
    """Verifica, al PRIMO scontrino fiscale del giorno, se la chiusura fiscale (Z)
    della sessione precedente e' stata eseguita.

    Logica (fiscalmente robusta): ogni scontrino e' numerato 'ZZZZ-NNNN' dove ZZZZ
    e' il periodo di chiusura APERTO al momento dell'emissione (= lastZ+1, vedi
    send_to_rch). Se l'ultimo scontrino di un giorno PRECEDENTE appartiene ancora al
    periodo aperto sulla stampante (lastZ+1), allora la Z non e' stata eseguita e i
    nuovi scontrini finirebbero nello stesso periodo fiscale del giorno prima: in quel
    caso bisogna eseguire la chiusura prima di emettere il primo scontrino di oggi.

    Ritorna {needs_closure: bool, reason: str, ...}. In caso di incertezza (stampante
    non leggibile, nessuno scontrino precedente, non e' il primo di oggi) NON blocca
    (fail-open): si blocca SOLO quando si e' certi che manchi la Z, per non fermare
    mai la normale operativita'.
    """
    try:
        today = date.today()
        day_start = datetime.combine(today, datetime.min.time())

        # Gate attivo solo al PRIMO scontrino fiscale di oggi (esclusi gli ADJ di
        # allineamento DGFE, che non sono scontrini reali).
        today_count = Receipt.query.filter(
            Receipt.created_at >= day_start,
            Receipt.is_fiscale == True,
            or_(Receipt.numero_progressivo.is_(None),
                ~Receipt.numero_progressivo.like('ADJ-%'))
        ).count()
        if today_count > 0:
            return {"needs_closure": False, "reason": "not_first_today"}

        # Ultimo scontrino fiscale di un giorno PRECEDENTE con progressivo 'Z-N' valido.
        prev_receipts = Receipt.query.filter(
            Receipt.created_at < day_start,
            Receipt.is_fiscale == True,
        ).order_by(Receipt.created_at.desc()).limit(50).all()
        last_period = None
        last_receipt_dt = None
        for r in prev_receipts:
            m = re.match(r'^(\d+)-(\d+)$', str(r.numero_progressivo or ""))
            if m:
                last_period = int(m.group(1))
                last_receipt_dt = r.created_at
                break
        if last_period is None:
            return {"needs_closure": False, "reason": "no_prior_receipts"}

        # Periodo di chiusura attualmente APERTO sulla stampante (= ultima Z + 1).
        last_z = _read_printer_lastz(ip, printer_model)
        if last_z is None:
            # Stampante non leggibile: tipicamente c'e' un DOCUMENTO APERTO della sessione
            # precedente (Z non eseguita), situazione frequente DOPO un giorno di chiusura.
            # Se la Z fosse stata fatta la stampante sarebbe "pulita" e leggibile (=> z_done,
            # non arriveremmo qui). Percio': se IERI era un giorno di chiusura configurato e
            # ci sono scontrini di un giorno precedente, avvisa di fare la Z.
            if _previous_day_was_closure(today):
                # MA: se nel registro DB risulta una Z eseguita DOPO l'ultimo scontrino,
                # la chiusura e' gia' stata fatta -> NESSUN avviso (anche a stampante muta).
                bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
                bid = bi.id if bi else 0
                if _z_recorded_since(bid, last_receipt_dt):
                    return {"needs_closure": False, "reason": "z_recorded_db"}
                return {
                    "needs_closure": True,
                    "reason": "closure_day_missing_z",
                    "last_receipt_period": last_period,
                    "open_period": None,
                }
            # Altrimenti non blocchiamo (la stampa stessa rileggera' lastZ).
            return {"needs_closure": False, "reason": "printer_unreadable"}
        open_period = last_z + 1

        # Blocco SOLO quando il giorno precedente e' ancora nel periodo aperto:
        # nessuna Z lo ha chiuso. open_period > last_period => Z eseguita (ok).
        # open_period < last_period => anomalia (es. stampante sostituita/azzerata):
        # non blocchiamo per non fermare l'attivita' su un caso ambiguo.
        if open_period == last_period:
            return {
                "needs_closure": True,
                "reason": "missing_z",
                "last_receipt_period": last_period,
                "open_period": open_period,
            }
        return {
            "needs_closure": False,
            "reason": "z_done" if open_period > last_period else "anomaly",
            "last_receipt_period": last_period,
            "open_period": open_period,
        }
    except Exception as exc:
        try:
            current_app.logger.warning("check chiusura precedente fallito: %s", str(exc))
        except Exception:
            pass
        return {"needs_closure": False, "reason": "error"}


def _closure_required_response(ip, printer_model):
    """Ri-controlla se manca la chiusura Z precedente e, in caso, ritorna la response
    HTTP 409 needs_closure da restituire al posto del generico errore/'documento aperto'.
    Altrimenti None. Fail-safe: converte in avviso-Z SOLO quando puo' confermarlo
    leggendo la stampante (se non leggibile -> None -> resta il flusso generico)."""
    try:
        gate = _check_chiusura_precedente(ip, printer_model)
    except Exception:
        return None
    if gate.get("needs_closure"):
        try:
            current_app.logger.warning(
                "RCH errore/timeout + chiusura Z mancante (periodo aperto %s == ultimo scontrino %s): "
                "richiesta chiusura fiscale.",
                gate.get("open_period"), gate.get("last_receipt_period")
            )
        except Exception:
            pass
        return jsonify({
            "needs_closure": True,
            "error": "Chiusura fiscale precedente mancante.",
            "message": ("Attenzione! Esegui una chiusura fiscale (Z) — come prassi dopo "
                        "un giorno di chiusura — prima di emettere nuovi scontrini."),
        }), 409
    return None


@cassa_bp.route('/cassa/send-to-rch', methods=['POST'])
def send_to_rch():
    data = request.get_json(force=True)
    voci = data.get("voci", [])

    def _is_fiscale(v):
        if not isinstance(v, dict):
            return True
        if "is_fiscale" in v:
            return bool(v.get("is_fiscale"))
        if "is_non_fiscale" in v:
            return not bool(v.get("is_non_fiscale"))
        return True

    voci_fiscali = [v for v in voci if _is_fiscale(v)]
    voci_non_fiscali = [v for v in voci if not _is_fiscale(v)]

    if voci_fiscali:
        idempotency_key = data.get("idempotency_key")
        if not idempotency_key:
            return jsonify({"error": "Missing idempotency_key for fiscal payments"}), 400
        if idempotency_key in IDEMPOTENCY_STORE:
            return jsonify(IDEMPOTENCY_STORE[idempotency_key])
    else:
        idempotency_key = None

    cliente_id = data.get("cliente_id")
    operatore_id = data.get("operatore_id")

    if not voci:
        return jsonify({"error": "Nessuna voce da registrare"}), 400
    
    # Variabile per tracciare redirect a pacchetto prepagata
    redirect_pacchetto_id = None
    
    # --- VALIDAZIONE E NORMALIZZAZIONE PREZZI: solo numeri >= 0 ---
    for idx, v in enumerate(voci, start=1):
        # ensure prezzo key exists and is numeric
        prezzo_raw = v.get("prezzo", 0)
        try:
            # accetta stringhe numeriche, numeri; vuoto -> 0
            prezzo_val = float(prezzo_raw) if prezzo_raw not in (None, "") else 0.0
        except Exception:
            return jsonify({"error": f"Prezzo non valido nella voce #{idx} ({v.get('nome') or 'sconosciuto'})."}), 400

        if prezzo_val < 0:
            return jsonify({"error": f"Prezzi negativi non consentiti nella voce #{idx} ({v.get('nome') or 'sconosciuto'})."}), 400

        # normalizza il prezzo nella voce (2 decimali)
        v["prezzo"] = round(prezzo_val, 2)

    # Ricalcola voci fiscali/non fiscali dopo normalizzazione prezzi
    voci_fiscali = [v for v in voci if _is_fiscale(v)]
    voci_non_fiscali = [v for v in voci if not _is_fiscale(v)]
    results = []
    oggi = datetime.now().date()

    # completa nomi servizi mancanti
    for v in voci:
        if not v.get("nome") and v.get("servizio_id"):
            srv = db.session.get(Service, v["servizio_id"])
            if srv:
                v["nome"] = srv.servizio_nome

    # =========================
    # 1. SCONTRINO FISCALE
    # =========================
    if voci_fiscali:
        ip, printer_model = _get_printer_config()
        if not ip:
            return jsonify({"error": "IP stampante RCH non configurato"}), 400

        # GATE CHIUSURA FISCALE: il PRIMO scontrino fiscale del giorno NON viene
        # stampato se la chiusura (Z) della sessione precedente non e' stata eseguita,
        # altrimenti i nuovi corrispettivi finirebbero nel periodo fiscale del giorno
        # prima. In quel caso non stampiamo e chiediamo all'operatore di fare la Z.
        gate = _check_chiusura_precedente(ip, printer_model)
        if gate.get("needs_closure"):
            current_app.logger.warning(
                "Stampa primo scontrino bloccata: chiusura fiscale precedente mancante "
                "(periodo aperto %s == ultimo scontrino %s).",
                gate.get("open_period"), gate.get("last_receipt_period")
            )
            return jsonify({
                "needs_closure": True,
                "error": "Chiusura fiscale precedente mancante.",
                "message": ("Prima di emettere il primo scontrino di oggi devi eseguire la "
                            "chiusura fiscale (Z) della giornata precedente. Esegui la "
                            "chiusura e riprova a stampare."),
            }), 409

        xml_lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<Service>'
        ]
        totali = {}  # tender RCH (es. "T1", "T4") -> centesimi

        for v in voci_fiscali:
            srv = db.session.get(Service, v.get("servizio_id"))
            prezzo_pieno = float(srv.servizio_prezzo) if srv else float(v.get("prezzo", 0))
            prezzo_finale = float(v.get("prezzo", prezzo_pieno))
            prezzo_cents = int(round(prezzo_finale * 100))

            desc = (v.get("nome") or (srv.servizio_nome if srv else "Servizio"))[:32]
            desc = clean_str(html.unescape(desc)).replace(")", "").replace("(", "").replace("/", "-")

            reparto = "R2" if getattr(srv, "servizio_sottocategoria", None) and \
                               srv.servizio_sottocategoria.nome.upper() == "PRODOTTI" else "R1"
            xml_lines.append(f'<cmd>={reparto}/${prezzo_cents}/({desc})</cmd>')

            if prezzo_pieno > 0 and prezzo_finale < prezzo_pieno:
                sconto = 100 - (prezzo_finale / prezzo_pieno * 100)
                xml_lines.append(f'<cmd>="/(Scontato del {sconto:.2f}%)</cmd>')

            # Split pagamento: una singola voce puo' essere saldata con piu' metodi
            # (es. 50€ = 30 contanti + 20 POS). In tal caso 'pagamenti' contiene la
            # ripartizione; la riga merce resta stampata una sola volta, ma il totale
            # finisce su tender distinti. Se assente, comportamento storico (un metodo).
            pagamenti_split = v.get("pagamenti")
            if isinstance(pagamenti_split, list) and pagamenti_split:
                assegnati = 0
                for p in pagamenti_split:
                    cents_p = int(round(float(p.get("importo", 0)) * 100))
                    if cents_p <= 0:
                        continue
                    tcode_p = _tender_code(p.get("metodo", "cash"), printer_model)
                    totali[tcode_p] = totali.get(tcode_p, 0) + cents_p
                    assegnati += cents_p
                # eventuale arrotondamento: assegna il resto al primo tender valido
                diff = prezzo_cents - assegnati
                if diff != 0 and pagamenti_split:
                    tcode_first = _tender_code(pagamenti_split[0].get("metodo", "cash"), printer_model)
                    totali[tcode_first] = totali.get(tcode_first, 0) + diff
            else:
                metodo = v.get("metodo_pagamento", "cash")
                tcode = _tender_code(metodo, printer_model)
                totali[tcode] = totali.get(tcode, 0) + prezzo_cents

        def _voce_ha_digitale(v):
            if v.get("metodo_pagamento", "cash") in ("pos", "bank"):
                return True
            return any(
                p.get("metodo", "cash") in ("pos", "bank")
                for p in (v.get("pagamenti") or [])
            )

        codice_lotteria = (data.get("lotteria") or "").strip().upper()
        pagamenti_digitali = any(_voce_ha_digitale(v) for v in voci_fiscali)
        if (
            len(codice_lotteria) == 8
            and codice_lotteria.isalnum()
            and pagamenti_digitali
        ):
            xml_lines.insert(2, f'<cmd>="/?L/$1/({codice_lotteria})</cmd>')

        if not totali or sum(totali.values()) == 0:
            xml_lines.append('<cmd>=T5/$0</cmd>')
        else:
            for tcode in ("T1", "T2", "T3", "T4", "T5"):
                if totali.get(tcode, 0) > 0:
                    xml_lines.append(f'<cmd>={tcode}/${totali[tcode]}</cmd>')

        xml_lines.append('</Service>')
        payload_vendita = "\n".join(xml_lines)

        # --- STAMPA IL PAYLOAD NEL TERMINALE ---
        current_app.logger.debug("PAYLOAD XML INVIATO:\n%s", payload_vendita)

        # ip/printer_model gia' letti all'inizio del blocco fiscale
        url = _rch_url(ip, printer_model)
        headers = _rch_headers(printer_model)
        rch_kwargs = _rch_request_kwargs(printer_model)

        # expected_total e line_count usati sia per RCH_PENDING sia per il lazy recover
        expected_total = round(sum(float(v.get("prezzo", 0)) for v in voci_fiscali), 2)
        expected_line_count = len(voci_fiscali)

        def _build_pending_entry():
            return {
                "payload_xml": payload_vendita,
                "cliente_id": cliente_id,
                "operatore_id": operatore_id,
                "voci": voci_fiscali,
                "created_ts": pytime.time(),
                "expected_total": expected_total,
                "giorno": datetime.now().strftime("%Y-%m-%d"),
                "line_count": expected_line_count,
                "printer_ip": ip,
                "printer_model": printer_model
            }

        fiscale_recovered = False
        progressivo_completo = None
        resp_vendita = None

        try:
            resp_vendita = requests.post(
                url, data=payload_vendita.encode("UTF-8"), headers=headers, timeout=120,
                **rch_kwargs
            )
            current_app.logger.info("RCH risposta: %s", resp_vendita.text[:300] if resp_vendita.text else "(vuoto)")
        except requests.exceptions.Timeout as exc:
            # TIMEOUT = la stampante POTREBBE aver gia' chiuso il documento ma la response
            # non e' arrivata. Provo prima il lazy recover (legge lastDocF + DGFE).
            current_app.logger.warning("RCH TIMEOUT: tentativo lazy recover... (%s)", str(exc))
            prog = _try_lazy_recover(voci_fiscali, cliente_id, operatore_id,
                                     expected_total, expected_line_count, ip, printer_model)
            if prog:
                current_app.logger.info("RCH lazy recover OK dopo timeout: progressivo %s", prog)
                progressivo_completo = prog
                fiscale_recovered = True
                results.append({
                    "message": f"Scontrino fiscale registrato (progressivo {prog})",
                    "is_fiscale": True
                })
            else:
                # Il timeout puo' dipendere da un DOCUMENTO APERTO della sessione
                # precedente (tipico dopo un giorno di chiusura senza Z): se la Z manca
                # davvero, avvisa di farla invece del generico "documento aperto".
                closure_resp = _closure_required_response(ip, printer_model)
                if closure_resp:
                    return closure_resp
                if idempotency_key:
                    RCH_PENDING[idempotency_key] = _build_pending_entry()
                    return jsonify({
                        "pending": True,
                        "reason": "timeout",
                        "message": "Stampante in attesa (cambio carta?). Risolvere e riprovare.",
                        "idempotency_key": idempotency_key,
                        "expected_total": expected_total,
                        "retry_after": 3
                    }), 202
                log_crm_error(
                    "RCH timeout invio scontrino fiscale",
                    context={"idempotency_key": idempotency_key, "operatore_id": operatore_id,
                             "printer_ip": ip, "printer_model": printer_model,
                             "expected_total": expected_total, "exception": str(exc)},
                    client_id=cliente_id,
                )
                return jsonify({"error": "Stampante in attesa. Controllare carta e riprovare."}), 502
        except Exception as exc:
            current_app.logger.warning("RCH non raggiungibile (network): tentativo lazy recover... (%s)", str(exc))
            prog = _try_lazy_recover(voci_fiscali, cliente_id, operatore_id,
                                     expected_total, expected_line_count, ip, printer_model)
            if prog:
                current_app.logger.info("RCH lazy recover OK dopo network error: progressivo %s", prog)
                progressivo_completo = prog
                fiscale_recovered = True
                results.append({
                    "message": f"Scontrino fiscale registrato (progressivo {prog})",
                    "is_fiscale": True
                })
            else:
                # Anche su errore di rete: se la stampante e' invece raggiungibile e
                # manca la Z della sessione precedente, avvisa di eseguire la chiusura.
                closure_resp = _closure_required_response(ip, printer_model)
                if closure_resp:
                    return closure_resp
                if idempotency_key:
                    RCH_PENDING[idempotency_key] = _build_pending_entry()
                    return jsonify({
                        "pending": True,
                        "reason": "network",
                        "message": "Stampante non raggiungibile. Attendere e riprovare.",
                        "idempotency_key": idempotency_key,
                        "expected_total": expected_total,
                        "retry_after": 3
                    }), 202
                log_crm_error(
                    "RCH non raggiungibile (network) invio scontrino fiscale",
                    context={"idempotency_key": idempotency_key, "operatore_id": operatore_id,
                             "printer_ip": ip, "printer_model": printer_model,
                             "expected_total": expected_total, "exception": str(exc)},
                    client_id=cliente_id,
                )
                return jsonify({"error": "Stampante non raggiungibile. Riprova."}), 502

        # Se la prima POST e' andata ma la risposta non e' "OK" (errCode!=0 da qualche parte),
        # provo lazy recover prima di dare per fallito.
        if not fiscale_recovered and not _rch_is_success(resp_vendita):
            current_app.logger.warning("RCH ha risposto con errore: tentativo lazy recover... (body=%s)",
                                       (resp_vendita.text[:400] if resp_vendita is not None else ""))
            prog = _try_lazy_recover(voci_fiscali, cliente_id, operatore_id,
                                     expected_total, expected_line_count, ip, printer_model)
            if prog:
                current_app.logger.info("RCH lazy recover OK dopo errore stampante: progressivo %s", prog)
                progressivo_completo = prog
                fiscale_recovered = True
                results.append({
                    "message": f"Scontrino fiscale registrato (progressivo {prog})",
                    "is_fiscale": True
                })
            else:
                # L'errore stampante potrebbe dipendere dalla CHIUSURA FISCALE (Z) mancante
                # della sessione precedente: tipico DOPO un giorno di chiusura, quando sono
                # passate >24h senza Z e la RCH blocca l'emissione del primo scontrino.
                # Il gate pre-stampa puo' non aver bloccato (es. lastZ momentaneamente non
                # leggibile -> fail-open): ora la stampante HA risposto, quindi ri-leggiamo
                # lo stato e, se manca la Z, mostriamo l'avviso corretto invece di un generico
                # "stampante in errore / riprovare".
                closure_resp = _closure_required_response(ip, printer_model)
                if closure_resp:
                    return closure_resp
                if idempotency_key:
                    RCH_PENDING[idempotency_key] = _build_pending_entry()
                    return jsonify({
                        "pending": True,
                        "reason": "printer_error",
                        "message": "Stampante in errore. Attendere (es. cambio carta) e riprovare.",
                        "idempotency_key": idempotency_key,
                        "expected_total": expected_total,
                        "retry_after": 3
                    }), 202
                log_crm_error(
                    "RCH ha risposto con errore (errCode) invio scontrino fiscale",
                    context={"idempotency_key": idempotency_key, "operatore_id": operatore_id,
                             "printer_ip": ip, "printer_model": printer_model,
                             "expected_total": expected_total,
                             "response_body": (resp_vendita.text[:400] if resp_vendita is not None else "")},
                    client_id=cliente_id,
                )
                return jsonify({"error": "Stampante in errore. Riprova."}), 502

        if not fiscale_recovered:
            # ---------- lettura progressivo NR DOC (happy path) ----------
            numero_progressivo = None
            numero_z = None
            for cmd in ("=C453/$0", "=DGFE/REG"):
                payload_prog = f'''<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'''
                for _ in range(6):
                    pytime.sleep(0.5)
                    resp = requests.post(url, data=payload_prog.encode('utf-8'), headers=headers, timeout=5,
                                         **rch_kwargs)
                    m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', resp.text) or
                             re.search(r'<C453[^>]*>(\d+)</C453>', resp.text) or
                             re.search(r'<result>(\d+)</result>', resp.text))
                    m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp.text)
                    if m_doc and m_z:
                        numero_progressivo = int(m_doc.group(1))
                        numero_z = int(m_z.group(1)) + 1
                        break
                if numero_progressivo is not None and numero_z is not None:
                    break

            if numero_progressivo is None or numero_z is None:
                log_crm_error(
                    "RCH: risposta senza progressivo/lastZ (XML malformato o non letto)",
                    context={"operatore_id": operatore_id, "printer_ip": ip, "printer_model": printer_model,
                             "expected_total": expected_total},
                    client_id=cliente_id,
                )
                return jsonify({"error": "La stampante non ha restituito il progressivo"}), 500

            progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"

            # ---------- persiste Receipt ----------
            nuovo_receipt = Receipt(
                created_at       = datetime.now(),
                total_amount     = expected_total,
                is_fiscale       = True,
                voci             = voci_fiscali,
                cliente_id       = cliente_id,
                operatore_id     = operatore_id,
                numero_progressivo = progressivo_completo  # stringa tipo 1825-0046
            )
            db.session.add(nuovo_receipt)
            db.session.commit()

            ids_pagati = [v.get("appointment_id") for v in voci_fiscali if v.get("appointment_id")]
            if ids_pagati:
                Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                    {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
                )
                db.session.commit()

            results.append({
                "message": f"Scontrino fiscale registrato (progressivo {progressivo_completo})",
                "is_fiscale": True
            })

    # =========================
    # 2. SCONTRINO NON FISCALE
    # =========================
    if voci_non_fiscali:
        ultimo = Receipt.query.filter(
            Receipt.created_at >= datetime.combine(oggi, datetime.min.time()),
            Receipt.created_at <= datetime.combine(oggi, datetime.max.time())
        ).order_by(Receipt.numero_progressivo.desc()).first()
        if not ultimo or not str(ultimo.numero_progressivo).isdigit():
            numero_progressivo = "1"
        else:
            numero_progressivo = str(int(ultimo.numero_progressivo) + 1)

        total_amount = round(sum(float(v.get("prezzo", 0)) for v in voci_non_fiscali), 2)
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = total_amount,
            is_fiscale       = False,
            voci             = voci_non_fiscali,
            cliente_id       = cliente_id,
            operatore_id     = operatore_id,
            numero_progressivo = numero_progressivo
        )
        db.session.add(nuovo_receipt)
        db.session.commit()

        ids_pagati = [v.get("appointment_id") for v in voci_non_fiscali if v.get("appointment_id")]
        if ids_pagati:
            Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
            )
            db.session.commit()

        results.append({
            "message": "Scontrino non fiscale registrato",
            "is_fiscale": False
        })

    # IMPORTANTE: Gestione prepagata/rate PRIMA di costruire response
    # Deve essere FUORI dai blocchi fiscale/non fiscale perché le prepagate
    # possono essere in entrambi i casi
    pacchetto_ids_modificati = set()
    
    # Processa TUTTE le voci per prepagata/rate (sia fiscali che non fiscali)
    for v in voci:
        # Gestione ricarica carta prepagata
        ricarica_prepagata_id = v.get('ricarica_prepagata_id')
        if ricarica_prepagata_id:
            try:
                pacchetto = Pacchetto.query.get(int(ricarica_prepagata_id))
                if pacchetto and pacchetto.tipo.value == 'prepagata':
                    importo = Decimal(str(v.get('ricarica_importo', 0)))
                    credito_da_caricare = Decimal(str(v.get('ricarica_credito', importo)))
                    descrizione = v.get('ricarica_descrizione', 'Ricarica')
                    
                    vecchio_saldo = pacchetto.credito_residuo or Decimal('0')
                    nuovo_saldo = vecchio_saldo + credito_da_caricare
                    pacchetto.credito_residuo = nuovo_saldo
                    
                    # Se era in preventivo, attivala
                    if pacchetto.status == PacchettoStatus.Preventivo:
                        pacchetto.status = PacchettoStatus.Attivo
                    
                    from appl.models import MovimentoPrepagata
                    movimento = MovimentoPrepagata(
                        pacchetto_id=pacchetto.id,
                        tipo_movimento='ricarica',
                        importo=importo,
                        saldo_dopo=nuovo_saldo,
                        descrizione=descrizione
                    )
                    db.session.add(movimento)
                    db.session.commit()
                    current_app.logger.info(f"Ricarica prepagata {ricarica_prepagata_id}: +€{importo:.2f}, nuovo saldo €{nuovo_saldo:.2f}")
                    # IMPORTANTE: Salva ID per redirect
                    redirect_pacchetto_id = int(ricarica_prepagata_id)
            except Exception as e:
                current_app.logger.error(f"Errore ricarica prepagata {ricarica_prepagata_id}: {e}")

        # Gestione pagamento carta prepagata (ATTIVAZIONE)
        prepagata_id = v.get('prepagata_id')
        if prepagata_id:
            try:
                pacchetto = Pacchetto.query.get(int(prepagata_id))
                if pacchetto and pacchetto.tipo.value == 'prepagata':
                    credito = Decimal(str(v.get('credito_da_caricare', pacchetto.credito_iniziale)))
                    
                    pacchetto.credito_residuo = credito
                    pacchetto.status = PacchettoStatus.Attivo
                    
                    from appl.models import MovimentoPrepagata
                    movimento = MovimentoPrepagata(
                        pacchetto_id=pacchetto.id,
                        tipo_movimento='ricarica',
                        importo=credito,
                        saldo_dopo=credito,
                        descrizione='Caricamento iniziale (pagamento)'
                    )
                    db.session.add(movimento)
                    db.session.commit()
                    current_app.logger.info(f"Prepagata {prepagata_id} attivata con credito €{credito:.2f}")
                    # IMPORTANTE: Salva l'ID per redirect
                    redirect_pacchetto_id = int(prepagata_id)
            except Exception as e:
                current_app.logger.error(f"Errore attivazione prepagata {prepagata_id}: {e}")

        # Gestione rate pacchetto
        rata_id = v.get('rata_id')
        if rata_id:
            try:
                rata = PacchettoRata.query.get(int(rata_id))
                if rata and not rata.is_pagata:
                    importo_pagato = float(v.get('prezzo', 0))
                    importo_originale = float(rata.importo)
                    importo_modificato = abs(importo_pagato - importo_originale) > 0.01
                    
                    if importo_modificato:
                        rata.importo = importo_pagato
                        pacchetto_ids_modificati.add(rata.pacchetto_id)
                    
                    rata.is_pagata = True
                    rata.data_pagamento = datetime.now()
                    
                    pacchetto = rata.pacchetto
                    if pacchetto:
                        rata_num = next((i+1 for i, r in enumerate(pacchetto.rate) if r.id == rata.id), 0)
                        try:
                            history = json.loads(pacchetto.history) if pacchetto.history else []
                        except:
                            history = []
                        
                        if importo_modificato:
                            history.append({"ts": datetime.now().isoformat(), "azione": f"Pagata rata {rata_num} (importo modificato: €{importo_pagato:.2f})"})
                        else:
                            history.append({"ts": datetime.now().isoformat(), "azione": f"Pagata rata {rata_num}"})
                        pacchetto.history = json.dumps(history)
                        
                        if pacchetto.status.value not in ("completato", "eliminato"):
                            pacchetto.status = PacchettoStatus.Attivo
                    
                    db.session.commit()
                    current_app.logger.info(f"Rata {rata_id} marcata come pagata (importo: €{importo_pagato:.2f})")
            except Exception as e:
                current_app.logger.error(f"Errore marcatura rata {rata_id}: {e}")

    # Prepara response con info per redirect a pacchetto se necessario
    response = {"results": results, "reset_voci": True}

    # Verifica se il modulo pacchetti è abilitato per questo tenant
    _pacchetti_abilitati = True
    try:
        from appl.models import OWNER
        _owner_cfg = OWNER.query.first()
        if _owner_cfg:
            _pacchetti_abilitati = bool(_owner_cfg.module_pacchetti_enabled)
    except Exception:
        pass

    if _pacchetti_abilitati:
        # PRIORITA' 1: Redirect a prepagata se è stata attivata/ricaricata
        if redirect_pacchetto_id:
            response["redirect_to_pacchetto"] = redirect_pacchetto_id
            response["prepagata_attivata"] = True
            current_app.logger.info(f"Redirect impostato a prepagata {redirect_pacchetto_id}")
        # PRIORITA' 2: Se c'è un pacchetto con rata modificata
        elif pacchetto_ids_modificati:
            pacchetto_id = list(pacchetto_ids_modificati)[0]
            response["redirect_to_pacchetto"] = pacchetto_id
            response["rata_importo_modificato"] = True
        # PRIORITA' 3: Se c'era una rata, redirect al pacchetto
        elif any(v.get('rata_id') for v in voci):
            for v in voci:
                if v.get('rata_id'):
                    rata = PacchettoRata.query.get(int(v['rata_id']))
                    if rata:
                        response["redirect_to_pacchetto"] = rata.pacchetto_id
                        break
        # PRIORITA' 4: Cerca prepagata_id o ricarica nelle voci (fallback)
        if not response.get("redirect_to_pacchetto"):
            for v in voci:
                pid = v.get('prepagata_id') or v.get('ricarica_prepagata_id')
                if pid:
                    response["redirect_to_pacchetto"] = int(pid)
                    current_app.logger.info(f"Redirect fallback a prepagata {pid}")
                    break
    
    # Salva idempotency solo se non ci sono errori nei risultati
    if idempotency_key and not any("error" in str(r).lower() for r in results):
        IDEMPOTENCY_STORE[idempotency_key] = response
    return jsonify(response)

@cassa_bp.route('/cassa/registro-scontrini')
def registro_scontrini():
    # 1. Determina il giorno da visualizzare
    data_str = request.args.get('data')
    if data_str:
        try:
            giorno = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            giorno = date.today()
    else:
        giorno = date.today()

    # 2. Ottieni utente e ruolo
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    user_role = user.ruolo.value if user else None

    # 3. Carica scontrini del giorno (filtro per ruolo)
    giorno_start = datetime.combine(giorno, datetime.min.time())
    giorno_end = datetime.combine(giorno, datetime.max.time())
    
    # Include ANCHE le voci di allineamento DGFE (dummy ADJ-YYYYMMDD): sono fiscali,
    # concorrono ai totali e ora vengono mostrate come riga dedicata
    # ("ALLINEAMENTO DGFE") cosi' il totale del registro combacia col totale DGFE.
    if user_role == "user":
        scontrini = Receipt.query.filter(
            Receipt.is_fiscale == True,
            Receipt.created_at >= giorno_start,
            Receipt.created_at <= giorno_end,
        ).order_by(Receipt.created_at.asc()).all()
    else:
        scontrini = Receipt.query.filter(
            Receipt.created_at >= giorno_start,
            Receipt.created_at <= giorno_end,
        ).order_by(Receipt.created_at.asc()).all()

    # 4. Normalizza i dati di ogni scontrino
    for s in scontrini:
        s.is_fiscale = bool(s.is_fiscale)
        if isinstance(s.voci, str):
            try:
                s.voci = json.loads(s.voci)
            except Exception:
                s.voci = []
        if s.voci is None:
            s.voci = []
        # Voce di allineamento DGFE (dummy ADJ-YYYYMMDD): riga dedicata, NON e' uno
        # scontrino reale ne' uno storno.
        s.is_adjustment = bool(s.numero_progressivo and str(s.numero_progressivo).startswith('ADJ-'))
        if s.is_adjustment:
            s.display_numero_progressivo = 'ALLINEAMENTO DGFE'
        else:
            s.display_numero_progressivo = s.numero_progressivo
        s.annullato = False

    # 5. Separa scontrini positivi (originali) e negativi (storni).
    #    Le voci di allineamento DGFE (ADJ) sono escluse: non sono storni.
    storni = [s for s in scontrini if not s.is_adjustment and s.is_fiscale and s.total_amount is not None and float(s.total_amount) < 0]
    positivi = [s for s in scontrini if not s.is_adjustment and s.is_fiscale and s.total_amount is not None and float(s.total_amount) > 0]

    # 6. Per ogni storno, trova lo scontrino originale corrispondente
    progressivi_stornati = set()
    
    for storno in storni:
        candidati = [
            p for p in positivi
            if (
                p.operatore_id == storno.operatore_id
                and p.cliente_id == storno.cliente_id
                and abs(float(p.total_amount) - abs(float(storno.total_amount))) < 0.01
                and p.created_at < storno.created_at
            )
        ]
        
        if candidati:
            originale = max(candidati, key=lambda x: x.created_at)
            storno.display_numero_progressivo = f"STORNO {originale.numero_progressivo}"
            if originale.numero_progressivo:
                progressivi_stornati.add(str(originale.numero_progressivo))
        else:
            storno.display_numero_progressivo = f"STORNO {storno.numero_progressivo}"

    # 7. Marca come "annullato" SOLO gli scontrini il cui progressivo è stato stornato
    for s in scontrini:
        if not s.is_adjustment and s.is_fiscale and s.total_amount is not None and float(s.total_amount) > 0:
            if s.numero_progressivo and str(s.numero_progressivo) in progressivi_stornati:
                s.annullato = True

    # 8. Riepilogo conciliazione DGFE per il giorno (solo informativo, no I/O stampante).
    #    Legge il log di riconciliazione gia' persistito (reconcile_day / Allinea a DGFE)
    #    cosi' l'utente vede SEMPRE se il registro fiscale quadra col DGFE, anche quando
    #    NON c'e' la riga "ALLINEAMENTO DGFE" perche' i totali gia' combaciano (delta 0).
    dgfe_recon = None
    if user_role in ('admin', 'owner'):
        try:
            registro_fiscale_total = round(
                sum(float(s.total_amount or 0) for s in scontrini if s.is_fiscale), 2
            )
            has_adj = any(getattr(s, 'is_adjustment', False) for s in scontrini)
            bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
            recon = _load_reconciliation_log(bi.id).get(giorno.strftime('%Y-%m-%d')) if bi else None

            dgfe_total = recon.get('dgfe_total') if recon else None
            dgfe_count = int(recon.get('dgfe_count') or 0) if recon else 0
            dgfe_total_f = float(dgfe_total) if dgfe_total is not None else None
            available = bool(recon) and dgfe_count > 0 and dgfe_total_f is not None
            aligned = available and abs(dgfe_total_f - registro_fiscale_total) < 0.01
            run_at = recon.get('run_at') if recon else None
            run_at_fmt = None
            if run_at:
                try:
                    run_at_fmt = datetime.fromisoformat(run_at).strftime('%d/%m/%Y %H:%M')
                except Exception:
                    run_at_fmt = run_at
            # SEMPRE valorizzato per admin/owner: se per il giorno non c'e' una lettura
            # DGFE nel log, mostriamo lo stato grigio "non ancora letto" (available=False).
            # Cosi' il badge e' SEMPRE visibile, non sparisce mai.
            dgfe_recon = {
                'available': available,
                'aligned': aligned,
                'has_adj': has_adj,
                'registro_total': registro_fiscale_total,
                'dgfe_total': dgfe_total_f,
                'dgfe_count': dgfe_count,
                'delta': round((dgfe_total_f - registro_fiscale_total), 2) if dgfe_total_f is not None else None,
                'run_at': run_at_fmt,
            }
        except Exception:
            current_app.logger.exception("registro_scontrini: riepilogo DGFE non calcolabile")
            dgfe_recon = None

    # 9. Render template
    return render_template(
        'registro_scontrini.html',
        scontrini=scontrini,
        giorno=giorno,
        user_role=user_role,
        date_today=date.today(),
        dgfe_recon=dgfe_recon,
    )

@cassa_bp.route('/cassa/api/receipt/<int:receipt_id>')
def api_receipt_detail(receipt_id):
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    s = db.session.get(Receipt, receipt_id)
    if not s:
        abort(404)
    # Filtro: se user e lo scontrino NON è fiscale, blocca l'accesso
    if user and user.ruolo.value == "user" and not s.is_fiscale:
        return jsonify({"error": "Non autorizzato"}), 403

    voci = s.voci
    if isinstance(voci, str):
        try:
            voci = json.loads(voci)
        except Exception:
            voci = []
    if voci is None:
        voci = []

    for v in voci:
        if not v.get("nome") and v.get("servizio_id"):
            servizio = db.session.get(Service, v["servizio_id"])
            if servizio:
                v["nome"] = servizio.servizio_nome

    return jsonify({
        "id": s.id,
        "created_at": s.created_at.strftime('%d/%m/%Y %H:%M:%S'),
        "is_fiscale": s.is_fiscale,
        "operatore": f"{s.operatore.user_nome} {s.operatore.user_cognome}" if s.operatore else "-",
        "cliente": f"{s.cliente.cliente_nome} {s.cliente.cliente_cognome}" if s.cliente else "Generico",
        "voci": [
            {
                "nome": v.get('servizio_nome') or v.get('nome', ''),
                "prezzo": v.get('prezzo', 0),
                "metodo_pagamento": v.get('metodo_pagamento', ''),
                "is_non_fiscale": v.get('is_non_fiscale', False)
            } for v in (voci or [])
        ],
        "totale": s.total_amount,
        "totale_scontrinato": s.total_amount if s.is_fiscale else 0
    })

def ripristina_rate_da_scontrino(scontrino):
    """Ripristina le rate pacchetto associate a uno scontrino stornato/eliminato"""
    if not scontrino or not scontrino.voci:
        return
    
    voci = scontrino.voci
    if isinstance(voci, str):
        try:
            voci = json.loads(voci)
        except:
            voci = []
    
    for v in voci:
        rata_id = v.get('rata_id')
        if rata_id:
            try:
                rata = db.session.get(PacchettoRata, int(rata_id))
                if rata and rata.is_pagata:
                    rata.is_pagata = False
                    rata.data_pagamento = None
                    # Ricalcola status pacchetto
                    pacchetto = rata.pacchetto
                    if pacchetto and pacchetto.status == PacchettoStatus.Attivo:
                        # Verifica se ci sono ancora rate pagate o sedute effettuate
                        ha_rata_pagata = any(r.is_pagata for r in pacchetto.rate if r.id != rata.id)
                        ha_seduta_effettuata = any(s.stato == 4 for s in pacchetto.sedute)
                        if not ha_rata_pagata and not ha_seduta_effettuata:
                            pacchetto.status = PacchettoStatus.Preventivo
                    current_app.logger.info(f"Rata {rata_id} ripristinata (non pagata)")
            except Exception as e:
                current_app.logger.error(f"Errore ripristino rata {rata_id}: {e}")
    
    db.session.commit()

@cassa_bp.route('/cassa/api/receipt/<int:id>', methods=['DELETE'])
def api_receipt_delete(id):
    try:
        scontrino = db.session.get(Receipt, id)
        if not scontrino:
            abort(404)
        
        # Controllo ruolo: solo ADMIN/OWNER
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or user.ruolo.value not in ["admin", "owner"]:
            return jsonify({"error": "Non autorizzato: solo amministratori possono eliminare scontrini"}), 403
        
        oggi = datetime.now().date()
        data_scontrino = scontrino.created_at.date() if scontrino.created_at else None
        
        if scontrino.is_fiscale:
            if data_scontrino != oggi:
                return jsonify({"error": "Eliminazione possibile solo per scontrini fiscali del giorno corrente"}), 400
            
            # Storna fiscalmente prima (aggiunge la voce negativa)
            storno_result = stornare_scontrino_specifico(scontrino)
            if "error" in storno_result:
                return jsonify({"error": f"Storno fallito: {storno_result['error']}"}), 400
            
            # Ripristina rate pacchetto associate
            ripristina_rate_da_scontrino(scontrino)

            # NON eliminare lo scontrino originale!
            # Semplicemente termina qui: la voce negativa è già stata aggiunta da stornare_scontrino_specifico
            return '', 204

        # Per non fiscali, ripristina rate prima di eliminare
        ripristina_rate_da_scontrino(scontrino)
        
        # Per non fiscali, puoi continuare a eliminare
        db.session.delete(scontrino)
        db.session.commit()
        return '', 204
    except Exception as e:
        current_app.logger.error("Errore eliminazione scontrino %s: %s", id, str(e))
        return jsonify({"error": "Errore durante l'eliminazione"}), 400
    
@cassa_bp.route('/cassa/api/receipt/<int:receipt_id>/update-metodo', methods=['POST'])
def update_metodo_pagamento(receipt_id):
    scontrino = db.session.get(Receipt, receipt_id)
    if not scontrino:
        abort(404)
    data = request.get_json()
    metodi = data.get('metodi')
    voci = scontrino.voci
    if isinstance(voci, str):
        voci = json.loads(voci)
    if not isinstance(voci, list) or not isinstance(metodi, list) or len(metodi) != len(voci):
        return jsonify({'error': 'Dati non validi'}), 400
    for idx, metodo in enumerate(metodi):
        voci[idx]['metodo_pagamento'] = metodo
    scontrino.voci = voci
    flag_modified(scontrino, "voci")
    db.session.commit()
    return jsonify({'success': True})

def _run_post_z_reconciliation(max_attempts=6, settle_s=1.5, retry_sleep_s=2.5):
    """Esegue reconcile_day(today) usando la BusinessInfo corrente, DOPO la chiusura
    fiscale (Z). Subito dopo la Z la stampante puo' essere ancora occupata (invio
    corrispettivi all'AdE, finalizzazione DGFE): una singola lettura DGFE puo'
    fallire o tornare vuota, e in quel caso l'allineamento (dummy ADJ-YYYYMMDD che
    fa combaciare il totale del registro col totale DGFE) NON verrebbe applicato.

    Per questo riproviamo con una breve attesa finche' l'allineamento risulta
    effettivamente applicato (action created/updated/noop/deleted). Cosi' i
    Corrispettivi combaciano col DGFE in automatico, senza correzioni manuali.

    Best-effort: non solleva mai eccezioni al chiamante. Ritorna il summary o None.
    """
    try:
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        if not bi:
            return None

        # Piccola attesa iniziale: lascia che la Z si finalizzi prima di leggere il DGFE.
        if settle_s and settle_s > 0:
            pytime.sleep(settle_s)

        summary = None
        # action "buone" = allineamento applicato (o gia' allineato / niente da fare).
        good_actions = ("created", "updated", "noop", "deleted")
        # Statuti di lettura DGFE considerati affidabili.
        reliable_statuses = ("ok", "ej_empty", "ej_no_blocks")
        for attempt in range(1, max_attempts + 1):
            summary = reconcile_day(date.today(), bi)
            action = (summary or {}).get("alignment_action")
            diag = (summary or {}).get("dgfe_diagnostic") or {}
            dgfe_status = diag.get("status")
            dgfe_count = (summary or {}).get("dgfe_count") or 0
            current_app.logger.info(
                "post-Z reconciliation tentativo %d/%d: alignment=%s dgfe_status=%s dgfe_count=%s delta=%s",
                attempt, max_attempts, action, dgfe_status,
                dgfe_count, (summary or {}).get("alignment_delta")
            )
            if action in good_actions:
                break
            # Lettura affidabile ma giorno legittimamente vuoto (0 scontrini):
            # non c'e' nulla da allineare, inutile ritentare.
            if dgfe_status in reliable_statuses and dgfe_count == 0:
                break
            # Lettura DGFE non affidabile o vuota (stampante ancora occupata):
            # aspetta e riprova, tranne all'ultimo tentativo.
            if attempt < max_attempts:
                pytime.sleep(retry_sleep_s)

        if summary and summary.get("alignment_action") not in good_actions:
            current_app.logger.warning(
                "post-Z reconciliation: allineamento DGFE NON applicato dopo %d tentativi "
                "(alignment=%s). Il totale del registro potrebbe non combaciare col DGFE; "
                "usare 'Carica DGFE'/'Correggi' nei Corrispettivi.",
                max_attempts, summary.get("alignment_action")
            )
        return summary
    except Exception as exc:
        try:
            current_app.logger.error("Reconciliation post-Z fallita: %s", str(exc))
        except Exception:
            pass
        return None

@cassa_bp.route('/cassa/dgfe-total', methods=['GET'])
def dgfe_total_for_day():
    """Ritorna il totale fiscale letto dal DGFE della stampante per un singolo giorno.
    Solo owner. Usa lo stesso meccanismo di /cassa/api/dgfe (comando =C452).
    Query: ?day=YYYY-MM-DD
    Response: {date, dgfe_total, dgfe_count, status, http_status, body_len, error}
    """
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        day_str = (request.args.get('day') or '').strip()
        if not day_str:
            return jsonify({"error": "Parametro day mancante"}), 400
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400

        ip, _ = _get_printer_config()
        if not ip:
            return jsonify({"error": "IP stampante non configurato"}), 400

        entries, diag = _dgfe_entries_with_diag(ip, day)
        total = round(sum(float(e.get("totale_float", 0) or 0) for e in entries), 2)

        # Persisti la lettura in DB (anche se e' solo un "Carica DGFE"/check), cosi'
        # il badge del Registro Scontrini la riflette. Solo se la lettura e' affidabile.
        if diag.get("status") in ("ok", "ej_empty", "ej_no_blocks"):
            _persist_dgfe_reading(
                day, total, len(entries),
                status="checked",
                notes="Lettura DGFE da 'Carica DGFE' (Corrispettivi).",
            )

        return jsonify({
            "date": day_str,
            "dgfe_total": total,
            "dgfe_count": len(entries),
            "status": diag.get("status"),
            "http_status": diag.get("http_status"),
            "body_len": diag.get("body_len"),
            "error": diag.get("error"),
        })
    except Exception as exc:
        try:
            current_app.logger.exception("dgfe-total: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


CORREGGI_DAY_THRESHOLD = 0.15  # 15% sul totale DGFE: sopra → verifica rinforzata richiesta


def _adj_progressivo_for_day(day_date):
    """Progressivo univoco per la dummy ADJ del giorno: 'ADJ-YYYYMMDD'."""
    return f"ADJ-{day_date.strftime('%Y%m%d')}"


def _db_receipts_for_day_no_adj(day_date):
    """Tutti i Receipt fiscali del giorno escludendo le dummy ADJ-*."""
    day_start = datetime.combine(day_date, datetime.min.time())
    day_end = datetime.combine(day_date, datetime.max.time())
    return Receipt.query.filter(
        Receipt.created_at >= day_start,
        Receipt.created_at <= day_end,
        Receipt.is_fiscale == True,
        or_(Receipt.numero_progressivo.is_(None),
            ~Receipt.numero_progressivo.like('ADJ-%'))
    ).order_by(Receipt.created_at.asc()).all()


def _correggi_day_compute(day_date):
    """Calcola tutto cio' che serve per Correggi su un giorno:
    DGFE total/entries, DB total/entries (no ADJ), delta, soglia, eventuale ADJ esistente.
    Ritorna dict (errore -> 'error', altrimenti dati)."""
    ip, _ = _get_printer_config()
    if not ip:
        return {"error": "IP stampante non configurato"}

    entries, diag = _dgfe_entries_with_diag(ip, day_date)
    if not diag or diag.get("status") not in ("ok", "ej_empty", "ej_no_blocks"):
        return {
            "error": f"Lettura DGFE non affidabile ({diag.get('status') if diag else 'unknown'})."
                     " Riprova fra qualche secondo o controlla la stampante."
        }

    dgfe_total = round(sum(float(e.get("totale_float", 0) or 0) for e in entries), 2)
    dgfe_count = len(entries)

    db_receipts = _db_receipts_for_day_no_adj(day_date)
    db_total = round(sum(float(r.total_amount or 0) for r in db_receipts), 2)
    db_count = len(db_receipts)

    delta = round(dgfe_total - db_total, 2)
    # Soglia in valore assoluto rispetto al DGFE; se DGFE = 0 trattiamo come "fuori soglia"
    if dgfe_total > 0:
        rel = abs(delta) / dgfe_total
    else:
        rel = 1.0 if abs(delta) > 0.01 else 0.0
    needs_strong = (rel > CORREGGI_DAY_THRESHOLD)

    adj_prog = _adj_progressivo_for_day(day_date)
    existing_adj = Receipt.query.filter_by(numero_progressivo=adj_prog).first()

    # Persisti la lettura DGFE del giorno in DB (questa funzione e' usata da 'Allinea a
    # DGFE' anteprima/reale e da 'Correggi'): cosi' anche un semplice check dai
    # Corrispettivi popola la riconciliazione vista nel Registro Scontrini.
    _persist_dgfe_reading(
        day_date, dgfe_total, dgfe_count, db_total=db_total,
        status="checked", notes="Lettura DGFE da Corrispettivi.",
    )

    return {
        "ok": True,
        "date": day_date.strftime("%Y-%m-%d"),
        "dgfe_total": dgfe_total,
        "dgfe_count": dgfe_count,
        "db_total": db_total,
        "db_count": db_count,
        "delta": delta,
        "relative": round(rel * 100, 2),
        "threshold_pct": round(CORREGGI_DAY_THRESHOLD * 100, 2),
        "needs_strong_verification": needs_strong,
        "dgfe_safe": (dgfe_count > 0),  # se 0, blocchiamo
        "existing_adj_total": float(existing_adj.total_amount) if existing_adj else None,
        "dgfe_entries": [
            {
                "progressivo": e.get("progressivo_raw"),
                "dataora": e["dataora_dt"].strftime("%H:%M") if e.get("dataora_dt") else "",
                "totale": float(e.get("totale_float", 0) or 0),
                "line_count": e.get("line_count", 0),
            }
            for e in entries
        ],
        "db_entries": [
            {
                "id": r.id,
                "numero_progressivo": str(r.numero_progressivo) if r.numero_progressivo else "",
                "dataora": r.created_at.strftime("%H:%M") if r.created_at else "",
                "totale": float(r.total_amount or 0),
                "voci_count": len(r.voci) if isinstance(r.voci, list) else 0,
            }
            for r in db_receipts
        ],
    }


def _set_day_alignment_adj(day_date, dgfe_total):
    """Allinea il totale fiscale del giorno in DB al totale DGFE in modo ADDITIVO
    e reversibile: crea/aggiorna/elimina la dummy ADJ-YYYYMMDD col delta, senza
    toccare gli scontrini reali (cliente/operatore/voci restano intatti).

    Risultato garantito: somma scontrini reali del giorno + ADJ == dgfe_total.
    Ritorna (action, delta) con action in {created, updated, deleted, noop}.
    Esegue il commit. In caso di errore solleva (gestire dal chiamante).
    """
    db_receipts = _db_receipts_for_day_no_adj(day_date)
    db_total = round(sum(float(r.total_amount or 0) for r in db_receipts), 2)
    delta = round(float(dgfe_total or 0.0) - db_total, 2)

    adj_prog = _adj_progressivo_for_day(day_date)
    existing = Receipt.query.filter_by(numero_progressivo=adj_prog).first()
    adj_dt = datetime.combine(day_date, datetime.min.time().replace(hour=23, minute=59))

    if abs(delta) < 0.01:
        # Gia' allineato: rimuovo eventuale ADJ residua di una correzione precedente.
        if existing:
            db.session.delete(existing)
            db.session.commit()
            return ("deleted", delta)
        return ("noop", delta)

    voci = [{
        "_dummy_adjustment": True,
        "reason": "Allineamento DGFE",
        "applied_at": datetime.now().isoformat(timespec='seconds'),
        "delta": delta
    }]
    if existing:
        existing.total_amount = delta
        existing.created_at = adj_dt
        existing.voci = voci
        flag_modified(existing, "voci")
        db.session.commit()
        return ("updated", delta)

    new_adj = Receipt(
        created_at=adj_dt,
        total_amount=delta,
        is_fiscale=True,
        voci=voci,
        cliente_id=None,
        operatore_id=None,
        numero_progressivo=adj_prog
    )
    db.session.add(new_adj)
    db.session.commit()
    return ("created", delta)


@cassa_bp.route('/cassa/correggi-day/preview', methods=['GET'])
def correggi_day_preview():
    """Anteprima per il bottone Correggi: confronto DGFE vs DB per un giorno.
    Owner-only. Query: ?day=YYYY-MM-DD"""
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        day_str = (request.args.get('day') or '').strip()
        if not day_str:
            return jsonify({"error": "Parametro day mancante"}), 400
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400

        result = _correggi_day_compute(day)
        if result.get("error"):
            return jsonify(result), 400
        return jsonify(result)
    except Exception as exc:
        try:
            current_app.logger.exception("correggi-day/preview: errore")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


@cassa_bp.route('/cassa/correggi-day/apply', methods=['POST'])
def correggi_day_apply():
    """Applica la correzione: crea/aggiorna/elimina la dummy ADJ-YYYYMMDD.
    Body: {date: 'YYYY-MM-DD', confirmed_delta?: float}
    Se la discrepanza supera la soglia, confirmed_delta DEVE corrispondere al delta calcolato.
    Owner-only."""
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        data = request.get_json(force=True, silent=True) or {}
        day_str = (data.get("date") or "").strip()
        if not day_str:
            return jsonify({"error": "Parametro date mancante"}), 400
        try:
            day = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400

        result = _correggi_day_compute(day)
        if result.get("error"):
            return jsonify(result), 400

        if not result["dgfe_safe"]:
            return jsonify({
                "error": "DGFE vuoto o non leggibile per quel giorno: correzione bloccata. "
                         "Verifica manualmente prima di procedere."
            }), 400

        delta = result["delta"]
        if result["needs_strong_verification"]:
            confirmed = data.get("confirmed_delta")
            if confirmed is None:
                return jsonify({
                    "error": "Discrepanza oltre soglia: serve conferma esplicita.",
                    "preview": result
                }), 409
            try:
                confirmed_f = round(float(confirmed), 2)
            except (TypeError, ValueError):
                return jsonify({"error": "confirmed_delta non numerico"}), 400
            if abs(confirmed_f - delta) > 0.01:
                return jsonify({
                    "error": f"confirmed_delta {confirmed_f} non corrisponde al delta calcolato {delta}",
                    "preview": result
                }), 409

        try:
            # Allineamento additivo: l'helper porta (scontrini reali + ADJ) == DGFE.
            action, _applied = _set_day_alignment_adj(day, result["dgfe_total"])
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error("correggi-day/apply: scrittura DB fallita: %s", str(exc))
            return jsonify({"error": f"Errore scrittura DB: {exc}"}), 500

        # PERSISTENZA (come 'Allinea a DGFE'): scrivi l'esito nel log di
        # riconciliazione cosi' la colonna DGFE del report resta valorizzata col
        # totale fiscale corretto anche dopo ricarica/logout. Senza questo, la
        # correzione modificava solo gli scontrini (dummy ADJ) ma la colonna
        # continuava a mostrare il vecchio valore (es. 0 dopo una doppia Z
        # mattutina), facendo sembrare che "Correggi" non avesse funzionato.
        try:
            bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
            if bi is not None:
                _set_reconciliation_entry(bi.id, day_str, {
                    "status": "fixed" if action in ("created", "updated", "deleted") else "ok",
                    "date": day_str,
                    "run_at": datetime.now().isoformat(timespec='seconds'),
                    "dgfe_count": result["dgfe_count"],
                    "db_count": result["db_count"],
                    "dgfe_total": result["dgfe_total"],
                    # Dopo l'allineamento il totale fiscale del giorno == DGFE.
                    "db_total": result["dgfe_total"],
                    "created_orphans": 0,
                    "suspicious_extras": [],
                    "notes": f"Corretto a DGFE da 'Correggi' (delta {delta:+.2f}).",
                })
        except Exception:
            current_app.logger.warning("correggi-day/apply: log recon non scritto per %s", day_str)

        # Ricalcola lo stato post-correzione
        post = _correggi_day_compute(day)
        return jsonify({
            "ok": True,
            "action": action,
            "applied_delta": delta,
            "post": post,
        })
    except Exception as exc:
        try:
            current_app.logger.exception("correggi-day/apply: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


@cassa_bp.route('/cassa/dgfe-align-range', methods=['POST'])
def dgfe_align_range():
    """Allinea (e SALVA) il totale fiscale del DB al DGFE per ogni giorno del range.

    E' l'azione dietro al pulsante "Carica DGFE": per ogni giorno legge il totale
    dalla DGFE della stampante RCH e, se diverso dal totale registrato in DB, crea/
    aggiorna la voce fiscale di allineamento ADJ-YYYYMMDD (additiva e reversibile)
    cosi' che (scontrini reali + ADJ) == DGFE. La voce e' is_fiscale=True quindi
    rientra nei corrispettivi del CRM: il dato corretto persiste fra le sessioni.

    Sicurezza fiscale: NON azzera giorni con DGFE vuoto/illeggibile (dgfe_safe=False)
    e salta i giorni futuri. Solo owner/admin, solo on-premise (stampante in LAN).
    Body JSON: {dateFrom, dateTo}
    """
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        ip, _ = _get_printer_config()
        if not ip:
            return jsonify({"error": "IP stampante non configurato"}), 400

        data = request.get_json(force=True, silent=True) or {}
        date_from = (data.get("dateFrom") or "").strip()
        date_to = (data.get("dateTo") or "").strip()
        # dry_run=True: legge la DGFE e calcola i delta SENZA scrivere nulla.
        # Serve ad alimentare il modal di conferma prima del salvataggio.
        dry_run = bool(data.get("dry_run", False))
        if not date_from or not date_to:
            return jsonify({"error": "Date non valide"}), 400
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400
        if d_to < d_from:
            return jsonify({"error": "dateTo precede dateFrom"}), 400
        if (d_to - d_from).days > 366:
            return jsonify({"error": "Range troppo ampio (max 366 giorni)"}), 400

        # Business per il log di riconciliazione (serve solo al salvataggio reale).
        bi = None
        if not dry_run:
            bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()

        today = date.today()
        results = []
        corrected = 0
        skipped_future = 0
        skipped_unsafe = 0
        cur = d_from
        while cur <= d_to:
            day_str = cur.strftime("%Y-%m-%d")
            # Non leggere/correggere il futuro
            if cur > today:
                skipped_future += 1
                results.append({"date": day_str, "status": "skipped_future"})
                cur += timedelta(days=1)
                continue

            comp = _correggi_day_compute(cur)
            if comp.get("error"):
                # Lettura DGFE inaffidabile: NON tocchiamo il DB, segnaliamo.
                results.append({
                    "date": day_str,
                    "status": "unreadable",
                    "error": comp.get("error"),
                })
                cur += timedelta(days=1)
                continue

            if not comp.get("dgfe_safe"):
                # DGFE vuoto (0 scontrini): non azzeriamo dati validi del DB.
                skipped_unsafe += 1
                results.append({
                    "date": day_str,
                    "status": "skipped_empty_dgfe",
                    "dgfe_total": comp.get("dgfe_total", 0.0),
                    "dgfe_count": comp.get("dgfe_count", 0),
                    "db_total": comp.get("db_total", 0.0),
                })
                cur += timedelta(days=1)
                continue

            if dry_run:
                # Anteprima: nessuna scrittura. Comunichiamo cosa cambierebbe.
                will_change = abs(comp["delta"]) >= 0.01
                if will_change:
                    corrected += 1
                results.append({
                    "date": day_str,
                    "status": "preview",
                    "will_change": will_change,
                    "delta": comp["delta"],
                    "dgfe_total": comp["dgfe_total"],
                    "dgfe_count": comp["dgfe_count"],
                    "db_total_before": comp["db_total"],
                })
                cur += timedelta(days=1)
                continue

            try:
                action, applied = _set_day_alignment_adj(cur, comp["dgfe_total"])
            except Exception as exc:
                try:
                    db.session.rollback()
                except Exception:
                    pass
                current_app.logger.error("dgfe-align-range: scrittura DB fallita su %s: %s", day_str, str(exc))
                results.append({"date": day_str, "status": "error", "error": str(exc)})
                cur += timedelta(days=1)
                continue

            if action in ("created", "updated", "deleted"):
                corrected += 1
            current_app.logger.info(
                "dgfe-align-range: %s action=%s delta=%.2f dgfe=%.2f",
                day_str, action, comp["delta"], comp["dgfe_total"]
            )
            # Persisti l'esito nel log di riconciliazione cosi' la colonna DGFE
            # resta valorizzata (verde) anche dopo ricarica/logout.
            if bi is not None:
                try:
                    _set_reconciliation_entry(bi.id, day_str, {
                        "status": "fixed" if action in ("created", "updated", "deleted") else "ok",
                        "date": day_str,
                        "run_at": datetime.now().isoformat(timespec='seconds'),
                        "dgfe_count": comp["dgfe_count"],
                        "db_count": comp["db_count"],
                        "dgfe_total": comp["dgfe_total"],
                        # Dopo l'allineamento il totale fiscale del giorno == DGFE.
                        "db_total": comp["dgfe_total"],
                        "created_orphans": 0,
                        "suspicious_extras": [],
                        "notes": f"Allineato a DGFE da 'Allinea a DGFE' (delta {comp['delta']:.2f})",
                    })
                except Exception:
                    current_app.logger.warning("dgfe-align-range: log recon non scritto per %s", day_str)
            results.append({
                "date": day_str,
                "status": "aligned",
                "action": action,
                "delta": comp["delta"],
                "dgfe_total": comp["dgfe_total"],
                "dgfe_count": comp["dgfe_count"],
                # Totale fiscale del giorno DOPO l'allineamento == DGFE.
                "db_total": comp["dgfe_total"],
            })
            cur += timedelta(days=1)

        return jsonify({
            "ok": True,
            "dry_run": dry_run,
            "processed": len(results),
            "corrected": corrected,
            "skipped_future": skipped_future,
            "skipped_empty_dgfe": skipped_unsafe,
            "results": results,
        })
    except Exception as exc:
        try:
            current_app.logger.exception("dgfe-align-range: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500


@cassa_bp.route('/cassa/reconcile-range', methods=['POST'])
def reconcile_range():
    """Riconciliazione retroattiva su un range di date (solo owner).
    Body JSON: {dateFrom: 'YYYY-MM-DD', dateTo: 'YYYY-MM-DD', only_pending: bool}
    Esegue reconcile_day per ogni giorno del range.
    Se only_pending=True (default), salta i giorni che hanno gia' una entry diversa da 'pending'/'error'.
    """
    try:
        user_id = session.get("user_id")
        user = db.session.get(User, user_id)
        if not user or getattr(user.ruolo, 'value', None) not in ('owner', 'admin'):
            return jsonify({"error": "Accesso riservato a owner/admin"}), 403

        data = request.get_json(force=True, silent=True) or {}
        date_from = (data.get("dateFrom") or "").strip()
        date_to = (data.get("dateTo") or "").strip()
        only_pending = bool(data.get("only_pending", True))
        if not date_from or not date_to:
            return jsonify({"error": "Date non valide"}), 400
        try:
            d_from = datetime.strptime(date_from, "%Y-%m-%d").date()
            d_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            return jsonify({"error": "Formato data non valido (YYYY-MM-DD)"}), 400
        if d_to < d_from:
            return jsonify({"error": "dateTo precede dateFrom"}), 400
        # Limite di sicurezza: max 366 giorni in un singolo range
        if (d_to - d_from).days > 366:
            return jsonify({"error": "Range troppo ampio (max 366 giorni)"}), 400

        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        if not bi:
            return jsonify({"error": "BusinessInfo non configurata"}), 400

        # Le letture DGFE sono ora persistite in DB (tabella dgfe_readings), nessuna
        # cartella file da verificare.
        log_pre = _load_reconciliation_log(bi.id)

        today = date.today()
        results = []
        skipped_future = 0
        skipped_already_done = 0
        cur = d_from
        while cur <= d_to:
            # Non riconciliare il futuro
            if cur > today:
                skipped_future += 1
                cur += timedelta(days=1)
                continue
            if only_pending:
                existing = log_pre.get(cur.strftime("%Y-%m-%d"))
                if existing and existing.get('status') in ('ok', 'fixed', 'discrepant'):
                    skipped_already_done += 1
                    cur += timedelta(days=1)
                    continue
            try:
                summary = reconcile_day(cur, bi)
                results.append({
                    "date": cur.strftime("%Y-%m-%d"),
                    "status": summary.get("status"),
                    "created_orphans": summary.get("created_orphans", 0),
                    "suspicious_extras": len(summary.get("suspicious_extras", []) or []),
                })
            except Exception as exc:
                current_app.logger.error("reconcile-range: errore su %s: %s", cur, str(exc))
                results.append({"date": cur.strftime("%Y-%m-%d"), "status": "error", "error": str(exc)})
            cur += timedelta(days=1)

        return jsonify({
            "ok": True,
            "processed": len(results),
            "skipped_future": skipped_future,
            "skipped_already_done": skipped_already_done,
            "results": results
        })
    except Exception as exc:
        try:
            current_app.logger.exception("reconcile-range: errore non gestito")
        except Exception:
            pass
        return jsonify({"error": f"Errore interno: {exc}"}), 500

@cassa_bp.route('/cassa/chiusura-dovuta', methods=['GET'])
def chiusura_dovuta():
    """Check rapido SOLO su DB (niente stampante) da chiamare all'APERTURA della cassa.

    Regola: se IERI era un giorno di chiusura configurato (BusinessInfo.closing_days) e
    NON risulta una chiusura fiscale (Z) registrata in `fiscal_closures` da allora in poi,
    segnala che va eseguita la Z prima di battere scontrini ("dopo un giorno di chiusura,
    fai la chiusura fiscale"). Se la Z risulta gia' fatta -> nessun avviso.

    Fail-safe: in caso di errore (es. tabella non ancora creata) NON disturba.
    """
    try:
        today = date.today()
        if not _previous_day_was_closure(today):
            return jsonify({"warning": False, "reason": "no_closure_day"})

        yesterday = today - timedelta(days=1)
        from appl.models import FiscalClosure
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        bid = bi.id if bi else 0
        z = db.session.query(FiscalClosure.id).filter(
            FiscalClosure.business_info_id == bid,
            FiscalClosure.giorno >= yesterday,
        ).first()
        if z is not None:
            return jsonify({"warning": False, "reason": "z_done"})

        return jsonify({
            "warning": True,
            "reason": "missing_z_after_closure",
            "message": ("Ieri il negozio era chiuso. Prima di battere scontrini esegui una "
                        "chiusura fiscale (Z)."),
        })
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.warning("chiusura-dovuta check fallito: %s", str(exc))
        except Exception:
            pass
        return jsonify({"warning": False, "reason": "error"})


@cassa_bp.route('/cassa/chiusura-giornaliera', methods=['POST'])
def chiusura_giornaliera():
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400

    url = _rch_url(ip, printer_model)
    headers = _rch_chiusura_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)

    xml_payload = """<?xml version="1.0" encoding="UTF-8"?>
<Service>
<cmd>&gt;C117/$0/*1/&amp;0/[0/]0/_0/@0</cmd>
<cmd>=C3</cmd>
<cmd>=C10</cmd>
<cmd>=C1</cmd>
</Service>"""

    try:
        resp = requests.post(url, data=xml_payload.encode("UTF-8"), headers=headers, timeout=45,
                             **rch_kwargs)
        body = resp.text or ""
        masked = re.sub(r'([A-Za-z0-9_\-]{8,})', '[REDACTED]', body)
        current_app.logger.debug("Chiusura giornaliera raw (masked): %s", masked[:4000])

        # Estrai eventuali codici di esito dal body (diverse forme che la RCH può usare)
        codes = set()
        codes.update(int(m) for m in re.findall(r'<(?:errCode|errorCode)>(\d+)</(?:errCode|errorCode)>', body))
        codes.update(int(m) for m in re.findall(r'<result[^>]*>(\d+)</result>', body))
        codes.update(int(m) for m in re.findall(r'Risultat[oi]\s*:\s*(\d+)', body, flags=re.IGNORECASE))

        # Se non troviamo nulla ma la risposta è 200, assumiamo OK
        if not codes and resp.status_code == 200:
            recon = _run_post_z_reconciliation()
            # Registra la Z nel registro chiusure in DB (storico persistente).
            _record_fiscal_closure(ip, printer_model, (recon or {}).get("dgfe_total"))
            return jsonify({"status": "ok", "code": 200, "message": "Chiusura giornaliera completata",
                            "reconciliation": recon}), 200

        # Considera 0 e 410 come non fatali (410 = nessuna richiesta codici pendente)
        non_fatali = {0, 200, 410}
        fatali = {c for c in codes if c not in non_fatali}

        if not fatali:
            # Anche se l'HTTP code non è 200, l'esito è ok: non propagare l'errore al client
            recon = _run_post_z_reconciliation()
            # Registra la Z nel registro chiusure in DB (storico persistente).
            _record_fiscal_closure(ip, printer_model, (recon or {}).get("dgfe_total"))
            return jsonify({"status": "ok", "code": 200, "message": "Chiusura giornaliera completata",
                            "reconciliation": recon}), 200

        # Errori reali: prova best-effort di sblocco (=C1) e segnala errore
        try:
            unlock = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            requests.post(url, data=unlock.encode("UTF-8"), headers=headers, timeout=8,
                          **rch_kwargs)
        except Exception:
            pass
        current_app.logger.error("Chiusura giornaliera: codici fatali rilevati: %s", sorted(fatali))
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502

    except Exception as e:
        current_app.logger.error("Errore durante la chiusura giornaliera (network): %s", str(e))
        # Best-effort di sblocco
        try:
            unlock = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            requests.post(url, data=unlock.encode("UTF-8"), headers=headers, timeout=8,
                          **rch_kwargs)
        except Exception:
            pass
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502
 
@cassa_bp.route('/cassa/api/dgfe', methods=['POST'])
def api_dgfe():
    data = request.get_json(force=True) or {}
    current_app.logger.debug("DEBUG /cassa/api/dgfe: %s", {"date": data.get("date"), "ip": ("[REDACTED]" if data.get("ip") else None)})

    ip = data.get("ip") if isinstance(data.get("ip"), str) else None
    date_str = data.get("date") if isinstance(data.get("date"), str) else None

    if not ip or not date_str:
        return jsonify({"error": "IP e data obbligatori"}), 400

    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return jsonify({"error": "Formato data non valido"}), 400

    if not re.match(r'^(?:\d{1,3}\.){3}\d{1,3}$', ip) or any(int(p) > 255 for p in ip.split('.')):
        return jsonify({"error": "IP non valido"}), 400

    _, printer_model = _get_printer_config()
    url = _rch_url(ip, printer_model)
    headers = _rch_dgfe_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    timeout_short = 5
    timeout_mid = 10

    try:
        with requests.Session() as s:
            s.headers.update({'Connection': 'close'})
            if 'verify' in rch_kwargs:
                s.verify = rch_kwargs['verify']
            xml_c3 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C3</cmd></Service>'
            s.post(url, data=xml_c3.encode('iso-8859-1'), headers=headers, timeout=timeout_short, allow_redirects=False)

            d = datetime.strptime(date_str, '%Y-%m-%d')
            d_str = d.strftime('%d%m%y')
            xml_c452 = '<?xml version="1.0" encoding="UTF-8"?><Service>' \
                       f'<cmd>=C452/$0/&{d_str}/[1/]9999</cmd>' \
                       '</Service>'
            resp2 = s.post(url, data=xml_c452.encode('iso-8859-1'), headers=headers, timeout=timeout_mid, allow_redirects=False)

            xml_c1 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
            s.post(url, data=xml_c1.encode('iso-8859-1'), headers=headers, timeout=timeout_short, allow_redirects=False)
    except requests.exceptions.RequestException as e:
        current_app.logger.error("Errore durante la richiesta DGFE (network): %s", str(e))
        return jsonify({"error": "Errore di comunicazione con la stampante fiscale."}), 502

    ej_match = re.search(r"<EJ[^>]*>(.*?)</EJ>", resp2.text, re.DOTALL)
    dgfe_text = ej_match.group(1).strip() if ej_match else ""

    scontrini = []
    for blocco in dgfe_text.split('\n\n'):
        lines = blocco.strip().splitlines()
        if not lines:
            continue
        progressivo = re.search(r'PROGR:\s*(\d+)', blocco)
        dataora = re.search(r'DATA:\s*(\d{2}/\d{2}/\d{4} \d{2}:\d{2})', blocco)
        servizi = re.findall(r'SERVIZIO:\s*(.*?)\s*PREZZO:\s*([\d,.]+)', blocco)
        metodo = re.search(r'PAGAMENTO:\s*(\w+)', blocco)
        totale = re.search(r'TOTALE:\s*([\d,.]+)', blocco)
        if progressivo and dataora and servizi and metodo and totale:
            scontrini.append({
                "progressivo": progressivo.group(1),
                "dataora": dataora.group(1),
                "servizi": [{"nome": s[0], "prezzo": s[1]} for s in servizi],
                "metodo": metodo.group(1),
                "totale": totale.group(1)
            })

    return jsonify({
        "dgfe_text": dgfe_text or "Nessun dato DGFE trovato.",
        "scontrini": scontrini,
        "raw_xml": resp2.text
    })
    
@cassa_bp.route('/cassa/api/myspia')
def api_myspia():
    try:
        # Limite: solo appuntamenti IN_ISTITUTO della data corrente
        today = datetime.now().date()
        day_start = datetime.combine(today, datetime.min.time())
        day_end = datetime.combine(today, datetime.max.time())

        apps = Appointment.query.filter(
            Appointment.stato == AppointmentStatus.IN_ISTITUTO,
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end,
            Appointment.is_cancelled_by_client == False
        ).options(selectinload(Appointment.client), selectinload(Appointment.service), selectinload(Appointment.operator)).all()

        # Raggruppa per cliente
        gruppi = {}
        for app in apps:
            if not app.client:
                continue
            key = (app.client.id, app.client.cliente_nome, app.client.cliente_cognome)
            gruppi.setdefault(key, []).append(app)

        result = []
        for (client_id, nome, cognome), apps in gruppi.items():
            result.append({
                "cliente_id": client_id,
                "cliente_nome": nome,
                "cliente_cognome": cognome,
                "ids": [a.id for a in apps],
                "appuntamenti": [
                    {
                        "servizio_nome": a.service.servizio_nome if a.service else "",
                        "durata": a._duration,
                        "prezzo": a.service.servizio_prezzo if a.service else 0,
                        "bg_color": a.colore or "#fff",
                        "font_color": a.colore_font or "#000",
                        "data": a.start_time.strftime("%Y-%m-%d") if a.start_time else "",
                        "start_time": a.start_time.strftime("%H:%M") if a.start_time else "",
                        "operator_nome": f"{a.operator.user_nome} {a.operator.user_cognome}" if a.operator else ""
                    } for a in apps
                ]
            })
        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("api_myspia error")
        return jsonify([]), 500

@cassa_bp.route('/cassa/annulla-ultimo-scontrino', methods=['POST'])
def annulla_ultimo_scontrino():
    ultimo = Receipt.query.filter(Receipt.is_fiscale == True).order_by(Receipt.created_at.desc()).first()
    if not ultimo or not ultimo.numero_progressivo:
        return jsonify({"error": "Nessuno scontrino fiscale da annullare"}), 404
    try:
        progressivo_str = str(ultimo.numero_progressivo)
        progressivo_sx, progressivo_dx = progressivo_str.split('-')
        progressivo_sx = progressivo_sx.zfill(4)
        progressivo_dx = str(int(progressivo_dx))
    except Exception as e:
        current_app.logger.error("Errore durante l'annullamento dell'ultimo scontrino: %s", str(e))
        return jsonify({"error": "Errore durante l'annullamento."}), 500
    data_scontrino = ultimo.created_at if ultimo.created_at else datetime.now()
    data_str = data_scontrino.strftime("%d%m%y")
    cmd = f"=k/&{data_str}/[{progressivo_sx}/]{progressivo_dx}"
    xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <Service>
    <cmd>{cmd}</cmd>
    </Service>"""
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    try:
        resp = requests.post(url, data=xml.encode("UTF-8"), headers=headers, timeout=10,
                             **rch_kwargs)
        numero_progressivo = None
        numero_z = None
        for cmd in ("=C453/$0", "=DGFE/REG"):
            payload_prog = f'''<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'''
            for _ in range(6):
                pytime.sleep(0.5)
                resp2 = requests.post(url, data=payload_prog.encode('utf-8'), headers=headers, timeout=5,
                                      **rch_kwargs)
                m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', resp2.text) or
                        re.search(r'<C453[^>]*>(\d+)</C453>', resp2.text) or
                        re.search(r'<result>(\d+)</result>', resp2.text))
                m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp2.text)
                if m_doc and m_z:
                    numero_progressivo = int(m_doc.group(1))
                    numero_z = int(m_z.group(1)) + 1
                    break
            if numero_progressivo is not None and numero_z is not None:
                break
        if numero_progressivo is None or numero_z is None:
            return jsonify({"error": "La stampante non ha restituito il progressivo"}), 500
        progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"
        voci_storno = []
        for v in ultimo.voci:
            voce = v.copy()
            try:
                voce['prezzo'] = -abs(float(voce.get('prezzo', 0)))
            except Exception:
                voce['prezzo'] = -0.0
            voce['nome'] = voce.get('nome') or voce.get('servizio_nome') or "STORNO"
            voci_storno.append(voce)
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = -abs(ultimo.total_amount),
            is_fiscale       = True,
            voci             = voci_storno,
            cliente_id       = ultimo.cliente_id,
            operatore_id     = ultimo.operatore_id,
            numero_progressivo = progressivo_completo
        )
        db.session.add(nuovo_receipt)
        db.session.commit()
    except Exception as e:
        current_app.logger.error("Errore di rete durante l'annullamento: %s", str(e))
        return jsonify({"error": "Errore di rete durante l'annullamento."}), 500
    raw = resp.text or ""
    masked = re.sub(r'([A-Za-z0-9_\-]{8,})', '[REDACTED]', raw)
    current_app.logger.debug("Annullo raw (masked): %s", masked[:2000])
    return jsonify({"status": "ok" if resp.status_code == 200 else "error", "code": resp.status_code, "progressivo": progressivo_completo}), resp.status_code

@cassa_bp.route('/cassa/api/myspia/dettagli', methods=['POST'])
def myspia_dettagli():
    try:
        data = request.get_json(force=True) or {}
        ids = data.get('ids') or []
        if isinstance(ids, str):
            ids = [x for x in re.split(r'[,\s]+', ids) if x]
        ids = [int(x) for x in ids if str(x).isdigit()]
        if not ids:
            return jsonify({"success": False, "error": "Nessun id appuntamento"}), 400

        apps = (Appointment.query
                .filter(Appointment.id.in_(ids),
                        Appointment.is_cancelled_by_client == False)
                .options(selectinload(Appointment.client),
                        selectinload(Appointment.service),
                        selectinload(Appointment.operator))
                .all())
        if not apps:
            return jsonify({"success": False, "error": "Appuntamenti non trovati"}), 404

        apps.sort(key=lambda a: a.start_time or datetime.min)

        cli = next((a.client for a in apps if a.client), None)
        op = next((a.operator for a in apps if a.operator), None)

        result = {
            "success": True,
            "cliente_id": cli.id if cli else None,
            "cliente_nome": (cli.cliente_nome if cli else "") or "",
            "cliente_cognome": (cli.cliente_cognome if cli else "") or "",
            "operatore_id": op.id if op else None,
            "operatore_nome": (op.user_nome if op else "") or "",
            "appuntamenti": []
        }

        for a in apps:
            s = a.service
            # Operatore specifico di questo appuntamento
            appt_op = a.operator
            result["appuntamenti"].append({
                "id": s.id if s else None,
                "nome": s.servizio_nome if s else "",
                "prezzo": s.servizio_prezzo if s else 0,
                "tag": s.servizio_tag if s else "",
                "sottocategoria": s.servizio_sottocategoria.nome if (s and s.servizio_sottocategoria) else "",
                "appointment_id": a.id,
                "operator_id": appt_op.id if appt_op else None,
                "operator_nome": appt_op.user_nome if appt_op else ""
            })

        return jsonify(result)
    except Exception as e:
        current_app.logger.exception("Errore /cassa/api/myspia/dettagli")
        return jsonify({"success": False, "error": "Errore interno"}), 500
    
# Helper per stornare uno scontrino specifico (del giorno corrente)
def stornare_scontrino_specifico(scontrino):
    if not scontrino.is_fiscale or not scontrino.numero_progressivo:
        return {"error": "Scontrino non fiscale o senza progressivo"}
    
    try:
        progressivo_str = str(scontrino.numero_progressivo)
        progressivo_sx, progressivo_dx = progressivo_str.split('-')
        progressivo_sx = progressivo_sx.zfill(4)
        progressivo_dx = str(int(progressivo_dx))
    except Exception as e:
        return {"error": "Progressivo non valido"}
    
    data_scontrino = scontrino.created_at.date() if scontrino.created_at else datetime.now().date()
    oggi = datetime.now().date()
    if data_scontrino != oggi:
        return {"error": "Storno possibile solo per scontrini del giorno corrente"}
    
    data_str = data_scontrino.strftime("%d%m%y")
    cmd = f"=k/&{data_str}/[{progressivo_sx}/]{progressivo_dx}"
    xml = f"""<?xml version="1.0" encoding="UTF-8" ?>
    <Service>
    <cmd>{cmd}</cmd>
    </Service>"""
    
    ip, printer_model = _get_printer_config()
    if not ip:
        return {"error": "IP stampante RCH non configurato"}
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    try:
        resp = requests.post(url, data=xml.encode("UTF-8"), headers=headers, timeout=30,
                             **rch_kwargs)
        current_app.logger.info("Risposta RCH storno: %s", resp.text)
        
        # Leggi nuovo progressivo post-storno (come in annulla_ultimo_scontrino)
        numero_progressivo = None
        numero_z = None
        for cmd in ("=C453/$0", "=DGFE/REG"):
            payload_prog = f'''<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'''
            for _ in range(6):
                pytime.sleep(0.5)
                resp2 = requests.post(url, data=payload_prog.encode('utf-8'), headers=headers, timeout=30,
                                      **rch_kwargs)
                m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', resp2.text) or
                         re.search(r'<C453[^>]*>(\d+)</C453>', resp2.text) or
                         re.search(r'<result>(\d+)</result>', resp2.text))
                m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp2.text)
                if m_doc and m_z:
                    numero_progressivo = int(m_doc.group(1))
                    numero_z = int(m_z.group(1)) + 1
                    break
            if numero_progressivo is not None and numero_z is not None:
                break
        
        if numero_progressivo is None or numero_z is None:
            return {"error": "Impossibile leggere progressivo post-storno"}
        
        progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"
        
        # Crea sempre scontrino di storno nel DB (come in annulla_ultimo_scontrino)
        voci_storno = []
        for v in scontrino.voci:
            voce = v.copy()
            try:
                voce['prezzo'] = -abs(float(voce.get('prezzo', 0)))
            except Exception:
                voce['prezzo'] = -0.0
            voce['nome'] = voce.get('nome') or voce.get('servizio_nome') or "STORNO"
            voci_storno.append(voce)
        
        nuovo_receipt = Receipt(
            created_at       = datetime.now(),
            total_amount     = -abs(scontrino.total_amount),
            is_fiscale       = True,
            voci             = voci_storno,
            cliente_id       = scontrino.cliente_id,
            operatore_id     = scontrino.operatore_id,
            numero_progressivo = progressivo_completo  # Sequenziale come DGFE
        )
        db.session.add(nuovo_receipt)
        db.session.commit()
        
        # Restituisci flag rch_ok basato su HTTP status (come in annulla_ultimo_scontrino)
        rch_ok = resp.status_code == 200
        return {"success": True, "progressivo_storno": progressivo_completo, "rch_ok": rch_ok}
    except Exception as e:
        current_app.logger.error("Errore storno specifico: %s", str(e))
        return {"error": "Errore durante lo storno"}
    
@cassa_bp.route('/api/user-role')
def api_user_role():
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)
    return jsonify({"role": user.ruolo.value if user else None})

@cassa_bp.route('/cassa/rch-status', methods=['GET'])
def rch_status():
    key = request.args.get('idempotency_key', '').strip()
    if not key:
        return jsonify({"error": "Missing idempotency_key"}), 400
    if key in IDEMPOTENCY_STORE:
        return jsonify({"done": True, **IDEMPOTENCY_STORE[key]}), 200
    if key in RCH_PENDING:
        return jsonify({"done": False, "pending": True, "retry_after": 3}), 200
    return jsonify({"error": "Not found"}), 404

def _dgfe_entries_with_diag(ip: str, day: date):
    """Come _dgfe_entries_for_date ma ritorna (entries, diag) con info diagnostica.
    diag e' un dict con: status, http_status, body_len, ej_found, blocks, parsed_entries,
    parse_failures, error, body_excerpt, printer_model, url.
    """
    diag = {
        "status": "unknown",
        "http_status": None,
        "body_len": 0,
        "ej_found": False,
        "blocks": 0,
        "parsed_entries": 0,
        "parse_failures": 0,
        "error": None,
        "body_excerpt": "",
        "printer_model": None,
        "url": None,
    }
    resp = None
    try:
        _, printer_model = _get_printer_config()
        diag["printer_model"] = printer_model
        url = _rch_url(ip, printer_model)
        diag["url"] = url
        headers = _rch_dgfe_headers(printer_model)
        rch_kwargs = _rch_request_kwargs(printer_model)
        try:
            current_app.logger.info("DGFE read: ip=%s model=%s day=%s", ip, printer_model, day)
        except Exception:
            pass
        with requests.Session() as s:
            s.headers.update({'Connection': 'close'})
            if 'verify' in rch_kwargs:
                s.verify = rch_kwargs['verify']
            xml_c3 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C3</cmd></Service>'
            s.post(url, data=xml_c3.encode('iso-8859-1'), headers=headers, timeout=5, allow_redirects=False)
            d_str = day.strftime('%d%m%y')
            xml_c452 = '<?xml version="1.0" encoding="UTF-8"?><Service>' \
                       f'<cmd>=C452/$0/&{d_str}/[1/]9999</cmd>' \
                       '</Service>'
            resp = s.post(url, data=xml_c452.encode('iso-8859-1'), headers=headers, timeout=15, allow_redirects=False)
            # Unlock (best-effort)
            try:
                xml_c1 = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C1</cmd></Service>'
                s.post(url, data=xml_c1.encode('iso-8859-1'), headers=headers, timeout=4, allow_redirects=False)
            except Exception:
                pass
    except requests.exceptions.RequestException as exc:
        diag["status"] = "network_error"
        diag["error"] = str(exc)
        try:
            current_app.logger.warning("DGFE read network error per %s: %s", day, str(exc))
        except Exception:
            pass
        return [], diag
    except Exception as exc:
        diag["status"] = "unexpected_error"
        diag["error"] = str(exc)
        try:
            current_app.logger.exception("DGFE read errore inatteso per %s", day)
        except Exception:
            pass
        return [], diag

    diag["http_status"] = getattr(resp, 'status_code', None)
    body = resp.text or ""
    diag["body_len"] = len(body)
    diag["body_excerpt"] = body[:4000]

    try:
        current_app.logger.info(
            "DGFE %s body (first 2000 chars): %s",
            day, body[:2000].replace('\n', '\\n')
        )
    except Exception:
        pass

    ej_match = re.search(r"<EJ[^>]*>(.*?)</EJ>", body, re.DOTALL)
    if not ej_match:
        diag["status"] = "no_ej_block"
        try:
            current_app.logger.warning(
                "DGFE %s: nessun <EJ> nel body (http=%s len=%s)",
                day, diag["http_status"], diag["body_len"]
            )
        except Exception:
            pass
        return [], diag

    diag["ej_found"] = True
    dgfe_text = ej_match.group(1).strip()
    if not dgfe_text:
        diag["status"] = "ej_empty"
        try:
            current_app.logger.info("DGFE %s: <EJ> presente ma vuoto", day)
        except Exception:
            pass
        return [], diag

    # Parser specifico per il formato DGFE della RCH Print 3.0 RT.
    # Ogni scontrino fiscale e' delimitato da:
    #   "DOCUMENTO COMMERCIALE" ... "DOCUMENTO N. ZZZZ-NNNN"
    # All'interno trova:
    #   "TOTALE COMPLESSIVO    13,00"
    #   "DD-MM-YYYY HH:MM"
    receipt_pattern = re.compile(
        r'DOCUMENTO\s+COMMERCIALE'         # marker inizio scontrino
        r'(?P<body>.*?)'                    # corpo (lazy)
        r'DOCUMENTO\s+N\.\s+(?P<z>\d+)-(?P<n>\d+)',  # marker fine + progressivo Z-DOC
        re.DOTALL
    )

    matches = list(receipt_pattern.finditer(dgfe_text))
    diag["blocks"] = len(matches)

    entries = []
    parse_failures = 0
    for match in matches:
        body = match.group('body') or ""
        z_num = match.group('z')
        n_num = match.group('n')
        progressivo = f"{z_num}-{n_num}"

        # TOTALE COMPLESSIVO (solo dei DOCUMENTI COMMERCIALI; i DOCUMENTI GESTIONALI
        # di chiusura giornaliera usano "VENDITE" / "GRAN TOTALE" e sono esclusi dal
        # pattern perche' iniziano con "DOCUMENTO GESTIONALE", non "DOCUMENTO COMMERCIALE")
        # Supporta anche segno negativo eventuale (es. "-24,00") che alcune RCH
        # stampano per i documenti di annullamento/reso.
        m_tot = re.search(r'TOTALE\s+COMPLESSIVO\s+(-?[\d.,]+)', body)
        if not m_tot:
            parse_failures += 1
            continue
        raw_tot = m_tot.group(1).strip()
        sign = -1 if raw_tot.startswith('-') else 1
        raw_tot_abs = raw_tot.lstrip('-').strip()
        try:
            # Formato italiano: "1.006,00" -> 1006.00
            tot_float = sign * float(raw_tot_abs.replace('.', '').replace(',', '.'))
        except Exception:
            try:
                tot_float = sign * float(raw_tot_abs)
            except Exception:
                parse_failures += 1
                continue

        # I documenti di ANNULLAMENTO/RESO (emessi dalla RCH con il comando =k oppure =r)
        # appaiono nel DGFE come "DOCUMENTO COMMERCIALE / EMESSO PER ANNULLAMENTO" (o RESO).
        # Il "TOTALE COMPLESSIVO" e' tipicamente stampato come valore positivo perche' rappresenta
        # l'importo del documento; fiscalmente pero' e' un rimborso e nel DB SunBooking viene
        # salvato come total_amount negativo. Forziamo il segno negativo per allineare la somma
        # DGFE alla somma DB ed evitare falsi delta nella riconciliazione e nel modal Corrispettivi.
        is_storno = bool(re.search(r'EMESSO\s+PER\s+(?:ANNULLAMENTO|RESO)', body, re.IGNORECASE))
        if is_storno and tot_float > 0:
            tot_float = -tot_float
        tot_float = round(tot_float, 2)

        # Data/ora nel formato "04-05-2026 09:04"
        m_dt = re.search(r'(\d{2})-(\d{2})-(\d{4})\s+(\d{2}):(\d{2})', body)
        dt = None
        if m_dt:
            try:
                dt = datetime(
                    int(m_dt.group(3)), int(m_dt.group(2)), int(m_dt.group(1)),
                    int(m_dt.group(4)), int(m_dt.group(5))
                )
            except ValueError:
                dt = None
        if dt is None:
            dt = datetime.combine(day, datetime.min.time())

        # Numero voci: conto le righe "<IVA>%   <prezzo>" prima del primo "TOTALE COMPLESSIVO".
        # In questo formato ogni servizio ha una riga "Nome servizio    22%   13,00"
        body_before_total = body[:m_tot.start()] if m_tot else body
        line_count = len(re.findall(r'\b\d+%\s+[\d.,]+', body_before_total))

        entries.append({
            "dataora_dt": dt,
            "totale_float": tot_float,
            "progressivo_raw": progressivo,  # formato "ZZZZ-NNNN"
            "line_count": line_count,
            "raw": body[:300],
        })

    entries.sort(key=lambda e: e["dataora_dt"])
    diag["parsed_entries"] = len(entries)
    diag["parse_failures"] = parse_failures
    if entries:
        diag["status"] = "ok"
    elif matches:
        diag["status"] = "parse_failed_all"
    else:
        diag["status"] = "ej_no_blocks"

    try:
        current_app.logger.info(
            "DGFE %s: status=%s receipts=%d parse_failures=%d body_len=%d total_sum=%.2f",
            day, diag["status"], diag["parsed_entries"],
            diag["parse_failures"], diag["body_len"],
            sum(e["totale_float"] for e in entries)
        )
    except Exception:
        pass

    return entries, diag


def _dgfe_entries_for_date(ip: str, day: date):
    """Wrapper retro-compatibile: ritorna solo le entries (vuote in caso di qualunque errore)."""
    entries, _ = _dgfe_entries_with_diag(ip, day)
    return entries

def _max_progressivo_doc_in_db_today():
    """Massimo numero documento (parte dopo il '-') tra i Receipt fiscali odierni.
    Ritorna 0 se nessun Receipt presente."""
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    receipts_today = Receipt.query.filter(
        Receipt.created_at >= today_start,
        Receipt.created_at <= today_end,
        Receipt.is_fiscale == True
    ).all()
    max_doc = 0
    for r in receipts_today:
        try:
            parts = str(r.numero_progressivo).split('-')
            if len(parts) == 2:
                n = int(parts[1])
                if n > max_doc:
                    max_doc = n
        except Exception:
            pass
    return max_doc

def _try_lazy_recover(voci, cliente_id, operatore_id, expected_total,
                      expected_line_count, ip, printer_model):
    """Tenta di recuperare uno scontrino in caso di risposta ambigua dalla stampante.
    - Legge lastDocF/lastZ
    - Se progressivo > max in DB oggi e il DGFE conferma totale (e linee, se disponibili),
      scrive Receipt in DB, marca Appointment.PAGATO e ritorna progressivo_completo.
    - Altrimenti ritorna None (il chiamante decidera' se mettere in pending).
    Nessuna ristampa, nessun comando di scrittura inviato alla stampante.
    """
    try:
        url = _rch_url(ip, printer_model)
        headers = _rch_headers(printer_model)
        rch_kwargs = _rch_request_kwargs(printer_model)

        numero_progressivo, numero_z = _read_progressivo(url, headers, rch_kwargs,
                                                         max_attempts=10, sleep_s=0.5)
        if numero_progressivo is None or numero_z is None:
            return None

        progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"

        # Se gia' presente in DB con questo progressivo, non duplicare
        if Receipt.query.filter_by(numero_progressivo=progressivo_completo).first():
            return None

        # Verifica che il progressivo letto sia effettivamente "nuovo" rispetto a DB
        if numero_progressivo <= _max_progressivo_doc_in_db_today():
            return None

        # Conferma DGFE: stesso totale (e numero linee se disponibile)
        entries = _dgfe_entries_for_date(ip, date.today())
        if not entries:
            return None
        matched = None
        try:
            exp_total = round(float(expected_total), 2)
        except Exception:
            return None
        for e in reversed(entries):
            if abs(e["totale_float"] - exp_total) < 0.01:
                if expected_line_count and expected_line_count > 0 and e.get("line_count") is not None:
                    if e["line_count"] != expected_line_count:
                        continue
                matched = e
                break
        if not matched:
            return None

        nuovo_receipt = Receipt(
            created_at=datetime.now(),
            total_amount=exp_total,
            is_fiscale=True,
            voci=voci or [],
            cliente_id=cliente_id,
            operatore_id=operatore_id,
            numero_progressivo=progressivo_completo
        )
        db.session.add(nuovo_receipt)
        db.session.commit()

        ids_pagati = [v.get("appointment_id") for v in (voci or []) if v.get("appointment_id")]
        if ids_pagati:
            Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
            )
            db.session.commit()

        return progressivo_completo
    except Exception as exc:
        try:
            current_app.logger.warning("_try_lazy_recover: errore %s", str(exc))
        except Exception:
            pass
        return None

# ============================================================
# RECONCILIATION DGFE <-> DB (persistita IN DATABASE, tabella dgfe_readings)
# ============================================================
# La lettura DGFE riconciliata per ogni giorno e' salvata in DB (modello
# DgfeReading), NON piu' su file JSON. Una riga per (negozio, giorno). Il campo
# `payload` conserva il dict completo dell'esito per retro-compatibilita' con i
# consumatori (badge registro scontrini + colonna DGFE nei Corrispettivi), che
# continuano a ricevere la stessa forma {date_str: entry_dict}.

def _recon_bid(business_info_id):
    """Normalizza il business_info_id (None -> 0) come chiave del negozio."""
    try:
        return int(business_info_id) if business_info_id is not None else 0
    except Exception:
        return 0

def _load_reconciliation_log(business_info_id):
    """Legge da DB tutte le letture DGFE del negozio. Ritorna dict
    {date_str: entry_dict} per compatibilita' col vecchio formato.
    Non solleva mai eccezioni (es. se la tabella non esiste ancora -> {})."""
    try:
        from appl.models import DgfeReading
        bid = _recon_bid(business_info_id)
        rows = DgfeReading.query.filter_by(business_info_id=bid).all()
        out = {}
        for r in rows:
            key = r.giorno.strftime('%Y-%m-%d') if r.giorno else None
            entry = None
            if r.payload:
                try:
                    entry = json.loads(r.payload)
                except Exception:
                    entry = None
            if not isinstance(entry, dict):
                # Fallback dalle colonne dedicate se il payload manca/corrotto.
                entry = {
                    "date": key,
                    "dgfe_total": r.dgfe_total,
                    "dgfe_count": r.dgfe_count,
                    "status": r.status,
                    "run_at": r.run_at.isoformat(timespec='seconds') if r.run_at else None,
                }
            if key:
                out[key] = entry
        return out
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.warning("DgfeReading: load fallita: %s", str(exc))
        except Exception:
            pass
        return {}

def _set_reconciliation_entry(business_info_id, day_str, entry):
    """UPSERT in DB della lettura DGFE riconciliata del giorno (tabella dgfe_readings).

    ROBUSTEZZA FISCALE (anti-azzeramento): non degrada MAI un giorno gia'
    verificato col DGFE (dgfe_count>0 e totale>0) verso una lettura vuota
    (dgfe_count==0). Capita con la doppia chiusura Z mattutina a 0 (la 2a Z ha
    gran totale 0) o quando la stampante e' occupata: la lettura torna vuota ma
    il dato fiscale gia' acquisito NON deve essere sovrascritto/azzerato. Le
    correzioni reali ('Correggi'/'Allinea a DGFE') leggono sempre scontrini
    (dgfe_count>0) quindi non sono mai bloccate da questo guard.

    Best-effort: non solleva mai eccezioni al chiamante (se la tabella non esiste
    ancora, semplicemente non persiste; il flusso Z non si interrompe).
    """
    try:
        from appl.models import DgfeReading
        bid = _recon_bid(business_info_id)
        try:
            giorno = datetime.strptime(day_str, '%Y-%m-%d').date()
        except Exception:
            return

        existing = DgfeReading.query.filter_by(business_info_id=bid, giorno=giorno).first()

        # Guard anti-azzeramento.
        if existing is not None:
            try:
                prev_cnt = int(existing.dgfe_count or 0)
                prev_tot = abs(float(existing.dgfe_total or 0.0))
                new_cnt = int(entry.get("dgfe_count") or 0)
            except (TypeError, ValueError):
                prev_cnt = prev_tot = new_cnt = 0
            if prev_cnt > 0 and prev_tot > 0.01 and new_cnt == 0:
                try:
                    current_app.logger.warning(
                        "DgfeReading %s: ignoro lettura DGFE vuota (new dgfe_count=0, "
                        "status=%s) per non azzerare il dato gia' verificato "
                        "(prev dgfe_count=%s tot=%.2f).",
                        day_str, entry.get("status"), prev_cnt, prev_tot
                    )
                except Exception:
                    pass
                return

        run_at_dt = None
        ra = entry.get('run_at')
        if ra:
            try:
                run_at_dt = datetime.fromisoformat(ra)
            except Exception:
                run_at_dt = None

        try:
            dgfe_total_v = float(entry.get('dgfe_total')) if entry.get('dgfe_total') is not None else None
        except (TypeError, ValueError):
            dgfe_total_v = None
        try:
            dgfe_count_v = int(entry.get('dgfe_count') or 0)
        except (TypeError, ValueError):
            dgfe_count_v = 0

        payload = json.dumps(entry, ensure_ascii=False, default=str)
        status_v = (entry.get('status') or '')[:32] or None

        if existing is None:
            existing = DgfeReading(business_info_id=bid, giorno=giorno)
            db.session.add(existing)
        existing.dgfe_total = dgfe_total_v
        existing.dgfe_count = dgfe_count_v
        existing.status = status_v
        existing.run_at = run_at_dt
        existing.payload = payload
        existing.updated_at = datetime.now()
        db.session.commit()
    except Exception as exc:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.error("DgfeReading: UPSERT FALLITO per %s: %s", day_str, str(exc))
        except Exception:
            pass

def _persist_dgfe_reading(day_date, dgfe_total, dgfe_count, db_total=None,
                          status="checked", notes=None):
    """Persiste in DB la lettura DGFE di un giorno, da QUALSIASI sorgente: semplice
    'Carica DGFE'/check, anteprima, allineamento, chiusura Z. Cosi' il badge del
    Registro Scontrini riflette sempre l'ultima lettura. Best-effort, mai solleva.

    Rispetta il guard anti-azzeramento di `_set_reconciliation_entry` (non sovrascrive
    un giorno gia' verificato con una lettura vuota)."""
    try:
        bi = BusinessInfo.query.filter_by(is_deleted=False).order_by(BusinessInfo.id.asc()).first()
        if bi is None:
            return
        day_str = day_date.strftime("%Y-%m-%d")
        entry = {
            "status": status,
            "date": day_str,
            "run_at": datetime.now().isoformat(timespec='seconds'),
            "dgfe_count": dgfe_count,
            "dgfe_total": dgfe_total,
        }
        if db_total is not None:
            entry["db_total"] = db_total
        if notes:
            entry["notes"] = notes
        _set_reconciliation_entry(bi.id, day_str, entry)
    except Exception:
        try:
            current_app.logger.warning("persistenza lettura DGFE fallita per %s", day_date)
        except Exception:
            pass

def reconcile_day(day_date, business_info):
    """Riconcilia il giorno con il DGFE della stampante e crea Receipt orfani per le
    entry mancanti. Persiste un'entry nel log JSON per-tenant.
    business_info: oggetto BusinessInfo (id, business_name, city, printer_ip, printer_model).
    Ritorna dict riassuntivo: {status, dgfe_count, db_count, created_orphans, suspicious_extras, run_at}.
    """
    started_at = datetime.now()
    bid = getattr(business_info, 'id', None)
    ip = getattr(business_info, 'printer_ip', None)
    raw_model = getattr(business_info, 'printer_model', None)
    printer_model = _normalize_model(raw_model)

    summary = {
        "status": "error",
        "business_info_id": bid,
        "business_name": getattr(business_info, 'business_name', None),
        "city": getattr(business_info, 'city', None),
        "printer_ip": ip,
        "printer_model": printer_model,
        "date": day_date.strftime("%Y-%m-%d"),
        "run_at": started_at.isoformat(timespec='seconds'),
        "dgfe_count": 0,
        "db_count": 0,
        "dgfe_total": 0.0,
        "db_total": 0.0,
        "created_orphans": 0,
        "suspicious_extras": [],
        "dgfe_diagnostic": None,
        "notes": ""
    }

    if not ip:
        summary["notes"] = "IP stampante non configurato"
        try:
            _set_reconciliation_entry(bid, summary["date"], summary)
        except Exception:
            pass
        return summary

    try:
        dgfe_entries, dgfe_diag = _dgfe_entries_with_diag(ip, day_date)
        dgfe_entries = dgfe_entries or []
    except Exception as exc:
        summary["notes"] = f"Errore lettura DGFE: {exc}"
        try:
            _set_reconciliation_entry(bid, summary["date"], summary)
        except Exception:
            pass
        return summary

    summary["dgfe_diagnostic"] = dgfe_diag
    # Se la lettura DGFE non e' "ok", non possiamo pretendere riconciliazione affidabile.
    # In particolare per network_error / no_ej_block la status diventa "error" con nota.
    dgfe_status = dgfe_diag.get("status") if dgfe_diag else None
    if dgfe_status in ("network_error", "unexpected_error", "no_ej_block", "parse_failed_all"):
        summary["notes"] = (
            f"Lettura DGFE fallita ({dgfe_status}): "
            f"http={dgfe_diag.get('http_status')} body_len={dgfe_diag.get('body_len')}"
            + (f" err={dgfe_diag.get('error')}" if dgfe_diag.get('error') else "")
        )
        summary["status"] = "error"
        try:
            _set_reconciliation_entry(bid, summary["date"], summary)
        except Exception:
            pass
        return summary

    summary["dgfe_count"] = len(dgfe_entries)
    summary["dgfe_total"] = round(sum(float(e.get("totale_float", 0.0)) for e in dgfe_entries), 2)

    day_start = datetime.combine(day_date, datetime.min.time())
    day_end = datetime.combine(day_date, datetime.max.time())
    receipts = Receipt.query.filter(
        Receipt.created_at >= day_start,
        Receipt.created_at <= day_end,
        Receipt.is_fiscale == True
    ).all()
    summary["db_count"] = len(receipts)
    summary["db_total"] = round(sum(float(r.total_amount or 0) for r in receipts), 2)

    # Match DGFE -> DB per totale (+ line_count se disponibile)
    db_used = set()
    orphans_created = 0
    for e in dgfe_entries:
        try:
            tot_e = round(float(e.get("totale_float", 0)), 2)
        except Exception:
            continue
        line_e = e.get("line_count")
        matched_idx = None
        for idx, r in enumerate(receipts):
            if idx in db_used:
                continue
            try:
                tot_r = round(float(r.total_amount or 0), 2)
            except Exception:
                continue
            if abs(tot_r - tot_e) >= 0.01:
                continue
            if line_e and r.voci is not None:
                voci_list = r.voci if isinstance(r.voci, list) else []
                if voci_list and len(voci_list) != line_e:
                    continue
            matched_idx = idx
            break
        if matched_idx is not None:
            db_used.add(matched_idx)
            continue

        # Nessun match: crea Receipt orfano con created_at = data DGFE (non oggi)
        try:
            dt = e.get("dataora_dt") or datetime.combine(day_date, datetime.min.time())
            prog_raw = e.get("progressivo_raw") or ""
            # Per la RCH Print 3.0 RT progressivo_raw e' gia' "ZZZZ-NNNN", uguale
            # al formato che usa il flusso normale (cassa.py:849). Usalo direttamente.
            if re.match(r'^\d+-\d+$', prog_raw):
                prog_str = prog_raw
            else:
                try:
                    prog_n = int(prog_raw)
                    prog_str = f"DGFE-{prog_n:04d}"
                except Exception:
                    prog_str = f"DGFE-{prog_raw}" if prog_raw else "DGFE-?"

            # Se un Receipt con quel progressivo esiste gia' (es. flusso normale),
            # NON duplicare: e' lo stesso scontrino, gia' tracciato, ma con totale
            # diverso (raro). Salta — sara' segnalato come "extra DB" nella tabella.
            existing_same_prog = Receipt.query.filter_by(numero_progressivo=prog_str).first()
            if existing_same_prog:
                continue

            orphan = Receipt(
                created_at=dt,
                total_amount=tot_e,
                is_fiscale=True,
                voci=[],
                cliente_id=None,
                operatore_id=None,
                numero_progressivo=prog_str
            )
            db.session.add(orphan)
            db.session.commit()
            orphans_created += 1
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error("reconcile_day: errore creazione orfano: %s", str(exc))

    summary["created_orphans"] = orphans_created

    # Receipt extra (in DB ma non in DGFE) -> log soltanto, niente azione
    extras = []
    for idx, r in enumerate(receipts):
        if idx in db_used:
            continue
        extras.append({
            "id": r.id,
            "numero_progressivo": str(r.numero_progressivo),
            "total_amount": float(r.total_amount or 0),
            "created_at": r.created_at.isoformat(timespec='seconds') if r.created_at else None
        })
    summary["suspicious_extras"] = extras

    if orphans_created == 0 and not extras:
        summary["status"] = "ok"
    elif orphans_created > 0 and not extras:
        summary["status"] = "fixed"
    else:
        summary["status"] = "discrepant"

    # ALLINEAMENTO AUTOMATICO AL DGFE (chiusura fiscale serale).
    # Dopo aver creato gli orfani mancanti, porta in modo ADDITIVO e reversibile
    # il totale fiscale del giorno in DB a coincidere col totale DGFE, scrivendo
    # la dummy ADJ-YYYYMMDD col residuo. Cosi' il dato del registro scontrini in
    # DB resta permanentemente allineato al dato fiscale della DGFE.
    # SICUREZZA: solo se la DGFE ha almeno 1 scontrino (dgfe_count > 0), per non
    # azzerare un giorno su una lettura vuota/ambigua.
    summary["alignment_action"] = "skipped"
    summary["alignment_delta"] = 0.0
    if summary["dgfe_count"] > 0:
        try:
            action, applied = _set_day_alignment_adj(day_date, summary["dgfe_total"])
            summary["alignment_action"] = action
            summary["alignment_delta"] = applied
            # Totale fiscale effettivo del giorno (scontrini reali + ADJ) == DGFE.
            summary["db_total"] = summary["dgfe_total"]
            if action in ("created", "updated"):
                summary["notes"] = (
                    (summary.get("notes") or "")
                    + f" Allineamento DGFE applicato (delta {applied:+.2f})."
                ).strip()
        except Exception as exc:
            try:
                db.session.rollback()
            except Exception:
                pass
            current_app.logger.error("reconcile_day: allineamento DGFE fallito: %s", str(exc))
            summary["alignment_action"] = "error"
            summary["notes"] = (
                (summary.get("notes") or "") + f" Allineamento DGFE fallito: {exc}."
            ).strip()

    try:
        _set_reconciliation_entry(bid, summary["date"], summary)
    except Exception as exc:
        current_app.logger.error("reconcile_day: scrittura log fallita: %s", str(exc))
        summary["notes"] = f"Log non scritto: {exc}"

    return summary

@cassa_bp.route('/cassa/rch-retry', methods=['POST'])
def rch_retry():
    """
    Retry NON ristampa:
    - Legge tutto l'EJ del giorno (DGFE) senza limiti temporali
    - Match primario: ultimo scontrino con stesso totale (±0.01) e medesimo numero linee (se disponibile)
    - Match secondario: ultimo progressivo nuovo non presente nel DB (se il totale non coincide)
    - Registra il receipt se trovato, altrimenti resta in pending
    """
    data = request.get_json(force=True) or {}
    key = (data.get("idempotency_key") or "").strip()
    if not key:
        return jsonify({"error": "Missing idempotency_key"}), 400
    if key in IDEMPOTENCY_STORE:
        return jsonify(IDEMPOTENCY_STORE[key]), 200

    pending = RCH_PENDING.get(key)
    if not pending:
        return jsonify({"error": "Pending non trovato"}), 404

    ip, _ = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante RCH non configurato"}), 400

    try:
        expected_total = float(pending.get("expected_total")) \
            if pending.get("expected_total") is not None \
            else round(sum(float(v.get("prezzo", 0)) for v in pending.get("voci", [])), 2)
    except Exception:
        expected_total = round(sum(float(v.get("prezzo", 0)) for v in pending.get("voci", [])), 2)
    expected_total = round(expected_total, 2)
    expected_line_count = int(pending.get("line_count") or len(pending.get("voci", [])) or 0)

    # Leggi EJ completo del giorno
    entries = _dgfe_entries_for_date(ip, date.today())
    if not entries:
        return jsonify({"pending": True, "retry_after": 5}), 202

    # Match primario: stesso totale e (se disponibile) stesso numero linee
    matched = None
    for e in reversed(entries):
        if abs(e["totale_float"] - expected_total) < 0.01:
            if expected_line_count > 0 and e.get("line_count") is not None:
                if e["line_count"] != expected_line_count:
                    continue
            matched = e
            break

    # Match secondario: progressivo nuovo (se primario fallito)
    if not matched:
        # progressivi già in DB (solo fiscali)
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_end = datetime.combine(date.today(), datetime.max.time())
        receipts_today = Receipt.query.filter(
            Receipt.created_at >= today_start,
            Receipt.created_at <= today_end,
            Receipt.is_fiscale == True
        ).all()
        existing_prog = set()
        for r in receipts_today:
            try:
                existing_prog.add(str(r.numero_progressivo).strip())
            except Exception:
                pass
        # prendi l'ultimo blocco con progressivo_raw non vuoto
        for e in reversed(entries):
            if e.get("progressivo_raw"):
                # Non possiamo ricostruire Z qui, usiamo conferma via lastDocF dopo
                matched = e
                break

    if not matched:
        return jsonify({"pending": True, "retry_after": 6}), 202

    # Lettura progressivo ufficiale lastDocF/lastZ
    ip, printer_model = _get_printer_config()
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    numero_progressivo = None
    numero_z = None
    for cmd in ("=C453/$0", "=DGFE/REG"):
        payload_prog = f'''<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'''
        for _ in range(8):
            pytime.sleep(0.5)
            try:
                resp = requests.post(url, data=payload_prog.encode('utf-8'), headers=headers, timeout=6,
                                     **rch_kwargs)
            except Exception:
                continue
            m_doc = (re.search(r'<lastDocF>(\d+)</lastDocF>', resp.text) or
                     re.search(r'<C453[^>]*>(\d+)</C453>', resp.text) or
                     re.search(r'<result>(\d+)</result>', resp.text))
            m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp.text)
            if m_doc and m_z:
                try:
                    numero_progressivo = int(m_doc.group(1))
                    numero_z = int(m_z.group(1)) + 1
                except Exception:
                    numero_progressivo = None
                    numero_z = None
                break
        if numero_progressivo is not None and numero_z is not None:
            break

    if numero_progressivo is None or numero_z is None:
        return jsonify({"pending": True, "retry_after": 8}), 202

    progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"
    total_amount = round(sum(float(v.get("prezzo", 0)) for v in pending.get("voci", [])), 2)

    nuovo_receipt = Receipt(
        created_at         = datetime.now(),
        total_amount       = total_amount,
        is_fiscale         = True,
        voci               = pending.get("voci", []),
        cliente_id         = pending.get("cliente_id"),
        operatore_id       = pending.get("operatore_id"),
        numero_progressivo = progressivo_completo
    )
    db.session.add(nuovo_receipt)
    db.session.commit()

    ids_pagati = [v.get("appointment_id") for v in pending.get("voci", []) if v.get("appointment_id")]
    if ids_pagati:
        Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
            {Appointment.stato: AppointmentStatus.PAGATO}, synchronize_session=False
        )
        db.session.commit()

    result = {
        "results": [{
            "message": f"Scontrino fiscale registrato (progressivo {progressivo_completo})",
            "is_fiscale": True
        }],
        "reset_voci": True
    }
    IDEMPOTENCY_STORE[key] = result
    RCH_PENDING.pop(key, None)
    return jsonify(result), 200

# ========================================
# CONSOLE RCH - Route per sblocco manuale
# ========================================

@cassa_bp.route('/cassa/rch-console/status', methods=['GET'])
def rch_console_status():
    """Query stato stampante RCH"""
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    # Codici RCH che indicano stato OK (non errore)
    # 0 = OK, 20 = Idle/pronta, 99 = operazione completata
    RCH_OK_CODES = {0, 20, 99}
    # Codici che indicano documento aperto
    RCH_DOC_OPEN_CODES = {2, 3, 4}
    
    try:
        # Query stato con C453
        payload = '<?xml version="1.0" encoding="UTF-8"?><Service><cmd>=C453/$0</cmd></Service>'
        resp = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=8,
                             **rch_kwargs)
        
        result = {
            "printer_ip": ip,
            "printer_model": printer_model,
            "printer_url": url,
            "status": "ok",
            "error_code": None,
            "error_message": None,
            "document_open": False,
            "last_z": None,
            "last_doc": None,
            "raw_response": resp.text[:500]
        }
        
        # Parse errorCode / errCode (supporta entrambi i formati)
        m_err = re.search(r'<(?:errCode|errorCode)>(\d+)</(?:errCode|errorCode)>', resp.text)
        if m_err:
            code = int(m_err.group(1))
            result["error_code"] = code
            
            if code in RCH_OK_CODES:
                result["status"] = "ok"
                result["error_message"] = None
            elif code in RCH_DOC_OPEN_CODES:
                result["status"] = "warning"
                result["document_open"] = True
                result["error_message"] = "Documento fiscale aperto"
            else:
                result["status"] = "warning"
                result["error_message"] = f"Codice stato: {code}"
        
        # Parse lastZ e lastDocF
        m_z = re.search(r'<lastZ>(\d+)</lastZ>', resp.text)
        m_doc = re.search(r'<lastDocF>(\d+)</lastDocF>', resp.text)
        if m_z:
            result["last_z"] = int(m_z.group(1))
        if m_doc:
            result["last_doc"] = int(m_doc.group(1))
        
        return jsonify(result)
    except requests.exceptions.Timeout:
        return jsonify({"error": "Timeout - stampante non risponde", "printer_ip": ip}), 504
    except Exception as e:
        return jsonify({"error": str(e), "printer_ip": ip}), 500

@cassa_bp.route('/cassa/rch-console/send-cl', methods=['POST'])
def rch_console_send_cl():
    """Invia comando CL (C3 + C1) - equivale a premere tasto CL"""
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    results = []
    commands = ["=C3", "=C1"]
    
    for cmd in commands:
        try:
            payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
            resp = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=10,
                                 **rch_kwargs)
            success = _rch_is_success(resp)
            results.append({"cmd": cmd, "success": success, "response": resp.text[:200]})
            pytime.sleep(0.3)
        except Exception as e:
            results.append({"cmd": cmd, "success": False, "error": str(e)})
    
    return jsonify({"results": results})


@cassa_bp.route('/cassa/rch-console/full-reset', methods=['POST'])
def rch_console_full_reset():
    """Reset completo: C99 → C10 → C3 → T5/$0 → C3 → C1"""
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    results = []
    commands = ["=C99", "=C10", "=C3", "=T5/$0", "=C3", "=C1"]
    
    for cmd in commands:
        try:
            payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
            resp = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=15,
                                 **rch_kwargs)
            success = _rch_is_success(resp)
            results.append({"cmd": cmd, "success": success, "response": resp.text[:200]})
            pytime.sleep(0.5)
        except Exception as e:
            results.append({"cmd": cmd, "success": False, "error": str(e)})
    
    return jsonify({"results": results})


@cassa_bp.route('/cassa/rch-console/close-document', methods=['POST'])
def rch_console_close_document():
    """Chiude documento aperto con importo e metodo specificati"""
    data = request.get_json(force=True) or {}
    importo = float(data.get("importo", 0))
    metodo = data.get("metodo", "contanti")
    
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    results = []
    
    # Determina comando pagamento (tender dipendente dal modello, vedi _tender_code)
    if importo <= 0:
        pay_cmd = "=T5/$0"
    else:
        cents = int(round(importo * 100))
        pay_cmd = f"={_tender_code(metodo, printer_model)}/${cents}"
    
    commands = [pay_cmd, "=C3", "=C1"]
    
    for cmd in commands:
        try:
            payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{cmd}</cmd></Service>'
            resp = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=15,
                                 **rch_kwargs)
            success = _rch_is_success(resp)
            results.append({"cmd": cmd, "success": success, "response": resp.text[:200]})
            pytime.sleep(0.3)
        except Exception as e:
            results.append({"cmd": cmd, "success": False, "error": str(e)})
    
    all_success = all(r.get("success") for r in results)

    # Scrittura su Registro Scontrini per allineare DB ↔ AE/DGFE.
    # Eseguita solo se chiusura andata a buon fine e con importo > 0
    # (T5/$0 = abbandono documento, nessuno scontrino fiscale emesso da contabilizzare).
    receipt_progressivo = None
    db_already_present = False
    used_pending_key = None
    if all_success and importo > 0:
        try:
            numero_progressivo, numero_z = _read_progressivo(
                url, headers, rch_kwargs, max_attempts=8, sleep_s=0.5
            )
            if numero_progressivo is not None and numero_z is not None:
                progressivo_completo = f"{numero_z:04d}-{numero_progressivo:04d}"
                existing = Receipt.query.filter_by(
                    numero_progressivo=progressivo_completo
                ).first()
                if existing:
                    # Caso raro: send-to-rch ha gia' registrato il Receipt e nessuna
                    # discrepanza; non duplicare.
                    db_already_present = True
                    receipt_progressivo = progressivo_completo
                else:
                    # Cerca un RCH_PENDING odierno con totale corrispondente, per
                    # recuperare voci/cliente/operatore. Prendo il piu' recente.
                    today_str = datetime.now().strftime("%Y-%m-%d")
                    matched_key = None
                    matched_pending = None
                    for k, p in RCH_PENDING.items():
                        if p.get("giorno") != today_str:
                            continue
                        try:
                            ptot = float(p.get("expected_total") or 0)
                        except Exception:
                            ptot = 0.0
                        if abs(ptot - importo) < 0.01:
                            if (matched_pending is None
                                    or p.get("created_ts", 0) > matched_pending.get("created_ts", 0)):
                                matched_key = k
                                matched_pending = p

                    if matched_pending:
                        voci = matched_pending.get("voci", []) or []
                        cliente_id = matched_pending.get("cliente_id")
                        operatore_id = matched_pending.get("operatore_id")
                        used_pending_key = matched_key
                    else:
                        # Receipt orfano: nessun pending in memoria (es. server riavviato,
                        # o stampante sbloccata in un momento successivo).
                        voci = []
                        cliente_id = None
                        operatore_id = None

                    nuovo_receipt = Receipt(
                        created_at=datetime.now(),
                        total_amount=round(importo, 2),
                        is_fiscale=True,
                        voci=voci,
                        cliente_id=cliente_id,
                        operatore_id=operatore_id,
                        numero_progressivo=progressivo_completo
                    )
                    db.session.add(nuovo_receipt)
                    db.session.commit()

                    ids_pagati = [v.get("appointment_id") for v in voci if v.get("appointment_id")]
                    if ids_pagati:
                        Appointment.query.filter(Appointment.id.in_(ids_pagati)).update(
                            {Appointment.stato: AppointmentStatus.PAGATO},
                            synchronize_session=False
                        )
                        db.session.commit()

                    if used_pending_key:
                        # Popola IDEMPOTENCY_STORE cosi' il polling /cassa/rch-status
                        # del modal pending (se aperto sul frontend) chiude da solo.
                        IDEMPOTENCY_STORE[used_pending_key] = {
                            "results": [{
                                "message": f"Scontrino fiscale registrato (progressivo {progressivo_completo})",
                                "is_fiscale": True
                            }],
                            "reset_voci": True,
                            "closed_via_console": True
                        }
                        RCH_PENDING.pop(used_pending_key, None)

                    receipt_progressivo = progressivo_completo
        except Exception as exc:
            current_app.logger.error(
                "rch_console_close_document: errore scrittura Receipt: %s", str(exc)
            )
            # Non far fallire l'operazione: la stampante e' gia' sbloccata.

    return jsonify({
        "success": all_success,
        "results": results,
        "receipt_progressivo": receipt_progressivo,
        "db_already_present": db_already_present,
        "used_pending_key": used_pending_key
    })


@cassa_bp.route('/cassa/rch-console/send-raw', methods=['POST'])
def rch_console_send_raw():
    """Invia comando raw alla stampante"""
    data = request.get_json(force=True) or {}
    command = (data.get("command") or "").strip()
    
    if not command:
        return jsonify({"error": "Comando vuoto"}), 400
    
    # Aggiungi = se non presente
    # Il prefisso > è supportato solo su RCH Print 3.0 RT
    ip, printer_model = _get_printer_config()
    if not ip:
        return jsonify({"error": "IP stampante non configurato"}), 400
    
    # Il prefisso > è supportato solo su RCH Print 3.0 RT
    if printer_model == PrinterModel.RCH_PRINT_RT.value:
        if not command.startswith("=") and not command.startswith(">"):
            command = "=" + command
    else:
        if not command.startswith("="):
            command = "=" + command
    
    url = _rch_url(ip, printer_model)
    headers = _rch_headers(printer_model)
    rch_kwargs = _rch_request_kwargs(printer_model)
    
    try:
        payload = f'<?xml version="1.0" encoding="UTF-8"?><Service><cmd>{command}</cmd></Service>'
        resp = requests.post(url, data=payload.encode('utf-8'), headers=headers, timeout=15,
                             **rch_kwargs)
        
        error_code = _rch_parse_errcode(resp.text)
        
        return jsonify({
            "success": error_code == 0 or error_code is None,
            "error_code": error_code,
            "response": resp.text[:500],
            "command_sent": command
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500