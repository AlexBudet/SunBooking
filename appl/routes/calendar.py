# appl/routes/calendar.py
from collections import defaultdict
from flask import Blueprint, make_response, session, render_template, request, redirect, url_for, jsonify, flash, abort
from flask_caching import Cache
from sqlalchemy.orm import joinedload
from datetime import time as dtime
from datetime import datetime, timedelta, time, timezone
import requests
from ..models import OperatorShift, PacchettoSeduta, db, Appointment, AppointmentStatus, AppointmentSource, Operator, Client, Service, BusinessInfo
from appl import app
import random
import json
import re
import os
import html
from pytz import timezone as pytz_timezone
from sqlalchemy import func, and_, or_
from dotenv import load_dotenv

cache = Cache(app, config={'CACHE_TYPE': 'simple'}) 

NEW_CLIENT_MARKER = " ***NUOVO CLIENTE*** "

def is_first_appointment_for_client(client_id):
    """
    Ritorna True se il cliente non ha ancora NESSUN appuntamento salvato.
    """
    if not client_id:
        return False
    count = Appointment.query.filter(
        Appointment.client_id == client_id,
        Appointment.is_cancelled_by_client == False
    ).count()
    return count == 0

def append_new_client_marker(note_text):
    """
    Appende il marker se non già presente.
    """
    base = note_text or ""
    if NEW_CLIENT_MARKER.strip() in base:
        return base
    # Mantiene eventuale testo esistente e aggiunge il marker in fondo
    if base.strip():
        return f"{base.rstrip()} {NEW_CLIENT_MARKER}".strip()
    return NEW_CLIENT_MARKER.strip()

def estrai_nome_cognome_cellulare(note):
    nome = cognome = cellulare = email = ""
    if note:
        # Decodifica le entità HTML prima di processare (es. &#39; -> ')
        note = html.unescape(note)
        
        m_nome = re.search(r'Nome:\s*([^,]+)', note, re.IGNORECASE)
        m_cognome = re.search(r'Cognome:\s*([^,]+)', note, re.IGNORECASE)
        m_cell = re.search(r'(Cellulare|Telefono):\s*([^\s,]+(?:\s+[^\s,]+)*)', note, re.IGNORECASE)
        m_email = re.search(r'Email:\s*([^\s,]+)', note, re.IGNORECASE)
        if m_nome:
            nome = m_nome.group(1).strip().lower()
        if m_cognome:
            cognome = m_cognome.group(1).strip().lower()
        if m_cell:
            cellulare = m_cell.group(2).strip()
            cellulare = re.sub(r'\s+', '', cellulare)
            if cellulare.startswith('+39'):
                cellulare = cellulare[3:]
            if cellulare.startswith('0'):
                cellulare = cellulare[1:]
        if m_email:
            email = m_email.group(1).strip().lower()
    return nome, cognome, cellulare, email

def to_rome(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(pytz_timezone('Europe/Rome'))

calendar_bp = Blueprint('calendar', __name__)

def random_color():
    r = random.randint(0, 255)
    g = random.randint(0, 255)
    b = random.randint(0, 255)
    return f"#{r:02x}{g:02x}{b:02x}"

@calendar_bp.route('/', methods=['GET'])
def calendar_home():
    # Recupera la data come stringa e poi converti in datetime
    raw_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))
    selected_date = datetime.strptime(raw_date, '%Y-%m-%d')  # oggetto datetime

    # Calcola il giorno precedente, successivo e la stringa "oggi"
    day_before = selected_date - timedelta(days=1)
    day_after = selected_date + timedelta(days=1)
    today_str = datetime.today().strftime('%Y-%m-%d')

    day_before_str = day_before.strftime('%Y-%m-%d')
    day_after_str = day_after.strftime('%Y-%m-%d')

    # Recupera gli operatori non eliminati
    operators = Operator.query.filter_by(is_deleted=False, is_visible=True).order_by(Operator.order).all()

    shifts = OperatorShift.query.filter_by(shift_date=selected_date.date()).all()
    
    # Organizza i turni per operatore
    shifts_by_operator = defaultdict(list)
    for shift in shifts:
        shifts_by_operator[shift.operator_id].append({
            "start_time": shift.shift_start_time.strftime('%H:%M'),
            "end_time": shift.shift_end_time.strftime('%H:%M'),
        })

    # Filtra gli appuntamenti per la data selezionata (00:00 di selected_date fino alle 23:59)
    appointments = Appointment.query.filter(
        Appointment.start_time >= selected_date,
        Appointment.start_time < selected_date + timedelta(days=1),
        Appointment.is_cancelled_by_client == False
    ).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service),
        joinedload(Appointment.operator),
        joinedload(Appointment.pacchetto_seduta).joinedload(PacchettoSeduta.pacchetto)
    ).all()

    for appt in appointments:
        appt.created_at = to_rome(appt.created_at)
        if appt.last_edit:
            appt.last_edit = to_rome(appt.last_edit)
            try:
                if appt.last_edit < appt.created_at:
                    appt.last_edit = appt.created_at + timedelta(minutes=1)
            except Exception:
                pass

    # Prepara i dati degli appuntamenti per il rendering
    appointment_data = []
    for appt in appointments:
        client_name = "OFF" if appt.client is None else ("+" if appt.client.is_deleted else f"{appt.client.cliente_nome} {appt.client.cliente_cognome}")
        service_name = "OFF" if appt.service is None else appt.service.servizio_nome
        appointment_data.append({
            "id": appt.id,
            "client_name": client_name,
            "service_name": service_name,
            "start_time": appt.start_time.strftime('%H:%M'),
            "duration": appt.duration,
            "operator_id": appt.operator_id
        })

    # Prepara i dati degli appuntamenti per l'API (o altri scopi)
    appointments_data = [
        {
            "id": appt.id,
            "client": {
                "id": appt.client.id if appt.client else None,
                "name": appt.client.cliente_nome if appt.client else "OFF",
                "surname": appt.client.cliente_cognome if appt.client else ""
            },
            "service_name": "OFF" if appt.service is None else appt.service.servizio_nome,
            "start_time": appt.start_time.strftime('%H:%M'),
            "duration": appt.duration,
            "colore": appt.colore,
            "colore_font": appt.colore_font
        }
        for appt in appointments
    ]

    # Recupera le informazioni aziendali
    business_info = BusinessInfo.query.first()
    if business_info and getattr(business_info, "whatsapp_message", None):
        whatsapp_message = business_info.whatsapp_message
    else:
        whatsapp_message = "Buongiorno {{nome}}, ecco un memo per il tuo appuntamento del {{data}} alle ore {{ora}}. Ci vediamo presto! Sun Booking"

    # Assegna valori di default se business_info non è configurato
    if business_info is None:
        opening_time = datetime.strptime("08:00", "%H:%M").time()
        closing_time = datetime.strptime("20:00", "%H:%M").time()
        active_opening_time = datetime.strptime("09:00", "%H:%M").time()
        active_closing_time = datetime.strptime("19:00", "%H:%M").time()
        closing_days = []
    else:
        opening_time = business_info.opening_time
        closing_time = business_info.closing_time
        active_opening_time = business_info.active_opening_time
        active_closing_time = business_info.active_closing_time
        closing_days = business_info.closing_days_list

    # Logica se è un giorno di chiusura
    if selected_date.strftime('%A') in closing_days:
        app.logger.debug(f"{selected_date.strftime('%A')} è un giorno di chiusura.")

    # Recupera i clienti e i servizi
    clients = Client.query.filter(
        Client.is_deleted == False,
        ~((Client.cliente_nome == "cliente") & (Client.cliente_cognome == "booking")),
        ~((func.lower(Client.cliente_nome) == "booking") & (func.lower(Client.cliente_cognome) == "online")),
        func.lower(Client.cliente_nome) != "dummy",
        func.lower(Client.cliente_cognome) != "dummy",
    ).all()
    services = Service.query.filter(
        Service.is_deleted == False,
        Service.is_visible_in_calendar == True,
        func.lower(Service.servizio_nome) != "dummy"
    ).all()

    # Prepara i dati dei servizi per l'API
    services_data = [
        {
            "id": s.id,
            "name": s.servizio_nome,
            "duration": s.servizio_durata
        }
        for s in services
    ]

    # Log utile per debug
    app.logger.debug("Selected date: %s", selected_date.strftime('%Y-%m-%d'))
    app.logger.debug("Closing days: %s", closing_days)
    app.logger.debug("Active opening time: %s, Active closing time: %s",
                     active_opening_time, active_closing_time)
    
    if business_info and getattr(business_info, "whatsapp_message", None):
        whatsapp_message = business_info.whatsapp_message
    else:
        whatsapp_message = "Buongiorno {{nome}}, ecco un memo per il tuo appuntamento del {{data}} alle ore {{ora}}. Ci vediamo presto! Sun Booking"

    return render_template(
        'calendar.html',
        selected_date=selected_date,               # datetime
        selected_date_str=selected_date.strftime('%Y-%m-%d'),  # 'YYYY-MM-DD'
        day_before_str=day_before_str,
        day_after_str=day_after_str,
        today_str=today_str,
        operators=operators,
        appointments=appointments,
        appointments_data=appointments_data,
        opening_time=opening_time,
        closing_time=closing_time,
        active_opening_time=active_opening_time,
        active_closing_time=active_closing_time,
        closing_days=closing_days,
        clients=clients,
        services=services_data,
        shifts_by_operator=shifts_by_operator,
        whatsapp_message=whatsapp_message
    )

@calendar_bp.route('/api/search-services/<query>', methods=['GET'])
def search_services(query):
    if len(query) < 3:  # Potresti voler limitare la ricerca a query di almeno 3 caratteri
        return jsonify([])  # Ritorna una lista vuota se la query è troppo corta

    pattern = f'%{query}%'
    services = Service.query.filter(
        Service.servizio_nome.ilike(pattern),
        Service.is_deleted == False,
        Service.is_visible_in_calendar == True,
        func.lower(Service.servizio_nome) != "dummy"
    ).all()
    services_data = [{
    'id': service.id,
    'name': service.servizio_nome,
    'duration': service.servizio_durata,
    'price': service.servizio_prezzo,
    'tag': service.servizio_tag
} for service in services]

    return jsonify(services_data)

@calendar_bp.route('/api/search-clients/<query>', methods=['GET'])
def search_clients(query):
    if len(query) < 2:
        return jsonify([])
    q = query.strip().lower()
    parts = [p for p in q.split() if p]
    if len(parts) == 1:
        term = f"%{parts[0]}%"
        filters = or_(
            func.lower(Client.cliente_nome).like(term),
            func.lower(Client.cliente_cognome).like(term),
            Client.cliente_cellulare.like(term)
        )
    else:
        # Ottimizzato: usa and_ per combinare condizioni su più parti
        conditions = []
        for part in parts:
            term = f"%{part}%"
            conditions.append(
                or_(
                    func.lower(Client.cliente_nome).like(term),
                    func.lower(Client.cliente_cognome).like(term)
                )
            )
        filters = and_(*conditions)  # Combina in SQL invece di loop Python

    clients = Client.query.filter(
        filters,
        Client.is_deleted == False,
        ~((Client.cliente_nome == "cliente") & (Client.cliente_cognome == "booking")),
        ~((func.lower(Client.cliente_nome) == "booking") & (func.lower(Client.cliente_cognome) == "online")),
        func.lower(Client.cliente_nome) != "dummy",
        func.lower(Client.cliente_cognome) != "dummy",
    ).limit(10).all()
    clients_data = [
        {
            'id': client.id,
            'name': f"{client.cliente_nome} {client.cliente_cognome}",
            'phone': client.cliente_cellulare,
        }
        for client in clients
    ]
    return jsonify(clients_data)

@calendar_bp.route('/clients', methods=['GET'])
@cache.cached(timeout=300, key_prefix='list_clients')
def list_clients():
    """Restituisce la lista di tutti i clienti non eliminati."""
    clients = Client.query.filter(
        Client.is_deleted == False,
        ~((Client.cliente_nome == "cliente") & (Client.cliente_cognome == "booking")),
        ~((func.lower(Client.cliente_nome) == "booking") & (func.lower(Client.cliente_cognome) == "online")),
        func.lower(Client.cliente_nome) != "dummy",
        func.lower(Client.cliente_cognome) != "dummy",
    ).all()

    response = [
        {
            "id": client.id,
            "nome": client.cliente_nome,
            "cognome": client.cliente_cognome,
            "cellulare": client.cliente_cellulare,
            "email": client.cliente_email,
            "data_nascita": client.cliente_data_nascita
        }
        for client in clients
    ]
    return jsonify(response)

@calendar_bp.route('/create', methods=['GET', 'POST'])
def create_appointment():
    if request.method == 'GET':
        operator_id = request.args.get('operator_id', type=int)
        hour = request.args.get('hour', type=int)
        minute = request.args.get('minute', type=int)
        date = request.args.get('date')
        try:
            selected_date = datetime.strptime(date, '%Y-%m-%d')
        except (TypeError, ValueError):
            return jsonify({"error": "Formato data non valido"}), 400
        return render_template(
            'CreateNewAppt.html',
            operator_id=operator_id,
            hour=hour,
            minute=minute,
            date=selected_date.strftime('%Y-%m-%d')
        )

    # POST
    try:
        data = request.get_json(silent=True) or {}

        # --- helpers ---
        def _norm_id(v):
            if v in (None, "", "null", "dummy", "Dummy", "DUMMY", 0, "0"):
                return None
            try:
                vi = int(v)
                return vi if vi > 0 else None
            except Exception:
                return None

        def _norm_note(s):
            if s is None:
                return None
            # preserva i caratteri unicode senza escape
            try:
                return json.dumps(s, ensure_ascii=False)[1:-1]
            except Exception:
                return str(s)

        # --- payload base ---
        raw_client_id = data.get('client_id')
        client_id = _norm_id(raw_client_id)
        service_id = _norm_id(data.get('service_id'))
        operator_id = _norm_id(data.get('operator_id'))
        start_time_str = (data.get('start_time') or '').strip()           # "HH:MM"
        appointment_date = (data.get('appointment_date') or '').strip()   # "YYYY-MM-DD"
        duration = data.get('duration')
        try:
            duration = int(duration) if duration is not None else None
        except Exception:
            duration = None
        note = _norm_note(data.get('note'))

        # Colori
        colore = (data.get('colore') or '').strip() or random_color()
        colore_font = compute_font_color(colore)

        # Validazioni minime
        if not all([operator_id, start_time_str, appointment_date, duration is not None]):
            return jsonify({"error": "Parametri mancanti"}), 400

        # OFF block quando sia client che service sono None
        is_off_block = (client_id is None) and (service_id is None)
        if not is_off_block and not (client_id or service_id):
            return jsonify({"error": "Seleziona almeno un cliente o un servizio"}), 400

        # Parse datetime inizio
        try:
            start_time = datetime.strptime(f"{appointment_date} {start_time_str}", '%Y-%m-%d %H:%M')
        except ValueError:
            return jsonify({"error": "Formato data/ora non valido"}), 400

        # Verifica “nuovo cliente” PRIMA di creare (solo se client_id reale)
        is_new_client = is_first_appointment_for_client(client_id) if client_id else False

        # --- PSEUDOBLOCCHI ---
        pseudoblocks = data.get('pseudoblocks')
        created_appts = []
        if isinstance(pseudoblocks, list) and len(pseudoblocks) > 0:
            current_start = start_time
            first_created = None

            for pb in pseudoblocks:
                pb_color = (pb.get('colore') or colore) if isinstance(pb, dict) else colore
                try:
                    pb_duration = int(pb.get('duration', duration))
                except Exception:
                    pb_duration = duration

                pb_service_id = _norm_id(pb.get('serviceId') if isinstance(pb, dict) else None) \
                                or _norm_id(pb.get('service_id') if isinstance(pb, dict) else None) \
                                or service_id

                # Stato per blocco
                pb_status_raw = pb.get('status') if isinstance(pb, dict) else None
                if isinstance(pb_status_raw, int) and pb_status_raw in [e.value for e in AppointmentStatus]:
                    inherited_status = AppointmentStatus(pb_status_raw)
                else:
                    inherited_status = AppointmentStatus.DEFAULT

                # Recupera pacchetto_seduta_id se presente (per integrazione pacchetti)
                                # Recupera pacchetto_seduta_id se presente (per integrazione pacchetti)
                # Supporta sia snake_case (pacchetto_seduta_id) che camelCase (pacchettoSedutaId)
                pb_pacchetto_seduta_id = _norm_id(
                    pb.get('pacchetto_seduta_id') if isinstance(pb, dict) else None
                ) or _norm_id(
                    pb.get('pacchettoSedutaId') if isinstance(pb, dict) else None
                )

                new_appt = Appointment(
                    client_id=client_id,
                    operator_id=operator_id,
                    service_id=pb_service_id,
                    start_time=current_start,
                    _duration=int(pb_duration),
                    colore=pb_color,
                    colore_font=colore_font,
                    note=note,
                    stato=inherited_status,
                    pacchetto_seduta_id=pb_pacchetto_seduta_id
                )
                if first_created is None:
                    first_created = new_appt

                # Se il client “dummy/0” (placeholder) è stato richiesto nel payload originale
                if raw_client_id in ("dummy", "0"):
                    new_appt.note = (data.get('titolo') or '').strip()

                db.session.add(new_appt)
                created_appts.append(new_appt)

                # prossimo blocco
                current_start = current_start + timedelta(minutes=pb_duration)

            # Marker “NUOVO CLIENTE” solo sul primo blocco creato
            if is_new_client and first_created:
                first_created.note = append_new_client_marker(first_created.note)

            db.session.commit()
            
            # Aggiorna la data_trattamento della seduta se collegata a pacchetto
            pacchetto_info = None
            for appt in created_appts:
                if appt.pacchetto_seduta_id:
                    from appl.models import PacchettoSeduta
                    seduta = PacchettoSeduta.query.get(appt.pacchetto_seduta_id)
                    if seduta:
                        seduta.data_trattamento = appt.start_time
                        seduta.operatore_id = appt.operator_id
                        db.session.add(seduta)
                        
                        # Salva info per il redirect
                        if not pacchetto_info:
                            pacchetto_info = {
                                'pacchettoId': seduta.pacchetto_id,
                                'sedutaId': seduta.id,
                                'dataFissata': appt.start_time.strftime('%d/%m/%Y %H:%M'),
                                'sedutaOrdine': seduta.ordine
                            }
            
            db.session.commit()
            
            response_data = {
                "message": "Appuntamenti creati con successo!",
                "appointments": [
                    {
                        "id": appt.id,
                        "client_name": f"{appt.client.cliente_nome} {appt.client.cliente_cognome}" if appt.client else "OFF",
                        "service_name": appt.service.servizio_nome if appt.service else "OFF",
                        "start_time": appt.start_time.strftime('%H:%M'),
                        "duration": appt.duration,
                        "operator_id": appt.operator_id,
                        "status": appt.stato.value if hasattr(appt.stato, "value") else appt.stato
                    }
                    for appt in created_appts
                ]
            }
            
            # Aggiungi info pacchetto se presente
            if pacchetto_info:
                response_data['pacchettoInfo'] = pacchetto_info
            
            return jsonify(response_data), 201

        # --- CASO SINGOLO ---
        status_value = data.get('status', AppointmentStatus.DEFAULT.value)
        if not isinstance(status_value, int) or status_value not in [e.value for e in AppointmentStatus]:
            status_value = AppointmentStatus.DEFAULT.value

        # Recupera pacchetto_seduta_id se presente (supporta entrambi i formati)
        single_pacchetto_seduta_id = _norm_id(data.get('pacchetto_seduta_id')) or _norm_id(data.get('pacchettoSedutaId'))

        new_appt = Appointment(
            client_id=client_id,
            operator_id=operator_id,
            service_id=service_id,
            start_time=start_time,
            _duration=int(duration),
            colore=colore,
            colore_font=colore_font,
            note=note,
            stato=AppointmentStatus(status_value),
            pacchetto_seduta_id=single_pacchetto_seduta_id  # <-- AGGIUNTO
        )

        # titolo personalizzato per client dummy
        if raw_client_id in ("dummy", "0"):
            new_appt.note = (data.get('titolo') or '').strip()

        # Marker "NUOVO CLIENTE" se è il primo appuntamento storico
        if is_new_client:
            new_appt.note = append_new_client_marker(new_appt.note)

        db.session.add(new_appt)
        db.session.commit()

        # Aggiorna la data_trattamento della seduta se collegata a pacchetto (CASO SINGOLO)
        pacchetto_info = None
        if new_appt.pacchetto_seduta_id:
            from appl.models import PacchettoSeduta
            seduta = PacchettoSeduta.query.get(new_appt.pacchetto_seduta_id)
            if seduta:
                seduta.data_trattamento = new_appt.start_time
                seduta.operatore_id = new_appt.operator_id
                db.session.add(seduta)
                db.session.commit()
                
                pacchetto_info = {
                    'pacchettoId': seduta.pacchetto_id,
                    'sedutaId': seduta.id,
                    'dataFissata': new_appt.start_time.strftime('%d/%m/%Y %H:%M'),
                    'sedutaOrdine': seduta.ordine
                }

        response_data = {
            "id": new_appt.id,
            "client_name": f"{new_appt.client.cliente_nome} {new_appt.client.cliente_cognome}" if new_appt.client else "OFF",
            "service_name": new_appt.service.servizio_nome if new_appt.service else "OFF",
            "start_time": start_time.strftime('%H:%M'),
            "duration": new_appt.duration,
            "operator_id": new_appt.operator_id,
            "note": new_appt.note,
            "status": new_appt.stato.value if hasattr(new_appt.stato, "value") else new_appt.stato
        }
        
        # Aggiungi info pacchetto se presente
        if pacchetto_info:
            response_data['pacchettoInfo'] = pacchetto_info
            
        return jsonify(response_data), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error("Errore durante la creazione dell'appuntamento: %s", str(e))
        return jsonify({"error": "Si è verificato un errore interno durante la creazione."}), 500

@calendar_bp.route('/edit/<int:appt_id>', methods=['GET', 'POST'])
def edit_appointment(appt_id):
    appt = db.session.get(Appointment, appt_id)
    if not appt:
        abort(404)

    if request.method == 'GET':
        return render_template('EditApptClient.html', appointment=appt)

    elif request.method == 'POST':
        try:
            data = request.json or {}
            if not data:
                return jsonify({"error": "Nessun dato fornito"}), 400

            # Valori originali
            original_client_id = appt.client_id
            original_operator_id = appt.operator_id
            original_start_time = appt.start_time
            original_duration = appt.duration

            # Determina nuovo client_id (se cambiato) e verifica se va marcato come "nuovo cliente"
            new_client_id = original_client_id
            if 'client_id' in data:
                try:
                    new_client_id = int(data['client_id']) if data['client_id'] not in (None, "", "null") else None
                except Exception:
                    new_client_id = None

            will_mark_new_client = False
            if new_client_id is not None and new_client_id != original_client_id:
                # Conta appuntamenti pre-esistenti per il nuovo cliente, escludendo questo appt
                prev_count = Appointment.query.filter(
                    Appointment.client_id == new_client_id,
                    Appointment.id != appt.id,
                    Appointment.is_cancelled_by_client == False
                ).count()
                will_mark_new_client = (prev_count == 0)

            # Aggiornamenti campi
            if 'client_id' in data:
                appt.client_id = new_client_id
                
                # Se è un blocco web con placeholder, assegna nuovo colore random
                if appt.source == AppointmentSource.web and new_client_id != original_client_id:
                    new_color = random_color()
                    new_font_color = compute_font_color(new_color)
                    appt.colore = new_color
                    appt.colore_font = new_font_color
                    
                    # Propaga il colore a tutti i blocchi della stessa sessione
                    if appt.booking_session_id:
                        session_blocks = Appointment.query.filter_by(
                            booking_session_id=appt.booking_session_id,
                            is_cancelled_by_client=False
                        ).all()
                        for block in session_blocks:
                            block.colore = new_color
                            block.colore_font = new_font_color

            if 'operator_id' in data:
                try:
                    appt.operator_id = int(data['operator_id'])
                except Exception:
                    pass

            if 'start_time' in data:
                existing_date = appt.start_time.date()
                new_time = datetime.strptime(data['start_time'], '%H:%M').time()
                appt.start_time = datetime.combine(existing_date, new_time)

            if 'duration' in data:
                try:
                    appt.duration = int(data['duration'])
                except Exception:
                    pass

            if 'colore' in data:
                appt.colore = data['colore']
            if 'colore_font' in data:
                appt.colore_font = data['colore_font']

            if 'service_id' in data:
                try:
                    appt.service_id = int(data['service_id'])
                except Exception:
                    pass

            if 'note' in data and data['note'] is not None:
                try:
                    appt.note = json.dumps(data['note'], ensure_ascii=False)[1:-1]
                except Exception:
                    appt.note = str(data['note'])

            # Applica marker se riassegnato a cliente senza storico
            if will_mark_new_client:
                appt.note = append_new_client_marker(appt.note)

            # Aggiorna last_edit se uno dei campi principali è cambiato
            if (
                appt.client_id != original_client_id or
                appt.operator_id != original_operator_id or
                appt.start_time != original_start_time or
                appt.duration != original_duration
            ):
                appt.last_edit = datetime.now(timezone.utc)

            db.session.commit()

            return jsonify({
                "message": "Appuntamento aggiornato con successo!",
                "appointment": {
                    "id": appt.id,
                    "client_id": appt.client_id,
                    "client_name": f"{appt.client.cliente_nome} {appt.client.cliente_cognome}" if appt.client else "",
                    "service_id": appt.service_id,
                    "service_name": appt.service.servizio_nome if appt.service else "",
                    "start_time": appt.start_time.strftime('%Y-%m-%d %H:%M'),
                    "end_time": appt.end_time.strftime('%Y-%m-%d %H:%M') if appt.end_time else "",
                    "duration": appt.duration,
                    "colore": appt.colore or "#FFFFFF",
                    "colore_font": appt.colore_font or "#000000",
                    "note": appt.note or ""
                }
            }), 200

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Errore durante la modifica dell'appuntamento {appt_id}: {e}")
            return jsonify({"error": "Si è verificato un errore interno durante l'aggiornamento."}), 500
        
@calendar_bp.route('/update/<int:appt_id>', methods=['POST'])
def update_appointment_position(appt_id):
    data = request.get_json()
    operator_id = data.get('operator_id')
    hour = data.get('hour')
    minute = data.get('minute')
    new_date_str = data.get('date')  # Nuovo parametro che indica la data

    if operator_id is None or hour is None or minute is None or new_date_str is None:
        return jsonify({"error": "Parametri mancanti"}), 400

    appt = db.session.get(Appointment, appt_id)
    if not appt:
        abort(404)
    original_operator_id = appt.operator_id
    original_start_time = appt.start_time

    try:
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date()
    except Exception as e:
        app.logger.error("Errore conversione data/ora in update_appointment_position: %s", str(e))
        return jsonify({"error": "Formato data o ora non valido."}), 400

    try:
        new_start_time = datetime.combine(new_date, time(int(hour), int(minute)))
    except Exception as e:
        app.logger.error("Errore nel calcolo del nuovo orario")
        return jsonify({"error": f"Errore nel calcolo del nuovo orario: {e}"}), 400

    appt.operator_id = int(operator_id)
    appt.start_time = new_start_time

    # update_appointment_position: assegna UTC consapevole
    if appt.operator_id != original_operator_id or appt.start_time != original_start_time:
        appt.last_edit = datetime.now(timezone.utc)

    db.session.commit()
    return jsonify({"message": "Posizione aggiornata", "duration": appt.duration}), 200

@calendar_bp.route('/api/services', methods=['GET'])
@cache.cached(timeout=300, key_prefix='list_services_api')
def list_services_api():
    services = Service.query.filter(
        Service.is_deleted == False,
        Service.is_visible_in_calendar == True,
        func.lower(Service.servizio_nome) != "dummy"
    ).all()
    return jsonify([
        {
            "id": s.id,
            "servizio_nome": s.servizio_nome,  # Assicurati che questo nome sia coerente
            "durata": s.servizio_durata,
            "price": s.servizio_prezzo,
            "tag": s.servizio_tag,
        }
        for s in services
    ])

@calendar_bp.route('/delete/<int:appointment_id>', methods=['POST'])
def delete_appointment(appointment_id):
    try:
        appt = db.session.get(Appointment, appointment_id)
        if not appt:
            return jsonify({"error": "Appuntamento non trovato"}), 404

        # Se l'appuntamento è collegato a una seduta pacchetto, cancella la data_trattamento
        if appt.pacchetto_seduta_id:
            seduta = db.session.get(PacchettoSeduta, appt.pacchetto_seduta_id)
            if seduta:
                seduta.data_trattamento = None
                seduta.operatore_id = None  # Opzionale: resetta anche l'operatore
                app.logger.info(f"Cancellata data_trattamento dalla seduta {seduta.id} del pacchetto {seduta.pacchetto_id}")

        db.session.delete(appt)
        db.session.commit()
        return jsonify({"message": "Appuntamento eliminato con successo!"}), 200
    except Exception as e:
        app.logger.error(f"Errore durante l'eliminazione dell'appuntamento {appointment_id}: {e}")
        return jsonify({"error": "Si è verificato un errore interno durante l'eliminazione."}), 500

@calendar_bp.route('/adjust-duration/<int:appointment_id>', methods=['POST'])
def adjust_duration(appointment_id):
    try:
        data = request.get_json()
        if data is None:
            return jsonify({"error": "Nessun dato fornito"}), 400

        # Prova a convertire il parametro 'adjustment' in intero
        try:
            adjustment = int(data.get('adjustment'))
        except (ValueError, TypeError):
            return jsonify({"error": "Parametro 'adjustment' non valido"}), 400

        if adjustment <= 0:
            return jsonify({"error": "La durata deve essere maggiore di 0"}), 400

        appointment = db.session.get(Appointment, appointment_id)
        if not appointment:
            abort(404)
        original_duration = appointment.duration

        new_end_time = appointment.start_time + timedelta(minutes=adjustment)
        appointment.end_time = new_end_time

        # Aggiorna last_edit solo se la durata è cambiata
        if appointment.duration != original_duration:
            appointment.last_edit = datetime.now(timezone.utc)

        db.session.commit()

        new_duration = (appointment.end_time - appointment.start_time).total_seconds() // 60
        return jsonify({"message": "Durata aggiornata", "duration": new_duration}), 200
    except Exception as e:
        app.logger.error("Errore durante l'aggiornamento della durata: %s", str(e))
        return jsonify({"error": "Errore durante l'aggiornamento della durata."}), 500

@calendar_bp.route('/api/operators/<int:operator_id>/shifts', methods=['POST'])
def save_operator_shift(operator_id):
    """Salva un turno (con o senza pausa) per un operatore."""
    try:
        data = request.json
        date_str = data['date']
        start_time_str = data['startTime']
        end_time_str = data['endTime']

        # Converti stringhe in oggetti datetime
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()

        # Elimina i turni esistenti per l'operatore in quella data
        OperatorShift.query.filter_by(operator_id=operator_id, shift_date=date).delete()

        # Crea e salva il nuovo turno
        new_shift = OperatorShift(
            operator_id=operator_id,
            shift_date=date,
            shift_start_time=start_time,
            shift_end_time=end_time
        )
        db.session.add(new_shift)
        db.session.commit()

        return jsonify({
            "message": "Turno salvato con successo!",
            "shift": {
                "id": new_shift.id,
                "start_time": new_shift.shift_start_time.strftime('%H:%M'),
                "end_time": new_shift.shift_end_time.strftime('%H:%M'),
            }
        }), 200

    except Exception as e:
        db.session.rollback()  # Rollback in case of errors
        app.logger.error(f"Error saving shift for operator {operator_id}: {e}")
        return jsonify({"error": "Errore durante il salvataggio del turno."}), 500
    
@calendar_bp.route('/api/shifts', methods=['GET'])
@cache.cached(timeout=300, key_prefix='get_all_shifts')
def get_all_shifts():
    """Restituisce tutti i turni salvati nel database."""
    shifts = OperatorShift.query.all()
    shifts_data = []
    for shift in shifts:
        shifts_data.append({
            'id': shift.id,
            'operator_id': shift.operator_id,
            'operator_name': shift.operator.user_nome,
            'date': shift.shift_date.strftime('%Y-%m-%d'),
            'start_time': shift.shift_start_time.strftime('%H:%M'),
            'end_time': shift.shift_end_time.strftime('%H:%M')
        })
    return jsonify(shifts_data)

@calendar_bp.route('/api/operators/<int:operator_id>/shifts', methods=['GET'])
def get_operator_shifts(operator_id):
    date = request.args.get('date')
    if not date:
        return jsonify({"error": "Parametro 'date' mancante"}), 400
    
    try:
        shift_date = datetime.strptime(date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Formato data non valido (usa YYYY-MM-DD)"}), 400
    
    shifts = OperatorShift.query.filter_by(
        operator_id=operator_id, 
        shift_date=shift_date
    ).all()
    
    return jsonify([{
        "id": s.id,
        "start_time": s.shift_start_time.strftime('%H:%M'),
        "end_time": s.shift_end_time.strftime('%H:%M')
    } for s in shifts])

@calendar_bp.route('/api/operators/<int:operator_id>/shifts/multi', methods=['POST'])
def operator_multi_shifts(operator_id):
    data = request.get_json()
    if not data or 'startDate' not in data or 'endDate' not in data or 'shifts' not in data:
        return jsonify({"error": "Dati mancanti"}), 400

    try:
        start_date = datetime.strptime(data['startDate'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['endDate'], '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Formato data non valido"}), 400

    # Recupera il dummy service; assicurati che Service.get_dummy() funzioni correttamente
    try:
        dummy_service = Service.get_dummy()
        if not dummy_service:
            raise ValueError("Dummy service non trovato")
        dummy_service_id = dummy_service.id
    except Exception as e:
        app.logger.error("Errore nel recupero del dummy service: %s", str(e))
        return jsonify({"error": "Errore nel dummy service"}), 500

    # Usa un dummy client id numerico (es., 0)
    dummy_client = Client.get_dummy()
    dummy_client_id = dummy_client.id

    shifts_data = data['shifts']
    current_date = start_date

    while current_date <= end_date:
        weekday = current_date.strftime('%A').lower()  # es. "monday", "tuesday", ecc.
        if weekday in shifts_data:
            day_info = shifts_data.get(weekday)

            # GIORNO OFF: Se il campo 'start' è "NO", tratta il giorno come riposo
            if day_info.get('start') == "NO":
                # Elimina il turno esistente per il giorno, se presente
                shift = OperatorShift.query.filter_by(operator_id=operator_id, shift_date=current_date).first()
                if shift:
                    db.session.delete(shift)
                # Definisci l’intervallo dell’intera giornata
                day_start = datetime.combine(current_date, datetime.min.time())
                day_end = datetime.combine(current_date, datetime.max.time())
                # Elimina tutti i blocchi Appointment con note "PAUSA" o "OFF" per il giorno
                off_appts = Appointment.query.filter(
                    Appointment.operator_id == operator_id,
                    Appointment.start_time >= day_start,
                    Appointment.start_time <= day_end,
                    Appointment.note.in_(["PAUSA", "OFF"]),
                    Appointment.is_cancelled_by_client == False
                ).all()
                for appt in off_appts:
                    db.session.delete(appt)
                # Crea il blocco OFF per il giorno, usando orario simbolico 00:00
                new_off = Appointment(
                    client_id=dummy_client_id,
                    operator_id=operator_id,
                    service_id=dummy_service_id,
                    start_time=datetime.combine(current_date, datetime.strptime("00:00", "%H:%M").time()),
                    colore="#FF0000",       # evidenzia il giorno off con questo colore
                    colore_font="#FFFFFF",
                    note="OFF"
                )
                new_off._duration = 0
                db.session.add(new_off)
                current_date += timedelta(days=1)
                continue

            # CASO NORMALE: Se sono impostati start e end, crea o aggiorna il turno
            if day_info.get('start') and day_info.get('end'):
                shift = OperatorShift.query.filter_by(operator_id=operator_id, shift_date=current_date).first()
                if not shift:
                    shift = OperatorShift(operator_id=operator_id, shift_date=current_date)
                    db.session.add(shift)
                shift.shift_start_time = datetime.strptime(day_info['start'], '%H:%M').time()
                shift.shift_end_time = datetime.strptime(day_info['end'], '%H:%M').time()

                # Se sono impostati pausa (breakStart e breakDuration), crea il blocco OFF per la pausa
                if day_info.get('breakStart') and day_info.get('breakDuration'):
                    break_start_time = datetime.strptime(day_info['breakStart'], '%H:%M').time()
                    break_start_dt = datetime.combine(current_date, break_start_time)
                    break_duration = int(day_info['breakDuration'])
                    existing_break = Appointment.query.filter_by(
                        operator_id=operator_id,
                        start_time=break_start_dt,
                        client_id=dummy_client_id,
                        is_cancelled_by_client=False
                    ).first()
                    if not existing_break:
                        new_break = Appointment(
                            client_id=dummy_client_id,
                            operator_id=operator_id,
                            service_id=dummy_service_id,
                            start_time=break_start_dt,
                            duration=break_duration,
                            colore="#CCCCCC",
                            colore_font="#000000",
                            note="PAUSA"
                        )
                        db.session.add(new_break)
        current_date += timedelta(days=1)

    try:
        db.session.commit()
        return jsonify({"message": "Turno multi salvato con successo"}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error("Errore durante il commit del multi turno: %s", str(e))
        return jsonify({"error": "Errore durante il salvataggio dei turni."}), 500

@calendar_bp.route('/update_note/<int:appt_id>', methods=['POST'])
def update_note(appt_id):
    data = request.get_json()
    note_text = data.get('note')
    if note_text is None:
        return jsonify({"error": "Parametro 'note' mancante"}), 400

    appt = db.session.get(Appointment, appt_id)
    if not appt:
        abort(404)
    appt.note = note_text
    db.session.commit()

    return jsonify({"message": "Nota aggiornata", "appointment_id": appt_id}), 200

@calendar_bp.route('/update_color/<int:appt_id>', methods=['POST'])
def update_color(appt_id):
    data = request.get_json()
    new_color = data.get('colore')
    new_font_color = data.get('colore_font')
    if not new_color:
        return jsonify({"error": "Colore non fornito"}), 400
    if not new_font_color:
        return jsonify({"error": "Colore del font non fornito"}), 400
    appt = db.session.get(Appointment, appt_id)
    if not appt:
        abort(404)
    appt.colore = new_color
    appt.colore_font = new_font_color
    db.session.commit()
    return jsonify({
        "message": "Colori aggiornati",
        "colore": new_color,
        "colore_font": new_font_color
    }), 200

@calendar_bp.route('/api/top-frequent-or-latest-services', methods=['GET'])
def top_frequent_or_latest_services():
    # Query ottimizzata: combina frequenti e ultimi in una sola chiamata
    freq_subquery = db.session.query(
        Appointment.service_id,
        func.count(Appointment.service_id).label('count')
    ).group_by(Appointment.service_id).subquery()

    frequent_services = db.session.query(Service).join(
        freq_subquery, Service.id == freq_subquery.c.service_id
    ).filter(
        Service.is_deleted == False,
        Service.is_visible_in_calendar == True,
        func.lower(Service.servizio_nome) != "dummy"
    ).order_by(freq_subquery.c.count.desc()).limit(10).all()

    if frequent_services:
        services_data = [{
            "id": s.id,
            "name": s.servizio_nome,
            "duration": s.servizio_durata,
            "price": s.servizio_prezzo,
            "tag": s.servizio_tag
        } for s in frequent_services]
        return jsonify(services_data)

    # Fallback ottimizzato: usa order_by una volta
    latest_services = Service.query.filter(
        Service.is_deleted == False,
        Service.is_visible_in_calendar == True,
        func.lower(Service.servizio_nome) != "dummy"
    ).order_by(Service.id.desc()).limit(10).all()
    services_data = [{
        "id": s.id,
        "name": s.servizio_nome,
        "duration": s.servizio_durata,
        "price": s.servizio_prezzo,
        "tag": s.servizio_tag
    } for s in latest_services]

    return jsonify(services_data)

@calendar_bp.route('/api/last-services-for-client/<int:client_id>', methods=['GET'])
def last_services_for_client(client_id):
    app.logger.info(f"[DEBUG] last-services-for-client chiamato per client_id={client_id}")
    today = datetime.today()
    # Top 10 servizi pagati per quel cliente (ordinati per data ultimo appuntamento pagato desc), solo quelli mai fatti non appaiono
    freq_subq = (
        db.session.query(
            Appointment.service_id,
            func.count(Appointment.service_id).label('cnt'),
            func.max(Appointment.start_time).label('last_date')
        )
        .filter(
            Appointment.client_id == client_id,
            Appointment.service_id.isnot(None),
            Appointment.stato == AppointmentStatus.PAGATO,  # Solo pagati
            Appointment.start_time <= today
        )
        .group_by(Appointment.service_id)
        .subquery()
    )
    services = (
        db.session.query(Service, freq_subq.c.last_date)
        .join(freq_subq, Service.id == freq_subq.c.service_id)
        .filter(
            Service.is_deleted == False,
            Service.is_visible_in_calendar == True,
            func.lower(Service.servizio_nome) != "dummy"
        )
        .order_by(freq_subq.c.last_date.desc())  # Ordina per data ultimo appuntamento (più recente prima)
        .limit(10)
        .all()
    )
    app.logger.info(f"[DEBUG] Servizi pagati per cliente {client_id}: trovati {len(services)} da stato PAGATO")
    
    # Popola i restanti slot con servizi più usati in generale (escludendo quelli già presenti)
    client_service_ids = {s.id for s, _ in services}
    if len(services) < 10:
        global_freq_subq = (
            db.session.query(
                Appointment.service_id,
                func.count(Appointment.service_id).label('cnt')
            )
            .filter(Appointment.service_id.isnot(None))
            .group_by(Appointment.service_id)
            .subquery()
        )
        additional_services = (
            db.session.query(Service)
            .join(global_freq_subq, Service.id == global_freq_subq.c.service_id)
            .filter(
                Service.is_deleted == False,
                Service.is_visible_in_calendar == True,
                func.lower(Service.servizio_nome) != "dummy",
                Service.id.notin_(client_service_ids)  # Escludi quelli già del cliente
            )
            .order_by(global_freq_subq.c.cnt.desc())
            .limit(10 - len(services))
            .all()
        )
        # Aggiungi con last_date None (non ha storico per il cliente)
        services.extend([(s, None) for s in additional_services])
        app.logger.info(f"[DEBUG] Aggiunti {len(additional_services)} servizi globali")
    
    services_data = [{
        "id": s.id,
        "name": s.servizio_nome,
        "duration": s.servizio_durata,
        "price": s.servizio_prezzo,
        "tag": s.servizio_tag,
        "last_date": last_date.isoformat() if last_date else None
    } for s, last_date in services]
    app.logger.info(f"[DEBUG] Restituiti {len(services_data)} servizi (cliente + globali) per client_id={client_id}")
    return jsonify(services_data)

@calendar_bp.route('/update_layout/<int:appt_id>', methods=['POST'])
def update_layout(appt_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "Nessun dato fornito"}), 400

    width = data.get('widthValue')
    left = data.get('leftValue')
    z_index = data.get('zIndexValue')

    if width is None or left is None or z_index is None:
        return jsonify({"error": "Parametri layout mancanti"}), 400

    appt = db.session.get(Appointment, appt_id)
    if not appt:
        abort(404)

    try:
        appt.layout_width = width
        appt.layout_left = left
        appt.layout_zindex = z_index
        db.session.commit()
        return jsonify({
            "message": "Layout aggiornato",
            "layout": {
                "width": width,
                "left": left,
                "zIndex": z_index
            }
        }), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error("Errore durante l'aggiornamento del layout per appt %s: %s", appt_id, str(e))
        return jsonify({"error": "Errore durante il salvataggio del layout."}), 500
    
@calendar_bp.route('/add-client', methods=['POST'])
def add_client():
    try:
        # Recupera i dati JSON invece di form
        data = request.get_json()
        if not data:
            return jsonify({"error": "Dati non forniti"}), 400

        cliente_nome = (data.get('cliente_nome') or "").strip()
        cliente_cognome = (data.get('cliente_cognome') or "").strip()
        cliente_cellulare = (data.get('cliente_cellulare') or "").strip()
        cliente_sesso = data.get('cliente_sesso', "-").strip()

            # --- normalizzazione telefono per confronto duplicati ---
        def _normalize_phone(p):
            if not p:
                return ''
            s = re.sub(r'\D', '', str(p))
            if s.startswith('00'):
                s = s[2:]
            if s.startswith('39'):
                s = s[2:]
            if s.startswith('0'):
                s = s[1:]
            return s
        phone_norm = _normalize_phone(cliente_cellulare)
        if phone_norm:
            existing = Client.query.filter(
                func.replace(func.replace(Client.cliente_cellulare, ' ', ''), '+39', '') == phone_norm
            ).first()
            if existing:
               return jsonify({"error": "Attenzione! questo numero risulta assegnato ad un altro cliente"}), 400

        if not cliente_nome or not cliente_cognome or not cliente_cellulare:
            return jsonify({"error": "cliente_nome, cliente_cognome e cliente_cellulare sono obbligatori"}), 400

        # Capitalizza i nomi per uniformità
        cliente_nome = cliente_nome.capitalize()
        cliente_cognome = cliente_cognome.capitalize()

        # Imposta i valori di default per i campi opzionali
        cliente_email = ""
        cliente_data_nascita = None

        # Creazione del nuovo cliente
        new_client = Client(
            cliente_nome=cliente_nome,
            cliente_cognome=cliente_cognome,
            cliente_cellulare=cliente_cellulare,
            cliente_email=cliente_email,
            cliente_data_nascita=cliente_data_nascita,
            cliente_sesso=cliente_sesso
        )
        db.session.add(new_client)
        db.session.commit()

        return jsonify({
            "message": "Cliente aggiunto con successo!",
            "cliente_id": new_client.id,
            "cliente_nome": new_client.cliente_nome,
            "cliente_cognome": new_client.cliente_cognome,
            "cliente_cellulare": new_client.cliente_cellulare
        }), 201

    except Exception as e:
        db.session.rollback()
        app.logger.error("Errore durante l'aggiunta del cliente dal calendario: %s", str(e))
        return jsonify({"error": "Errore durante la creazione del cliente."}), 500
    
def compute_font_color(hex_color):
    # Rimuove il carattere '#' se presente
    hex_color = hex_color.lstrip('#')
    # Se il colore è in formato corto (3 caratteri), raddoppialo
    if len(hex_color) == 3:
        hex_color = ''.join([c * 2 for c in hex_color])
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
    except ValueError:
        # In caso di errore, restituisci un colore di default
        return "#ffffff"
    # Calcola la luminosità secondo la formula standard
    brightness = (r * 299 + g * 587 + b * 114) / 1000
    # Se la luminosità è alta (sfondo chiaro), il font deve essere scuro; altrimenti, bianco
    return "rgba(0, 0, 0, 0.7)" if brightness > 204 else "#ffffff"

@calendar_bp.route('/no-show', methods=['POST'])
def set_no_show():
    """Imposta lo stato NON_ARRIVATO (3) per l'appuntamento dato."""
    data = request.json
    appointment_id = data.get('appointment_id')
    if not appointment_id:
        return jsonify({"error": "appointment_id mancante"}), 400

    appointment = db.session.get(Appointment, appointment_id)
    if not appointment:
        abort(404)
    if not appointment:
        return jsonify({"error": "Appuntamento non trovato"}), 404
    
    # Stato NON_ARRIVATO = 3 usando l'enum
    appointment.stato = AppointmentStatus.NON_ARRIVATO
    db.session.commit()

    return jsonify({
        "success": True,
        "appointment_id": appointment.id,
        "new_status": 3
    })

@calendar_bp.route('/update_status/<int:appointment_id>', methods=['POST'])
def update_status(appointment_id):
    data = request.get_json()
    print("DEBUG update_status payload:", data)
    if not data or 'status' not in data:
        return jsonify({"error": "Parametro 'status' mancante"}), 400

    try:
        new_status = int(data.get('status'))
    except (ValueError, TypeError):
        return jsonify({"error": "Il valore di 'status' non è valido"}), 400
    
    if new_status not in [e.value for e in AppointmentStatus]:
        return jsonify({"error": "Valore status non valido"}), 400

    # Recupera l'appuntamento e aggiorna lo stato usando l'enum
    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        abort(404)
    appt.stato = AppointmentStatus(int(new_status))

    # Manteniamo il comportamento esistente per IN_ISTITUTO (colori)
    if new_status == AppointmentStatus.IN_ISTITUTO:
        if 'colore' in data:
            appt.colore = data['colore']
        if 'colore_font' in data:
            appt.colore_font = data['colore_font']

    # Nuovo: supporto opzionale per appending di nota descrittiva senza cambiare comportamento esistente
    # campo JSON atteso: note_append (string) -- verrà concatenato alla nota esistente con separatore " ; "
    note_append = data.get('note_append')
    if note_append:
        existing = (getattr(appt, 'note', None) or "").strip()
        sep = " ; " if existing != "" else ""
        try:
            appt.note = (existing + sep + str(note_append)).strip()
        except Exception:
            # in caso di problemi formattazione, fallback a stringa semplice
            appt.note = (existing + sep + (note_append or "")).strip()

    db.session.commit()
    appt = db.session.get(Appointment, appointment_id)  # Refresha dopo commit

    print(f"UPDATE_STATUS: appointment_id={appointment_id}, new_status={new_status}, stato_in_db={appt.stato}")

    tooltips = {
        0: "Cliente non ancora arrivato",
        1: "Cliente in istituto",
        2: "Pagato",
        3: "Non arrivato"
    }
    return jsonify({"status_name": tooltips.get(new_status, "Status sconosciuto")})

@calendar_bp.route('/api/appointment_status', methods=['POST'])
def api_appointment_status():
    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({"success": False, "error": "Nessun appuntamento selezionato"}), 400
    # Ottimizzazione: query unica invece di loop N+1
    appointments = Appointment.query.filter(
        Appointment.id.in_(ids),
        Appointment.is_cancelled_by_client == False
    ).all()
    result = [{"id": app.id, "stato": app.stato.value if hasattr(app.stato, "value") else app.stato} for app in appointments]
    return jsonify({"success": True, "appointments": result})

@calendar_bp.route('/calendar.html')
def calendar_html():
    date = request.args.get('date')
    hour = request.args.get('hour')
    # Passa i parametri alla home del calendario
    return redirect(url_for('.calendar_home', date=date, hour=hour))

@calendar_bp.route('/api/next-appointments-for-client/<int:client_id>', methods=['GET'])
def next_appointments_for_client(client_id):
    """Restituisce i prossimi appuntamenti (da ora in poi) per un dato cliente, ordinati per data."""
    now = datetime.now()
    appointments = Appointment.query.filter(
        Appointment.client_id == client_id,
        Appointment.start_time >= now,
        Appointment.client.has(is_deleted=False),
        Appointment.is_cancelled_by_client == False
    ).order_by(Appointment.start_time.asc()).limit(10).all()

    result = []
    for appt in appointments:
        result.append({
            "id": appt.id,
            "data": appt.start_time.strftime('%Y-%m-%d'),
            "ora_inizio": appt.start_time.strftime('%Y-%m-%d %H:%M'),
            "servizio_tag": appt.service.servizio_tag if appt.service else "",
            "durata": appt.duration,
            "operatore": appt.operator.user_nome if appt.operator else "",
            "costo": appt.service.servizio_prezzo if appt.service else "",
            "stato": appt.stato.value if hasattr(appt.stato, "value") else appt.stato
        })
    return jsonify(result)

@calendar_bp.route('/api/online-appointments-by-booking-date', methods=['GET'])
def online_appointments_by_booking_date():
    date_str = request.args.get('date')
    search = request.args.get('search', '').strip()
    pending_only = request.args.get('pending_only', '').strip() == '1'

    query = Appointment.query.filter(
        Appointment.source == "web",
        Appointment.is_cancelled_by_client == False
    ).options(
        joinedload(Appointment.client),
        joinedload(Appointment.service)
    )

    # CASO SPECIALE: pending_only filtra solo appuntamenti con cliente "Booking Online"
    if pending_only:
        # Trova il client placeholder "Booking Online"
        booking_client = Client.query.filter(
            func.lower(Client.cliente_nome) == 'booking',
            func.lower(Client.cliente_cognome) == 'online'
        ).first()
        
        if booking_client:
            appointments = (
                query.filter(Appointment.client_id == booking_client.id)
                .order_by(Appointment.created_at.desc())
                .all()
            )
        else:
            appointments = []
    elif search and len(search) >= 3:
        pattern = f"%{search.lower()}%"
        raw_appointments = (
            query.join(Client, isouter=True)
            .filter(
                or_(
                    func.lower(Client.cliente_nome).like(pattern),
                    func.lower(Client.cliente_cognome).like(pattern),
                    func.lower(Appointment.note).like(pattern),
                    func.lower(Appointment.source).like(pattern)
                )
            )
            .order_by(Appointment.created_at.desc())
            .all()
        )

        # Post-filter: manteniamo solo gli appuntamenti in cui la query
        # corrisponde al nome o al cognome (sia dal record Client sia estratto dalla nota).
        appointments = []
        s = search.strip().lower()
        for appt in raw_appointments:
            try:
                matched = False
                # 1) se esiste client collegato, controlla nome/cognome DB
                if appt.client:
                    if s in (appt.client.cliente_nome or '').lower() or s in (appt.client.cliente_cognome or '').lower():
                        matched = True

                # 2) estrai nome/cognome dalla nota strutturata e controlla
                if not matched:
                    nome, cognome, _ = estrai_nome_cognome_cellulare(appt.note)
                    if nome and s in nome.strip().lower():
                        matched = True
                    elif cognome and s in cognome.strip().lower():
                        matched = True

                # 3) fallback molto conservativo: se la nota comincia con il pattern "Nome:" o "Cognome:"
                # e contiene il termine cercato, accettala (copre formati leggermente diversi)
                if not matched and appt.note:
                    note_l = (appt.note or '').lower()
                    if ('nome:' in note_l or 'cognome:' in note_l) and s in note_l:
                        # ma assicuriamoci che la corrispondenza non sia solo in email/telefono:
                        # accettiamo solo se s appare vicino a "nome" o "cognome"
                        # (semplice check: substring in finestra di 40 caratteri intorno)
                        idx = note_l.find(s)
                        if idx >= 0:
                            start = max(0, idx - 40)
                            ctx = note_l[start: idx + len(s) + 40]
                            if 'nome' in ctx or 'cognome' in ctx:
                                matched = True

                if matched:
                    appointments.append(appt)
            except Exception:
                # In caso di errori non blocchiamo tutto: ignora la riga
                continue
    elif date_str:
        try:
            booking_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            return jsonify({"error": "Formato data non valido"}), 400
        start_dt = datetime.combine(booking_date, datetime.min.time())
        end_dt = datetime.combine(booking_date, datetime.max.time())
        appointments = (
            query.filter(Appointment.created_at >= start_dt, Appointment.created_at <= end_dt)
            .order_by(Appointment.created_at.desc())
            .all()
        )
    else:
        appointments = query.order_by(Appointment.created_at.desc()).all()

    client_cache = {}
    grouped = {}

    try:
        dummy_booking = Client.get_dummy_booking()
        dummy_booking_id = dummy_booking.id if dummy_booking else None
    except Exception:
        dummy_booking_id = None

    for appt in appointments:
        session_id = appt.booking_session_id or f"single-{appt.id}"
        if session_id not in grouped:
            grouped[session_id] = {
                "booking_session_id": session_id,
                "data_booking": to_rome(appt.created_at).strftime("%Y-%m-%d %H:%M"),
                "nome": "", "cognome": "", "cellulare": "", "email": "",
                "client_id": appt.client_id,
                "note": appt.note,
                "services": [],
                "match_cliente": "",
                "match_cliente_id": None,
                "match_type": "none",
                "data_appuntamento": [],
                "ids": [],
                "placeholder_exists": False,
            }

            nome, cognome, cellulare, email = estrai_nome_cognome_cellulare(appt.note)
            nome_norm = (nome or "").strip().lower()
            cognome_norm = (cognome or "").strip().lower()
            cellulare_norm = (cellulare or "").strip().lower()
            if not nome_norm:
                nome_norm = "cliente"
            if not cognome_norm:
                cognome_norm = "booking"

            grouped[session_id]["nome"] = nome_norm
            grouped[session_id]["cognome"] = cognome_norm
            grouped[session_id]["cellulare"] = cellulare_norm
            grouped[session_id]["email"] = (email or "").strip().lower()

            key = (nome_norm, cognome_norm, cellulare_norm)
            if key not in client_cache:
                # Match completo: nome + cognome + cellulare
                client_cache[key] = Client.query.filter(
                    func.lower(Client.cliente_nome) == nome_norm,
                    func.lower(Client.cliente_cognome) == cognome_norm,
                    func.replace(func.replace(func.lower(Client.cliente_cellulare), ' ', ''), '+39', '') == func.replace(func.replace(cellulare_norm, ' ', ''), '+39', '')
                ).first()
            client = client_cache[key]
            
            # NEW: Se non c'è match completo, prova match solo cellulare
            phone_only_match = None
            if not client and cellulare_norm:
                phone_key = f"phone_{cellulare_norm}"
                if phone_key not in client_cache:
                    client_cache[phone_key] = Client.query.filter(
                        func.replace(func.replace(func.lower(Client.cliente_cellulare), ' ', ''), '+39', '') == func.replace(func.replace(cellulare_norm, ' ', ''), '+39', ''),
                        Client.is_deleted == False
                    ).first()
                phone_only_match = client_cache[phone_key]
            
            if client:
                # Match completo
                grouped[session_id]["match_cliente"] = f"{client.cliente_nome} {client.cliente_cognome} - {client.cliente_cellulare}"
                grouped[session_id]["match_cliente_id"] = client.id
                grouped[session_id]["match_type"] = "full"
            elif phone_only_match:
                # Match solo cellulare
                grouped[session_id]["match_cliente"] = f"{phone_only_match.cliente_nome} {phone_only_match.cliente_cognome} - {phone_only_match.cliente_cellulare}"
                grouped[session_id]["match_cliente_id"] = phone_only_match.id
                grouped[session_id]["match_type"] = "phone_only"
            else:
                # Nessun match
                grouped[session_id]["match_type"] = "none"

        grouped[session_id]["services"].append(appt.service.servizio_tag if appt.service else "")
        grouped[session_id]["data_appuntamento"].append(appt.start_time.strftime("%Y-%m-%d %H:%M") if appt.start_time else "")
        grouped[session_id]["ids"].append(appt.id)

        try:
            if appt.client:
                cn = (appt.client.cliente_nome or '').strip().lower()
                cc = (appt.client.cliente_cognome or '').strip().lower()
                is_placeholder = (dummy_booking_id and appt.client.id == dummy_booking_id) or (cn == 'booking' and cc == 'online')
                if is_placeholder:
                    grouped[session_id]["placeholder_exists"] = True
        except Exception:
            pass

    result = []
    for session in grouped.values():
        session["data_appuntamento"] = sorted([d for d in session["data_appuntamento"] if d])
        result.append({
            "booking_session_id": session["booking_session_id"],
            "data_booking": session["data_booking"],
            "nome": session["nome"],
            "cognome": session["cognome"],
            "cellulare": session["cellulare"],
            "client_id": session["client_id"],
            "note": session["note"],
            "services": session["services"],
            "match_cliente": session["match_cliente"],
            "match_cliente_id": session.get("match_cliente_id", None),
            "match_type": session.get("match_type", "none"),
            "data_appuntamento": session["data_appuntamento"][0] if session["data_appuntamento"] else "",
            "ids": session["ids"],
            "placeholder_exists": session["placeholder_exists"],
        })

    return jsonify(result)

@calendar_bp.route('/api/associa-cliente-booking', methods=['POST'])
def associa_cliente_booking():
    data = request.get_json() or {}
    appointment_id = data.get('appointment_id')
    client_id = data.get('client_id')
    nome = data.get('nome')
    cognome = data.get('cognome')
    cellulare = data.get('cellulare')

    client = None
    if client_id:
        try:
            client = db.session.get(Client, int(client_id))
        except Exception:
            client = None
    else:
        # normalizza cellulare e nome/cognome per comparazione
        cell_norm = (cellulare or '').strip()
        import re
        cell_norm = re.sub(r'\s+', '', cell_norm)
        if cell_norm.startswith('+39'):
            cell_norm = cell_norm[3:]
        if cell_norm.startswith('0'):
            cell_norm = cell_norm[1:]
        nome_norm = (nome or '').strip().lower()
        cognome_norm = (cognome or '').strip().lower()

        client = Client.query.filter(
            func.lower(Client.cliente_nome) == nome_norm,
            func.lower(Client.cliente_cognome) == cognome_norm,
            func.replace(func.replace(func.lower(Client.cliente_cellulare), ' ', ''), '+39', '') == cell_norm.lower()
        ).first()

    if not client:
        return jsonify({"success": False, "error": "Cliente non trovato"}), 404

    appt = db.session.get(Appointment, appointment_id)
    if not appt:
        return jsonify({"success": False, "error": "Appuntamento non trovato"}), 404

    if appt.booking_session_id:
        blocks = Appointment.query.filter_by(
            booking_session_id=appt.booking_session_id,
            is_cancelled_by_client=False
        ).all()
    else:
        blocks = [appt]

    new_color = random_color()
    new_font_color = compute_font_color(new_color)

    try:
        import re
        email_match = re.search(r'EMAIL:\s*([^\s]+)', appt.note or '', re.IGNORECASE)
        if email_match:
            extracted_email = email_match.group(1).strip().lower()
            # Controlla se il campo email è vuoto/None
            if not client.cliente_email or client.cliente_email.strip() == '':
                client.cliente_email = extracted_email
                app.logger.info(f"Email estratta e salvata per cliente {client.id}: {extracted_email}")
    except Exception as e:
        app.logger.warning(f"Errore estrazione email per cliente {client.id}: {e}")

    for block in blocks:
        block.client_id = client.id
        block.cliente_nome = client.cliente_nome
        block.cliente_cognome = client.cliente_cognome
        block.cliente_cellulare = client.cliente_cellulare
        block.colore = new_color
        block.colore_font = new_font_color

    db.session.commit()

    date_str = appt.start_time.strftime("%Y-%m-%d") if appt.start_time else ""
    hour = appt.start_time.strftime("%H") if appt.start_time else ""
    minute = appt.start_time.strftime("%M") if appt.start_time else ""
    return jsonify({
        "success": True, 
        "date": date_str, 
        "hour": hour, 
        "minute": minute, 
        "new_client_id": client.id,
        "new_color": new_color,
        "new_font_color": new_font_color
    })

@calendar_bp.route('/api/last-online-booking', methods=['GET'])
def last_online_booking():
    last = Appointment.query.filter_by(
        source='web',
        is_cancelled_by_client=False
    ).order_by(Appointment.created_at.desc()).first()
    if last:
        return jsonify({"id": last.id, "created_at": last.created_at.isoformat()})
    return jsonify({"id": None, "created_at": None})

@calendar_bp.route('/api/client-id-booking')
def get_client_id_booking():
    # Usa get_dummy_booking per creare il cliente se non esiste
    dummy = Client.get_dummy_booking()
    if not dummy:
        return jsonify({"error": "Errore nella creazione del cliente booking"}), 500
    return jsonify({"client_id_booking": dummy.id})

@app.route('/settings/api/update_client_info', methods=['POST'])
def update_client_info():
    """
    Aggiorna nome e/o cognome del cliente.
    Body JSON atteso: { "client_id": <id>, "cliente_nome": "Mario", "cliente_cognome": "Rossi" }
    """
    data = request.get_json(silent=True) or {}
    client_id = data.get('client_id')
    if not client_id:
        return jsonify(success=False, error="client_id mancante"), 400

    try:
        client = db.session.get(Client, int(client_id))
        if not client:
            return jsonify(success=False, error="cliente non trovato"), 404

        nome = data.get('cliente_nome')
        cognome = data.get('cliente_cognome')
        if nome is not None:
            client.cliente_nome = nome.strip()
        if cognome is not None:
            client.cliente_cognome = cognome.strip()

        db.session.commit()
        return jsonify(success=True, cliente_nome=client.cliente_nome, cliente_cognome=client.cliente_cognome), 200

    except Exception as e:
        db.session.rollback()
        app.logger.exception("update_client_info error")
        return jsonify(success=False, error="errore interno"), 500

@app.route('/settings/api/update_client_phone', methods=['POST'])
def update_client_phone():
    data = request.get_json()
    client = db.session.get(Client, data.get('client_id'))
    if client:
        client.cliente_cellulare = data.get('phone', '')
        db.session.commit()
        return jsonify(success=True, phone=client.cliente_cellulare)
    return jsonify(success=False), 404

@app.route('/settings/api/update_client_email', methods=['POST'])
def update_client_email():
    data = request.get_json()
    client = db.session.get(Client, data.get('client_id'))
    if client:
        client.cliente_email = data.get('email', '')
        db.session.commit()
        return jsonify(success=True, email=client.cliente_email)
    return jsonify(success=False), 404

@app.route('/settings/api/client_info/<int:client_id>')
def client_info(client_id):
    client = db.session.get(Client, client_id)
    if not client:
        return jsonify({})
    return jsonify({
        'cliente_nome': client.cliente_nome,
        'cliente_cognome': client.cliente_cognome,
        'cliente_cellulare': client.cliente_cellulare,
        'cliente_email': client.cliente_email,
        'note': client.note
    })

@app.route('/settings/api/update_client_note', methods=['POST'])
def update_client_note():
    data = request.get_json()
    client = db.session.get(Client, data.get('client_id'))
    if client:
        client.note = data.get('note', '')
        db.session.commit()
        return jsonify(success=True, note=client.note)
    return jsonify(success=False), 404

@calendar_bp.route('/api/next_appointments')
def calendar_next_appointments():
    """
    Agenda COMPLETA di OGGI (00:00–23:59) con:
      - Appuntamenti reali
      - Blocchi OFF (Appointment 'dummy') con durata da Appointment._duration
    Ordinamento: per operatore (A→Z) poi per orario.

    Per OGNI riga, la route popola:
      shift_start / shift_end:
        1) se presenti in OperatorShift (min start / max end per operatore nel giorno)
        2) altrimenti derivati da appuntamenti dell'operatore (min/max orari odierni)
        3) altrimenti fallback a BusinessInfo.active_opening_time / active_closing_time
    """
 
    now = datetime.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    today_date = day_start.date()

    # --- util: format ---
    def fmt_time_obj(t):
        try:
            if isinstance(t, datetime):
                return t.strftime("%H:%M")
            if isinstance(t, dtime):
                return t.strftime("%H:%M")
        except Exception:
            pass
        return ""

    def fmt_duration_any(v):
        try:
            if v is None:
                return ""
            if isinstance(v, timedelta):
                mins = int(v.total_seconds() // 60)
            elif isinstance(v, (int, float)):
                mins = int(v)
            elif isinstance(v, str):
                s = v.strip()
                if ":" in s:
                    parts = s.split(":")
                    if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                        h = int(parts[0]); m = int(parts[1])
                        return f"{h}:{m:02d}"
                    return s
                if s.isdigit():
                    mins = int(s)
                else:
                    return s
            else:
                return ""
            h = mins // 60
            m = mins % 60
            return f"{h}:{m:02d}"
        except Exception:
            return ""

    # --- 0) Orario apertura/chiusura attività come fallback ---
    try:
        bi = BusinessInfo.query.first()
        fallback_open = getattr(bi, "active_opening_time", None)
        fallback_close = getattr(bi, "active_closing_time", None)
    except Exception:
        bi = None
        fallback_open = None
        fallback_close = None
    # default se mancanti
    if not isinstance(fallback_open, dtime):
        fallback_open = dtime(8, 0)
    if not isinstance(fallback_close, dtime):
        fallback_close = dtime(20, 0)

    # --- 1) Turni da OperatorShift (min start / max end per operatore nel giorno) ---
    # Schema:
    # operator_shifts(operator_id, shift_date, shift_start_time(Time), shift_end_time(Time))
    shifts_by_operator = {}  # op_id -> {"start": time, "end": time}
    rows = (
        db.session.query(
            OperatorShift.operator_id,
            func.min(OperatorShift.shift_start_time).label('min_start'),
            func.max(OperatorShift.shift_end_time).label('max_end')
        )
        .filter(OperatorShift.shift_date == today_date)
        .group_by(OperatorShift.operator_id)
        .all()
    )
    for row in rows:
        shifts_by_operator[row.operator_id] = {"start": row.min_start, "end": row.max_end}

    # --- 2) Appuntamenti REALI di oggi (con preloading) ---
    appointments = (
        Appointment.query
        .filter(Appointment.start_time >= day_start, Appointment.start_time <= day_end)
        .filter(Appointment.is_cancelled_by_client == False)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
            joinedload(Appointment.operator)
        )
        .order_by(Appointment.start_time.asc())
        .all()
    )

    operators_with_cells = set()
    for appt in appointments:
        op_id = getattr(appt, "operator_id", None)
        if not op_id:
            op = getattr(appt, "operator", None)
            op_id = getattr(op, "id", None) if op else None
        if op_id:
            operators_with_cells.add(op_id)

    def resolve_shift_for_operator(op_id):
        # 1) OperatorShift presente
        info = shifts_by_operator.get(op_id)
        if info and (isinstance(info.get("start"), dtime) or isinstance(info.get("end"), dtime)):
            return (fmt_time_obj(info.get("start")), fmt_time_obj(info.get("end")))
        # 2) Nessuno shift ma l’operatore ha celle attive oggi → usa apertura/chiusura attività
        if op_id in operators_with_cells:
            return (fmt_time_obj(fallback_open), fmt_time_obj(fallback_close))
        # 3) Nessuna cella attiva → niente turno
        return ("", "")

    # --- costruisci risposta flat ---
    result = []
    for appt in appointments:
        # OFF se dummy / client None / service None
        is_off = (
            appt.client is None or
            (getattr(appt.client, "cliente_nome", "") or "").strip().lower() == "dummy" or
            appt.service is None or
            (getattr(appt.service, "servizio_nome", "") or "").strip().lower() == "dummy"
        )

        # Operatore e op_id
        operator_name = ""
        op_id = getattr(appt, "operator_id", None)
        try:
            if appt.operator:
                nome = getattr(appt.operator, "user_nome", "") or ""
                cognome = getattr(appt.operator, "user_cognome", "") or ""
                operator_name = f"{nome} {cognome}".strip()
                if op_id is None:
                    op_id = getattr(appt.operator, "id", None)
        except Exception:
            pass

        # turno risolto (OperatorShift -> appuntamenti -> fallback attività)
        sh_start, sh_end = resolve_shift_for_operator(op_id)

        # durata OFF da Appointment._duration
        duration_str = fmt_duration_any(getattr(appt, "_duration", None)) if is_off else ""

        item = {
            "id": appt.id,
            "start_time": appt.start_time.strftime("%H:%M"),
            "date": appt.start_time.strftime("%d/%m/%Y"),
            "client": "OFF" if is_off else (
                f"{getattr(appt.client, 'cliente_nome', '')} {getattr(appt.client, 'cliente_cognome', '')}".strip()
                if appt.client else ""
            ),
            "client_phone": "" if is_off else (getattr(appt.client, "cliente_cellulare", "") if appt.client else ""),
            "service": "" if is_off else (getattr(appt.service, "servizio_nome", "") if appt.service else ""),
            "operator": operator_name,
            "is_off": bool(is_off),
            "note": (appt.note or "").strip() if is_off else "",
            "duration": duration_str,
            "shift_start": sh_start,
            "shift_end": sh_end,
        }
        item["_sort_dt"] = appt.start_time
        result.append(item)

    # Ordinamento: operatore -> orario
    result.sort(key=lambda x: ((x.get("operator") or "").strip().lower(), x.get("_sort_dt") or day_start))
    for r in result:
        r.pop("_sort_dt", None)

    return jsonify(result)

def format_data_italiana(dt):
    mesi = [
        "Gennaio", "Febbraio", "Marzo", "Aprile", "Maggio", "Giugno",
        "Luglio", "Agosto", "Settembre", "Ottobre", "Novembre", "Dicembre"
    ]
    giorno = dt.day
    mese_nome = mesi[dt.month - 1]
    anno = dt.year
    return f"{giorno} {mese_nome} {anno}"

@calendar_bp.route('/send-whatsapp-auto', methods=['POST'])
def send_whatsapp_auto():
    data = request.get_json(force=True)
    app.logger.info(f"[WHATSAPP] Richiesta ricevuta: {data}")
    numero = data.get('numero')
    messaggio = data.get('messaggio')
    nome = data.get('cliente_nome') or data.get('nome') or data.get('client_name') or ''
    client_id = data.get('client_id')
    data_app = data.get('data', '')
    ora = data.get('ora', '')

        # Se nome non è valorizzato, prova a recuperarlo dal DB tramite client_id
    if not nome and client_id:
        client = db.session.get(Client, client_id)
        if client:
            nome = client.cliente_nome

    if not numero:
        return jsonify({'error': 'Numero mancante'}), 400
    
    # Converti la stringa in oggetto datetime
    try:
        dt = datetime.strptime(data_app, "%Y-%m-%d")
        data_app_italiana = format_data_italiana(dt)
    except Exception:
        data_app_italiana = data_app  # fallback se parsing fallisce

    # Calcola servizi/ids e imposta SEMPRE l'ora dal primo blocco della sessione booking (se presente)
    servizi_str = ""
    try:
        # 0) Se l'ora non è fornita, prova a comporla da hour/minute nel payload
        if not ora:
            hh = (data.get('hour') or "").strip()
            mm = (data.get('minute') or "").strip()
            if hh != "" and mm != "":
                try:
                    ora = f"{int(hh):02d}:{int(mm):02d}"
                except Exception:
                    pass

        servizi_payload = data.get('servizi', None)
        if isinstance(servizi_payload, list):
            servizi_str = "\n".join(f"• {str(s).strip()}" for s in servizi_payload if str(s).strip())
        elif isinstance(servizi_payload, str):
            servizi_str = servizi_payload.strip()

        # Ricava gli appuntamenti di riferimento:
        # 1) appointment_ids dal payload
        appt_ids = data.get('appointment_ids', [])
        if isinstance(appt_ids, str):
            appt_ids = [x for x in appt_ids.split(',') if x.strip().isdigit()]
        ids = [int(x) for x in appt_ids if str(x).strip().isdigit()]

        # 2) Se mancano, prova con appointment_id singolo (e costruisci il gruppo lato server)
        if not ids:
            appt_id_single = data.get('appointment_id') or data.get('id')
            try:
                appt_id_single = int(appt_id_single) if appt_id_single is not None else None
            except Exception:
                appt_id_single = None

            if appt_id_single:
                appt_ref = db.session.get(Appointment, appt_id_single)
                if appt_ref:
                    # Gruppo: stessa sessione web, altrimenti tutti gli appuntamenti dello stesso cliente nella stessa data
                    if getattr(appt_ref, 'booking_session_id', None):
                        appts = (Appointment.query
                                 .filter(
                                     Appointment.booking_session_id == appt_ref.booking_session_id,
                                     Appointment.is_cancelled_by_client == False
                                 )
                                 .order_by(Appointment.start_time.asc())
                                 .all())
                    else:
                        if appt_ref.client_id and appt_ref.start_time:
                            day_start = appt_ref.start_time.replace(hour=0, minute=0, second=0, microsecond=0)
                            day_end = appt_ref.start_time.replace(hour=23, minute=59, second=59, microsecond=999999)
                            appts = (Appointment.query
                                     .filter(
                                         Appointment.client_id == appt_ref.client_id,
                                         Appointment.start_time >= day_start,
                                         Appointment.start_time <= day_end,
                                         Appointment.is_cancelled_by_client == False
                                     )
                                     .order_by(Appointment.start_time.asc())
                                     .all())
                        else:
                            appts = [appt_ref]
                    ids = [a.id for a in appts if a and a.id]

                    # Se l'ora non è ancora valorizzata, prendila dal primo del gruppo
                    if not ora and appts and appts[0].start_time:
                        ora = appts[0].start_time.strftime('%H:%M')
                    # Se la data italiana non è valorizzata correttamente, ricavala dal primo del gruppo
                    try:
                        if appts and appts[0].start_time:
                            data_app_italiana = format_data_italiana(appts[0].start_time)
                    except Exception:
                        pass

        # 3) Se ancora non abbiamo ids, prova client_id + data (YYYY-MM-DD) per tutti gli appuntamenti del giorno
        if not ids:
            if client_id and data_app:
                dt_day = None
                try:
                    dt_day = datetime.strptime(data_app, "%Y-%m-%d")
                except Exception:
                    # prova dd/mm/yyyy
                    try:
                        dt_day = datetime.strptime(data_app, "%d/%m/%Y")
                    except Exception:
                        dt_day = None
                if dt_day:
                    day_start = dt_day.replace(hour=0, minute=0, second=0, microsecond=0)
                    day_end = dt_day.replace(hour=23, minute=59, second=59, microsecond=999999)
                    appts = (Appointment.query
                             .filter(
                                 Appointment.client_id == int(client_id),
                                 Appointment.start_time >= day_start,
                                 Appointment.start_time <= day_end,
                                 Appointment.is_cancelled_by_client == False
                             )
                             .order_by(Appointment.start_time.asc())
                             .all())
                    ids = [a.id for a in appts if a and a.id]
                    if not ora and appts and appts[0].start_time:
                        ora = appts[0].start_time.strftime('%H:%M')

        # OVERRIDE: se gli appuntamenti appartengono a UNA sola booking_session_id, forza SEMPRE ora/data dal PRIMO blocco della sessione
        try:
            session_id = None
            if ids:
                sess_rows = db.session.query(Appointment.booking_session_id)\
                                      .filter(Appointment.id.in_(ids))\
                                      .distinct().all()
                non_empty_sessions = [row[0] for row in sess_rows if row and row[0]]
                if len(non_empty_sessions) == 1:
                    session_id = non_empty_sessions[0]
            if not session_id:
                appt_id_probe = data.get('appointment_id') or data.get('id')
                try:
                    appt_id_probe = int(appt_id_probe) if appt_id_probe is not None else None
                except Exception:
                    appt_id_probe = None
                if appt_id_probe:
                    a0 = db.session.get(Appointment, appt_id_probe)
                    if a0 and getattr(a0, 'booking_session_id', None):
                        session_id = a0.booking_session_id

            if session_id:
                session_appts = (Appointment.query
                                 .filter(
                                     Appointment.booking_session_id == session_id,
                                     Appointment.is_cancelled_by_client == False
                                 )
                                 .order_by(Appointment.start_time.asc())
                                 .all())
                if session_appts and session_appts[0].start_time:
                    first_dt = session_appts[0].start_time
                    ora = first_dt.strftime('%H:%M')  # forza SEMPRE l'ora del primo
                    try:
                        data_app_italiana = format_data_italiana(first_dt)
                    except Exception:
                        pass
                    ids = [a.id for a in session_appts if a and a.id]  # ids in ordine, utile per servizi
        except Exception:
            pass

        # 4) Costruisci i servizi dal gruppo trovato
        if not servizi_str and ids:
            appts = Appointment.query.filter(
                Appointment.id.in_(ids),
                Appointment.is_cancelled_by_client == False
            ).order_by(Appointment.start_time.asc()).all()
            lines = []
            for appt in appts:
                svc = db.session.get(Service, appt.service_id) if appt.service_id else None
                label = ((getattr(svc, 'servizio_nome', '') or "").strip() if svc else "")
                if label:
                    lines.append(f"• {label}")
            servizi_str = "\n".join(lines)
    except Exception:
        servizi_str = ""

    # Se il messaggio non è fornito, usa il template AUTOMATICO da settings
    if not messaggio:
        business_info = BusinessInfo.query.first()
        if business_info and getattr(business_info, "whatsapp_message_auto", None):
            messaggio = business_info.whatsapp_message_auto
        else:
            messaggio = "Ciao {{nome}}, la tua prenotazione per il {{data}} alle ore {{ora}} è stata registrata! Grazie da Sun Booking."

    # Sostituisci i placeholder anche se 'messaggio' è già stato passato dal client
    nome_fmt = " ".join([w.capitalize() for w in str(nome or "").strip().split()])
    messaggio = (
        (messaggio or "")
        .replace("{{nome}}", nome_fmt)
        .replace("{{data}}", data_app_italiana or "")
        .replace("{{ora}}", ora or "")
        .replace("{{servizi}}", ("\n" + servizi_str + "\n") if servizi_str else "")
    )

    try:
        # ===== UNIPILE INTEGRATION =====
        unipile_dsn = os.getenv("UNIPILE_DSN")
        unipile_token = os.getenv("UNIPILE_ACCESS_TOKEN")
        
        # Leggi account_id SOLO da DB (isolamento multi-tenant)
        business_info = BusinessInfo.query.filter_by(is_deleted=False).first()
        unipile_account_id = business_info.unipile_account_id if business_info else None

        if not unipile_dsn or not unipile_account_id or not unipile_token:
            app.logger.error("[WHATSAPP] Configurazione UNIPILE mancante: DSN/ACCOUNT_ID/ACCESS_TOKEN non presenti")
            return jsonify({'error': 'Configurazione WhatsApp mancante sul server.'}), 500

        # Normalizzazione numero in base alle regole:
        # - Se inizia con '+': non modificare
        # - Se inizia con '3':
        #    - Se lunghezza > 10: assumiamo internazionale (es. 33...) -> aggiungi '+'
        #    - Altrimenti (<= 10): assumiamo cellulare italiano -> aggiungi '+39'
        # - Se inizia con cifra diversa da '3' e non ha '+': aggiungi '+'
        raw = (str(numero or '')).strip().replace(' ', '')
        if not raw:
            app.logger.error("[WHATSAPP] Numero vuoto in input")
            return jsonify({'error': 'Numero cliente non valido'}), 400

        if raw.startswith('+'):
            numero_norm = raw
        elif raw and raw[0].isdigit():
            if raw.startswith('3'):
                # Euristica: i cellulari italiani sono tipicamente 10 cifre (es. 333 1234567)
                # I numeri internazionali che iniziano con 3 (es. Francia 33...) sono spesso più lunghi
                if len(raw) > 10:
                    numero_norm = '+' + raw
                else:
                    numero_norm = '+39' + raw
            else:
                numero_norm = '+' + raw
        else:
            # Fallback: se non inizia con '+' o cifra, usa com'è
            numero_norm = raw

        # Normalizzazione per Unipile: formato numero@s.whatsapp.net
        numero_pulito = re.sub(r'\D', '', numero_norm)  # solo cifre
        if numero_pulito.startswith('00'):
            numero_pulito = numero_pulito[2:]
        if not numero_pulito:
            app.logger.error("[WHATSAPP] Numero vuoto dopo normalizzazione")
            return jsonify({'error': 'Numero cliente non valido'}), 400
        # Aggiungi prefisso 39 (senza +) se manca
        if not numero_pulito.startswith('39') and len(numero_pulito) <= 10:
            numero_pulito = '39' + numero_pulito
        # Formato Unipile: numero@s.whatsapp.net
        numero_whatsapp = f"{numero_pulito}@s.whatsapp.net"
        
        if len(numero_pulito) < 8:
            app.logger.error("[WHATSAPP] Numero troppo corto dopo normalizzazione: %s", numero_pulito)
            return jsonify({'error': 'Numero cliente non valido'}), 400

        app.logger.info("[WHATSAPP-UNIPILE] preparing send: phone=%s account=%s msg_len=%d",
                        numero_pulito, unipile_account_id, len(messaggio or ""))

        # Costruisci l'URL per Unipile
        # DSN format: api15.unipile.com:14552
        unipile_base_url = f"https://{unipile_dsn}"
        send_url = f"{unipile_base_url}/api/v1/chats"

        headers = {
            "X-API-KEY": unipile_token,
            "accept": "application/json"
        }

        # Payload per Unipile: attendees_ids deve essere STRINGA, non array
        payload = {
            "account_id": unipile_account_id,
            "attendees_ids": numero_whatsapp,
            "text": messaggio
        }

        try:
            import requests
            # IMPORTANTE: usa data= (form-encoded) NON json=
            response = requests.post(send_url, data=payload, headers=headers, timeout=30)
            app.logger.info("[WHATSAPP-UNIPILE] Response status=%s body=%s", response.status_code, response.text[:500] if response.text else "")

            if response.status_code in (200, 201, 202):
                try:
                    resp_json = response.json()
                except Exception:
                    resp_json = {"raw": response.text}
                return jsonify({'success': True, 'unipile_response': resp_json})
            else:
                app.logger.error("[WHATSAPP-UNIPILE] send failed http_status=%s body=%s", response.status_code, response.text)
                return jsonify({'error': 'Invio fallito', 'http_status': response.status_code, 'details': response.text}), 500

        except Exception as exc:
            app.logger.exception("[WHATSAPP-UNIPILE] Exception during requests.post")
            return jsonify({'error': str(exc)}), 500

    except Exception as e:
        app.logger.exception("[WHATSAPP] Errore invio WhatsApp: %s", e)
        return jsonify({'error': str(e)}), 500
    
@calendar_bp.route('/api/web-appointments/count-pending', methods=['GET'])
def count_pending_web_appointments():
    """
    Conta le SESSIONI di booking 'web' che non sono state ancora gestite/associate.
    Raggruppa per booking_session_id (o appuntamento singolo se NULL).
    Esclude appuntamenti cancellati dal cliente e quelli assegnati a operatori eliminati o non visibili.
    """
    try:
        # Subquery: trova tutti gli appuntamenti web pending validi
        # poi raggruppa per booking_session_id (o id se booking_session_id è NULL)
        from sqlalchemy import case, literal_column
        
        # Conta sessioni uniche: usa COALESCE per trattare booking_session_id NULL come id singolo
        count = db.session.query(
            func.count(func.distinct(
                func.coalesce(Appointment.booking_session_id, func.concat('single-', Appointment.id))
            ))
        ).select_from(Appointment).join(Client).join(Operator).filter(
            Appointment.source == 'web',
            Appointment.is_cancelled_by_client == False,
            Operator.is_deleted == False,
            Operator.is_visible == True,
            or_(
                and_(func.upper(Client.cliente_nome) == 'BOOKING', func.upper(Client.cliente_cognome) == 'ONLINE'),
                and_(func.upper(Client.cliente_nome) == 'CLIENTE', func.upper(Client.cliente_cognome) == 'BOOKING')
            )
        ).scalar()

        return jsonify({'count': count or 0})
    except Exception as e:
        app.logger.exception("Errore conteggio web pending")
        return jsonify({'count': 0})
    
@calendar_bp.route('/api/service-by-name', methods=['GET'])
def get_service_by_name():
    """Recupera un servizio dal nome (per integrazione pacchetti)"""
    service_name = request.args.get('name', '').strip()
    if not service_name:
        return jsonify({"error": "Nome servizio mancante"}), 400
    
    service = Service.query.filter(
        Service.servizio_nome == service_name,
        Service.is_deleted == False
    ).first()
    
    if not service:
        return jsonify({"error": f"Servizio '{service_name}' non trovato"}), 404
    
    return jsonify({
        "id": service.id,
        "nome": service.servizio_nome,
        "tag": service.servizio_tag,
        "durata": service.servizio_durata,
        "prezzo": service.servizio_prezzo,
        "colore": getattr(service, 'colore', None)
    })

@calendar_bp.route('/api/find-similar-client', methods=['POST'])
def find_similar_client():
    """
    Trova il cliente più simile in database basandosi su nome/cognome/cellulare.
    Ritorna il miglior match o None.
    """
    data = request.get_json()
    nome = (data.get('nome') or '').strip().lower()
    cognome = (data.get('cognome') or '').strip().lower()
    cellulare = (data.get('cellulare') or '').strip()
    
    if not nome and not cognome and not cellulare:
        return jsonify({'match': None}), 200
    
    # Query per trovare clienti simili
    query = db.session.query(Client).filter(Client.is_deleted == False)
    
    # Lista di candidati con punteggio
    candidates = []
    
    for client in query.all():
        score = 0
        client_nome = (client.cliente_nome or '').strip().lower()
        client_cognome = (client.cliente_cognome or '').strip().lower()
        client_cell = (client.cliente_cellulare or '').strip()
        
        # Punteggio per nome (almeno 2 caratteri in comune)
        if nome and client_nome:
            common_chars = set(nome) & set(client_nome)
            if len(common_chars) >= 2:
                score += len(common_chars) * 2
                # Bonus se inizia con stessa lettera
                if nome[0] == client_nome[0]:
                    score += 5
        
        # Punteggio per cognome (almeno 2 caratteri in comune)
        if cognome and client_cognome:
            common_chars = set(cognome) & set(client_cognome)
            if len(common_chars) >= 2:
                score += len(common_chars) * 2
                # Bonus se inizia con stessa lettera
                if cognome[0] == client_cognome[0]:
                    score += 5
        
        # Punteggio per cellulare parziale (almeno 4 cifre consecutive)
        if cellulare and client_cell:
            # Normalizza (solo numeri)
            import re
            norm_search = re.sub(r'\D', '', cellulare)
            norm_client = re.sub(r'\D', '', client_cell)
            
            # Cerca sottosequenza comune
            if len(norm_search) >= 4:
                for i in range(len(norm_search) - 3):
                    substr = norm_search[i:i+4]
                    if substr in norm_client:
                        score += 10
        
        if score > 0:
            candidates.append({
                'client': client,
                'score': score
            })
    
    # Ordina per punteggio decrescente
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    if not candidates:
        return jsonify({'match': None}), 200
    
    # Ritorna il migliore
    best = candidates[0]['client']
    return jsonify({
        'match': {
            'id': best.id,
            'nome': best.cliente_nome or '',
            'cognome': best.cliente_cognome or '',
            'cellulare': best.cliente_cellulare or '',
            'email': best.cliente_email or '',
            'score': candidates[0]['score']
        }
    }), 200

@calendar_bp.route('/api/create-client-from-booking', methods=['POST'])
def create_client_from_booking():
    """
    Crea un nuovo cliente dai dati della prenotazione online.
    """
    data = request.get_json() or {}
    nome = (data.get('nome') or '').strip()
    cognome = (data.get('cognome') or '').strip()
    cellulare = (data.get('cellulare') or '').strip()
    email = (data.get('email') or '').strip()
    
    if not nome or not cognome:
        return jsonify({'success': False, 'error': 'Nome e cognome obbligatori'}), 400
    
    try:
        # Funzione helper per dedurre il sesso dal nome (stessa logica del frontend)
        def deduci_sesso(nome):
            if not nome:
                return "-"
            nome_minuscolo = nome.lower()
            if nome_minuscolo.endswith('o'):
                return 'M'
            elif nome_minuscolo.endswith('a'):
                return 'F'
            else:
                return "-"
        
        # Crea nuovo cliente
        new_client = Client(
            cliente_nome=nome,
            cliente_cognome=cognome,
            cliente_cellulare=cellulare,
            cliente_email=email,
            cliente_sesso=deduci_sesso(nome),
            is_deleted=False
        )
        db.session.add(new_client)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'client': {
                'id': new_client.id,
                'nome': new_client.cliente_nome,
                'cognome': new_client.cliente_cognome,
                'cellulare': new_client.cliente_cellulare,
                'email': new_client.cliente_email
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500